from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from edit_episode_graph.nodes import p3_render_segments as node_module
from edit_episode_graph.nodes.p3_render_segments import p3_render_segments_node


def _ok(stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom", code: int = 1) -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=code, stdout="", stderr=stderr)


def _ffprobe_payload(duration_s: float) -> str:
    return json.dumps({"format": {"duration": f"{duration_s:.3f}"}})


@pytest.fixture
def project_root_episode(tmp_path, monkeypatch):
    """HOM-223: pin `HOMESTUDIO_PROJECT_ROOT` so `EpisodePaths(slug)` lands
    under tmp_path. Slug = `ep`; episode dir = `<tmp_path>/episodes/ep`.
    """
    slug = "ep"
    episode_dir = tmp_path / "episodes" / slug
    episode_dir.mkdir(parents=True)
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return slug, episode_dir


def _setup_episode(episode_dir: Path, total: float = 10.0, ranges_n: int = 3) -> Path:
    edit = episode_dir / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    ranges = [
        {"source": "raw", "start": float(i), "end": float(i) + total / ranges_n}
        for i in range(ranges_n)
    ]
    edl = {
        "version": 1,
        "sources": {"raw": str(episode_dir / "raw.mp4")},
        "ranges": ranges,
        "grade": "neutral_punch",
        "overlays": [],
        "total_duration_s": total,
    }
    (edit / "edl.json").write_text(json.dumps(edl), encoding="utf-8")
    return episode_dir


def _state(slug: str, episode_dir: Path, total: float = 10.0, ranges_n: int = 3) -> dict:
    return {
        "slug": slug,
        "episode_dir": str(episode_dir),
        "edit": {
            "edl": {
                "version": 1,
                "ranges": [{} for _ in range(ranges_n)],
                "total_duration_s": total,
                "overlays": [],
            },
        },
    }


def test_render_happy_path_invokes_canon_and_ffprobes(project_root_episode, monkeypatch):
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir, total=10.0, ranges_n=3)
    final_path = episode_dir / "edit" / "final.mp4"

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

    update = p3_render_segments_node(_state(slug, episode_dir), runner=runner)

    assert "errors" not in update
    render = update["edit"]["render"]
    # HOM-223: identity-only state — `final_mp4` / `clips_dir` no longer echoed.
    assert "final_mp4" not in render
    assert "clips_dir" not in render
    assert render["cached"] is False
    assert render["n_segments"] == 3
    assert render["expected_duration_s"] == 10.0
    assert render["duration_s"] == 9.97
    assert render["delta_ms"] == 30
    assert any(str(node_module.RENDER_PY) in c for c in calls)
    assert any(c[0] == "ffprobe" for c in calls)


def test_render_idempotent_when_final_exists(project_root_episode, monkeypatch):
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir, total=5.0, ranges_n=2)
    final_path = episode_dir / "edit" / "final.mp4"
    final_path.write_bytes(b"already rendered")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        calls.append(cmd)
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(5.0))
        raise AssertionError(f"render.py should not be invoked when final.mp4 exists; got {cmd}")

    update = p3_render_segments_node(
        _state(slug, episode_dir, total=5.0, ranges_n=2), runner=runner
    )

    assert "errors" not in update
    render = update["edit"]["render"]
    assert render["cached"] is True
    assert render["delta_ms"] == 0
    assert all(str(node_module.RENDER_PY) not in c for c in calls)


def test_render_errors_when_canon_fails(project_root_episode, monkeypatch):
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir)

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == sys.executable:
            return _fail("ffmpeg: codec error")
        raise AssertionError(f"unexpected command: {cmd}")

    update = p3_render_segments_node(_state(slug, episode_dir), runner=runner)

    assert "errors" in update
    assert "ffmpeg: codec error" in update["errors"][0]["message"]


def test_render_errors_when_duration_outside_tolerance(project_root_episode, monkeypatch):
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir, total=10.0, ranges_n=3)
    final_path = episode_dir / "edit" / "final.mp4"

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == sys.executable:
            final_path.write_bytes(b"x")
            return _ok()
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(8.0))
        raise AssertionError(cmd)

    update = p3_render_segments_node(_state(slug, episode_dir), runner=runner)

    assert "errors" in update
    msg = update["errors"][0]["message"]
    assert "deviates" in msg
    assert "2000ms" in msg


def test_render_errors_when_edl_json_missing(project_root_episode, monkeypatch):
    slug, episode_dir = project_root_episode
    (episode_dir / "edit").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    update = p3_render_segments_node(
        _state(slug, episode_dir), runner=lambda *a, **k: _ok()
    )

    assert "errors" in update
    assert "edl.json not found" in update["errors"][0]["message"]


def test_render_errors_when_edl_state_empty():
    update = p3_render_segments_node({"slug": "x", "edit": {"edl": {}}})
    assert "errors" in update
    assert "EDL missing" in update["errors"][0]["message"]


def test_render_skips_when_upstream_edl_skipped(project_root_episode):
    slug, episode_dir = project_root_episode
    state = {
        "slug": slug,
        "episode_dir": str(episode_dir),
        "edit": {"edl": {"skipped": True, "skip_reason": "no inventory"}},
    }
    update = p3_render_segments_node(state)
    assert update["edit"]["render"]["skipped"] is True
    assert "no inventory" in update["edit"]["render"]["skip_reason"]


def test_render_errors_when_slug_missing():
    update = p3_render_segments_node({})
    assert "errors" in update
    assert "slug missing" in update["errors"][0]["message"]


def test_render_omits_fps_flag_by_default(project_root_episode, monkeypatch):
    """When EDL has no target_fps, we don't pass --fps — canon defaults to 24."""
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir, total=10.0, ranges_n=3)
    final_path = episode_dir / "edit" / "final.mp4"

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    captured: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        captured.append(cmd)
        if cmd[0] == sys.executable and str(node_module.RENDER_PY) in cmd:
            final_path.write_bytes(b"x")
            return _ok()
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(10.0))
        raise AssertionError(cmd)

    update = p3_render_segments_node(_state(slug, episode_dir), runner=runner)

    assert "errors" not in update
    render_calls = [c for c in captured if c[0] == sys.executable]
    assert render_calls, "render.py must be invoked"
    assert "--fps" not in render_calls[0]


def test_render_forwards_target_fps_when_present(project_root_episode, monkeypatch):
    """EDL `target_fps` → canon `--fps <N>` (HOM-117)."""
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir, total=10.0, ranges_n=3)
    final_path = episode_dir / "edit" / "final.mp4"

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    captured: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        captured.append(cmd)
        if cmd[0] == sys.executable and str(node_module.RENDER_PY) in cmd:
            final_path.write_bytes(b"x")
            return _ok()
        if cmd[0] == "ffprobe":
            return _ok(_ffprobe_payload(10.0))
        raise AssertionError(cmd)

    state = _state(slug, episode_dir)
    state["edit"]["edl"]["target_fps"] = 60

    update = p3_render_segments_node(state, runner=runner)

    assert "errors" not in update
    render_calls = [c for c in captured if c[0] == sys.executable]
    assert render_calls, "render.py must be invoked"
    cmd = render_calls[0]
    assert "--fps" in cmd
    assert cmd[cmd.index("--fps") + 1] == "60"


def test_render_errors_on_non_int_target_fps(project_root_episode, monkeypatch):
    """Bad target_fps surfaces a clear error rather than a canon stack trace."""
    slug, episode_dir = project_root_episode
    _setup_episode(episode_dir, total=10.0, ranges_n=3)

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    state = _state(slug, episode_dir)
    state["edit"]["edl"]["target_fps"] = "not-a-number"

    update = p3_render_segments_node(state, runner=lambda *a, **k: _ok())

    assert "errors" in update
    assert "target_fps" in update["errors"][0]["message"]
