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
