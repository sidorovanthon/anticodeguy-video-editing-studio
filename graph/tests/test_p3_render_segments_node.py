from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

from edit_episode_graph.nodes import p3_render_segments as node_module
from edit_episode_graph.nodes.p3_render_segments import p3_render_segments_node


def _ok(stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom", code: int = 1) -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=code, stdout="", stderr=stderr)


def _ffprobe_payload(duration_s: float) -> str:
    return json.dumps({"format": {"duration": f"{duration_s:.3f}"}})


def _setup_episode(tmp_path: Path, total: float = 10.0, ranges_n: int = 3) -> Path:
    episode = tmp_path / "ep"
    edit = episode / "edit"
    edit.mkdir(parents=True)
    ranges = [
        {"source": "raw", "start": float(i), "end": float(i) + total / ranges_n}
        for i in range(ranges_n)
    ]
    edl = {
        "version": 1,
        "sources": {"raw": str(episode / "raw.mp4")},
        "ranges": ranges,
        "grade": "neutral_punch",
        "overlays": [],
        "total_duration_s": total,
    }
    (edit / "edl.json").write_text(json.dumps(edl), encoding="utf-8")
    return episode


def _state(episode: Path, total: float = 10.0, ranges_n: int = 3) -> dict:
    return {
        "episode_dir": str(episode),
        "edit": {
            "edl": {
                "version": 1,
                "ranges": [{} for _ in range(ranges_n)],
                "total_duration_s": total,
                "overlays": [],
            },
        },
    }


def test_render_happy_path_invokes_canon_and_ffprobes(tmp_path, monkeypatch):
    episode = _setup_episode(tmp_path, total=10.0, ranges_n=3)
    final_path = episode / "edit" / "final.mp4"

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        calls.append(cmd)
        if cmd[0] == sys.executable and str(node_module.RENDER_PY) in cmd:
            final_path.write_bytes(b"fake mp4")
            return _ok("rendered\n")
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(9.97))
        raise AssertionError(f"unexpected command: {cmd}")

    update = p3_render_segments_node(_state(episode), runner=runner)

    assert "errors" not in update
    render = update["edit"]["render"]
    assert render["cached"] is False
    assert render["final_mp4"] == str(final_path)
    assert render["n_segments"] == 3
    assert render["expected_duration_s"] == 10.0
    assert render["duration_s"] == 9.97
    assert render["delta_ms"] == 30
    assert any(str(node_module.RENDER_PY) in c for c in calls)
    assert any(c[0] == "ffprobe" for c in calls)


def test_render_idempotent_when_final_exists(tmp_path, monkeypatch):
    episode = _setup_episode(tmp_path, total=5.0, ranges_n=2)
    final_path = episode / "edit" / "final.mp4"
    final_path.write_bytes(b"already rendered")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        calls.append(cmd)
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(5.0))
        raise AssertionError(f"render.py should not be invoked when final.mp4 exists; got {cmd}")

    update = p3_render_segments_node(_state(episode, total=5.0, ranges_n=2), runner=runner)

    assert "errors" not in update
    render = update["edit"]["render"]
    assert render["cached"] is True
    assert render["delta_ms"] == 0
    assert all(str(node_module.RENDER_PY) not in c for c in calls)


def test_render_errors_when_canon_fails(tmp_path, monkeypatch):
    episode = _setup_episode(tmp_path)

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == sys.executable:
            return _fail("ffmpeg: codec error")
        raise AssertionError(f"unexpected command: {cmd}")

    update = p3_render_segments_node(_state(episode), runner=runner)

    assert "errors" in update
    assert "ffmpeg: codec error" in update["errors"][0]["message"]


def test_render_errors_when_duration_outside_tolerance(tmp_path, monkeypatch):
    episode = _setup_episode(tmp_path, total=10.0, ranges_n=3)
    final_path = episode / "edit" / "final.mp4"

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == sys.executable:
            final_path.write_bytes(b"x")
            return _ok()
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(8.0))
        raise AssertionError(cmd)

    update = p3_render_segments_node(_state(episode), runner=runner)

    assert "errors" in update
    msg = update["errors"][0]["message"]
    assert "deviates" in msg
    assert "2000ms" in msg


def test_render_errors_when_edl_json_missing(tmp_path, monkeypatch):
    episode = tmp_path / "ep"
    (episode / "edit").mkdir(parents=True)

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    update = p3_render_segments_node(_state(episode), runner=lambda *a, **k: _ok())

    assert "errors" in update
    assert "edl.json not found" in update["errors"][0]["message"]


def test_render_errors_when_edl_state_empty():
    update = p3_render_segments_node({"episode_dir": "/x", "edit": {"edl": {}}})
    assert "errors" in update
    assert "EDL missing" in update["errors"][0]["message"]


def test_render_skips_when_upstream_edl_skipped(tmp_path):
    state = {
        "episode_dir": str(tmp_path),
        "edit": {"edl": {"skipped": True, "skip_reason": "no inventory"}},
    }
    update = p3_render_segments_node(state)
    assert update["edit"]["render"]["skipped"] is True
    assert "no inventory" in update["edit"]["render"]["skip_reason"]


def test_render_errors_when_episode_dir_missing():
    update = p3_render_segments_node({})
    assert "errors" in update
    assert "episode_dir missing" in update["errors"][0]["message"]
