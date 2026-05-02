"""Tests for pickup.pick_episode (HOM-85 spec table + edge cases)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from scripts.pickup import pick_episode, PickupError


def _write(p: Path, content: bytes | str = b""):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        p.write_text(content, encoding="utf-8")
    else:
        p.write_bytes(content)


def _set_mtime(p: Path, age_sec: float):
    t = time.time() - age_sec
    os.utime(p, (t, t))


# ---------- Spec table ----------

def test_row1_empty_inbox_returns_idle(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    episodes = tmp_path / "episodes"
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert result.idle is True


def test_row2_video_without_script_errors(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "launch-promo.mp4", b"x")
    with pytest.raises(PickupError, match="missing script"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")


def test_row3_script_without_video_errors(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "notes.txt", "Hello world.")
    with pytest.raises(PickupError, match="missing video"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")


def test_row4_one_plus_one_pairs_regardless_of_stem(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "raw.mp4", b"x")
    _write(inbox / "script.txt", "Desktop software licensing, it turns out, is also a whole story.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert result.slug == "2026-05-02-desktop-software-licensing-it-turns-out-is"
    assert (result.episode_dir / "raw.mp4").exists()
    assert (result.episode_dir / "script.txt").exists()
    assert not (inbox / "raw.mp4").exists()
    assert not (inbox / "script.txt").exists()
    assert result.warning is None


def test_row5_multi_file_stem_pair_fifo_oldest(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "older.mp4", b"x")
    _write(inbox / "older.txt", "First episode body. Tail.")
    _set_mtime(inbox / "older.mp4", 100)
    _set_mtime(inbox / "older.txt", 100)
    _write(inbox / "newer.mp4", b"y")
    _write(inbox / "newer.txt", "Second episode body. Tail.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert "first" in result.slug
    assert (inbox / "newer.mp4").exists()
    assert (inbox / "newer.txt").exists()
    assert result.warning is not None
    assert "newer.mp4" in result.warning


def test_row6_multi_file_no_stem_pair_errors(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "a.mp4", b"x")
    _write(inbox / "b.mp4", b"y")
    _write(inbox / "x.txt", "one")
    _write(inbox / "y.txt", "two")
    with pytest.raises(PickupError, match=r"no video.*script pairs"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")


# ---------- Edge cases ----------

def test_edge1_one_video_two_scripts_orphan_warned(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "ep.mp4", b"x")
    _write(inbox / "ep.txt", "Episode body. Tail.")
    _write(inbox / "stray.txt", "Stray notes.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert (result.episode_dir / "raw.mp4").exists()
    assert (result.episode_dir / "script.txt").exists()
    assert result.warning is not None
    assert "stray.txt" in result.warning
    assert (inbox / "stray.txt").exists()


def test_edge2_two_videos_one_script_orphan_video_warned(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "ep.mp4", b"x")
    _write(inbox / "ep.txt", "Episode body. Tail.")
    _write(inbox / "extra.mp4", b"y")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert (result.episode_dir / "raw.mp4").exists()
    assert result.warning is not None
    assert "extra.mp4" in result.warning
    assert (inbox / "extra.mp4").exists()


def test_edge3_two_videos_two_scripts_no_match_errors(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "v1.mp4", b"x")
    _write(inbox / "v2.mp4", b"y")
    _write(inbox / "s1.txt", "one")
    _write(inbox / "s2.txt", "two")
    with pytest.raises(PickupError, match=r"no video.*script pairs"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")


def test_edge4_two_pairs_all_match_fifo(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "a.mp4", b"x")
    _write(inbox / "a.txt", "Alpha episode body. Tail.")
    _set_mtime(inbox / "a.mp4", 100)
    _set_mtime(inbox / "a.txt", 100)
    _write(inbox / "b.mp4", b"y")
    _write(inbox / "b.txt", "Beta episode body. Tail.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert "alpha" in result.slug
    assert (inbox / "b.mp4").exists()
    assert (inbox / "b.txt").exists()
    assert result.warning is not None
    assert "b.mp4" in result.warning


def test_edge5_one_plus_one_matching_stem(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "take1.mp4", b"x")
    _write(inbox / "take1.md", "# Hello world\n\nbody")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert (result.episode_dir / "script.txt").exists()
    assert not (result.episode_dir / "script.md").exists()


# ---------- Existing invariants ----------

def test_collision_appends_numeric_suffix(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    existing = episodes / "2026-05-02-hello-world"
    _write(existing / "raw.mp4", b"old")
    _write(inbox / "take.mp4", b"new")
    _write(inbox / "take.txt", "Hello world. Rest of script.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert result.slug == "2026-05-02-hello-world-2"
    assert (result.episode_dir / "raw.mp4").read_bytes() == b"new"
    assert (existing / "raw.mp4").read_bytes() == b"old"


def test_resume_with_explicit_slug(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(episodes / "previous-episode" / "raw.mov", b"x")
    result = pick_episode(
        inbox=inbox, episodes=episodes, today="2026-05-02", slug_arg="previous-episode"
    )
    assert result.slug == "previous-episode"
    assert result.resumed is True


def test_explicit_slug_unknown_errors(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    with pytest.raises(PickupError, match="no episode"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02", slug_arg="nope")


def test_srt_script_extension_accepted(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "ep.mp4", b"x")
    _write(inbox / "ep.srt", "Subtitle body. Tail.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert (result.episode_dir / "script.txt").exists()


def test_same_mtime_script_tiebreak_prefers_txt(tmp_path: Path):
    # When two scripts share a stem AND mtime, .txt wins per SCRIPT_EXTS order.
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "ep.mp4", b"x")
    _write(inbox / "ep.txt", "Txt body. Tail.")
    _write(inbox / "ep.md", "# Md body\n\nTail.")
    _set_mtime(inbox / "ep.txt", 50)
    _set_mtime(inbox / "ep.md", 50)
    # 1+1 short-circuit doesn't apply (1 video + 2 scripts) → stem-pair path runs.
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    # The .txt got staged; .md is the orphan.
    assert (result.episode_dir / "script.txt").read_text(encoding="utf-8").startswith("Txt body")
    assert result.warning is not None
    assert "ep.md" in result.warning


def test_json_script_extension_accepted(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "ep.mp4", b"x")
    _write(inbox / "ep.json", '{"text": "JSON-shaped script body. Tail."}')
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-05-02")
    assert (result.episode_dir / "script.txt").exists()
