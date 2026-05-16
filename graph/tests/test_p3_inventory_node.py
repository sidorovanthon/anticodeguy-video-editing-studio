from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from edit_episode_graph.nodes import p3_inventory as node_module
from edit_episode_graph.nodes.p3_inventory import p3_inventory_node


def _ok(stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture
def project_root_episode(tmp_path, monkeypatch):
    """HOM-223: pin `HOMESTUDIO_PROJECT_ROOT` so `EpisodePaths(slug)` resolves
    under tmp_path. Slug = `ep`; episode dir = `<tmp_path>/episodes/ep`.
    """
    slug = "ep"
    episode_dir = tmp_path / "episodes" / slug
    episode_dir.mkdir(parents=True)
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return slug, episode_dir


def test_inventory_uses_cached_transcript_and_packs(project_root_episode, monkeypatch):
    slug, episode = project_root_episode
    source = episode / "raw.mp4"
    source.write_bytes(b"not a real video")
    edit = episode / "edit"
    transcripts = edit / "transcripts"
    transcripts.mkdir(parents=True)
    transcript = transcripts / "raw.json"
    transcript.write_text(json.dumps({"words": []}), encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        calls.append(cmd)
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({
                "format": {"duration": "12.5"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "duration": "12.4",
                        "avg_frame_rate": "30000/1001",
                        "width": 1920,
                        "height": 1080,
                    },
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
            }))
        if cmd[0] == sys.executable and str(node_module.PACK_TRANSCRIPTS) in cmd:
            (edit / "takes_packed.md").write_text("# Packed transcripts\n", encoding="utf-8")
            return _ok("packed 1 transcripts\n")
        return _ok("found 1 videos (1 cached, 0 to transcribe)\nnothing to do\n")

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "errors" not in update
    # HOM-223: identity-only state — `source_dir`, `transcript_json_paths`,
    # `takes_packed_path`, `timeline_view_samples` no longer echoed.
    inv = update["edit"]["inventory"]
    assert "source_dir" not in inv
    assert "transcript_json_paths" not in inv
    assert "takes_packed_path" not in inv
    assert "timeline_view_samples" not in inv
    assert inv["sources"] == [
        {
            "path": str(source),
            "name": "raw.mp4",
            "stem": "raw",
            "duration_s": 12.4,
            "video_codec": "h264",
            "audio_codec": "aac",
            "fps": 30000 / 1001,
            "width": 1920,
            "height": 1080,
        }
    ]
    # `transcripts` namespace no longer carries paths.
    assert "transcripts" not in update or "raw_json_paths" not in (update.get("transcripts") or {})
    assert any(str(node_module.TRANSCRIBE_BATCH) in cmd for cmd in calls)
    assert any(str(node_module.PACK_TRANSCRIPTS) in cmd for cmd in calls)
    # HOM-282: state-channel sentinel for `route_after_preflight`. ISO
    # 8601 UTC timestamp set after `pack_transcripts.py` confirms the
    # on-disk file is materialized.
    from datetime import datetime
    assert "takes_packed_at" in inv
    datetime.fromisoformat(inv["takes_packed_at"])


def test_inventory_hoists_raw_transcript_body_into_state(project_root_episode, monkeypatch):
    """HOM-285: after `transcribe_batch.py` + `pack_transcripts.py` land
    `raw.json` on disk, `p3_inventory` reads it back into
    `state.transcripts.bodies.raw` (+ `raw_path`). This is what closes
    the gap that made `gate:edl_ok` fall back to disk pre-HOM-285.
    """
    slug, episode = project_root_episode
    source = episode / "raw.mp4"
    source.write_bytes(b"x")
    edit = episode / "edit"
    transcripts = edit / "transcripts"
    transcripts.mkdir(parents=True)
    raw_payload = {"words": [
        {"text": "hello", "start": 0.0, "end": 0.5, "type": "word"},
    ]}
    raw_path = transcripts / "raw.json"
    raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({
                "format": {"duration": "10.0"},
                "streams": [{"codec_type": "video", "duration": "10.0"}],
            }))
        if cmd[0] == sys.executable and str(node_module.PACK_TRANSCRIPTS) in cmd:
            (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "errors" not in update, update
    bodies = update["transcripts"]["bodies"]
    assert json.loads(bodies["raw"]) == raw_payload
    assert bodies["raw_path"] == str(raw_path)


def test_inventory_skips_body_hoist_when_raw_json_absent(project_root_episode, monkeypatch):
    """HOM-285: multi-source episodes (stem != 'raw') do not produce a
    canonical `raw.json` — `p3_inventory` skips the hoist cleanly
    instead of erroring. Future work widens the body channel to a
    per-source map; today we cover the single-source canonical fixture.
    """
    slug, episode = project_root_episode
    source = episode / "take1.mov"
    source.write_bytes(b"x")
    transcripts = episode / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    # take1.json exists but no canonical raw.json.
    (transcripts / "take1.json").write_text(
        json.dumps({"words": []}), encoding="utf-8"
    )
    (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({"format": {"duration": "1.0"}, "streams": []}))
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "errors" not in update, update
    # No transcripts namespace emitted when raw.json absent on disk.
    assert "transcripts" not in update or "bodies" not in (update.get("transcripts") or {})


def test_inventory_prefers_edit_sources_dir(project_root_episode, monkeypatch):
    slug, episode = project_root_episode
    source_dir = episode / "edit" / "sources"
    source_dir.mkdir(parents=True)
    (source_dir / "take1.mov").write_bytes(b"x")
    transcripts = episode / "edit" / "transcripts"
    transcripts.mkdir()
    (transcripts / "take1.json").write_text(json.dumps({"words": []}), encoding="utf-8")
    (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({"format": {"duration": "1.0"}, "streams": []}))
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "errors" not in update
    # HOM-223: source_dir no longer in state — verify behavior by checking the
    # source was discovered (it's in `sources[0].path`).
    sources = update["edit"]["inventory"]["sources"]
    assert len(sources) == 1
    assert sources[0]["path"] == str(source_dir / "take1.mov")


def test_inventory_reports_missing_transcript_after_helper(project_root_episode, monkeypatch):
    slug, episode = project_root_episode
    (episode / "raw.mp4").write_bytes(b"x")
    (episode / "edit" / "transcripts").mkdir(parents=True)
    (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({"format": {"duration": "1.0"}, "streams": []}))
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "missing transcript" in update["errors"][0]["message"]


def test_inventory_runs_timeline_view_full_overview_for_short_source(project_root_episode, tmp_path, monkeypatch):
    """Canon Step 1 sampling: ≤10min source → single full-length overview PNG."""
    slug, episode = project_root_episode
    (episode / "raw.mp4").write_bytes(b"x")
    transcripts = episode / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "raw.json").write_text(json.dumps({"words": []}), encoding="utf-8")

    fake_helper = tmp_path / "timeline_view.py"
    fake_helper.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    monkeypatch.setattr(node_module, "TIMELINE_VIEW", fake_helper)
    timeline_calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({
                "format": {"duration": "30.0"},
                "streams": [{"codec_type": "video", "duration": "30.0"}],
            }))
        if cmd[0] == sys.executable and str(fake_helper) in cmd:
            timeline_calls.append(cmd)
            out_idx = cmd.index("-o") + 1
            Path(cmd[out_idx]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[out_idx]).write_bytes(b"\x89PNG")
            return _ok()
        if cmd[0] == sys.executable and str(node_module.PACK_TRANSCRIPTS) in cmd:
            (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")
            return _ok()
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "errors" not in update
    # HOM-223: `timeline_view_samples` no longer in state — verify the helper
    # ran (single window for short source) and the PNG landed on disk.
    assert len(timeline_calls) == 1
    cmd = timeline_calls[0]
    out_idx = cmd.index("-o") + 1
    out_png = Path(cmd[out_idx])
    assert out_png.exists()
    assert out_png.name == "raw.png"
    # Window covers the entire 30s source — canon's "visual first impression".
    start = float(cmd[cmd.index(str(episode / "raw.mp4")) + 1])
    end = float(cmd[cmd.index(str(episode / "raw.mp4")) + 2])
    assert start == 0.0
    assert 29.5 <= end <= 30.0
    assert "--transcript" in cmd


def test_inventory_runs_two_timeline_views_for_long_source(project_root_episode, tmp_path, monkeypatch):
    """Canon Step 1: >10min source → two ±60s windows around the quartiles."""
    slug, episode = project_root_episode
    (episode / "raw.mp4").write_bytes(b"x")
    transcripts = episode / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "raw.json").write_text(json.dumps({"words": []}), encoding="utf-8")

    fake_helper = tmp_path / "timeline_view.py"
    fake_helper.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    monkeypatch.setattr(node_module, "TIMELINE_VIEW", fake_helper)
    timeline_calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({
                "format": {"duration": "1800.0"},
                "streams": [{"codec_type": "video", "duration": "1800.0"}],
            }))
        if cmd[0] == sys.executable and str(fake_helper) in cmd:
            timeline_calls.append(cmd)
            out_idx = cmd.index("-o") + 1
            Path(cmd[out_idx]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[out_idx]).write_bytes(b"\x89PNG")
            return _ok()
        if cmd[0] == sys.executable and str(node_module.PACK_TRANSCRIPTS) in cmd:
            (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")
            return _ok()
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert len(timeline_calls) == 2
    out_pngs = [Path(c[c.index("-o") + 1]).name for c in timeline_calls]
    assert out_pngs[0] == "raw_q1.png"
    assert out_pngs[1] == "raw_q3.png"
    cmd1 = timeline_calls[0]
    s1 = float(cmd1[cmd1.index(str(episode / "raw.mp4")) + 1])
    e1 = float(cmd1[cmd1.index(str(episode / "raw.mp4")) + 2])
    assert 389 <= s1 <= 391 and 509 <= e1 <= 511
    cmd2 = timeline_calls[1]
    s2 = float(cmd2[cmd2.index(str(episode / "raw.mp4")) + 1])
    e2 = float(cmd2[cmd2.index(str(episode / "raw.mp4")) + 2])
    assert 1289 <= s2 <= 1291 and 1409 <= e2 <= 1411


def test_inventory_warns_when_timeline_view_helper_missing(project_root_episode, tmp_path, monkeypatch):
    slug, episode = project_root_episode
    (episode / "raw.mp4").write_bytes(b"x")
    transcripts = episode / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "raw.json").write_text(json.dumps({"words": []}), encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    monkeypatch.setattr(node_module, "TIMELINE_VIEW", tmp_path / "does-not-exist.py")

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({
                "format": {"duration": "10.0"},
                "streams": [{"codec_type": "video", "duration": "10.0"}],
            }))
        if cmd[0] == sys.executable and str(node_module.PACK_TRANSCRIPTS) in cmd:
            (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")
            return _ok()
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "errors" not in update
    notices = update.get("notices") or []
    assert any("timeline_view sampling skipped" in n for n in notices)


def test_inventory_rejects_webm_before_helpers(project_root_episode, monkeypatch):
    slug, episode = project_root_episode
    (episode / "raw.webm").write_bytes(b"x")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        calls.append(cmd)
        return _ok()

    update = p3_inventory_node({"slug": slug}, runner=runner)

    assert "unsupported source extension" in update["errors"][0]["message"]
    assert calls == []
