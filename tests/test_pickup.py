"""Tests for pickup.pick_episode."""
import json
from pathlib import Path

import pytest

from scripts.pickup import pick_episode, PickupResult, PickupError

SUPPORTED = (".mp4", ".mov", ".mkv", ".webm")


def _write(p: Path, content: bytes | str = b""):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        p.write_text(content, encoding="utf-8")
    else:
        p.write_bytes(content)


def test_pair_with_script_uses_derived_slug(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "raw.mp4", b"x")
    _write(inbox / "raw.txt", "Desktop software licensing, it turns out, is also a whole story.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")
    assert result.slug == "2026-04-30-desktop-software-licensing-it-turns-out-is"
    assert result.episode_dir == episodes / result.slug
    assert (result.episode_dir / "raw.mp4").exists()
    assert (result.episode_dir / "script.txt").exists()
    # inbox emptied
    assert not (inbox / "raw.mp4").exists()
    assert not (inbox / "raw.txt").exists()


def test_md_script_renamed_to_script_txt(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "take1.mp4", b"x")
    _write(inbox / "take1.md", "# Hello world\n\nbody")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")
    assert (result.episode_dir / "script.txt").exists()
    assert not (result.episode_dir / "script.md").exists()


def test_fallback_to_stem_when_no_script(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "launch-promo.mp4", b"x")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")
    assert result.slug == "launch-promo"
    assert result.warning is not None  # script-missing warning surfaced


def test_fallback_rejects_invalid_stem(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "Bad Name With Spaces.mp4", b"x")
    with pytest.raises(PickupError, match="invalid slug"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")


def test_collision_appends_numeric_suffix(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    # First episode already exists
    existing = episodes / "2026-04-30-hello-world"
    _write(existing / "raw.mp4", b"old")
    # New drop with same derived slug
    _write(inbox / "take.mp4", b"new")
    _write(inbox / "take.txt", "Hello world. Rest of script.")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")
    assert result.slug == "2026-04-30-hello-world-2"
    assert (result.episode_dir / "raw.mp4").read_bytes() == b"new"
    # original untouched
    assert (existing / "raw.mp4").read_bytes() == b"old"


def test_resume_with_explicit_slug(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(episodes / "previous-episode" / "raw.mov", b"x")
    result = pick_episode(
        inbox=inbox, episodes=episodes, today="2026-04-30", slug_arg="previous-episode"
    )
    assert result.slug == "previous-episode"
    assert result.episode_dir == episodes / "previous-episode"
    assert result.resumed is True


def test_explicit_slug_unknown_errors(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    with pytest.raises(PickupError, match="no episode"):
        pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30", slug_arg="nope")


def test_fifo_picks_oldest_when_multiple(tmp_path: Path):
    import os, time
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    _write(inbox / "older.mp4", b"x")
    _write(inbox / "older.txt", "First. tail")
    older_time = time.time() - 100
    os.utime(inbox / "older.mp4", (older_time, older_time))
    os.utime(inbox / "older.txt", (older_time, older_time))
    _write(inbox / "newer.mp4", b"y")
    _write(inbox / "newer.txt", "Second. tail")
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")
    assert "first" in result.slug


def test_empty_inbox_no_episodes_returns_idle(tmp_path: Path):
    inbox = tmp_path / "inbox"
    episodes = tmp_path / "episodes"
    inbox.mkdir()
    episodes.mkdir()
    result = pick_episode(inbox=inbox, episodes=episodes, today="2026-04-30")
    assert result.idle is True
