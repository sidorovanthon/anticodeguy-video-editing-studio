"""Unit tests for studio_launch node (HOM-125).

These tests stub out `subprocess.Popen` to avoid spawning a real preview
server during unit runs. The smoke (`smoke_hom125.py`) exercises the real
subprocess shape end-to-end.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

from edit_episode_graph.nodes import studio_launch as sl


class _FakePopen:
    """Captures the arguments Popen would have been called with and writes
    a synthetic line to the log handle so on-disk artifacts look real."""

    last_kwargs: dict[str, Any] = {}
    last_argv: list[str] = []

    def __init__(self, argv, **kwargs):
        type(self).last_argv = list(argv)
        type(self).last_kwargs = kwargs
        self.pid = 424242
        log_handle = kwargs.get("stdout")
        if hasattr(log_handle, "write"):
            log_handle.write("fake preview server ready\n")
            log_handle.flush()


def _hf_with_index(tmp_path: Path) -> Path:
    hf = tmp_path / "hyperframes"
    hf.mkdir()
    (hf / "index.html").write_text("<html></html>", encoding="utf-8")
    return hf


def _state(hf: Path, **overrides) -> dict:
    compose = {"hyperframes_dir": str(hf)}
    compose.update(overrides)
    return {"compose": compose}


def test_errors_when_no_hyperframes_dir():
    update = sl.studio_launch_node({})
    assert update["errors"]
    assert "no compose.hyperframes_dir" in update["errors"][0]["message"]


def test_errors_when_hyperframes_dir_missing(tmp_path: Path):
    update = sl.studio_launch_node({"compose": {"hyperframes_dir": str(tmp_path / "nope")}})
    assert update["errors"]
    assert "not on disk" in update["errors"][0]["message"]


def test_errors_when_index_html_missing(tmp_path: Path):
    hf = tmp_path / "hyperframes"
    hf.mkdir()
    update = sl.studio_launch_node(_state(hf))
    assert update["errors"]
    assert "index.html" in update["errors"][0]["message"]


def test_launches_and_records_pid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf = _hf_with_index(tmp_path)
    monkeypatch.setattr(sl.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(sl, "_bundled_hf_cli", lambda d: None)
    monkeypatch.setattr(sl.shutil, "which", lambda _: "/usr/bin/npx")

    update = sl.studio_launch_node(_state(hf))

    compose = update["compose"]
    assert compose["studio_pid"] == 424242
    assert compose["preview_port"] == sl.DEFAULT_PORT
    assert compose["studio_reused"] is False
    log_path = Path(compose["preview_log_path"])
    assert log_path.is_file()
    assert "fake preview server ready" in log_path.read_text(encoding="utf-8")
    pid_path = hf / ".hyperframes" / "preview.pid"
    assert pid_path.read_text(encoding="utf-8").strip() == "424242"
    # CLI argv: hyperframes preview --port 3002
    assert _FakePopen.last_argv[-3:] == ["preview", "--port", "3002"]


def test_idempotent_reuse_when_pid_alive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf = _hf_with_index(tmp_path)
    state_dir = hf / ".hyperframes"
    state_dir.mkdir()
    (state_dir / "preview.log").write_text("prior run output\n", encoding="utf-8")
    (state_dir / "preview.pid").write_text("9999", encoding="utf-8")

    monkeypatch.setattr(sl, "_is_pid_alive", lambda pid: pid == 9999)

    def _fail_popen(*a, **kw):
        raise AssertionError("should not respawn when prior PID is alive")

    monkeypatch.setattr(sl.subprocess, "Popen", _fail_popen)

    update = sl.studio_launch_node(_state(hf))
    compose = update["compose"]
    assert compose["studio_pid"] == 9999
    assert compose["studio_reused"] is True
    # Existing log preserved
    assert (
        "prior run output"
        in (state_dir / "preview.log").read_text(encoding="utf-8")
    )


def test_respawns_on_stale_pid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf = _hf_with_index(tmp_path)
    state_dir = hf / ".hyperframes"
    state_dir.mkdir()
    (state_dir / "preview.pid").write_text("1234", encoding="utf-8")

    monkeypatch.setattr(sl, "_is_pid_alive", lambda pid: False)
    monkeypatch.setattr(sl.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(sl, "_bundled_hf_cli", lambda d: None)
    monkeypatch.setattr(sl.shutil, "which", lambda _: "/usr/bin/npx")

    update = sl.studio_launch_node(_state(hf))
    assert update["compose"]["studio_pid"] == 424242
    assert update["compose"]["studio_reused"] is False


def test_resolved_port_state_overrides_env_and_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("STUDIO_PREVIEW_PORT", "4040")
    state = {"compose": {"preview_port": 5050}}
    assert sl._resolved_port(state) == 5050
    assert sl._resolved_port({"compose": {}}) == 4040
    monkeypatch.delenv("STUDIO_PREVIEW_PORT", raising=False)
    assert sl._resolved_port({"compose": {}}) == sl.DEFAULT_PORT


def test_errors_when_no_cli_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf = _hf_with_index(tmp_path)
    monkeypatch.setattr(sl, "_bundled_hf_cli", lambda d: None)
    monkeypatch.setattr(sl.shutil, "which", lambda _: None)

    update = sl.studio_launch_node(_state(hf))
    assert update["errors"]
    assert "not found on PATH" in update["errors"][0]["message"]


def test_uses_bundled_cli_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf = _hf_with_index(tmp_path)
    bundled = tmp_path / "fake-hf"
    bundled.write_text("", encoding="utf-8")
    monkeypatch.setattr(sl, "_bundled_hf_cli", lambda d: bundled)
    monkeypatch.setattr(sl.subprocess, "Popen", _FakePopen)

    sl.studio_launch_node(_state(hf))
    assert _FakePopen.last_argv[0] == str(bundled)
    assert _FakePopen.last_argv[1:] == ["preview", "--port", "3002"]


def test_is_pid_alive_returns_false_for_zero():
    assert sl._is_pid_alive(0) is False


def test_is_pid_alive_returns_true_for_self():
    """Self-PID is always alive — sanity check the cross-platform impl."""
    assert sl._is_pid_alive(os.getpid()) is True
