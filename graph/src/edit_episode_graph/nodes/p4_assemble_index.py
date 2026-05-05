"""p4_assemble_index node — assemble root composition from Pattern A scene
fragments produced by the per-beat fan-out (HOM-133/134).

Deterministic class-1 node. Source-of-truth is the **filesystem**: each
`p4_beat` Send writes one HTML fragment to
`<hyperframes_dir>/compositions/<scene_id>.html`. This node iterates
`state["compose"]["plan"]["beats"]` (the canonical beat order) and inlines
the fragments — verbatim, no `<template>` strip — into the scaffolded root
`index.html` between dedicated injection markers. State carries no
`compose.beats[]` echo (deprecated; see `state.py`).

Per spec (`docs/superpowers/specs/2026-05-04-hom-122-p4-beats-fan-out-design.md`
§"`p4_assemble_index` edits"):

  1. Source of beats = `compose.plan.beats[]` (FS-truth, not a state echo).
  2. Inline fragments **as-is** — they are direct `<div id="scene-…" …>`
     under Pattern A; no inner-div extraction needed.
  3. Missing-scene aggregation: gather every gap before deciding, then
     skip with reason `"missing scenes: hook, payoff"` so the operator
     sees all gaps in one halt rather than chasing one at a time.
  4. v4 visibility shim: append a generated root-timeline `<script>`
     bracketed by `<!-- p4_assemble_index: shim begin -->` …
     `<!-- p4_assemble_index: shim end -->` markers. The shim sets each
     non-first scene's `opacity: 1` at its `data_start_s` and nests the
     scene-local `__sceneTimelines[id]` into the root timeline, producing
     hard-cut scene visibility pending the canonical transitions node
     (HOM-77/v5). The brackets let the future transitions node replace
     the shim cleanly.

Canon (`~/.agents/skills/hyperframes/SKILL.md` §"Composition Structure"):
the root composition is a STANDALONE composition — its `data-composition-id`
div sits directly in `<body>`, NOT wrapped in `<template>`. Pattern B
sub-comp loading via `<template>` + `data-composition-src` would be the
canonical way to reference each scene as its own composition, but HF
0.4.41/0.4.44's loader produces black renders / 0 elements with that
pattern (memory `feedback_hf_subcomp_loader_data_composition_src`,
upstream #589 closed-but-not-fixed). Until that lands, beats are inlined
directly into the root composition body — Pattern A per
`transitions/catalog.md` L36-80.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .._scene_id import scene_id_for


_BEAT_INJECTION_MARKER = "<!-- p4_assemble_index: beats -->"
_CAPTIONS_INJECTION_MARKER = "<!-- p4_assemble_index: captions -->"
_END_INJECTION_MARKER = "<!-- p4_assemble_index: end -->"
_SHIM_BEGIN_MARKER = "<!-- p4_assemble_index: shim begin -->"
_SHIM_END_MARKER = "<!-- p4_assemble_index: shim end -->"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {
        "errors": [
            {"node": "p4_assemble_index", "message": message, "timestamp": _now()},
        ]
    }


def _skip(reason: str) -> dict:
    return {
        "compose": {
            "assemble": {"skipped": True, "skip_reason": reason},
        },
    }


def _strip_block(html: str, begin: str, end: str) -> str:
    """Remove a marker-bracketed block; recover from interrupted writes by
    dropping a stray begin marker (and everything after it) when the end
    marker is missing — same belt-and-suspenders pattern as the original
    implementation, generalised across both block kinds."""
    full = re.compile(re.escape(begin) + r".*?" + re.escape(end), flags=re.DOTALL)
    cleaned = full.sub("", html)
    if begin in cleaned:
        cleaned = cleaned.split(begin, 1)[0]
    return cleaned


def _strip_existing_injection(html: str) -> str:
    """Remove previously-injected beats and shim blocks so re-runs are idempotent."""
    html = _strip_block(html, _BEAT_INJECTION_MARKER, _END_INJECTION_MARKER)
    html = _strip_block(html, _SHIM_BEGIN_MARKER, _SHIM_END_MARKER)
    return html


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically via tmp + os.replace.

    Prevents the partial-injection state described in `_strip_block`: on
    crash mid-write, the original file is preserved untouched rather than
    left half-written.
    """
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def build_visibility_shim(
    scene_ids: list[str], scene_starts: list[float]
) -> str | None:
    """Generate the v4 root-timeline visibility shim (returns None if no scenes).

    Produces hard-cut scene visibility pending the canonical transitions node
    (HOM-77/v5). For each scene at index `i` with start time `t`:
      - if `i > 0`: `root.set('#scene-<id>', { opacity: 1 }, t)` — the first
        scene starts visible (opacity: 1 in its fragment style); subsequent
        scenes carry `opacity: 0` initially per `transitions/catalog.md` L9.
      - always: `root.add(window.__sceneTimelines[id], t)` — nest the
        scene-local timeline at its start so its entrance tweens fire under
        non-linear seek.

    The script is defensive about both `__timelines["root"]` and
    `__sceneTimelines[id]` being undefined so a missing scaffold piece (or
    a scene whose author skipped the timeline registration) degrades to a
    no-op rather than throwing in the browser.
    """
    if not scene_ids:
        return None
    ids_json = json.dumps(scene_ids)
    starts_json = json.dumps(scene_starts)
    return (
        f"{_SHIM_BEGIN_MARKER}\n"
        "<script>\n"
        "(function() {\n"
        '  var root = window.__timelines && window.__timelines["root"];\n'
        "  if (!root) return;\n"
        f"  var ids = {ids_json};\n"
        f"  var starts = {starts_json};\n"
        "  ids.forEach(function(id, i) {\n"
        "    if (i > 0) {\n"
        "      root.set('#scene-' + id, { opacity: 1 }, starts[i]);\n"
        "    }\n"
        "    var sceneTl = window.__sceneTimelines && window.__sceneTimelines[id];\n"
        "    if (sceneTl) root.add(sceneTl, starts[i]);\n"
        "  });\n"
        "})();\n"
        "</script>\n"
        f"{_SHIM_END_MARKER}"
    )


def assemble_html(
    *,
    root_html: str,
    beat_html_fragments: list[tuple[str, str]],
    captions_html: str | None,
    visibility_shim: str | None = None,
) -> str:
    """Inject beat fragments + optional captions block + optional v4 shim
    before `</body>`.

    Pure function so unit tests drive it without touching disk.

    Args:
        root_html: scaffolded index.html as written by p4_scaffold.
        beat_html_fragments: list of (scene_id, html_fragment) pairs. Each
            fragment is a Pattern A scene `<div id="scene-…" …>`, inlined
            as-is (no inner-div extraction).
        captions_html: optional captions block HTML; injected after beats.
        visibility_shim: optional `<script>` block (with shim markers
            already attached by `build_visibility_shim`); injected last.
    """
    cleaned = _strip_existing_injection(root_html)
    pieces = [_BEAT_INJECTION_MARKER]
    for name, fragment in beat_html_fragments:
        pieces.append(f"<!-- beat: {name} -->")
        pieces.append(fragment.strip())
    if captions_html:
        pieces.append(_CAPTIONS_INJECTION_MARKER)
        pieces.append(captions_html.strip())
    pieces.append(_END_INJECTION_MARKER)
    if visibility_shim:
        pieces.append(visibility_shim)
    injection = "\n".join(pieces) + "\n"

    if "</body>" in cleaned:
        return cleaned.replace("</body>", injection + "</body>", 1)
    # No </body> — append at end. (Scaffolded index.html always has one,
    # but this keeps the function total for tests / hand-edited inputs.)
    return cleaned + injection


def p4_assemble_index_node(state):
    compose = state.get("compose") or {}
    plan = compose.get("plan") or {}
    plan_beats = plan.get("beats") or []
    if not plan_beats:
        return _skip("no beats in compose.plan (p4_plan must run first)")

    index_html_path = compose.get("index_html_path")
    if not index_html_path:
        return _error("compose.index_html_path missing (p4_scaffold must run first)")
    index_path = Path(index_html_path)
    if not index_path.is_file():
        return _error(f"root index.html not found at {index_path}")

    compositions_dir = index_path.parent / "compositions"

    # Single pass: derive scene_ids + cumulative starts; locate fragments;
    # aggregate ALL missing scenes before deciding so the skip reason
    # surfaces every gap in one notice.
    scene_ids: list[str] = []
    scene_starts: list[float] = []
    fragments: list[tuple[str, str]] = []
    missing: list[str] = []
    cumulative_s = 0.0

    for idx, beat in enumerate(plan_beats):
        if not isinstance(beat, dict):
            return _error(
                f"plan beat at index {idx} is not a dict: {type(beat).__name__}"
            )
        label = beat.get("beat") or beat.get("name") or ""
        if not label:
            return _error(f"plan beat at index {idx} missing 'beat' label")
        sid = scene_id_for(label)
        scene_path = compositions_dir / f"{sid}.html"
        duration = float(beat.get("duration_s") or 0.0)

        scene_ids.append(sid)
        scene_starts.append(cumulative_s)

        if not scene_path.is_file():
            missing.append(sid)
        else:
            fragments.append((sid, scene_path.read_text(encoding="utf-8")))

        cumulative_s += duration

    if missing:
        return _skip(f"missing scenes: {', '.join(missing)}")

    captions_html: str | None = None
    captions_path_str = compose.get("captions_block_path")
    if captions_path_str:
        cp = Path(captions_path_str)
        if not cp.is_file():
            return _error(f"captions block path does not exist: {cp}")
        captions_html = cp.read_text(encoding="utf-8")

    shim = build_visibility_shim(scene_ids, scene_starts)
    root_html = index_path.read_text(encoding="utf-8")
    patched = assemble_html(
        root_html=root_html,
        beat_html_fragments=fragments,
        captions_html=captions_html,
        visibility_shim=shim,
    )
    if patched != root_html:
        _atomic_write_text(index_path, patched)

    return {
        "compose": {
            "index_html_path": str(index_path),
            "assemble": {
                "assembled_at": _now(),
                "beat_names": scene_ids,
                "captions_included": captions_html is not None,
            },
        },
    }
