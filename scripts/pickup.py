"""Episode pickup: pair video+script, derive slug, move to episodes/<slug>/.

Pairing rules (HOM-85):
* 0 files                       -> idle
* videos > 0, scripts == 0      -> error (script required for slug derivation)
* scripts > 0, videos == 0      -> error (orphan scripts)
* exactly 1 video + 1 script    -> pair regardless of stem
* multi-file, >=1 stem-pair     -> FIFO oldest pair; orphans warned, left in inbox
* multi-file, no stem-pair      -> error
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import date as _date
from pathlib import Path

from scripts.slugify import derive_slug

SUPPORTED_EXTS = (".mp4", ".mov", ".mkv", ".webm")
# Order matters for stem-collision tie-breaking — keep .txt first.
SCRIPT_EXTS = (".txt", ".md", ".srt", ".json")


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
    return sorted(
        (p for p in inbox.iterdir()
         if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS),
        key=lambda p: p.stat().st_mtime,
    )


def _find_scripts(inbox: Path) -> list[Path]:
    if not inbox.exists():
        return []
    # Sort by mtime, then by SCRIPT_EXTS index so same-mtime ties are
    # deterministic (.txt wins over .md wins over .srt wins over .json).
    return sorted(
        (p for p in inbox.iterdir()
         if p.is_file() and p.suffix.lower() in SCRIPT_EXTS),
        key=lambda p: (p.stat().st_mtime, SCRIPT_EXTS.index(p.suffix.lower())),
    )


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


def _stage_pair(
    *,
    video: Path,
    script: Path,
    episodes: Path,
    today: str,
    warning: str | None,
) -> PickupResult:
    text = script.read_text(encoding="utf-8")
    slug = derive_slug(text, date=today)
    slug = _resolve_collision(episodes, slug)
    ep_dir = episodes / slug
    ep_dir.mkdir(parents=True, exist_ok=True)

    raw_dst = ep_dir / f"raw{video.suffix.lower()}"
    shutil.move(str(video), str(raw_dst))

    # script.txt is canonical — extension normalized regardless of source (.txt/.md/.srt/.json).
    script_dst = ep_dir / "script.txt"
    shutil.move(str(script), str(script_dst))

    return PickupResult(
        slug=slug,
        episode_dir=ep_dir,
        raw_path=raw_dst,
        script_path=script_dst,
        warning=warning,
    )


def pick_episode(
    *,
    inbox: Path,
    episodes: Path,
    today: str,
    slug_arg: str | None = None,
) -> PickupResult:
    """Resolve which episode to work on and stage its files."""
    if slug_arg:
        return _resume_existing(episodes, slug_arg)

    videos = _find_videos(inbox)
    scripts = _find_scripts(inbox)

    if not videos and not scripts:
        return PickupResult(slug="", episode_dir=Path(), raw_path=None, script_path=None, idle=True)
    if not videos:
        raise PickupError(
            f"missing video — orphan scripts: {[s.name for s in scripts]}"
        )
    if not scripts:
        raise PickupError(
            "missing script — pickup requires a paired script for slug derivation"
        )

    # 1+1 single-pair convenience: trust the user's intent regardless of stems.
    if len(videos) == 1 and len(scripts) == 1:
        return _stage_pair(
            video=videos[0],
            script=scripts[0],
            episodes=episodes,
            today=today,
            warning=None,
        )

    # General path: stem-pair.
    pairs: list[tuple[Path, Path]] = []
    unpaired_videos: list[Path] = []
    paired_script_names: set[str] = set()
    for v in videos:
        match = next(
            (s for s in scripts
             if s.stem == v.stem and s.name not in paired_script_names),
            None,
        )
        if match:
            pairs.append((v, match))
            paired_script_names.add(match.name)
        else:
            unpaired_videos.append(v)
    unpaired_scripts = [s for s in scripts if s.name not in paired_script_names]

    if not pairs:
        raise PickupError(
            f"no video↔script pairs (stems must match): "
            f"videos={[v.name for v in videos]}, scripts={[s.name for s in scripts]}"
        )

    video, script = pairs[0]
    warning_parts: list[str] = []
    if unpaired_videos:
        warning_parts.append(
            f"orphan video(s) left in inbox: {[v.name for v in unpaired_videos]}"
        )
    if unpaired_scripts:
        warning_parts.append(
            f"orphan script(s) left in inbox: {[s.name for s in unpaired_scripts]}"
        )
    leftover_pairs = pairs[1:]
    if leftover_pairs:
        warning_parts.append(
            f"additional paired episode(s) left in inbox: "
            f"{[v.name for v, _ in leftover_pairs]}"
        )
    warning = "; ".join(warning_parts) or None
    return _stage_pair(
        video=video, script=script, episodes=episodes, today=today, warning=warning,
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
