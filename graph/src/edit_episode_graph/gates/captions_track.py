"""gate:captions_track — verifies the captions layer is present in index.html.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks /
Captions" and `references/captions.md`: a tone-adaptive captions layer
must be inlined into the assembled `index.html` for any episode whose
narration has a transcript. The orchestrator-house contract for the
captions producer (`p4_captions_layer` → inlined by `p4_assemble_index`)
is a `<div id="captions-layer">` block plus a `__captionTimelines`
registration — see `briefs/p4_captions_layer.j2` and
`memory feedback_brief_consider_means_mandatory` (captions are
mandatory, not optional).

Phase 3 emits no captions; Phase 4's `p4_captions_layer` is the only
producer. Absence of the captions layer in the assembled index ⇒ either
the captions node was skipped, or the assemble step dropped its block.
Either way: bug worth surfacing.

## Why we don't grep for `transcript.json`

The HOM-141 ticket text suggested `grep -c transcript.json index.html ≥ 1`
as the check. That's a misread of the implementation: the canonical
producer **inlines** the word-timing data into a GSAP timeline embedded
in `index.html` and does not retain a string reference to the transcript
file. So a literal `transcript.json` grep returns 0 on a correctly
assembled episode (verified against
`episodes/2026-05-05-desktop-software-licensing-it-turns-out-is/`).

The structural marker that is actually authored — `id="captions-layer"`
plus `__captionTimelines["captions"]` — is the contract this gate
verifies instead.
"""

from __future__ import annotations

import re

from ._base import Gate, hyperframes_dir


# Primary marker: the canonical wrapper div emitted by p4_captions_layer.
# Quotes are tolerant (single, double, or none — HTML5 attribute syntax).
_CAPTIONS_LAYER_DIV = re.compile(
    r"""<div\b[^>]*\bid\s*=\s*['"]?captions-layer['"]?""",
    re.IGNORECASE,
)

# Fallback marker: the runtime registration. Caught when the wrapper div
# was renamed but the timeline still binds. Less authoritative than the
# div but still proves the producer ran.
_CAPTION_TIMELINE_REG = re.compile(
    r"""__captionTimelines\s*\[\s*['"]captions['"]\s*\]""",
)


class CaptionsTrackGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:captions_track")

    def checks(self, state: dict) -> list[str]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot read index.html"]
        index_path = hf_dir / "index.html"
        if not index_path.is_file():
            return [f"index.html not on disk at {index_path}"]
        try:
            html = index_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return [f"could not read index.html: {exc}"]

        has_div = bool(_CAPTIONS_LAYER_DIV.search(html))
        has_timeline = bool(_CAPTION_TIMELINE_REG.search(html))
        if has_div or has_timeline:
            return []

        return [
            "index.html missing captions layer — expected `<div id=\"captions-layer\">` "
            "or `window.__captionTimelines[\"captions\"]` registration. "
            "p4_captions_layer is the only canonical producer; absence ⇒ node was "
            "skipped or its block was dropped during assemble."
        ]


def captions_track_gate_node(state: dict) -> dict:
    return CaptionsTrackGate()(state)
