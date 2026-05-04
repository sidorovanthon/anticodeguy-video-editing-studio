from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

from edit_episode_graph.nodes import p3_inventory as node_module
from edit_episode_graph.nodes.p3_inventory import p3_inventory_node


def _ok(stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_inventory_uses_cached_transcript_and_packs(tmp_path, monkeypatch):
    episode = tmp_path / "ep"
    episode.mkdir()
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

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    assert "errors" not in update
    assert update["edit"]["inventory"]["source_dir"] == str(episode)
    assert update["edit"]["inventory"]["sources"] == [
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
    assert update["transcripts"]["raw_json_paths"] == [str(transcript)]
    assert update["transcripts"]["takes_packed_path"].endswith("takes_packed.md")
    assert any(str(node_module.TRANSCRIBE_BATCH) in cmd for cmd in calls)
    assert any(str(node_module.PACK_TRANSCRIPTS) in cmd for cmd in calls)


def test_inventory_prefers_edit_sources_dir(tmp_path, monkeypatch):
    episode = tmp_path / "ep"
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

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    assert "errors" not in update
    assert update["edit"]["inventory"]["source_dir"] == str(source_dir)


def test_inventory_reports_missing_transcript_after_helper(tmp_path, monkeypatch):
    episode = tmp_path / "ep"
    episode.mkdir()
    (episode / "raw.mp4").write_bytes(b"x")
    (episode / "edit" / "transcripts").mkdir(parents=True)
    (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        if cmd[0] == "ffprobe":
            return _ok(json.dumps({"format": {"duration": "1.0"}, "streams": []}))
        return _ok()

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    assert "missing transcript" in update["errors"][0]["message"]


def test_inventory_runs_timeline_view_full_overview_for_short_source(tmp_path, monkeypatch):
    """Canon Step 1 sampling: ≤10min source → single full-length overview PNG."""
    episode = tmp_path / "ep"
    episode.mkdir()
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
            # Helper writes the PNG via -o argument.
            out_idx = cmd.index("-o") + 1
            Path(cmd[out_idx]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[out_idx]).write_bytes(b"\x89PNG")
            return _ok()
        if cmd[0] == sys.executable and str(node_module.PACK_TRANSCRIPTS) in cmd:
            (episode / "edit" / "takes_packed.md").write_text("# t\n", encoding="utf-8")
            return _ok()
        return _ok()

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    assert "errors" not in update
    samples = update["edit"]["inventory"]["timeline_view_samples"]
    assert len(samples) == 1
    assert samples[0].endswith("raw.png")  # short source: bare {stem}.png, no suffix
    assert Path(samples[0]).exists()
    # Window covers the entire 30s source — canon's "visual first impression".
    cmd = timeline_calls[0]
    start = float(cmd[cmd.index(str(episode / "raw.mp4")) + 1])
    end = float(cmd[cmd.index(str(episode / "raw.mp4")) + 2])
    assert start == 0.0
    assert 29.5 <= end <= 30.0
    # Transcript path forwarded when available.
    assert "--transcript" in cmd


def test_inventory_runs_two_timeline_views_for_long_source(tmp_path, monkeypatch):
    """Canon Step 1: >10min source → two ±60s windows around the quartiles."""
    episode = tmp_path / "ep"
    episode.mkdir()
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
                "format": {"duration": "1800.0"},  # 30 min
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

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    samples = update["edit"]["inventory"]["timeline_view_samples"]
    assert len(samples) == 2
    assert samples[0].endswith("raw_q1.png")
    assert samples[1].endswith("raw_q3.png")
    # Window 1: ±60s around 1800*0.25 = 450s → [390, 510]
    cmd1 = timeline_calls[0]
    s1 = float(cmd1[cmd1.index(str(episode / "raw.mp4")) + 1])
    e1 = float(cmd1[cmd1.index(str(episode / "raw.mp4")) + 2])
    assert 389 <= s1 <= 391 and 509 <= e1 <= 511
    # Window 2: ±60s around 1800*0.75 = 1350s → [1290, 1410]
    cmd2 = timeline_calls[1]
    s2 = float(cmd2[cmd2.index(str(episode / "raw.mp4")) + 1])
    e2 = float(cmd2[cmd2.index(str(episode / "raw.mp4")) + 2])
    assert 1289 <= s2 <= 1291 and 1409 <= e2 <= 1411


def test_inventory_warns_when_timeline_view_helper_missing(tmp_path, monkeypatch):
    episode = tmp_path / "ep"
    episode.mkdir()
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

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    assert "errors" not in update
    assert update["edit"]["inventory"]["timeline_view_samples"] == []
    notices = update.get("notices") or []
    assert any("timeline_view sampling skipped" in n for n in notices)


def test_inventory_rejects_webm_before_helpers(tmp_path, monkeypatch):
    episode = tmp_path / "ep"
    episode.mkdir()
    (episode / "raw.webm").write_bytes(b"x")

    monkeypatch.setattr(node_module, "_ensure_tools", lambda: None)
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, cwd: Path) -> CompletedProcess[str]:
        calls.append(cmd)
        return _ok()

    update = p3_inventory_node({"episode_dir": str(episode)}, runner=runner)

    assert "unsupported source extension" in update["errors"][0]["message"]
    assert calls == []
