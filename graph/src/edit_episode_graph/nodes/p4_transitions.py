"""p4_transitions node — root-timeline scene-to-scene transitions (HOM-137).

Replaces the v4 visibility shim that `p4_assemble_index` writes (HOM-122c)
with a canonical transitions block authored on the root timeline per
`~/.agents/skills/hyperframes/references/transitions/catalog.md` §"Scene
Template" + §"CSS Transitions". Reads `state["compose"]["plan"]["transitions"]`
(per-boundary mechanism + duration + easing chosen at plan time by HOM-120's
`p4_plan` node) and emits the appropriate tween block in root `index.html`
between `<!-- p4_transitions: begin -->` … `<!-- p4_transitions: end -->`.

Per the ticket (HOM-137 §"Decision: deterministic node vs LLM helper"):
transitions are largely mechanical (CSS templates from catalog, fixed shader
API). The plan already chose mechanism + name + duration + easing; this node
substitutes those parameters into the canonical baseline. Per-name catalog
variants (blur crossfade, focus pull, glitch, etc. — 14 reference files)
add filter/scale ornamentation on top of the same baseline opacity-swap
structure (`tl.to(old, opacity:0)` + `tl.fromTo(new, 0→1)` per
`references/transitions/css-dissolve.md` L8-9). Emitting the baseline with
plan-chosen duration/easing is canon-compliant; the named-variant
ornamentation is an LLM concern (HOM-77/v5+ — node body is a docstring
extension point, not a hard limit).

Three mechanisms (from `BeatTransition.mechanism` literal, schema enforces):

  * ``css``        — `tl.to(outgoing, opacity:0)` + `tl.fromTo(incoming, 0→1)`
                     at root-timeline position = cumulative start of `to_beat`.
                     The `name` field is recorded as a comment so reviewers can
                     see which catalog variant the plan asked for.
  * ``shader``     — `@hyperframes/shader-transitions` integration call
                     (see `references/beat-direction.md` L64-70 +
                     `references/transitions/catalog.md` §"Shader Transitions").
                     Wraps incoming/outgoing scene refs + duration into the
                     package's runtime API (`window.HFShaderTransitions.start({…})`)
                     so the actual GLSL setup remains in the package — no raw
                     shader code in our emitted JS.
  * ``final-fade`` — `tl.to('#scene-<last>', { opacity:0 }, end - duration)`
                     (HR 4 exception in canon — only valid on the very last
                     scene's exit; `gate:plan_ok` already enforces
                     `to_beat == "END"` and `from_beat == last beat`).

Replaces the v4 shim block in root `index.html` — strips the old markers
(`<!-- p4_assemble_index: shim begin -->` … `shim end`) cleanly and writes
the new transitions block in the same position. v4 shim is an intermediate
state per spec §"v4 visibility shim"; this node is its canonical replacement.

Skip clean if `compose.plan.transitions` is missing/empty (1-beat plan with
no final-fade has zero transitions; that's schema-valid). Error loud if a
`from_beat`/`to_beat` references a scene id not in `compose.plan.beats[]` —
`gate:plan_ok` already validates non-empty + interior-boundary coverage,
but this node fails closed on referential breakage rather than emitting a
broken `tl.to('#scene-undefined', …)` selector.
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
from .._paths import EpisodePaths
from .._scene_id import scene_id_for


# Bump on emit-block shape / marker change / mechanism-template change.
# Spec §8.
_CACHE_VERSION = 1


_BEGIN_MARKER = "<!-- p4_transitions: begin -->"
_END_MARKER = "<!-- p4_transitions: end -->"
# Markers from p4_assemble_index's v4 visibility shim — stripped here so the
# canonical transitions block replaces it cleanly. Kept in sync with
# `p4_assemble_index._SHIM_BEGIN_MARKER` / `_SHIM_END_MARKER`.
_SHIM_BEGIN_MARKER = "<!-- p4_assemble_index: shim begin -->"
_SHIM_END_MARKER = "<!-- p4_assemble_index: shim end -->"


def _index_html_path(state: dict) -> Path | None:
    """HOM-224 pattern: derive index.html via slug; fall back to legacy echo."""
    slug = state.get("slug")
    if slug:
        return EpisodePaths(slug).index_html_path
    compose = state.get("compose") or {}
    legacy = compose.get("index_html_path")
    if legacy:
        return Path(legacy)
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {
        "errors": [
            {"node": "p4_transitions", "message": message, "timestamp": _now()},
        ]
    }


def _skip(reason: str) -> dict:
    return {
        "compose": {
            "transitions": {"skipped": True, "skip_reason": reason},
        },
    }


def _cache_key(state, *_args, **_kwargs):
    """Deterministic cache key for p4_transitions.

    Mutates `<hyperframes_dir>/index.html` (atomic write) — that path is the
    OUTPUT and is NOT in `files=` (mirrors `p4_assemble_index`'s
    mutated-output rule). Inputs that change emitted block content:
      - `compose.plan.transitions` list (mechanism/name/duration/easing/why)
      - `compose.plan.beats` order + duration_s (for cumulative starts)
    Both are in-memory state, fingerprinted as extras via stable_fingerprint.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_transitions cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    plan = compose.get("plan") or {}
    transitions = plan.get("transitions") or []
    beats = plan.get("beats") or []
    return make_key(
        node="p4_transitions",
        version=_CACHE_VERSION,
        slug=slug,
        files=(),
        extras=(
            stable_fingerprint(transitions),
            # Beat ordering and durations drive cumulative `T` positions in
            # the emitted timeline — a duration edit must invalidate even if
            # transitions list is byte-identical.
            stable_fingerprint(
                [
                    {"beat": b.get("beat") or b.get("name"),
                     "duration_s": b.get("duration_s")}
                    for b in beats if isinstance(b, dict)
                ]
            ),
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _strip_block(html: str, begin: str, end: str) -> str:
    """Remove a marker-bracketed block; same belt-and-suspenders pattern as
    `p4_assemble_index._strip_block` — drop a stray begin marker if the end
    is missing (recovery from interrupted writes)."""
    full = re.compile(re.escape(begin) + r".*?" + re.escape(end), flags=re.DOTALL)
    cleaned = full.sub("", html)
    if begin in cleaned:
        cleaned = cleaned.split(begin, 1)[0]
    return cleaned


def _strip_existing(html: str) -> str:
    """Strip both the v4 shim block and any prior p4_transitions block."""
    html = _strip_block(html, _SHIM_BEGIN_MARKER, _SHIM_END_MARKER)
    html = _strip_block(html, _BEGIN_MARKER, _END_MARKER)
    return html


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically via tmp + os.replace."""
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


def _cumulative_starts(beats: list[dict]) -> dict[str, float]:
    """Map beat label → cumulative start time on the root timeline.

    Mirrors the order/duration arithmetic in `p4_assemble_index._scene_html_paths`
    so transitions land at exactly the same `T` the visibility shim used to
    set scene-opacity at — only now it's a `tl.to`/`tl.fromTo` instead of a
    `tl.set`. Per `references/motion-principles.md` L125-133 — every motion
    is timeline-attached; no bare `gsap.to()`.
    """
    starts: dict[str, float] = {}
    cumulative = 0.0
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        label = beat.get("beat") or beat.get("name")
        if not label:
            continue
        starts[label] = cumulative
        cumulative += float(beat.get("duration_s") or 0.0)
    return starts


def _total_duration(beats: list[dict]) -> float:
    total = 0.0
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        total += float(beat.get("duration_s") or 0.0)
    return total


def _emit_css_tween(transition: dict, t_position: float) -> list[str]:
    """Emit canonical CSS crossfade tween at position `t_position`.

    Per `references/transitions/catalog.md` L36-80 (Scene Template) and
    `references/transitions/css-dissolve.md` L8-9 (Crossfade baseline) —
    every CSS transition reduces to outgoing-opacity-out + incoming-opacity-in
    at the boundary `T`. Variants in the catalog (blur crossfade, focus pull,
    color dip …) ornament that baseline with filter/scale animations; the
    plan's `name` is recorded as a comment so a v5+ LLM helper can extend
    this branch with per-name templates without rewiring the routing.
    """
    from_label = transition["from_beat"]
    to_label = transition["to_beat"]
    from_sid = scene_id_for(from_label)
    to_sid = scene_id_for(to_label)
    duration = float(transition["duration_s"])
    easing = transition["easing"]
    name = transition.get("name") or ""
    why = transition.get("why") or ""
    t_repr = f"{t_position:.4f}".rstrip("0").rstrip(".") or "0"
    d_repr = f"{duration:.4f}".rstrip("0").rstrip(".") or "0"
    return [
        f"  // css transition: {from_label} → {to_label} "
        f"(name={json.dumps(name)}, why={json.dumps(why)})",
        f"  root.to('#scene-{from_sid}', "
        f"{{ opacity: 0, duration: {d_repr}, ease: {json.dumps(easing)} }}, "
        f"{t_repr});",
        f"  root.fromTo('#scene-{to_sid}', "
        f"{{ opacity: 0 }}, "
        f"{{ opacity: 1, duration: {d_repr}, ease: {json.dumps(easing)} }}, "
        f"{t_repr});",
    ]


def _emit_shader_tween(transition: dict, t_position: float) -> list[str]:
    """Emit a `@hyperframes/shader-transitions` runtime call at `t_position`.

    Canon — `references/transitions/catalog.md` §"Shader Transitions" L31-33
    + L115-117 — directs us to the `@hyperframes/shader-transitions` package
    for setup/capture/WebGL init/render loop/GSAP integration, and warns
    "do not copy raw GLSL manually". The package's runtime entry point is
    invoked here with the from/to scene selectors + name + duration; the
    package handles the actual `gsap.timeline()` integration and renders the
    transition into a canvas overlay between scenes. Defensive: degrades to a
    plain crossfade if `window.HFShaderTransitions` isn't loaded, mirroring
    the v4 shim's `if (!root) return` defence pattern.
    """
    from_label = transition["from_beat"]
    to_label = transition["to_beat"]
    from_sid = scene_id_for(from_label)
    to_sid = scene_id_for(to_label)
    duration = float(transition["duration_s"])
    easing = transition["easing"]
    name = transition.get("name") or ""
    t_repr = f"{t_position:.4f}".rstrip("0").rstrip(".") or "0"
    d_repr = f"{duration:.4f}".rstrip("0").rstrip(".") or "0"
    return [
        f"  // shader transition: {from_label} → {to_label} (name={json.dumps(name)})",
        "  if (window.HFShaderTransitions && window.HFShaderTransitions.attach) {",
        f"    window.HFShaderTransitions.attach(root, {{",
        f"      from: '#scene-{from_sid}',",
        f"      to: '#scene-{to_sid}',",
        f"      name: {json.dumps(name)},",
        f"      duration: {d_repr},",
        f"      ease: {json.dumps(easing)},",
        f"      position: {t_repr},",
        "    });",
        "  } else {",
        "    // Fallback: package not loaded — degrade to crossfade so the run is still viewable.",
        f"    root.to('#scene-{from_sid}', "
        f"{{ opacity: 0, duration: {d_repr}, ease: {json.dumps(easing)} }}, "
        f"{t_repr});",
        f"    root.fromTo('#scene-{to_sid}', "
        f"{{ opacity: 0 }}, "
        f"{{ opacity: 1, duration: {d_repr}, ease: {json.dumps(easing)} }}, "
        f"{t_repr});",
        "  }",
    ]


def _emit_final_fade(
    transition: dict, last_label: str, total_duration: float
) -> list[str]:
    """Emit `tl.to('#scene-<last>', { opacity: 0 }, end - duration)`.

    Canon HR 4 exception — `references/transitions.md` §"Animation Rules"
    + memory `feedback_translucent_transitions` — final-fade is the only
    canon-allowed exit animation. `gate:plan_ok` (`gates/plan_ok.py` L106-121)
    enforces `from_beat == last beat label` and `to_beat == "END"`; this
    helper trusts that contract.
    """
    from_sid = scene_id_for(transition["from_beat"])
    duration = float(transition["duration_s"])
    easing = transition["easing"]
    name = transition.get("name") or ""
    position = max(0.0, total_duration - duration)
    t_repr = f"{position:.4f}".rstrip("0").rstrip(".") or "0"
    d_repr = f"{duration:.4f}".rstrip("0").rstrip(".") or "0"
    return [
        f"  // final-fade: {last_label} → END (name={json.dumps(name)})",
        f"  root.to('#scene-{from_sid}', "
        f"{{ opacity: 0, duration: {d_repr}, ease: {json.dumps(easing)} }}, "
        f"{t_repr});",
    ]


def build_transitions_block(
    *,
    transitions: list[dict],
    beats: list[dict],
) -> str | None:
    """Build the `<!-- p4_transitions: begin --> … end -->` block.

    Returns ``None`` when there are no transitions to emit (1-beat plan
    without a final-fade), so the caller can omit the marker pair entirely
    rather than write an empty IIFE.
    """
    if not transitions:
        return None

    starts = _cumulative_starts(beats)
    total = _total_duration(beats)
    last_label: str | None = None
    for beat in reversed(beats):
        if isinstance(beat, dict):
            last_label = beat.get("beat") or beat.get("name")
            if last_label:
                break

    body_lines: list[str] = []
    for i, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            continue
        mech = transition.get("mechanism")
        from_label = transition.get("from_beat")
        to_label = transition.get("to_beat")
        if mech == "final-fade":
            body_lines.extend(
                _emit_final_fade(transition, last_label or from_label, total)
            )
            continue
        # Position transitions at cumulative start of `to_beat` — same anchor
        # the v4 shim used for scene-opacity reveal.
        t_position = starts.get(to_label, 0.0)
        if mech == "css":
            body_lines.extend(_emit_css_tween(transition, t_position))
        elif mech == "shader":
            body_lines.extend(_emit_shader_tween(transition, t_position))
        else:
            # Schema enforces the literal — defensive comment for unexpected drift.
            body_lines.append(
                f"  // transitions[{i}] mechanism={mech!r}: unsupported, skipped"
            )

    body = "\n".join(body_lines)
    return (
        f"{_BEGIN_MARKER}\n"
        "<script>\n"
        "(function() {\n"
        '  var root = window.__timelines && window.__timelines["root"];\n'
        "  if (!root) return;\n"
        f"{body}\n"
        "})();\n"
        "</script>\n"
        f"{_END_MARKER}"
    )


def _validate_refs(
    transitions: list[dict], beat_labels: set[str]
) -> str | None:
    """Return error string if any from_beat/to_beat is dangling.

    `final-fade` legitimately has `to_beat == "END"` (gate:plan_ok enforces);
    that's not a dangling ref.
    """
    for i, t in enumerate(transitions):
        if not isinstance(t, dict):
            continue
        mech = t.get("mechanism")
        from_b = t.get("from_beat")
        to_b = t.get("to_beat")
        if from_b not in beat_labels:
            return (
                f"transitions[{i}].from_beat={from_b!r} not in plan.beats "
                f"({sorted(beat_labels)})"
            )
        if mech == "final-fade":
            if to_b != "END":
                return (
                    f"transitions[{i}].to_beat={to_b!r} for final-fade "
                    "must be 'END' (canon `references/transitions.md`)"
                )
            continue
        if to_b not in beat_labels:
            return (
                f"transitions[{i}].to_beat={to_b!r} not in plan.beats "
                f"({sorted(beat_labels)})"
            )
    return None


def assemble_html(
    *,
    root_html: str,
    transitions_block: str | None,
) -> str:
    """Strip prior shim/transitions blocks and inject the new one before </body>."""
    cleaned = _strip_existing(root_html)
    if transitions_block is None:
        return cleaned
    injection = transitions_block + "\n"
    if "</body>" in cleaned:
        return cleaned.replace("</body>", injection + "</body>", 1)
    return cleaned + injection


def p4_transitions_node(state):
    compose = state.get("compose") or {}
    plan = compose.get("plan") or {}
    plan_beats = plan.get("beats") or []
    transitions = plan.get("transitions") or []

    if not transitions:
        # Schema-valid for 1-beat plans without final-fade; nothing to emit.
        # We still STRIP the old v4 shim from index.html so the canonical
        # block-or-nothing replaces it cleanly.
        index_path = _index_html_path(state)
        if index_path is not None and index_path.is_file():
            root_html = index_path.read_text(encoding="utf-8")
            patched = assemble_html(root_html=root_html, transitions_block=None)
            if patched != root_html:
                _atomic_write_text(index_path, patched)
        return _skip("no transitions in compose.plan (1-beat plan or plan missing)")

    if not plan_beats:
        return _error(
            "compose.plan.transitions present but compose.plan.beats empty — "
            "cannot resolve from_beat/to_beat to scene ids"
        )

    index_path = _index_html_path(state)
    if index_path is None:
        return _error("slug missing in state — cannot resolve index.html path")
    if not index_path.is_file():
        return _error(
            f"root index.html not found at {index_path} "
            "(p4_assemble_index must run first)"
        )

    beat_labels = {
        b.get("beat") or b.get("name")
        for b in plan_beats
        if isinstance(b, dict) and (b.get("beat") or b.get("name"))
    }
    err = _validate_refs(transitions, beat_labels)
    if err:
        return _error(err)

    block = build_transitions_block(transitions=transitions, beats=plan_beats)
    root_html = index_path.read_text(encoding="utf-8")
    patched = assemble_html(root_html=root_html, transitions_block=block)
    if patched != root_html:
        _atomic_write_text(index_path, patched)

    return {
        "compose": {
            "transitions": {
                "authored_at": _now(),
                "n_transitions": len(transitions),
                "mechanisms": [
                    t.get("mechanism") for t in transitions if isinstance(t, dict)
                ],
            },
        },
    }
