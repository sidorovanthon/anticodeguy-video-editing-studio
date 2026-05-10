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

from langgraph.types import CachePolicy

from .._caching import make_key, stable_fingerprint
from .._scene_id import scene_id_for

# Bump on assemble_html / shim shape / marker change. Spec §8.
# v4 (HOM-214): two changes to make the Pattern A root-timeline composition
# self-consistent and observable from the assembled `index.html` alone, per
# canon `~/.agents/skills/hyperframes/patterns.md` "Top-Level Composition" +
# `~/.agents/skills/hyperframes/references/transitions/catalog.md` Hard Rules:
#   1. The visibility shim now emits `root.set('#scene-<id>', { opacity: 1 }, t)`
#      for EVERY scene (including i=0 at t=0), not just non-first scenes.
#      The fragment style still carries `opacity: 1` for scene-0 so the page
#      renders the Hook before the timeline first ticks; the explicit
#      anchor at t=0 makes "first scene at t=0" a structurally observable
#      property of the root timeline (HOM-211 diagnostic surfaced an empty
#      t=0..2 window — Hook absent on the root timeline). It also gives the
#      future canonical transitions node (HOM-77) a clean handoff: it can
#      replace these `set(... opacity: 1)` calls with fade-in tweens at
#      identical positions without re-deriving cumulative starts.
#   2. The root composition's `data-duration` is reconciled to
#      `max(current, cumulative_end)` at assemble time. `p4_scaffold` writes
#      `data-duration` from ffprobe of `final.mp4` (audio-driven), but
#      `compose.plan.beats[]` durations are LLM-rounded and routinely sum
#      higher (HOM-211: 22.367 vs 26.5). When the sum exceeds ffprobe length
#      the last scene's `data-start + data-duration` runs past the root's
#      end, producing a dead-zone black tail in preview. Reconciliation
#      makes the timeline long enough to contain every scene; the renderer
#      still cuts the audio at final.mp4's actual length via the el-audio
#      `<audio>` element's own `data-duration`.
# v3 (HOM-191): also injects a `:root { --bg: …; --fg: …; --font-body: …; }`
# tokens block consuming `compose.design.palette` + `compose.design.typography`,
# so `p4_scaffold`'s `var(--bg, transparent)` placeholder resolves to the
# DESIGN.md palette without `gate:design_adherence` flagging a stray hex.
# v2 (HOM-164): visibility shim now unpauses scene-local timelines before
# nesting them into root via `tl.add(child)`. GSAP semantics: a parent's
# `seek()` does NOT advance a child timeline whose `paused: true` flag is
# still set — the child stays at t=0 even when the parent is at t=N. Per-scene
# `p4_beat` fragments register `gsap.timeline({ paused: true })` (HF canon
# `~/.agents/skills/hyperframes/SKILL.md` §"Timeline Contract"); the shim
# must clear that flag immediately before `root.add(...)` so the HF runtime's
# seek of `__timelines["root"]` actually plays the entrance tweens. Without
# this, every scene-1+ frame stays at the fromTo from-state — the
# Phase 4 black-screen symptom HOM-164 was filed for. Repro confirmed in a
# clean `npx hyperframes init` scaffold; fix is purely orchestrator-side.
_CACHE_VERSION = 4


def _scene_html_paths(state: dict) -> list[str | None]:
    """Resolve per-beat `<scene_id>.html` paths from `compose.plan.beats[]`.

    Spec §6 originally listed `[b.html_path for b in beats]` referencing the
    deprecated `compose.beats[]` state echo. HOM-133/134 moved beats fan-out
    to FS-truth (`<hyperframes_dir>/compositions/<scene_id>.html`); this
    helper rebuilds the list on the same FS basis the node body uses.
    """
    compose = state.get("compose") or {}
    plan = compose.get("plan") or {}
    plan_beats = plan.get("beats") or []
    index_html_path = compose.get("index_html_path")
    if not index_html_path or not plan_beats:
        return []
    compositions_dir = Path(index_html_path).parent / "compositions"
    paths: list[str | None] = []
    for beat in plan_beats:
        if not isinstance(beat, dict):
            continue
        label = beat.get("beat") or beat.get("name") or ""
        if not label:
            continue
        sid = scene_id_for(label)
        paths.append(str(compositions_dir / f"{sid}.html"))
    return paths


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p4_assemble_index` (HOM-132.4).

    Inputs are the per-beat scene fragments and the optional captions block.
    The node mutates `<hyperframes_dir>/index.html` (atomic write) — that
    path is the OUTPUT and is NOT in `files=` (mirrors the
    `p3_render_segments` / `p3_persist_session` mutated-output rule).

    Spec §6 amendment in this PR: `[b.html_path for b in beats]` was based
    on the deprecated `compose.beats[]` echo; the live source is
    `compose.plan.beats[]` with derived `<scene_id>.html` paths under
    `<hyperframes_dir>/compositions/`.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_assemble_index cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    files: list[str | None] = list(_scene_html_paths(state))
    captions_path = (state.get("compose") or {}).get("captions_block_path")
    if captions_path:
        files.append(str(captions_path))
    # HOM-191: design palette + typography are inlined as a `:root { … }` tokens
    # block. They're in-memory state (not files), so fingerprint them as extras
    # to invalidate when the design changes without an upstream file edit.
    design = (state.get("compose") or {}).get("design") or {}
    design_tokens = {
        "palette": design.get("palette"),
        "typography": design.get("typography"),
    }
    return make_key(
        node="p4_assemble_index",
        version=_CACHE_VERSION,
        slug=slug,
        files=files,
        extras=(stable_fingerprint(design_tokens),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


_BEAT_INJECTION_MARKER = "<!-- p4_assemble_index: beats -->"
_CAPTIONS_INJECTION_MARKER = "<!-- p4_assemble_index: captions -->"
_END_INJECTION_MARKER = "<!-- p4_assemble_index: end -->"
_SHIM_BEGIN_MARKER = "<!-- p4_assemble_index: shim begin -->"
_SHIM_END_MARKER = "<!-- p4_assemble_index: shim end -->"
_TOKENS_BEGIN_MARKER = "<!-- p4_assemble_index: tokens begin -->"
_TOKENS_END_MARKER = "<!-- p4_assemble_index: tokens end -->"

# Canonical CSS variable names for the late-bound design tokens. Scaffold
# emits `var(--bg, transparent)` etc. as placeholders; this block resolves
# them from `compose.design.palette` / `compose.design.typography` (HOM-191).
# Roles map by string match against `palette[*].role` / `typography[*].role`.
_PALETTE_ROLE_TO_VAR = {
    "background": "--bg",
    "foreground": "--fg",
    "accent": "--accent",
    "surface": "--surface",
}
_TYPOGRAPHY_ROLE_TO_VAR = {
    "body": "--font-body",
    "headline": "--font-display",
    "display": "--font-display",
}


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
    """Remove previously-injected beats, shim, and tokens blocks so re-runs are idempotent."""
    html = _strip_block(html, _BEAT_INJECTION_MARKER, _END_INJECTION_MARKER)
    html = _strip_block(html, _SHIM_BEGIN_MARKER, _SHIM_END_MARKER)
    html = _strip_block(html, _TOKENS_BEGIN_MARKER, _TOKENS_END_MARKER)
    return html


def build_root_tokens_block(
    palette: list[dict] | None,
    typography: list[dict] | None,
) -> str | None:
    """Generate a `:root { --bg: …; --fg: …; --font-body: …; }` tokens block.

    Resolves the CSS custom-property placeholders `p4_scaffold` writes
    (`var(--bg, transparent)` etc.) against the DESIGN.md tokens produced by
    `p4_design_system`. Roles that don't map to a known variable are skipped
    silently — the fallback in the placeholder keeps the page renderable.

    Returns `None` when neither palette nor typography contains a recognised
    role, so the caller can omit the marker pair entirely.
    """
    declarations: list[str] = []
    seen_vars: set[str] = set()
    for entry in palette or []:
        if not isinstance(entry, dict):
            continue
        role = (entry.get("role") or "").strip().lower()
        hx = entry.get("hex")
        var_name = _PALETTE_ROLE_TO_VAR.get(role)
        if not var_name or not isinstance(hx, str) or var_name in seen_vars:
            continue
        declarations.append(f"  {var_name}: {hx};")
        seen_vars.add(var_name)
    for entry in typography or []:
        if not isinstance(entry, dict):
            continue
        role = (entry.get("role") or "").strip().lower()
        family = entry.get("family")
        var_name = _TYPOGRAPHY_ROLE_TO_VAR.get(role)
        if not var_name or not isinstance(family, str) or var_name in seen_vars:
            continue
        # Quote multi-word families per CSS spec; single-word stays bare for readability.
        family_token = f'"{family}"' if " " in family.strip() else family.strip()
        declarations.append(f"  {var_name}: {family_token}, sans-serif;")
        seen_vars.add(var_name)
    if not declarations:
        return None
    body = "\n".join(declarations)
    return (
        f"{_TOKENS_BEGIN_MARKER}\n"
        "<style>\n"
        ":root {\n"
        f"{body}\n"
        "}\n"
        "</style>\n"
        f"{_TOKENS_END_MARKER}"
    )


_SCENE_OPEN_TAG_RE = re.compile(
    r"""<div\b[^>]*?\bid=(?P<q>["'])scene-[^"']+?(?P=q)[^>]*>""",
    flags=re.IGNORECASE | re.DOTALL,
)
_CLASS_ATTR_RE = re.compile(
    r"""\bclass\s*=\s*(?P<q>["'])(?P<val>[^"']*)(?P=q)""",
    flags=re.IGNORECASE,
)


def _ensure_scene_clip_class(fragment: str) -> str:
    """Ensure the root scene `<div id="scene-…">` carries `class="clip"`.

    HF lint flags `timed_element_missing_clip_class` on any element with
    `data-start`/`data-duration` but no `.clip` — and the runtime really does
    use `.clip` to hard-cut visibility (`feedback_hf_pattern_a_vs_b`,
    `transitions/catalog.md` L13 rationale). Pattern A as authored by
    `p4_beat` keeps timing attrs on the scene div for the v4 visibility
    shim, so the class must follow.

    Defensive post-process — the brief mandates `class="scene clip"`, but
    drift through the LLM (or stale fragments under re-run) shouldn't quietly
    leave the assembled index.html lint-broken. Idempotent: returns the
    fragment unchanged if `clip` is already in the class list.
    """
    match = _SCENE_OPEN_TAG_RE.search(fragment)
    if not match:
        return fragment
    open_tag = match.group(0)
    class_attr = _CLASS_ATTR_RE.search(open_tag)
    if class_attr is None:
        # No class attr — inject one carrying just `clip`.
        new_open_tag = open_tag[:-1] + ' class="clip">'
        return fragment[: match.start()] + new_open_tag + fragment[match.end() :]
    classes = class_attr.group("val").split()
    if "clip" in classes:
        return fragment
    classes.append("clip")
    quote = class_attr.group("q")
    new_class_attr = f"class={quote}{' '.join(classes)}{quote}"
    new_open_tag = open_tag[: class_attr.start()] + new_class_attr + open_tag[class_attr.end() :]
    return fragment[: match.start()] + new_open_tag + fragment[match.end() :]


_SCRIPT_BLOCK_RE = re.compile(
    r"(?P<open><script(?P<attrs>[^>]*)>)(?P<body>.*?)(?P<close></script>)",
    flags=re.IGNORECASE | re.DOTALL,
)
_HAS_SRC_ATTR_RE = re.compile(r"""\bsrc\s*=\s*["']""", flags=re.IGNORECASE)
# Detects bodies already wrapped in an IIFE — `(function() { ... })()` or
# `(() => { ... })()`, possibly preceded by leading whitespace and/or // or
# /* */ comments. Anchored at start of trimmed body.
# Leading semicolons (defensive `;(function(){…})()`) are tolerated so a
# protectively-written IIFE is recognised as already-wrapped. A literal
# `</script>` inside a JS string literal would prematurely close
# `_SCRIPT_BLOCK_RE`'s match — both briefs forbid the dynamic-write APIs
# that produce that pattern, and the failure mode is loud (the trailing
# end-tag is left behind as text) and would surface immediately in the
# next gate:lint run.
_IIFE_HEAD_RE = re.compile(
    r"""\A(?:\s|;|//[^\n]*\n|/\*.*?\*/)*\(\s*(?:function\b|\([^)]*\)\s*=>)""",
    flags=re.DOTALL,
)


def _ensure_inlined_script_iife(fragment: str) -> str:
    """Wrap top-level `<script>` bodies in an IIFE so that `const`/`let`/`var`
    declarations don't leak into the document's shared script lexical scope.

    The scaffolded root composition's script declares `const tl = ...` at
    top level (canonical `hyperframes init` shape). Multiple `<script>`
    blocks share the same script-lexical environment in non-module HTML, so
    *any* other top-level `const tl`/`let tl`/`var tl` (or in fact any
    duplicate top-level identifier) trips
    `Identifier 'tl' has already been declared` under headless validate.

    The `p4_beat` and `p4_captions_layer` briefs both mandate IIFE wrapping
    — but LLM drift produces un-wrapped scripts under re-run, and the
    failure mode is brittle: `validate` halts the entire episode on the
    second `const tl`. Defensive post-process at inline time keeps the
    assembled `index.html` valid regardless of brief drift. Idempotent:
    bodies that already begin with `(function` / `(() =>` / `((arg) =>`
    pass through unchanged.

    Skips `<script src="...">` (no inline body) and empty-body scripts.
    """
    def _wrap(match: re.Match[str]) -> str:
        attrs = match.group("attrs") or ""
        if _HAS_SRC_ATTR_RE.search(attrs):
            return match.group(0)
        body = match.group("body")
        if not body.strip():
            return match.group(0)
        if _IIFE_HEAD_RE.match(body):
            return match.group(0)
        leading_ws = body[: len(body) - len(body.lstrip("\n"))]
        trailing_ws = body[len(body.rstrip()) :]
        inner = body[len(leading_ws) : len(body) - len(trailing_ws)]
        wrapped = f"{leading_ws}(function() {{\n{inner}\n}})();{trailing_ws}"
        return match.group("open") + wrapped + match.group("close")

    return _SCRIPT_BLOCK_RE.sub(_wrap, fragment)


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
      - `root.set('#scene-<id>', { opacity: 1 }, t)` — for EVERY scene,
        including i=0 at t=0. The fragment style still carries `opacity: 1`
        for scene-0 (so the page paints before the timeline first ticks),
        but the explicit `set` at t=0 makes "first scene anchors at t=0"
        a property observable from the assembled root-timeline JS rather
        than relying on inter-fragment coupling. See `_CACHE_VERSION` v4
        note (HOM-214). Subsequent scenes carry `opacity: 0` initially per
        canon `~/.agents/skills/hyperframes/references/transitions/catalog.md`
        Hard Rules — the `set` reveals them at their cumulative start.
      - unpause `window.__sceneTimelines[id]` and nest it via
        `root.add(sceneTl, t)` — see `_CACHE_VERSION` v2 note for the GSAP
        rationale (a paused child timeline does not advance under parent
        `seek()`, so HOM-164's black-screen symptom is fixed by clearing the
        `paused: true` flag the per-scene `p4_beat` fragment authored).

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
        "    // HOM-214: anchor every scene's reveal on the root timeline,\n"
        "    // including i=0 at t=0, so the position chain is observable\n"
        "    // from the shim alone. Scene-0's fragment also has opacity: 1\n"
        "    // in CSS for first-paint, so this is a no-op visually.\n"
        "    root.set('#scene-' + id, { opacity: 1 }, starts[i]);\n"
        "    var sceneTl = window.__sceneTimelines && window.__sceneTimelines[id];\n"
        "    if (sceneTl) {\n"
        "      // HOM-164: unpause child timeline before nesting — GSAP does\n"
        "      // not advance a paused child under parent.seek(), which left\n"
        "      // every scene at fromTo from-state (Phase 4 black screen).\n"
        "      sceneTl.paused(false);\n"
        "      root.add(sceneTl, starts[i]);\n"
        "    }\n"
        "  });\n"
        "})();\n"
        "</script>\n"
        f"{_SHIM_END_MARKER}"
    )


# Targets ONLY the root composition's `data-duration`, not nested element
# `data-duration` attributes (scene divs, video/audio clips). The match is
# anchored to the same `<div ... data-composition-id="..." ...>` opening tag
# `p4_scaffold` writes; sibling timed elements live OUTSIDE that opening tag.
_ROOT_DATA_DURATION_RE = re.compile(
    r"""(<div\b[^>]*?\bdata-composition-id\s*=\s*["'][^"']+["'][^>]*?\bdata-duration\s*=\s*["'])"""
    r"""(?P<value>[\d.]+)"""
    r"""(["'])""",
    flags=re.IGNORECASE | re.DOTALL,
)


def _reconcile_root_data_duration(html: str, cumulative_end_s: float) -> str:
    """Patch the root composition's `data-duration` to `max(current, cumulative_end_s)`.

    HOM-214/HOM-211: `p4_scaffold` writes `data-duration` from ffprobe of
    `final.mp4` (audio length). LLM-rounded `compose.plan.beats[]` durations
    routinely sum higher (canonical fixture: 22.367 ffprobe vs 26.5 cumulative).
    When the sum exceeds ffprobe length, the last scene's data-start +
    data-duration runs past the root timeline end → preview dead-zone /
    black tail. Reconciliation extends the root timeline to contain every
    scene; the audio element keeps its own data-duration so playback still
    cuts at final.mp4's actual length.

    Idempotent: if the current value already meets/exceeds cumulative_end_s,
    the HTML is returned unchanged. Returns the input unchanged if no root
    data-duration is found (defensive — keeps the function total).
    """
    if cumulative_end_s <= 0.0:
        return html

    match = _ROOT_DATA_DURATION_RE.search(html)
    if not match:
        return html

    try:
        current = float(match.group("value"))
    except ValueError:
        return html

    if current >= cumulative_end_s:
        return html

    # Format with one decimal when fractional, integer otherwise — keeps
    # diffs minimal vs the scaffold's typical integer durations.
    new_value = (
        f"{cumulative_end_s:.3f}".rstrip("0").rstrip(".")
        if cumulative_end_s != int(cumulative_end_s)
        else str(int(cumulative_end_s))
    )
    start, end = match.span("value")
    return html[:start] + new_value + html[end:]


def assemble_html(
    *,
    root_html: str,
    beat_html_fragments: list[tuple[str, str]],
    captions_html: str | None,
    visibility_shim: str | None = None,
    tokens_block: str | None = None,
    cumulative_end_s: float | None = None,
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
    if cumulative_end_s is not None:
        cleaned = _reconcile_root_data_duration(cleaned, cumulative_end_s)
    pieces: list[str] = []
    if tokens_block:
        pieces.append(tokens_block)
    pieces.append(_BEAT_INJECTION_MARKER)
    for name, fragment in beat_html_fragments:
        pieces.append(f"<!-- beat: {name} -->")
        pieces.append(
            _ensure_inlined_script_iife(_ensure_scene_clip_class(fragment.strip()))
        )
    if captions_html:
        pieces.append(_CAPTIONS_INJECTION_MARKER)
        pieces.append(_ensure_inlined_script_iife(captions_html.strip()))
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
    design = compose.get("design") or {}
    tokens_block = build_root_tokens_block(
        design.get("palette"), design.get("typography")
    )
    root_html = index_path.read_text(encoding="utf-8")
    patched = assemble_html(
        root_html=root_html,
        beat_html_fragments=fragments,
        captions_html=captions_html,
        visibility_shim=shim,
        tokens_block=tokens_block,
        cumulative_end_s=cumulative_s,
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
