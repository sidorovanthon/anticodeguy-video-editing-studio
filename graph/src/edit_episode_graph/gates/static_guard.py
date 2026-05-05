"""gate:static_guard — scan `preview.log` for HF StaticGuard violations.

Sleeps `STATIC_GUARD_WINDOW_S` (default 5s) after `studio_launch` returns,
then reads `compose.preview_log_path` and looks for either of:

  * `[StaticGuard]` — runtime contract violation flagged by HF preview
  * `Invalid HyperFrame contract` — schema-level rejection

Per HOM-125 / spec §6.2 (gates table). Honors two memories:

  - `feedback_studio_player_empty_state` — "Drop media here" is the
    Studio Player's default UI when no composition is selected, NOT a
    render fail. We only scan the preview-CLI log (which never emits
    that string), not the Studio screenshot — so the empty-state UI
    cannot false-positive this gate by construction.
  - `feedback_hf_video_audio_canon_bug` — HF's canonical "Video and
    Audio" example trips StaticGuard with `data-has-audio` not set;
    when that *specific* shape appears in the log we annotate the
    pass with a `canon_video_audio_artifact` flag so downstream tools
    can apply the `data-has-audio="false"` workaround. The orchestrator
    explicitly chooses NOT to treat unrelated StaticGuard hits as the
    same artifact — those still fail loudly.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_WINDOW_S = 5.0

# Hard markers — presence of either fails the gate (subject to the
# canon-bug triage below).
_STATICGUARD_MARKER = "[StaticGuard]"
_INVALID_CONTRACT_MARKER = "Invalid HyperFrame contract"

# Heuristic for the Video/Audio canon-bug shape. Looking for the StaticGuard
# message that surfaces when the canon example's `<video>` element omits
# `data-has-audio` — the diagnostic mentions both "video" and "audio" /
# "data-has-audio" together. Conservative on purpose: if the regex doesn't
# match exactly this shape, the gate fails loudly rather than masking an
# unrelated StaticGuard hit.
_CANON_VIDEO_AUDIO_RE = re.compile(
    r"\[StaticGuard\][^\n]*\bvideo\b[^\n]*\b(?:audio|data-has-audio)\b",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolved_window_s() -> float:
    raw = os.environ.get("STATIC_GUARD_WINDOW_S")
    if not raw:
        return DEFAULT_WINDOW_S
    try:
        v = float(raw)
    except ValueError:
        return DEFAULT_WINDOW_S
    return v if v >= 0 else DEFAULT_WINDOW_S


@dataclass
class _ScanOutcome:
    violations: list[str]
    extras: dict


def scan_log_text(text: str) -> _ScanOutcome:
    """Pure inspection of preview log content.

    Returns violations + optional extras (canon-bug annotation). Pulled out
    of the gate body so unit tests drive it without disk or sleeps.
    """
    sg_lines = [ln for ln in text.splitlines() if _STATICGUARD_MARKER in ln]
    contract_lines = [ln for ln in text.splitlines() if _INVALID_CONTRACT_MARKER in ln]

    if not sg_lines and not contract_lines:
        return _ScanOutcome(violations=[], extras={})

    # Canon-bug triage: every StaticGuard line matches the Video/Audio
    # shape AND there's no separate "Invalid HyperFrame contract" line.
    if (
        sg_lines
        and not contract_lines
        and all(_CANON_VIDEO_AUDIO_RE.search(ln) for ln in sg_lines)
    ):
        return _ScanOutcome(
            violations=[],
            extras={
                "canon_video_audio_artifact": True,
                "annotation": (
                    "preview.log contains [StaticGuard] hits matching the "
                    "canonical Video/Audio example shape — applying the "
                    "data-has-audio=\"false\" workaround per memory "
                    "feedback_hf_video_audio_canon_bug. Do NOT iterate the "
                    "composition in response."
                ),
                "matched_lines": sg_lines[:5],
            },
        )

    violations: list[str] = []
    for ln in sg_lines[:10]:
        violations.append(f"StaticGuard: {ln.strip()}")
    for ln in contract_lines[:10]:
        violations.append(f"Invalid HyperFrame contract: {ln.strip()}")
    return _ScanOutcome(violations=violations, extras={})


def static_guard_gate_node(state: dict, *, sleep_fn=time.sleep) -> dict:
    """Sleep the scan window, then evaluate `preview.log`.

    `sleep_fn` is parameterised so unit tests can pass a no-op — the gate's
    own time budget is incidental to its decision logic.
    """
    name = "gate:static_guard"
    iteration = sum(
        1 for r in (state.get("gate_results") or []) if r.get("gate") == name
    ) + 1

    def _record(passed: bool, violations: list[str], extras: dict) -> dict:
        record = {
            "gate": name,
            "passed": passed,
            "violations": violations,
            "iteration": iteration,
            "timestamp": _now(),
            **extras,
        }
        update: dict = {"gate_results": [record]}
        if not passed:
            update["notices"] = [
                f"{name}: FAILED ({len(violations)} violation(s)) — see gate_results"
            ]
        elif extras.get("canon_video_audio_artifact"):
            update["notices"] = [
                f"{name}: passed with canon_video_audio_artifact — apply "
                "data-has-audio=\"false\" workaround"
            ]
        return update

    compose = state.get("compose") or {}
    log_path_str = compose.get("preview_log_path")
    if not log_path_str:
        return _record(
            False,
            ["compose.preview_log_path missing — studio_launch must run first"],
            {},
        )
    log_path = Path(log_path_str)
    if not log_path.is_file():
        return _record(False, [f"preview log not on disk: {log_path}"], {})

    sleep_fn(_resolved_window_s())

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _record(False, [f"could not read preview log: {exc}"], {})

    outcome = scan_log_text(text)
    return _record(not outcome.violations, outcome.violations, outcome.extras)
