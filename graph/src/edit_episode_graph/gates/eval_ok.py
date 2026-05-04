"""gate:eval_ok — validates the self-eval report + final.mp4 duration.

Per spec §6.2 / canon §"The process" Step 7:
  - `state.edit.eval.passed == true` (the LLM verdict).
  - No `blocker`-severity issues remain.
  - ffprobe duration of `final.mp4` matches EDL `total_duration_s` within
    `_render_constants.duration_tolerance_ms(n_segments)` (24fps frame-snap
    drift; shared with p3_render_segments).

Iteration cap (3) is enforced by the routing helper, not by the gate
itself — the gate stays pure (state-update only) so Studio always sees
the violation list. Routing reads `gate_results` and decides retry vs
escalate via `interrupt()`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .._render_constants import duration_tolerance_ms
from ._base import Gate


def _probe_duration_s(path: Path) -> float | None:
    if shutil.which("ffprobe") is None or not path.exists():
        return None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        probe = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    raw = (probe.get("format") or {}).get("duration")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


class EvalOkGate(Gate):
    def __init__(self, *, probe: callable = _probe_duration_s) -> None:
        super().__init__(name="gate:eval_ok")
        self._probe = probe

    def checks(self, state: dict) -> list[str]:
        violations: list[str] = []
        edit = state.get("edit") or {}
        eval_report = edit.get("eval") or {}
        render = edit.get("render") or {}
        edl = edit.get("edl") or {}

        if eval_report.get("skipped"):
            return [f"eval skipped upstream: {eval_report.get('skip_reason')}"]
        if "raw_text" in eval_report and "issues" not in eval_report:
            return ["eval unparseable (raw_text only — schema validation failed upstream)"]

        if not eval_report.get("passed", False):
            violations.append("self-eval reported passed=false")
        blockers = [
            i for i in (eval_report.get("issues") or [])
            if isinstance(i, dict) and i.get("severity") == "blocker"
        ]
        if blockers:
            violations.append(
                f"{len(blockers)} blocker-severity issue(s): "
                + "; ".join(f"{b.get('kind')}@{b.get('location')}" for b in blockers[:3])
                + ("…" if len(blockers) > 3 else "")
            )

        final_mp4 = render.get("final_mp4")
        expected = edl.get("total_duration_s")
        try:
            expected_f = float(expected) if expected is not None else None
        except (TypeError, ValueError):
            expected_f = None
        if not final_mp4:
            violations.append("render.final_mp4 missing in state")
        elif expected_f is None:
            violations.append("edl.total_duration_s missing — cannot verify duration")
        else:
            duration = self._probe(Path(final_mp4))
            if duration is None:
                violations.append(f"ffprobe failed on {final_mp4}")
            else:
                delta_ms = int(round(abs(duration - expected_f) * 1000))
                n_segments = len(edl.get("ranges") or [])
                tolerance_ms = duration_tolerance_ms(n_segments)
                if delta_ms > tolerance_ms:
                    violations.append(
                        f"final.mp4 duration {duration:.3f}s deviates from EDL "
                        f"total_duration_s {expected_f:.3f}s by {delta_ms}ms "
                        f"(tolerance {tolerance_ms}ms for {n_segments} segments)"
                    )

        return violations


def eval_ok_gate_node(state: dict) -> dict:
    return EvalOkGate()(state)
