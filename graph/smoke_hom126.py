"""HOM-126 smoke: real-CLI Haiku invocation of p4_persist_session.

Three layers (cost order):

  1. Topology check (free, deterministic) — p4_persist_session present in the
     compiled graph; assemble→persist→studio edges wired.

  2. Real-CLI Haiku invocation of p4_persist_session against a tmp episode.
     The sub-agent reads canon (~/.claude/skills/video-use/SKILL.md §Memory),
     scans an existing project.md (with a Phase 3 Session 1 block already
     present), and appends a Phase 4 Session 2 block. We assert the file
     grew, the new heading exists, the prior block is intact, and the
     session number incremented.

  3. Idempotent re-run — invoke the node a second time on the just-modified
     file. The agent should scan, see Session 2, and write Session 3 (NOT
     overwrite Session 2). Asserts monotonic-by-N: re-runs add blocks, never
     replace prior ones.

Cost: ~2 Haiku calls @ ~$0.001 each.

Run from the worktree's graph directory:
    PYTHONPATH=$(pwd -W)/src .venv/Scripts/python smoke_hom126.py
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.backends.codex import CodexBackend
from edit_episode_graph.graph import build_graph_uncompiled
from edit_episode_graph.nodes.p4_persist_session import _build_node, _render_ctx

HAIKU_MODEL = "claude-haiku-4-5-20251001"

PRIOR_PROJECT_MD = """\
# demo-episode

Phase 3 edit notes go here.

## Session 1 — 2026-05-04

- Strategy: hook-up
- Decisions: trimmed slips, neutral grade
- Reasoning log: pre-scan flagged 2 slips, both inside takes
- Outstanding: none
"""

SESSION_HEADING_RE = re.compile(r"^## Session (\d+) — (\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _router() -> BackendRouter:
    backends = [ClaudeCodeBackend(), CodexBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    return BackendRouter(backends, sems)


def _seed_episode(root: Path) -> Path:
    edit = root / "edit"
    hf = root / "hyperframes"
    (hf / ".hyperframes").mkdir(parents=True, exist_ok=True)
    edit.mkdir(parents=True, exist_ok=True)
    (edit / "project.md").write_text(PRIOR_PROJECT_MD, encoding="utf-8")
    (hf / "DESIGN.md").write_text("# Design\n\nPalette: noir\n", encoding="utf-8")
    (hf / ".hyperframes" / "expanded-prompt.md").write_text(
        "# Expanded prompt\n\nA two-beat composition.\n", encoding="utf-8"
    )
    (hf / ".hyperframes" / "captions.html").write_text(
        '<div data-hf-captions></div>\n', encoding="utf-8"
    )
    (hf / "index.html").write_text("<html><body></body></html>\n", encoding="utf-8")
    return root


def _state(root: Path) -> dict:
    hf = root / "hyperframes"
    return {
        "slug": "smoke-hom126",
        "episode_dir": str(root),
        "compose": {
            "design": {"design_md_path": str(hf / "DESIGN.md")},
            "expansion": {"expanded_prompt_path": str(hf / ".hyperframes" / "expanded-prompt.md")},
            "plan": {
                "beats": [
                    {"id": "b1", "title": "Hook", "duration_s": 3.0},
                    {"id": "b2", "title": "Reveal", "duration_s": 4.5},
                ],
                "total_duration_s": 7.5,
            },
            "captions_block_path": str(hf / ".hyperframes" / "captions.html"),
            "assemble": {
                "assembled_at": str(hf / "index.html"),
                "index_html_path": str(hf / "index.html"),
                "beat_names": ["b1", "b2"],
            },
            "beats": [
                {"beat_id": "b1", "scene_path": "compositions/b1.html", "status": "rendered"},
                {"beat_id": "b2", "scene_path": "compositions/b2.html", "status": "rendered"},
            ],
        },
        "gate_results": [
            {"gate": "gate:design_ok", "passed": True},
            {"gate": "gate:plan_ok", "passed": True},
        ],
    }


def case_topology() -> int:
    print("\n=== Case 1: topology check ===")
    g = build_graph_uncompiled().compile().get_graph()
    nodes = set(g.nodes.keys())
    edges = {(e.source, e.target) for e in g.edges}
    if "p4_persist_session" not in nodes:
        print("SMOKE FAIL: p4_persist_session missing from compiled graph", file=sys.stderr)
        return 1
    expected = {
        ("p4_assemble_index", "p4_persist_session"),
        ("p4_persist_session", "studio_launch"),
    }
    missing = expected - edges
    if missing:
        print(f"SMOKE FAIL: missing edges: {sorted(missing)}", file=sys.stderr)
        return 1
    print("  ✓ p4_persist_session wired between p4_assemble_index and studio_launch")
    return 0


def _invoke(state: dict) -> dict:
    node = _build_node()
    return node._invoke_with(
        _router(), state,
        render_ctx={"slug": state["slug"], "episode_dir": state["episode_dir"], **_render_ctx(state)},
        model_override=HAIKU_MODEL,
        timeout_s=180,
    )


def case_real_haiku_first_append(root: Path) -> int:
    print("\n=== Case 2: Haiku appends Phase 4 Session block ===")
    state = _state(root)
    project_md = Path(root) / "edit" / "project.md"
    before = project_md.read_text(encoding="utf-8")
    headings_before = SESSION_HEADING_RE.findall(before)
    print(f"  before: {len(headings_before)} Session block(s) — {headings_before}")

    update = _invoke(state)
    runs = update.get("llm_runs") or []
    for r in runs:
        wall = r.get("wall_time_s")
        wall_s = f"{wall:.1f}" if isinstance(wall, (int, float)) else "n/a"
        print(f"  - model={r.get('model')} success={r.get('success')} "
              f"wall_s={wall_s} reason={r.get('reason')}")
    persist = (update.get("compose") or {}).get("persist") or {}
    if "raw_text" in persist or persist.get("skipped"):
        print(f"SMOKE FAIL: persist did not produce structured output: {persist!r}",
              file=sys.stderr)
        return 1
    if persist.get("session_n") not in (2,):
        print(
            f"SMOKE FAIL: expected session_n=2 (after Session 1 in seed), got {persist!r}",
            file=sys.stderr,
        )
        return 1

    after = project_md.read_text(encoding="utf-8")
    headings_after = SESSION_HEADING_RE.findall(after)
    print(f"  after: {len(headings_after)} Session block(s) — {headings_after}")
    if not after.startswith(before):
        print("SMOKE FAIL: prior project.md content was modified — append not preserving", file=sys.stderr)
        return 1
    if len(headings_after) != len(headings_before) + 1:
        print(
            f"SMOKE FAIL: expected one new Session heading, got delta "
            f"{len(headings_after) - len(headings_before)}",
            file=sys.stderr,
        )
        return 1
    print(f"  ✓ Phase 4 Session {persist['session_n']} appended; prior content intact")
    return 0


def case_idempotent_re_run(root: Path) -> int:
    print("\n=== Case 3: re-run appends another block (monotonic N) ===")
    state = _state(root)
    project_md = Path(root) / "edit" / "project.md"
    before = project_md.read_text(encoding="utf-8")
    headings_before = SESSION_HEADING_RE.findall(before)

    update = _invoke(state)
    persist = (update.get("compose") or {}).get("persist") or {}
    if persist.get("skipped") or "raw_text" in persist:
        print(f"SMOKE FAIL: re-run produced no structured output: {persist!r}", file=sys.stderr)
        return 1
    after = project_md.read_text(encoding="utf-8")
    headings_after = SESSION_HEADING_RE.findall(after)
    print(f"  before: {len(headings_before)} blocks → after: {len(headings_after)} blocks")
    if not after.startswith(before):
        print("SMOKE FAIL: re-run rewrote prior content (must monotonic-append)", file=sys.stderr)
        return 1
    if len(headings_after) != len(headings_before) + 1:
        print(
            f"SMOKE FAIL: re-run did not append a new block "
            f"(headings_after={headings_after}, headings_before={headings_before})",
            file=sys.stderr,
        )
        return 1
    if persist.get("session_n") <= int(headings_before[-1][0]):
        print(
            f"SMOKE FAIL: session_n={persist.get('session_n')} did not increment "
            f"past existing max {headings_before[-1][0]}",
            file=sys.stderr,
        )
        return 1
    print(f"  ✓ re-run added Session {persist['session_n']} (monotonic)")
    return 0


def main() -> int:
    rc = case_topology()
    if rc:
        return rc
    tmp_root = Path(tempfile.mkdtemp(prefix="hom126-smoke-"))
    try:
        _seed_episode(tmp_root)
        rc = case_real_haiku_first_append(tmp_root)
        if rc:
            return rc
        rc = case_idempotent_re_run(tmp_root)
        if rc:
            return rc
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    print("\nSMOKE OK: p4_persist_session wired + Haiku append + idempotent re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
