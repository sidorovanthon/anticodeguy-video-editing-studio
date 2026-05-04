"""HOM-104 real-CLI smoke: drive p3_self_eval + gate:eval_ok against a
synthetic ffmpeg-testsrc episode rendered by canon render.py.

Two cases:
  PASS — clean EDL whose declared total_duration_s matches the rendered
         output; gate:eval_ok passes (assuming the LLM also reports
         passed=true). Routes to halt_llm_boundary.
  FAIL — stub the LLM step to report a blocker-severity issue every time;
         gate:eval_ok records failure, routing loops back to render, and
         after the 3rd iteration escalates to eval_failure_interrupt.
         Note: we don't drift `total_duration_s` for the fail case because
         p3_render_segments has its own ±100ms duration gate that would
         reject the EDL upfront — instead the LLM-side blocker is what
         keeps the gate failing, which mirrors the realistic loop body.

The LLM-side wiring is exercised separately via Studio runs against real
episodes (per spec DoD); the smoke target here is the gate + routing
loop, so the self-eval LLM step is stubbed deterministically.

Run:  PYTHONPATH=graph/src python graph/smoke_hom104.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "graph" / "src"))

from edit_episode_graph.gates.eval_ok import eval_ok_gate_node  # noqa: E402
from edit_episode_graph.nodes import _routing  # noqa: E402
from edit_episode_graph.nodes.p3_render_segments import p3_render_segments_node  # noqa: E402


def _make_testsrc(out_path: Path, duration: int = 10) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=24",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _setup_episode(workdir: Path, total_override: float | None = None) -> dict:
    episode = workdir / "ep"
    edit = episode / "edit"
    edit.mkdir(parents=True)
    raw = episode / "raw.mp4"
    _make_testsrc(raw, duration=10)

    ranges = [
        {"source": "raw", "start": 0.5, "end": 2.0, "beat": "A", "quote": "x", "reason": "smoke"},
        {"source": "raw", "start": 3.0, "end": 5.5, "beat": "B", "quote": "x", "reason": "smoke"},
    ]
    real_total = sum(r["end"] - r["start"] for r in ranges)
    declared_total = total_override if total_override is not None else real_total
    edl = {
        "version": 1,
        "sources": {"raw": str(raw)},
        "ranges": ranges,
        "grade": "neutral_punch",
        "overlays": [],
        "total_duration_s": declared_total,
    }
    (edit / "edl.json").write_text(json.dumps(edl, indent=2), encoding="utf-8")
    return {
        "episode_dir": str(episode),
        "edit": {"edl": dict(edl)},
    }


def _step_render(state: dict) -> dict:
    out = p3_render_segments_node(state)
    if "errors" in out:
        raise RuntimeError(f"render failed: {out['errors']}")
    state.setdefault("edit", {}).update(out["edit"])
    return state


def _stub_self_eval_step(state: dict, *, fail_with_blocker: bool = False) -> dict:
    if fail_with_blocker:
        state.setdefault("edit", {})["eval"] = {
            "passed": False,
            "issues": [{
                "kind": "audio_pop",
                "location": "cut[0]@1.5s",
                "severity": "blocker",
                "note": "synthetic blocker for smoke",
            }],
            "final_mp4_path": state["edit"]["render"]["final_mp4"],
        }
    else:
        state.setdefault("edit", {})["eval"] = {
            "passed": True,
            "issues": [],
            "final_mp4_path": state["edit"]["render"]["final_mp4"],
        }
    return state


def _run_gate(state: dict) -> dict:
    out = eval_ok_gate_node(state)
    state.setdefault("gate_results", [])
    state["gate_results"].extend(out["gate_results"])
    return out["gate_results"][-1]


def smoke_pass(workdir: Path) -> int:
    print("\n[PASS-CASE] declared duration matches rendered duration")
    state = _setup_episode(workdir / "pass")
    state = _step_render(state)
    state = _stub_self_eval_step(state)
    decision = _routing.route_after_self_eval(state)
    assert decision == "gate_eval_ok", decision
    record = _run_gate(state)
    print(f"  gate record: passed={record['passed']} iter={record['iteration']} "
          f"violations={record['violations']}")
    if not record["passed"]:
        print("SMOKE FAIL: pass-case gate did not pass", file=sys.stderr)
        return 1
    if _routing.route_after_eval_ok(state) != "halt_llm_boundary":
        print("SMOKE FAIL: pass-case did not route to halt", file=sys.stderr)
        return 1
    print("  -> halt_llm_boundary (OK)")
    return 0


def smoke_fail_loop(workdir: Path) -> int:
    print("\n[FAIL-CASE] LLM stub emits blocker; expect 3 iters -> escalate")
    state = _setup_episode(workdir / "fail")
    state = _step_render(state)

    for i in range(1, 4):
        state = _stub_self_eval_step(state, fail_with_blocker=True)
        record = _run_gate(state)
        decision = _routing.route_after_eval_ok(state)
        preview = record["violations"][0] if record["violations"] else ""
        print(f"  iter {i}: passed={record['passed']} decision={decision} "
              f"violation_preview={preview!r}")
        if record["passed"]:
            print(f"SMOKE FAIL: fail-case unexpectedly passed at iter {i}", file=sys.stderr)
            return 1
        if i < 3 and decision != "p3_render_segments":
            print(f"SMOKE FAIL: iter {i} should re-render, got {decision}", file=sys.stderr)
            return 1
        if i == 3 and decision != "eval_failure_interrupt":
            print(f"SMOKE FAIL: iter 3 should escalate, got {decision}", file=sys.stderr)
            return 1
        if i < 3:
            state = _step_render(state)
    print("  -> eval_failure_interrupt (OK)")
    return 0


def main() -> int:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg/ffprobe not on PATH", file=sys.stderr)
        return 2
    workdir = Path(tempfile.mkdtemp(prefix="hom104-smoke-"))
    print(f"smoke workdir: {workdir}")
    try:
        rc = smoke_pass(workdir)
        if rc:
            return rc
        rc = smoke_fail_loop(workdir)
        if rc:
            return rc
        print("\nSMOKE OK: pass-case + fail-loop + escalate")
        return 0
    finally:
        if os.environ.get("HOM104_SMOKE_KEEP", "1") != "1":
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
