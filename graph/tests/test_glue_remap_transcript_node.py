"""Tests for `glue_remap_transcript_node`.

Focus: HOM-144 EDL hydration contract. The node must populate
`state.edit.edl` from `<episode_dir>/edit/edl.json` so the in-graph
Phase 4 chain sees the same EDL as the legacy `/edit-episode` flow.

The remap subprocess itself is exercised by `smoke_test_v1.py`; here
we patch it out to keep the suite hermetic.
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


def _scaffold(tmp_path: Path) -> Path:
    """Lay out the minimum on-disk artifacts the node needs."""
    edit = tmp_path / "edit"
    (edit / "transcripts").mkdir(parents=True)
    (edit / "transcripts" / "raw.json").write_text(
        json.dumps({"words": []}), encoding="utf-8"
    )
    (edit / "edl.json").write_text(json.dumps(_VALID_EDL), encoding="utf-8")
    return tmp_path


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "ok") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_subprocess_ok(final_json_envelope: dict | None = None):
    """Stub `subprocess.run` and ensure final.json exists for the post-run read."""
    envelope = final_json_envelope or {"edl_hash": "abc123", "words": []}

    def _fake_run(cmd, *args, **kwargs):
        # The script writes final.json — emulate that side effect so the
        # node's post-run envelope read succeeds.
        out_idx = cmd.index("--out") + 1
        Path(cmd[out_idx]).write_text(json.dumps(envelope), encoding="utf-8")
        return _FakeProc()

    return patch(
        "edit_episode_graph.nodes.glue_remap_transcript.subprocess.run",
        side_effect=_fake_run,
    )


def test_hydrates_edl_from_disk(tmp_path):
    """HOM-144 contract: state.edit.edl is populated from edit/edl.json."""
    ep = _scaffold(tmp_path)
    with _patch_subprocess_ok():
        out = glue_remap_transcript_node({"episode_dir": str(ep)})
    assert "errors" not in out, out
    assert out["edit"]["edl"] == _VALID_EDL
    # transcripts namespace contract still intact
    assert out["transcripts"]["edl_hash"] == "abc123"


def test_missing_episode_dir_errors():
    out = glue_remap_transcript_node({})
    assert "errors" in out
    assert "episode_dir missing" in out["errors"][0]["message"]


def test_missing_edl_file_errors(tmp_path):
    edit = tmp_path / "edit"
    (edit / "transcripts").mkdir(parents=True)
    (edit / "transcripts" / "raw.json").write_text("{}", encoding="utf-8")
    # NO edl.json
    out = glue_remap_transcript_node({"episode_dir": str(tmp_path)})
    assert "errors" in out
    assert "edl.json" in out["errors"][0]["message"]
    assert "edit" not in out  # no partial hydration


def test_malformed_edl_errors_hard(tmp_path):
    """A malformed edl.json must surface a precise error, not silently
    leave state.edit.edl empty (which would re-create the original
    HOM-144 symptom — Phase 4 nodes skipping with no upstream signal)."""
    ep = _scaffold(tmp_path)
    (ep / "edit" / "edl.json").write_text("{not json", encoding="utf-8")
    out = glue_remap_transcript_node({"episode_dir": str(ep)})
    assert "errors" in out
    assert "edl.json" in out["errors"][0]["message"].lower() or "unreadable" in out["errors"][0]["message"].lower()
    assert "edit" not in out


def test_edl_without_ranges_list_errors(tmp_path):
    """The EDL contract requires a `ranges` list — anything else means a
    different file shape sneaked in (or a mid-edit truncation). Surface
    that precisely instead of letting Phase 4 nodes skip later."""
    ep = _scaffold(tmp_path)
    (ep / "edit" / "edl.json").write_text(
        json.dumps({"version": 1, "sources": {}}), encoding="utf-8"
    )
    out = glue_remap_transcript_node({"episode_dir": str(ep)})
    assert "errors" in out
    assert "ranges" in out["errors"][0]["message"]
    assert "edit" not in out  # no partial hydration on malformed EDL


def test_subprocess_failure_propagates(tmp_path):
    """If the remap subprocess fails we must not pretend success — and we
    must not have hydrated EDL into state (since the run aborted)."""
    ep = _scaffold(tmp_path)

    def _fake_run(cmd, *args, **kwargs):
        return _FakeProc(returncode=1, stderr="boom")

    with patch(
        "edit_episode_graph.nodes.glue_remap_transcript.subprocess.run",
        side_effect=_fake_run,
    ):
        out = glue_remap_transcript_node({"episode_dir": str(ep)})
    assert "errors" in out
    assert "boom" in out["errors"][0]["message"]
    assert "edit" not in out
