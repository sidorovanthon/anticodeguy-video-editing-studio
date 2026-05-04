"""HOM-119 smoke: real-CLI invocation of p4_prompt_expansion.

Per CLAUDE.md graph DoD: smoke runs through the cheapest available model
(Haiku 4.5) to verify subprocess shape, stdout parsing, schema extraction,
and that the dispatched sub-agent actually writes
`.hyperframes/expanded-prompt.md` with the six canonical sections defined
in `references/prompt-expansion.md`. Cost is negligible (~$0.001).

Production runs use tier=smart (Opus 4.7 — see config.yaml override and
memory `feedback_creative_nodes_flagship_tier`); the smoke pins Haiku
locally via per-run model_override since cheap-model creative quality is
out of scope here — only the integration is.

Skip with SMOKE_SKIP=1.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom119.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.nodes.p4_prompt_expansion import _build_node, _render_ctx

REPO_ROOT = Path(__file__).resolve().parent.parent
SLUG = "smoke-hom119-prompt-expansion"
EPISODE = REPO_ROOT / "episodes" / SLUG

# Six canonical headings from references/prompt-expansion.md §"What to generate".
# Each heading is matched as a substring (case-insensitive) on a markdown
# heading line — we don't lock the exact heading text since the canon
# describes the section purpose, not a verbatim title.
# Canon `references/prompt-expansion.md` §"What to generate" calls for a
# leading "Title + style block" — in practice this is the document's H1
# (the production title) plus a style frontmatter that cites design.md
# tokens. We accept ANY top-level H1 followed within the first 1500 chars
# by a hex/font reference as evidence the section exists. The other five
# sections have explicit canonical names and are matched as headings.
CANONICAL_SECTIONS = [
    ("rhythm",     r"(?im)^#{1,6}.*\brhythm\b"),
    ("global",     r"(?im)^#{1,6}.*\bglobal\b"),
    ("scenes",     r"(?im)^#{1,6}.*\b(scene|beat|per-scene)\b"),
    ("motifs",     r"(?im)^#{1,6}.*\bmotif"),
    ("negative",   r"(?im)^#{1,6}.*\bnegative\b"),
]


def _has_title_style_block(text: str) -> bool:
    head = text[:1500]
    has_h1 = bool(re.search(r"(?m)^# \S", head))
    cites_design = bool(re.search(r"#[0-9a-fA-F]{3,8}\b", head)) or bool(
        re.search(r"(?i)\b(helvetica|inter|font[- ]family)\b", head)
    )
    return has_h1 and cites_design

# Minimal DESIGN.md fixture — the expansion must read it and cite its tokens.
DESIGN_MD = """\
---
style_name: Swiss Pulse
palette:
  background: "#0a0a0a"
  foreground: "#f0f0f0"
  accent:     "#0066FF"
typography:
  headline: { family: "Helvetica Neue", weight: 700 }
  body:     { family: "Inter",          weight: 400 }
mood: editorial / analytical / restrained
---

# Overview
Editorial restraint, grid-locked stats, no decoratives for decoration's sake.

# Colors
Background `#0a0a0a`, foreground `#f0f0f0`, accent `#0066FF`.

# Typography
Helvetica Neue 700 for headlines (5rem), Inter 400 for body (1rem).

# Beat Visual Mapping
- HOOK: tight typographic close-up; accent at full saturation.
- PROBLEM: stat at 7rem dominates the frame.
- PAYOFF: wide reveal with hairline rules; staggered entrance.
"""


def _state(design_md_path: Path) -> dict:
    return {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "transcripts": {"final_json_path": str(EPISODE / "edit" / "transcripts" / "final.json")},
        "compose": {
            "design_md_path": str(design_md_path),
            "style_request": "Editorial calm with Stripe-press energy; analytical tone, restrained motion.",
        },
        "edit": {
            "strategy": {
                "shape": "Hook on the licensing surprise, problem framed in two beats, payoff with a stat.",
                "takes": ["[003.76-010.86] hook", "[013.78-024.24] problem", "[032.00-040.50] payoff"],
                "grade": "neutral",
                "pacing": "tight",
                "length_estimate_s": 22.0,
            },
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 3.95, "end": 10.85,
                     "beat": "HOOK",    "quote": "desktop software licensing", "reason": "x"},
                    {"source": "raw", "start": 13.95, "end": 24.20,
                     "beat": "PROBLEM", "quote": "it turns out is", "reason": "x"},
                    {"source": "raw", "start": 32.05, "end": 40.45,
                     "beat": "PAYOFF",  "quote": "...", "reason": "x"},
                ],
            },
        },
    }


def main() -> int:
    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE SKIP: SMOKE_SKIP=1")
        return 0

    EPISODE.mkdir(parents=True, exist_ok=True)
    hf_dir = EPISODE / "hyperframes"
    hf_dir.mkdir(parents=True, exist_ok=True)
    design_md = hf_dir / "DESIGN.md"
    design_md.write_text(DESIGN_MD, encoding="utf-8")
    expanded_path = hf_dir / ".hyperframes" / "expanded-prompt.md"
    if expanded_path.exists():
        expanded_path.unlink()

    state = _state(design_md)
    backends = [ClaudeCodeBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    router = BackendRouter(backends, sems)

    print("\n=== Case 1: real-CLI Haiku invocation of p4_prompt_expansion ===")
    node = _build_node()
    update = node._invoke_with(
        router, state,
        render_ctx={
            "slug": SLUG, "episode_dir": str(EPISODE),
            **_render_ctx(state),
        },
        timeout_s=300,
        model_override="claude-haiku-4-5-20251001",
    )
    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        wall = r.get("wall_time_s")
        wall_s = f"{wall:.1f}" if isinstance(wall, (int, float)) else "n/a"
        print(f"  - model={r.get('model')} success={r.get('success')} "
              f"wall_s={wall_s} tokens_in={r.get('tokens_in')} "
              f"tokens_out={r.get('tokens_out')} reason={r.get('reason')}")

    expansion = (update.get("compose") or {}).get("expansion") or {}
    if "raw_text" in expansion and "expanded_prompt_path" not in expansion:
        print(f"SMOKE FAIL: schema extraction failed; raw_text head: "
              f"{(expansion.get('raw_text') or '')[:300]!r}", file=sys.stderr)
        return 1
    if not expansion.get("expanded_prompt_path"):
        print(f"SMOKE FAIL: no ExpandedPrompt in update: {update!r}", file=sys.stderr)
        return 1

    out_path = Path(expansion["expanded_prompt_path"])
    if not out_path.is_file():
        print(f"SMOKE FAIL: expanded-prompt.md not on disk at {out_path}", file=sys.stderr)
        return 1
    size = out_path.stat().st_size
    text = out_path.read_text(encoding="utf-8")
    print(f"  ✓ expanded-prompt.md on disk: {size}B at {out_path}")

    print("\n=== Case 2: six canonical sections present ===")
    missing: list[str] = []
    if _has_title_style_block(text):
        print("  ✓ title_style  (H1 + design.md token citation in opening block)")
    else:
        missing.append("title_style")
        print("  ✗ title_style  (no H1 + design-token citation in first 1500 chars)")
    for name, pattern in CANONICAL_SECTIONS:
        if re.search(pattern, text):
            print(f"  ✓ {name}")
        else:
            missing.append(name)
            print(f"  ✗ {name}  (no heading matched /{pattern}/)")
    if missing:
        print(
            f"SMOKE FAIL: missing canonical sections: {missing}; "
            f"see {out_path} for the produced expansion",
            file=sys.stderr,
        )
        return 1

    print("\nSMOKE OK: real Haiku invocation + expanded-prompt.md written + 6 canonical sections present")
    head = text[:800]
    print("\nOutput preview (first 800 chars):\n")
    print(head)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
