"""HOM-125 smoke: real-subprocess integration of studio_launch + gate:static_guard.

Three layers of verification, in cost order:

  1. Topology check (free, deterministic) — studio_launch + gate_static_guard
     present in the compiled graph; expected edges wired.

  2. Real subprocess invocation of studio_launch on a fresh tmp HF project —
     verifies Popen shape (background, log redirection, PID file persistence,
     bundled CLI vs npx fallback) actually works end-to-end. Uses a stub
     `hyperframes` shim that emits one log line and sleeps, so we don't need
     a full HF runtime to prove the orchestrator-side wiring.

  3. Gate evaluation against synthetic logs — clean log passes; canon
     Video/Audio shape passes with annotation; arbitrary StaticGuard fails.

Run from the worktree's graph directory:
    PYTHONPATH=$(pwd -W)/src .venv/Scripts/python smoke_hom125.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from edit_episode_graph.gates.static_guard import static_guard_gate_node
from edit_episode_graph.graph import build_graph_uncompiled
from edit_episode_graph.nodes import studio_launch as sl


def case_topology() -> int:
    print("\n=== Case 1: topology check ===")
    g = build_graph_uncompiled().compile().get_graph()
    nodes = set(g.nodes.keys())
    edges = {(e.source, e.target) for e in g.edges}
    missing_nodes = {"studio_launch", "gate_static_guard"} - nodes
    if missing_nodes:
        print(f"SMOKE FAIL: missing nodes: {sorted(missing_nodes)}", file=sys.stderr)
        return 1
    expected_edges = {
        ("p4_assemble_index", "studio_launch"),
        ("studio_launch", "gate_static_guard"),
        ("gate_static_guard", "halt_llm_boundary"),
    }
    missing_edges = expected_edges - edges
    if missing_edges:
        print(f"SMOKE FAIL: missing edges: {sorted(missing_edges)}", file=sys.stderr)
        return 1
    print("  ✓ studio_launch + gate_static_guard wired into Phase 4 chain")
    return 0


def _make_stub_cli(tmp_dir: Path) -> Path:
    """Create a tiny shell script that mimics `hyperframes preview --port N`.

    Emits one line (so the gate sees real log content) and sleeps so the
    process is observably alive. Used as the bundled CLI to bypass `npx`
    entirely for a deterministic smoke.
    """
    if os.name == "nt":
        stub = tmp_dir / "fake-hf.bat"
        stub.write_text(
            "@echo off\r\n"
            "echo fake-preview server ready %1 %2 %3\r\n"
            "ping -n 4 127.0.0.1 > nul\r\n",
            encoding="utf-8",
        )
    else:
        stub = tmp_dir / "fake-hf.sh"
        stub.write_text(
            "#!/bin/sh\n"
            "echo fake-preview server ready $@\n"
            "sleep 3\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
    return stub


def case_real_subprocess() -> int:
    print("\n=== Case 2: real-subprocess studio_launch with stub CLI ===")
    tmp_root = Path(tempfile.mkdtemp(prefix="hom125-smoke-"))
    try:
        hf_dir = tmp_root / "hyperframes"
        hf_dir.mkdir()
        (hf_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        stub = _make_stub_cli(tmp_root)
        # Patch _bundled_hf_cli so the node uses our stub instead of looking
        # for node_modules/.bin/hyperframes (we don't have one on the smoke
        # tmpdir, and we don't want to depend on a real `npx` shell-out).
        original_resolver = sl._bundled_hf_cli
        sl._bundled_hf_cli = lambda d: stub  # type: ignore[assignment]
        try:
            state = {"compose": {"hyperframes_dir": str(hf_dir), "preview_port": 3099}}
            update = sl.studio_launch_node(state)
            if update.get("errors"):
                print(f"SMOKE FAIL: studio_launch errored: {update['errors']}",
                      file=sys.stderr)
                return 1
            compose = update["compose"]
            pid = compose["studio_pid"]
            log_path = Path(compose["preview_log_path"])
            print(f"  pid={pid} port={compose['preview_port']} log={log_path}")
            # Give the stub a moment to write its line.
            time.sleep(1.0)
            log_text = log_path.read_text(encoding="utf-8")
            if "fake-preview server ready" not in log_text:
                print(f"SMOKE FAIL: log empty/unexpected: {log_text!r}", file=sys.stderr)
                return 1
            print("  ✓ subprocess spawned, log captured")

            # Idempotent re-run: stub still alive (3s sleep) → reuse.
            update2 = sl.studio_launch_node(state)
            if not update2["compose"].get("studio_reused"):
                print("SMOKE FAIL: expected studio_reused=True on re-run", file=sys.stderr)
                return 1
            if update2["compose"]["studio_pid"] != pid:
                print(
                    f"SMOKE FAIL: re-run produced different PID "
                    f"({update2['compose']['studio_pid']} vs {pid})",
                    file=sys.stderr,
                )
                return 1
            print("  ✓ re-run is idempotent (reused live PID)")

            # Wait for the stub to exit, then re-run — should respawn.
            for _ in range(40):
                if not sl._is_pid_alive(pid):
                    break
                time.sleep(0.25)
            update3 = sl.studio_launch_node(state)
            if update3["compose"].get("studio_reused"):
                print("SMOKE FAIL: expected respawn after stub exit", file=sys.stderr)
                return 1
            print("  ✓ respawn on stale PID")
        finally:
            sl._bundled_hf_cli = original_resolver  # type: ignore[assignment]
        return 0
    finally:
        # Best-effort cleanup; a still-running stub holds the dir on Windows.
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except OSError:
            pass


def case_gate_evaluates() -> int:
    print("\n=== Case 3: gate:static_guard evaluation ===")
    tmp_root = Path(tempfile.mkdtemp(prefix="hom125-gate-"))
    try:
        log = tmp_root / "preview.log"

        log.write_text("ready\n", encoding="utf-8")
        rc = static_guard_gate_node(
            {"compose": {"preview_log_path": str(log)}}, sleep_fn=lambda _s: None
        )["gate_results"][0]
        if not rc["passed"]:
            print(f"SMOKE FAIL: clean log should pass: {rc}", file=sys.stderr)
            return 1
        print("  ✓ clean log passes")

        log.write_text(
            "[StaticGuard] missing data-hf-anchor on .scene\n", encoding="utf-8"
        )
        rc = static_guard_gate_node(
            {"compose": {"preview_log_path": str(log)}}, sleep_fn=lambda _s: None
        )["gate_results"][0]
        if rc["passed"]:
            print(f"SMOKE FAIL: real StaticGuard should fail: {rc}", file=sys.stderr)
            return 1
        print(f"  ✓ real StaticGuard fails ({len(rc['violations'])} violation(s))")

        log.write_text(
            "[StaticGuard] <video> element missing data-has-audio attribute\n",
            encoding="utf-8",
        )
        rc = static_guard_gate_node(
            {"compose": {"preview_log_path": str(log)}}, sleep_fn=lambda _s: None
        )["gate_results"][0]
        if not rc["passed"] or not rc.get("canon_video_audio_artifact"):
            print(f"SMOKE FAIL: canon Video/Audio should pass with artifact: {rc}",
                  file=sys.stderr)
            return 1
        print("  ✓ canon Video/Audio shape annotated as artifact")
        return 0
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def main() -> int:
    for fn in (case_topology, case_real_subprocess, case_gate_evaluates):
        rc = fn()
        if rc:
            return rc
    print("\nSMOKE OK: studio_launch + gate:static_guard wired and behave correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
