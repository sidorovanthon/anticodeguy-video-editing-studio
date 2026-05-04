"""gate:design_ok — validates the DesignDoc produced by p4_design_system.

Per spec §6.2 / canon hyperframes SKILL.md §"Step 1: Design system":
  - DesignDoc parseable and not skipped upstream.
  - DESIGN.md actually exists at the path the agent claimed it wrote to —
    schema field is just a string; only the file's presence proves the
    Write tool actually fired.
  - Substance bounds the schema also enforces (refs≥2, alternatives≥1,
    anti_patterns≥3, beat_visual_mapping non-empty) — re-asserted at the
    gate so a schema regression never silently weakens enforcement.
  - Every EDL beat has a `beat_visual_mapping` entry (coverage). An
    unmapped beat means the downstream beat sub-agent has no visual
    direction for that scene.
  - When the operator named one of the 8 visual-styles presets in their
    prompt and the agent picked a `style_name`, it must match (best-effort
    case-insensitive substring match on the named preset). If we can't
    detect a named preset request, the check is skipped.
"""

from __future__ import annotations

from pathlib import Path

from ._base import Gate

# Threshold below which a DESIGN.md is treated as suspiciously small. Set so a
# skeleton document — all canonical YAML keys at one-word values plus all the
# canonical prose section headers with no body content — slips above 200B but
# is still rejected here. Empirically a minimal but operationally complete
# DESIGN.md (one sentence per section) is ~600–800B, so 500B is the smallest
# threshold that catches the failure mode without flagging real-but-terse
# documents.
DESIGN_MD_MIN_BYTES = 500

_VISUAL_STYLES = (
    "Swiss Pulse",
    "Velvet Standard",
    "Deconstructed",
    "Maximalist Type",
    "Data Drift",
    "Soft Signal",
    "Folk Frequency",
    "Shadow Cut",
)


def _named_preset(state: dict) -> str | None:
    """Return the visual-style preset the operator named, or None.

    Best-effort: looks at the strategy `shape` text and any
    `style_request` field that future operator-input nodes might add. We
    do not parse arbitrary user prompts — a missing detect path is
    treated as no-named-preset, not a violation.
    """
    edit = state.get("edit") or {}
    strategy = edit.get("strategy") or {}
    haystack_parts = [
        strategy.get("shape") or "",
        strategy.get("pacing") or "",
        (state.get("compose") or {}).get("style_request") or "",
    ]
    haystack = " ".join(haystack_parts).lower()
    for preset in _VISUAL_STYLES:
        if preset.lower() in haystack:
            return preset
    return None


def _edl_beats(state: dict) -> list[str]:
    edl = (state.get("edit") or {}).get("edl") or {}
    ranges = edl.get("ranges") or []
    seen: list[str] = []
    for r in ranges:
        beat = r.get("beat")
        if beat and beat not in seen:
            seen.append(beat)
    return seen


class DesignOkGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:design_ok")

    def checks(self, state: dict) -> list[str]:
        violations: list[str] = []
        design = (state.get("compose") or {}).get("design") or {}

        if design.get("skipped"):
            return [f"design skipped upstream: {design.get('skip_reason')}"]
        if "raw_text" in design and "palette" not in design:
            return ["design unparseable (raw_text only — schema validation failed upstream)"]

        path_str = design.get("design_md_path")
        if not path_str:
            violations.append("design_md_path missing in DesignDoc")
        else:
            path = Path(path_str)
            if not path.is_file():
                violations.append(f"DESIGN.md not on disk at {path_str} (Write tool did not fire)")
            elif path.stat().st_size < DESIGN_MD_MIN_BYTES:
                violations.append(
                    f"DESIGN.md at {path_str} is suspiciously small ({path.stat().st_size}B "
                    f"< {DESIGN_MD_MIN_BYTES}B); a skeleton with all canonical headers + "
                    "single-word YAML values would land in this range"
                )

        refs = design.get("refs") or []
        if len(refs) < 2:
            violations.append(f"refs has {len(refs)} entries; need ≥ 2")
        alternatives = design.get("alternatives") or []
        if len(alternatives) < 1:
            violations.append(f"alternatives has {len(alternatives)} entries; need ≥ 1")
        anti_patterns = design.get("anti_patterns") or []
        if len(anti_patterns) < 3:
            violations.append(f"anti_patterns has {len(anti_patterns)} entries; need ≥ 3")
        beat_map = design.get("beat_visual_mapping") or []
        if len(beat_map) < 1:
            violations.append("beat_visual_mapping is empty; need ≥ 1 entry")

        edl_beats = _edl_beats(state)
        if edl_beats and beat_map:
            mapped = {entry.get("beat") for entry in beat_map if isinstance(entry, dict)}
            missing = [b for b in edl_beats if b not in mapped]
            if missing:
                violations.append(
                    f"beat_visual_mapping missing EDL beats: {missing} "
                    f"(all EDL beats: {edl_beats})"
                )

        named = _named_preset(state)
        chosen = (design.get("style_name") or "").strip()
        if named and chosen:
            if named.lower() not in chosen.lower() and chosen.lower() not in named.lower():
                violations.append(
                    f"operator named preset {named!r} but design.style_name={chosen!r}; "
                    "either honor the named preset or document why a custom name was chosen"
                )

        return violations


def design_ok_gate_node(state: dict) -> dict:
    return DesignOkGate()(state)
