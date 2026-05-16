"""Tests for `glue_remap_transcript_node`.

Focus: HOM-144 EDL hydration contract. The node must populate
`state.edit.edl` from `<episode_dir>/edit/edl.json` so the in-graph
Phase 4 chain sees the same EDL as the legacy `/edit-episode` flow.

HOM-223 update: state carries `slug` only; paths derived via
`EpisodePaths(slug)`. Tests pin `HOMESTUDIO_PROJECT_ROOT` so the resolver
points at tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from edit_episode_graph.nodes.glue_remap_transcript import glue_remap_transcript_node


_VALID_EDL = {
    "version": 1,
    "sources": {"raw": "raw.mp4"},
    "ranges": [
        {"source": "raw", "start": 0.0, "end": 5.0, "beat": "HOOK", "quote": "x"},
        {"source": "raw", "start": 6.0, "end": 12.0, "beat": "PAYOFF", "quote": "y"},
    ],
    "grade": "",
    "overlays": [],
    "total_duration_s": 11.0,
}


@pytest.fixture
def project_root_episode(tmp_path, monkeypatch):
    slug = "ep"
    episode_dir = tmp_path / "episodes" / slug
    episode_dir.mkdir(parents=True)
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return slug, episode_dir


def _scaffold(episode_dir: Path) -> Path:
    """Lay out the minimum on-disk artifacts the node needs."""
    edit = episode_dir / "edit"
    (edit / "transcripts").mkdir(parents=True, exist_ok=True)
    (edit / "transcripts" / "raw.json").write_text(
        json.dumps({"words": []}), encoding="utf-8"
    )
    (edit / "edl.json").write_text(json.dumps(_VALID_EDL), encoding="utf-8")
    return episode_dir


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "ok") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_subprocess_ok(final_json_envelope: dict | None = None):
    envelope = final_json_envelope or {"edl_hash": "abc123", "words": []}

    def _fake_run(cmd, *args, **kwargs):
        out_idx = cmd.index("--out") + 1
        Path(cmd[out_idx]).write_text(json.dumps(envelope), encoding="utf-8")
        return _FakeProc()

    return patch(
        "edit_episode_graph.nodes.glue_remap_transcript.subprocess.run",
        side_effect=_fake_run,
    )


def test_hydrates_edl_from_disk(project_root_episode):
    """HOM-144 contract: state.edit.edl is populated from edit/edl.json.

    HOM-279 contract: transcripts.bodies.{raw,final} are populated with
    the JSON body strings so downstream Phase-4 consumers
    (`p4_captions_layer`, `p4_prompt_expansion`, `gate:edl_ok`) can
    read transcript content from state instead of disk.
    """
    slug, episode_dir = project_root_episode
    _scaffold(episode_dir)
    with _patch_subprocess_ok():
        out = glue_remap_transcript_node({"slug": slug})
    assert "errors" not in out, out
    assert out["edit"]["edl"] == _VALID_EDL
    # HOM-223: identity-only state — `raw_json_path`, `final_json_path` no
    # longer echoed; only content fingerprint (`edl_hash`) remains.
    transcripts = out["transcripts"]
    assert transcripts["edl_hash"] == "abc123"
    # HOM-279: bodies hoisted into state.
    bodies = transcripts["bodies"]
    assert json.loads(bodies["raw"]) == {"words": []}
    assert json.loads(bodies["final"]) == {"edl_hash": "abc123", "words": []}
    assert bodies["raw_path"].endswith("raw.json")
    assert bodies["final_path"].endswith("final.json")


def test_missing_slug_errors():
    out = glue_remap_transcript_node({})
    assert "errors" in out
    assert "slug missing" in out["errors"][0]["message"]


def test_missing_edl_file_errors(project_root_episode):
    slug, episode_dir = project_root_episode
    edit = episode_dir / "edit"
    (edit / "transcripts").mkdir(parents=True, exist_ok=True)
    (edit / "transcripts" / "raw.json").write_text("{}", encoding="utf-8")
    # NO edl.json
    out = glue_remap_transcript_node({"slug": slug})
    assert "errors" in out
    assert "edl.json" in out["errors"][0]["message"]
    assert "edit" not in out


def test_malformed_edl_errors_hard(project_root_episode):
    """A malformed edl.json must surface a precise error."""
    slug, episode_dir = project_root_episode
    _scaffold(episode_dir)
    (episode_dir / "edit" / "edl.json").write_text("{not json", encoding="utf-8")
    out = glue_remap_transcript_node({"slug": slug})
    assert "errors" in out
    assert "edl.json" in out["errors"][0]["message"].lower() or "unreadable" in out["errors"][0]["message"].lower()
    assert "edit" not in out


def test_edl_without_ranges_list_errors(project_root_episode):
    slug, episode_dir = project_root_episode
    _scaffold(episode_dir)
    (episode_dir / "edit" / "edl.json").write_text(
        json.dumps({"version": 1, "sources": {}}), encoding="utf-8"
    )
    out = glue_remap_transcript_node({"slug": slug})
    assert "errors" in out
    assert "ranges" in out["errors"][0]["message"]
    assert "edit" not in out


def test_subprocess_failure_propagates(project_root_episode):
    slug, episode_dir = project_root_episode
    _scaffold(episode_dir)

    def _fake_run(cmd, *args, **kwargs):
        return _FakeProc(returncode=1, stderr="boom")

    with patch(
        "edit_episode_graph.nodes.glue_remap_transcript.subprocess.run",
        side_effect=_fake_run,
    ):
        out = glue_remap_transcript_node({"slug": slug})
    assert "errors" in out
    assert "boom" in out["errors"][0]["message"]
    assert "edit" not in out
