"""preflight_canon node — v1 staleness-driven bare-repro dispatcher.

Automates the CLAUDE.md "Investigation methodology — bare-repro before
upstream-blame" rule: for each known-blocked upstream pattern tracked in
user memory (``feedback_hf_*.md``), if its ``last_verified`` timestamp is
older than ``MAX_STALE_DAYS`` (or absent), this node runs the corresponding
bare-repro script.

Tri-state per repro:

* exit 0 — bug still reproduces: bump ``last_verified`` in the sidecar
  state file and emit a ``still_broken`` ``BugCheck``.
* exit 1 — bug did NOT reproduce: emit a ``no_longer_reproducible``
  ``BugCheck`` plus a state ``notices[]`` warning. Do NOT auto-update the
  sidecar — flagging the bug as "fixed" is high-stakes (would let canon-
  blessed patterns back into briefs that we currently route around) and
  must be a human call against the underlying memory entry.
* exit 2 / timeout / OS error — emit ``inconclusive``. Do NOT update.

The sidecar state file is ``scripts/bare_repros/state.json`` (gitignored,
machine-local). Memory entries themselves are NEVER mutated by this node —
they remain the human-readable record; the sidecar is the machine record.

Spec §4.1 places this node between ``isolate_audio`` and the ``skip_phase3?``
fork. ``route_after_preflight`` does not depend on this node's state delta,
so a check that returns no useful verdicts (e.g. ``npx`` missing) does not
block the pipeline — it just logs the inconclusive results into Studio.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from .._paths import project_root

PROJECT_ROOT = project_root()
BARE_REPROS_DIR = PROJECT_ROOT / "scripts" / "bare_repros"
DEFAULT_STATE_PATH = BARE_REPROS_DIR / "state.json"

MAX_STALE_DAYS = 7
DEFAULT_TIMEOUT_S = 90.0


# Watchlist: (memory_slug, repro_script_filename). The slug doubles as the
# sidecar key. Backfill scripts for the remaining three known-blocked
# patterns (lint_regex, compositions_cli, hf_video_audio) ship in follow-up
# tickets per HOM-106 scope; entries listed here without a script file
# surface as ``missing_script`` so we don't silently lose them.
WATCHLIST: tuple[tuple[str, str], ...] = (
    (
        "feedback_hf_subcomp_loader_data_composition_src",
        "feedback_hf_subcomp_loader_data_composition_src.py",
    ),
)


Runner = Callable[[list[str], float], subprocess.CompletedProcess]


def _default_runner(cmd: list[str], timeout_s: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        shell=False,
    )


def _read_sidecar(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupted sidecar — treat as empty rather than crashing the graph.
        # The next still_broken result will atomically overwrite with a fresh dict.
        return {}


def _write_sidecar(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_stale(entry: dict | None, *, now: datetime, max_age_days: int) -> bool:
    if not entry:
        return True
    raw = entry.get("last_verified")
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) > timedelta(days=max_age_days)


def _classify(exit_code: int) -> str:
    if exit_code == 0:
        return "still_broken"
    if exit_code == 1:
        return "no_longer_reproducible"
    return "inconclusive"


def _run_one(
    *,
    bug_slug: str,
    script_filename: str,
    repros_dir: Path,
    sidecar: dict,
    now: datetime,
    max_age_days: int,
    timeout_s: float,
    runner: Runner,
) -> tuple[dict, dict | None, str | None]:
    """Run one repro (or skip if fresh).

    Returns ``(bug_check, sidecar_update_or_None, notice_or_None)``. The
    sidecar update is ``None`` when nothing should be persisted (skip,
    no-longer-reproducible, inconclusive — see module docstring).
    """
    script_path = repros_dir / script_filename
    entry = sidecar.get(bug_slug) or {}

    if not script_path.exists():
        return (
            {
                "bug_slug": bug_slug,
                "status": "missing_script",
                "last_verified": entry.get("last_verified"),
                "message": f"bare-repro script not found at {script_path}",
            },
            None,
            f"preflight_canon: bare-repro script missing for {bug_slug} at {script_path}",
        )

    if not _is_stale(entry, now=now, max_age_days=max_age_days):
        return (
            {
                "bug_slug": bug_slug,
                "status": "fresh",
                "last_verified": entry.get("last_verified"),
            },
            None,
            None,
        )

    started = time.monotonic()
    try:
        result = runner(
            [sys.executable, str(script_path), "--timeout-s", str(timeout_s)],
            # Outer wall-clock buffer. Bare-repro scripts internally budget
            # the inner subprocesses to SUM under their --timeout-s argument
            # (see scaffold_budget_s / compositions_budget_s in the HF
            # sub-comp script), so timeout_s + a Python-overhead headroom
            # is sufficient. Going to 2× would compound across watchlist
            # entries and stall the graph unnecessarily.
            timeout_s + 30.0,
        )
        exit_code = result.returncode
        message_tail = (result.stderr or result.stdout or "")[-400:].strip() or None
    except subprocess.TimeoutExpired:
        exit_code = 2
        message_tail = "bare-repro script timed out"
    except OSError as exc:
        exit_code = 2
        message_tail = f"bare-repro script invocation failed: {exc}"
    duration_s = round(time.monotonic() - started, 3)

    status = _classify(exit_code)
    bug_check: dict = {
        "bug_slug": bug_slug,
        "status": status,
        "repro_exit_code": exit_code,
        "duration_s": duration_s,
    }
    if message_tail:
        bug_check["message"] = message_tail

    sidecar_update = None
    notice = None
    if status == "still_broken":
        sidecar_update = {
            **entry,
            "last_verified": now.isoformat(),
            "last_status": "still_broken",
        }
        bug_check["last_verified"] = sidecar_update["last_verified"]
    elif status == "no_longer_reproducible":
        # High-stakes signal — the canonical pattern may now work upstream.
        # Surface to operator; do NOT auto-update the sidecar (would risk
        # false-clean memory clears from a flaky repro).
        bug_check["last_verified"] = entry.get("last_verified")
        notice = (
            f"preflight_canon: bare-repro for {bug_slug} did NOT reproduce "
            f"(exit 1). Upstream may be fixed; review the memory entry "
            f"manually before clearing."
        )
    else:  # inconclusive
        bug_check["last_verified"] = entry.get("last_verified")
        notice = (
            f"preflight_canon: bare-repro for {bug_slug} inconclusive "
            f"(exit {exit_code})."
        )

    return bug_check, sidecar_update, notice


def preflight_canon_node(
    state,
    *,
    runner: Runner | None = None,
    state_path: Path | None = None,
    repros_dir: Path | None = None,
    watchlist: Iterable[tuple[str, str]] | None = None,
    max_age_days: int = MAX_STALE_DAYS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
):
    """Run staleness-driven bare-repros and update sidecar state.

    Pure side effects are bounded to the sidecar JSON; node returns a
    state delta with ``preflight.checked`` and any ``notices``.
    """
    runner = runner or _default_runner
    state_path = state_path or DEFAULT_STATE_PATH
    repros_dir = repros_dir or BARE_REPROS_DIR
    items = list(watchlist) if watchlist is not None else list(WATCHLIST)

    sidecar = _read_sidecar(state_path)
    now = datetime.now(timezone.utc)

    checked: list[dict] = []
    notices: list[str] = []
    sidecar_dirty = False

    for bug_slug, script_filename in items:
        bug_check, sidecar_update, notice = _run_one(
            bug_slug=bug_slug,
            script_filename=script_filename,
            repros_dir=repros_dir,
            sidecar=sidecar,
            now=now,
            max_age_days=max_age_days,
            timeout_s=timeout_s,
            runner=runner,
        )
        checked.append(bug_check)
        if sidecar_update is not None:
            sidecar[bug_slug] = sidecar_update
            sidecar_dirty = True
        if notice:
            notices.append(notice)

    if sidecar_dirty:
        try:
            _write_sidecar(state_path, sidecar)
        except OSError as exc:
            notices.append(
                f"preflight_canon: failed to persist sidecar at {state_path}: {exc}"
            )

    update: dict = {
        "preflight": {
            "checked": checked,
            "state_path": str(state_path),
        }
    }
    if notices:
        update["notices"] = notices
    return update
