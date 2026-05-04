"""Unit tests for preflight_canon node — staleness, tri-state, sidecar."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from edit_episode_graph.nodes.preflight_canon import (
    DEFAULT_TIMEOUT_S,
    MAX_STALE_DAYS,
    preflight_canon_node,
)


def _result(exit_code: int, *, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=exit_code, stdout=stdout, stderr=stderr)


def _stub_script(dirpath: Path, filename: str = "repro.py") -> Path:
    """Write a placeholder repro script so existence checks pass."""
    p = dirpath / filename
    p.write_text("# stub\n", encoding="utf-8")
    return p


def test_runs_repro_when_sidecar_empty_and_records_still_broken(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"
    seen: list[list[str]] = []

    def runner(cmd, timeout_s):
        seen.append(cmd)
        return _result(0, stdout="VERDICT: reproduced")

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    assert seen, "repro script should have been invoked when sidecar is empty"
    assert update["preflight"]["checked"][0]["status"] == "still_broken"
    assert update["preflight"]["checked"][0]["repro_exit_code"] == 0
    assert "notices" not in update or update["notices"] == []
    persisted = json.loads(sidecar.read_text(encoding="utf-8"))
    assert persisted["bug-x"]["last_status"] == "still_broken"
    assert persisted["bug-x"]["last_verified"]  # ISO timestamp present


def test_skips_when_entry_is_fresh(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    sidecar.write_text(
        json.dumps({"bug-x": {"last_verified": fresh, "last_status": "still_broken"}}),
        encoding="utf-8",
    )

    invocations = 0

    def runner(cmd, timeout_s):
        nonlocal invocations
        invocations += 1
        return _result(0)

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    assert invocations == 0
    check = update["preflight"]["checked"][0]
    assert check["status"] == "fresh"
    assert check["last_verified"] == fresh


def test_runs_repro_when_entry_is_stale(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"
    stale = (datetime.now(timezone.utc) - timedelta(days=MAX_STALE_DAYS + 2)).isoformat()
    sidecar.write_text(
        json.dumps({"bug-x": {"last_verified": stale, "last_status": "still_broken"}}),
        encoding="utf-8",
    )

    def runner(cmd, timeout_s):
        return _result(0)

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    assert update["preflight"]["checked"][0]["status"] == "still_broken"
    persisted = json.loads(sidecar.read_text(encoding="utf-8"))
    # last_verified must have advanced past the stale value
    assert persisted["bug-x"]["last_verified"] > stale


def test_no_longer_reproducible_emits_warning_does_not_persist(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    sidecar.write_text(
        json.dumps({"bug-x": {"last_verified": stale, "last_status": "still_broken"}}),
        encoding="utf-8",
    )

    def runner(cmd, timeout_s):
        return _result(1, stdout="VERDICT: fixed")

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    check = update["preflight"]["checked"][0]
    assert check["status"] == "no_longer_reproducible"
    assert check["last_verified"] == stale  # unchanged
    assert any("did NOT reproduce" in n for n in update["notices"])
    persisted = json.loads(sidecar.read_text(encoding="utf-8"))
    # sidecar still pointing at the stale timestamp — humans must clear it
    assert persisted["bug-x"]["last_verified"] == stale


def test_inconclusive_on_exit_2(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"

    def runner(cmd, timeout_s):
        return _result(2, stderr="npx not found")

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    check = update["preflight"]["checked"][0]
    assert check["status"] == "inconclusive"
    assert check["repro_exit_code"] == 2
    assert any("inconclusive" in n for n in update["notices"])
    assert not sidecar.exists()  # never persisted


def test_inconclusive_on_timeout(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"

    def runner(cmd, timeout_s):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_s)

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    check = update["preflight"]["checked"][0]
    assert check["status"] == "inconclusive"
    assert "timed out" in (check.get("message") or "")


def test_missing_script_surfaces_notice(tmp_path):
    sidecar = tmp_path / "state.json"

    def runner(cmd, timeout_s):  # pragma: no cover — must not be invoked
        raise AssertionError("runner should not be called when script is missing")

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", "nope.py")],
    )

    check = update["preflight"]["checked"][0]
    assert check["status"] == "missing_script"
    assert any("script missing" in n for n in update["notices"])


def test_corrupt_sidecar_does_not_crash(tmp_path):
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"
    sidecar.write_text("{not json", encoding="utf-8")

    def runner(cmd, timeout_s):
        return _result(0)

    update = preflight_canon_node(
        {},
        runner=runner,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    assert update["preflight"]["checked"][0]["status"] == "still_broken"


def test_round_trip_flip_to_stale_triggers_repro(tmp_path):
    """DoD: manually flip last-verified to >7d ago, run node, confirm entry updated."""
    script = _stub_script(tmp_path)
    sidecar = tmp_path / "state.json"

    # First run with empty sidecar — fresh entry written.
    def reproduce(cmd, timeout_s):
        return _result(0)

    preflight_canon_node(
        {},
        runner=reproduce,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )
    after_first = json.loads(sidecar.read_text(encoding="utf-8"))
    first_ts = after_first["bug-x"]["last_verified"]

    # Manually backdate to 14 days ago.
    backdated = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    sidecar.write_text(
        json.dumps({"bug-x": {"last_verified": backdated, "last_status": "still_broken"}}),
        encoding="utf-8",
    )

    update = preflight_canon_node(
        {},
        runner=reproduce,
        state_path=sidecar,
        repros_dir=tmp_path,
        watchlist=[("bug-x", script.name)],
    )

    after_second = json.loads(sidecar.read_text(encoding="utf-8"))
    assert update["preflight"]["checked"][0]["status"] == "still_broken"
    assert after_second["bug-x"]["last_verified"] != backdated
    assert after_second["bug-x"]["last_verified"] >= first_ts


def test_default_timeout_constant_is_finite():
    assert 0 < DEFAULT_TIMEOUT_S < 600
