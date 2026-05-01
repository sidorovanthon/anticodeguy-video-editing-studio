"""Tests for scripts/check_parallel_dispatch.py SessionEnd hook.

The detector warns (non-blocking) when a Phase 4 session wrote a >=3-beat
composition `episodes/<slug>/hyperframes/index.html` without dispatching
parallel `Task` (Agent) tool calls beforehand. Hook MUST always exit 0.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_parallel_dispatch.py"
FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"

DESIGN_4_BEATS = """# Design

## Beat→Visual Mapping

### Beat 1 — Hook (0.00 – 6.72s)
content

### Beat 2 — Online Activation (6.72 – 35.50s)
content

### Beat 3 — Offline Schemes (35.50 – 47.50s)
content

### Beat 4 — CTA (47.50 – 52.60s, FINAL)
content
"""

DESIGN_2_BEATS = """# Design

## Beat→Visual Mapping

### Beat 1 — Hook (0 – 5s)
content

### Beat 2 — Outro (5 – 10s)
content
"""


def _run(transcript: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--transcript", str(transcript)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _stage_episode(tmp_path: Path, design_md: str) -> Path:
    """Mirror the real episode layout under tmp_path so the script can find DESIGN.md.

    Fixtures reference an absolute path inside the canonical repo. We copy the
    fixture, rewrite its file_path entries to point at tmp_path, and drop a
    paired DESIGN.md next to the index.html.
    """
    ep_dir = tmp_path / "episodes" / "test-slug" / "hyperframes"
    ep_dir.mkdir(parents=True)
    (ep_dir / "DESIGN.md").write_text(design_md, encoding="utf-8")
    return ep_dir


def _rewrite_fixture(src: Path, tmp_path: Path) -> Path:
    """Copy fixture and rewrite the canonical absolute path to point under tmp_path."""
    canonical = "C:/Users/sidor/repos/anticodeguy-video-editing-studio"
    new_root = tmp_path.as_posix().rstrip("/")
    text = src.read_text(encoding="utf-8").replace(canonical, new_root)
    dst = tmp_path / src.name
    dst.write_text(text, encoding="utf-8")
    return dst


def test_parallel_dispatch_does_not_trigger_warning(tmp_path: Path):
    _stage_episode(tmp_path, DESIGN_4_BEATS)
    transcript = _rewrite_fixture(FIXTURES / "parallel.jsonl", tmp_path)
    result = _run(transcript)
    assert result.returncode == 0
    assert "parallel" not in result.stderr.lower() or "not" in result.stderr.lower()
    # Cleanest assertion: no warn at all.
    assert "WARNING" not in result.stderr


def test_sequential_authoring_triggers_warning(tmp_path: Path):
    _stage_episode(tmp_path, DESIGN_4_BEATS)
    transcript = _rewrite_fixture(FIXTURES / "sequential.jsonl", tmp_path)
    result = _run(transcript)
    assert result.returncode == 0  # never block
    lower = result.stderr.lower()
    assert "parallel" in lower
    assert "beat" in lower or "phase 4" in lower


def test_skip_build_does_not_trigger_warning(tmp_path: Path):
    _stage_episode(tmp_path, DESIGN_4_BEATS)
    transcript = _rewrite_fixture(FIXTURES / "skip_build.jsonl", tmp_path)
    result = _run(transcript)
    assert result.returncode == 0
    assert result.stderr.strip() == ""


def test_missing_transcript_silent_exit(tmp_path: Path):
    nonexistent = tmp_path / "no-such-transcript.jsonl"
    result = _run(nonexistent)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_under_3_beats_does_not_trigger_warning(tmp_path: Path):
    _stage_episode(tmp_path, DESIGN_2_BEATS)
    transcript = _rewrite_fixture(FIXTURES / "sequential.jsonl", tmp_path)
    result = _run(transcript)
    assert result.returncode == 0
    assert "WARNING" not in result.stderr
