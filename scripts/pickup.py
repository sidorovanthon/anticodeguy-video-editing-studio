"""Episode pickup: pair video+script, derive slug, move to episodes/<slug>/.

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §3.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import date as _date
from pathlib import Path

from scripts.slugify import derive_slug

SUPPORTED_EXTS = (".mp4", ".mov", ".mkv", ".webm")
SCRIPT_EXTS = (".txt", ".md")
LEGACY_SLUG_RE = re.compile(r"^[a-z0-9._-]+$")


class PickupError(Exception):
    """Raised when pickup cannot proceed and the user must intervene."""


@dataclass
class PickupResult:
    slug: str
    episode_dir: Path
    raw_path: Path | None
    script_path: Path | None
    resumed: bool = False
    idle: bool = False
    warning: str | None = None

    def to_json(self) -> str:
        d = asdict(self)
        d["episode_dir"] = str(self.episode_dir)
        d["raw_path"] = str(self.raw_path) if self.raw_path else None
        d["script_path"] = str(self.script_path) if self.script_path else None
        return json.dumps(d, ensure_ascii=False)


def _find_videos(inbox: Path) -> list[Path]:
    if not inbox.exists():
        return []
    return [
        p for p in inbox.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    ]


def _find_script_for(video: Path) -> Path | None:
    for ext in SCRIPT_EXTS:
        candidate = video.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


def _resolve_collision(episodes: Path, slug: str) -> str:
    if not (episodes / slug).exists():
        return slug
    n = 2
    while (episodes / f"{slug}-{n}").exists():
        n += 1
    return f"{slug}-{n}"


def _resume_existing(episodes: Path, slug: str) -> PickupResult:
    ep_dir = episodes / slug
    if not ep_dir.is_dir():
        raise PickupError(f"no episode named {slug!r} — episodes/{slug}/ does not exist")
    raw_candidates = [p for p in ep_dir.iterdir() if p.stem == "raw" and p.suffix.lower() in SUPPORTED_EXTS]
    if len(raw_candidates) > 1:
        raise PickupError(f"ambiguous: multiple raw.* in episodes/{slug}/")
    raw = raw_candidates[0] if raw_candidates else None
    script = ep_dir / "script.txt" if (ep_dir / "script.txt").exists() else None
    return PickupResult(slug=slug, episode_dir=ep_dir, raw_path=raw, script_path=script, resumed=True)


def pick_episode(
    *,
    inbox: Path,
    episodes: Path,
    today: str,
    slug_arg: str | None = None,
) -> PickupResult:
    """Resolve which episode to work on and stage its files.

    Behavior matches §3.4 of the design spec exactly.
    """
    if slug_arg:
        return _resume_existing(episodes, slug_arg)

    videos = _find_videos(inbox)
    if not videos:
        return PickupResult(slug="", episode_dir=Path(), raw_path=None, script_path=None, idle=True)

    # FIFO: oldest mtime first
    videos.sort(key=lambda p: p.stat().st_mtime)
    video = videos[0]
    script = _find_script_for(video)

    warning: str | None = None
    if script is not None:
        text = script.read_text(encoding="utf-8")
        slug = derive_slug(text, date=today)
    else:
        stem = video.stem
        if not LEGACY_SLUG_RE.match(stem):
            raise PickupError(
                f"invalid slug derived from filename {video.name!r} "
                f"(legacy fallback expects ^[a-z0-9._-]+$). "
                f"Either drop a paired script.txt next to it or rename the file to kebab-case."
            )
        slug = stem
        warning = f"no script paired with {video.name!r} — using legacy stem-based slug"

    slug = _resolve_collision(episodes, slug)
    ep_dir = episodes / slug
    ep_dir.mkdir(parents=True, exist_ok=True)

    raw_dst = ep_dir / f"raw{video.suffix.lower()}"
    shutil.move(str(video), str(raw_dst))

    script_dst: Path | None = None
    if script is not None:
        script_dst = ep_dir / "script.txt"
        shutil.move(str(script), str(script_dst))

    return PickupResult(
        slug=slug,
        episode_dir=ep_dir,
        raw_path=raw_dst,
        script_path=script_dst,
        warning=warning,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Episode pickup orchestrator step.")
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--slug", type=str, default=None, help="Resume an existing episode.")
    parser.add_argument("--today", type=str, default=None, help="Override today's date (YYYY-MM-DD).")
    args = parser.parse_args(argv)

    today = args.today or _date.today().isoformat()
    try:
        result = pick_episode(
            inbox=args.inbox, episodes=args.episodes, today=today, slug_arg=args.slug
        )
    except PickupError as e:
        print(f"pickup error: {e}", file=sys.stderr)
        return 2
    print(result.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
