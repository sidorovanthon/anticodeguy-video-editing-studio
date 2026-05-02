"""Headless smoke test for v0 DoD §9.8 cases 2, 3, 4, 5, 6.

Case 1 (`langgraph dev` starts + Studio opens) needs a live process and is
exercised separately.

Mutates inbox/ and episodes/. Idempotent across re-runs except for case 2
which consumes the inbox video. Run from repo root with:
    .venv\\Scripts\\python.exe smoke_test_v0.py
"""

from __future__ import annotations

import json
from pathlib import Path

from edit_episode_graph.nodes.pickup import pickup_node
from scripts.pickup import SCRIPT_EXTS, SUPPORTED_EXTS

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX = REPO_ROOT / "inbox"
EPISODES = REPO_ROOT / "episodes"


def _snapshot_inbox() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in INBOX.iterdir() if p.is_file()}


def _restore_inbox(snapshot: dict[str, bytes]) -> None:
    for p in list(INBOX.iterdir()):
        if p.is_file() and p.name not in snapshot:
            p.unlink()
    for name, data in snapshot.items():
        target = INBOX / name
        if not target.exists():
            target.write_bytes(data)


def _print_case(n: int, label: str, result: dict) -> None:
    print(f"\n=== Case {n}: {label} ===")
    print(json.dumps(result, indent=2, default=str))


def main() -> int:
    INBOX.mkdir(exist_ok=True)
    EPISODES.mkdir(exist_ok=True)
    snapshot = _snapshot_inbox()
    print(f"inbox snapshot: {list(snapshot)} (sizes: {[len(v) for v in snapshot.values()]})")

    # Fail fast: case 2 needs a paired video + script (HOM-85: pickup now
    # requires a script for slug derivation; video-only inbox errors out).
    has_video = any(name.lower().endswith(SUPPORTED_EXTS) for name in snapshot)
    has_script = any(name.lower().endswith(SCRIPT_EXTS) for name in snapshot)
    if not (has_video and has_script):
        print(
            "\nFATAL: inbox/ must contain a paired video + script for case 2. "
            "Drop e.g. raw.mp4 + script.txt into inbox/ (or restore from a "
            "previous run) and retry."
        )
        return 2

    failures: list[str] = []

    # --- Case 3: empty inbox + no slug → idle ---
    for p in list(INBOX.iterdir()):
        if p.is_file():
            p.unlink()
    try:
        r3 = pickup_node({})
        _print_case(3, "empty inbox → idle", r3)
        if not r3.get("pickup", {}).get("idle"):
            failures.append("case 3: pickup.idle != true")
    finally:
        _restore_inbox(snapshot)

    # --- Case 2: real pickup → episodes/<slug>/raw.<ext> ---
    # (Run before case 4 since case 4 needs the produced slug.)
    r2 = pickup_node({})
    _print_case(2, "real pickup", r2)
    slug = r2.get("slug")
    ep_dir = Path(r2["episode_dir"]) if r2.get("episode_dir") else None
    if not slug or not ep_dir:
        failures.append("case 2: missing slug/episode_dir in result")
    elif r2.get("pickup", {}).get("idle"):
        failures.append("case 2: pickup.idle should be false on real pickup")
    elif not any(ep_dir.glob("raw.*")):
        failures.append(f"case 2: no raw.* under {ep_dir}")
    else:
        print(f"  raw.* present: {[p.name for p in ep_dir.glob('raw.*')]}")

    # --- Case 4: re-run with produced slug → resumed, no duplication ---
    if slug and ep_dir:
        r4 = pickup_node({"slug": slug})
        _print_case(4, "re-run with same slug → resumed", r4)
        if not r4.get("pickup", {}).get("resumed"):
            failures.append("case 4: pickup.resumed != true")
        raws = list(ep_dir.glob("raw.*"))
        if len(raws) != 1:
            failures.append(f"case 4: expected 1 raw.*, found {len(raws)}: {[p.name for p in raws]}")
    else:
        failures.append("case 4: skipped (case 2 produced no slug)")

    # --- Case 5: ambiguous resume (two raw.* in ep dir) → errors[] ---
    if slug and ep_dir:
        decoy = ep_dir / "raw.mov"
        decoy.write_bytes(b"\x00" * 1024)
        try:
            r5 = pickup_node({"slug": slug})
            _print_case(5, "ambiguous resume (two raw.*) → error", r5)
            if not r5.get("errors"):
                failures.append("case 5: errors[] not populated")
            elif "ambiguous" not in r5["errors"][0]["message"].lower() and "multiple" not in r5["errors"][0]["message"].lower():
                failures.append(f"case 5: error message unexpected: {r5['errors'][0]['message']!r}")
        finally:
            decoy.unlink(missing_ok=True)
    else:
        failures.append("case 5: skipped (no slug from case 2)")

    # --- Case 6: checkpointer integration ---
    # Spec §9.8 case 6 originally said "SQLite at graph/.langgraph_api/
    # checkpoints.sqlite" — wrong. langgraph-api supplies its own checkpointer
    # and rejects user-bound ones, so `build_graph()` returns a saver-free
    # graph. Production callers that need persistence outside `langgraph dev`
    # use `build_graph_uncompiled()` + their own checkpointer; this case
    # exercises that exact path against the same topology.
    print("\n=== Case 6: build_graph_uncompiled() + InMemorySaver ===")
    try:
        from langgraph.checkpoint.memory import InMemorySaver

        from edit_episode_graph.graph import build_graph_uncompiled

        compiled = build_graph_uncompiled().compile(checkpointer=InMemorySaver())
        cfg = {"configurable": {"thread_id": "smoke-test-case-6"}}
        for p in list(INBOX.iterdir()):
            if p.is_file():
                p.unlink()
        try:
            r6 = compiled.invoke({}, config=cfg)
        finally:
            _restore_inbox(snapshot)
        print(json.dumps({k: v for k, v in r6.items() if k != "errors"}, indent=2, default=str))
        snapshot_state = compiled.get_state(cfg)
        if snapshot_state is None or snapshot_state.values is None:
            failures.append("case 6: get_state returned None — checkpointer not wired")
        else:
            print(f"  checkpoint persisted thread state with keys: {list(snapshot_state.values.keys())}")
    except Exception as exc:
        failures.append(f"case 6: failed: {exc!r}")

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL HEADLESS CASES PASSED (2, 3, 4, 5, 6)")
    print("Case 1 (`langgraph dev` boots + Studio UI opens) — manual verification required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
