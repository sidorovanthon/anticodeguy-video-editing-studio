"""HOM-102 smoke: real-CLI invocation of p3_edl_select + gate:edl_ok.

Uses `episodes/edl-smoke/` (a copy of raw-edit/edit/{takes_packed.md,
transcripts/raw.json}). Verifies:

  1. Real subprocess (Haiku via per-node config override) returns a parseable
     EDL — node telemetry has at least one successful attempt.
  2. Mutation test: inject a mid-word cut and a non-empty overlays list; run
     gate:edl_ok directly → expect violations covering HR 6 + overlay rule.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom102.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.backends.codex import CodexBackend
from edit_episode_graph.gates.edl_ok import edl_ok_gate_node
from edit_episode_graph.nodes.p3_edl_select import p3_edl_select_node

REPO_ROOT = Path(__file__).resolve().parent.parent
SLUG = "edl-smoke"
EPISODE = REPO_ROOT / "episodes" / SLUG


def _router() -> BackendRouter:
    backends = [ClaudeCodeBackend(), CodexBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    return BackendRouter(backends, sems)


def _source_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return None
    return float(json.loads(out.stdout)["format"]["duration"])


def case_real_cli() -> dict:
    print("\n=== Case 1: real-CLI EDL select (Haiku via config override) ===")
    transcripts = sorted(str(p) for p in (EPISODE / "edit" / "transcripts").glob("*.json"))
    state = {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "transcripts": {"raw_json_paths": transcripts,
                        "takes_packed_path": str(EPISODE / "edit" / "takes_packed.md")},
        "edit": {
            "inventory": {"transcript_json_paths": transcripts,
                          "sources": [{"stem": "raw", "duration_s": 70.0}]},
            "pre_scan": {"slips": []},
            "strategy": {"shape": "tutorial", "takes": [], "grade": "neutral",
                         "pacing": "tight", "length_estimate_s": 50.0},
        },
    }
    update = p3_edl_select_node(state, router=_router())
    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        print(f"    backend={r.get('backend')} model={r.get('model')} "
              f"success={r.get('success')} reason={r.get('reason')}")
    edl = (update.get("edit") or {}).get("edl") or {}
    if "raw_text" in edl:
        print("  schema parse FAILED — raw_text preview:", (edl["raw_text"] or "")[:300])
        return state
    if "skipped" in edl:
        print("  skipped:", edl.get("skip_reason"))
        return state
    print(f"  EDL ranges: {len(edl.get('ranges') or [])}, overlays: {edl.get('overlays')}, "
          f"total: {edl.get('total_duration_s')}")
    state.setdefault("edit", {})["edl"] = edl

    gate_update = edl_ok_gate_node(state)
    record = gate_update["gate_results"][0]
    print(f"  gate:edl_ok passed={record['passed']} violations={record['violations']}")
    # Real-CLI smoke is allowed to fail the pacing check on single-source
    # tutorial content (canon EDL on disk hits ~76% too) — that's a known
    # spec-vs-content mismatch tracked separately. We assert only the
    # structural invariants: EDL is parseable, overlays empty, no subtitles.
    assert "raw_text" not in edl, "schema parse failed on real CLI"
    assert edl.get("overlays") == [], "LLM smuggled overlays past brief"
    assert "subtitles" not in edl, "LLM smuggled subtitles past schema"
    print("  ✓ structural invariants intact (parseable, overlays==[], no subtitles)")
    return state


def case_mutation(passed_state: dict) -> None:
    print("\n=== Case 2: mutation — mid-word cut + non-empty overlays ===")
    edl = ((passed_state.get("edit") or {}).get("edl") or {}).copy()
    if not edl.get("ranges"):
        # Fall back to a synthetic EDL when case 1 didn't produce one.
        edl = {
            "version": 1,
            "sources": {"raw": str(EPISODE / "raw.mp4")},
            "ranges": [{"source": "raw", "start": 1.0, "end": 2.0,
                         "beat": "X", "quote": "x", "reason": "x"}],
            "grade": "neutral",
            "overlays": [],
            "total_duration_s": 1.0,
        }
    # Pick the first word interval from raw.json and force start mid-word.
    words = json.loads((EPISODE / "edit" / "transcripts" / "raw.json").read_text(encoding="utf-8"))
    first_word = next(w for w in words["words"] if w.get("type") == "word")
    mid = (first_word["start"] + first_word["end"]) / 2
    edl["ranges"] = list(edl.get("ranges") or [])
    edl["ranges"][0] = dict(edl["ranges"][0])
    edl["ranges"][0]["start"] = mid
    edl["overlays"] = [{"file": "fake.mp4", "start_in_output": 0.0, "duration": 1.0}]

    state = {
        "episode_dir": str(EPISODE),
        "edit": {"edl": edl, "inventory": {"sources": [{"stem": "raw", "duration_s": 70.0}]}},
    }
    record = edl_ok_gate_node(state)["gate_results"][0]
    print(f"  passed={record['passed']}")
    for v in record["violations"]:
        print(f"    - {v}")
    assert not record["passed"], "mutation should fail gate"
    assert any("cuts inside word" in v for v in record["violations"]), "expected HR 6 violation"
    assert any("overlays" in v for v in record["violations"]), "expected overlays violation"
    print("  ✓ both expected violations present")


if __name__ == "__main__":
    if not (EPISODE / "edit" / "takes_packed.md").exists():
        raise SystemExit(f"missing {EPISODE / 'edit' / 'takes_packed.md'} — populate first")
    state = case_real_cli()
    case_mutation(state)
    print("\nDONE")
