# Pipeline & Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the orchestrator-side pipeline & enforcement layer per `docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md` — three glue scripts, a rewritten slash command with sub-agent + Skill briefs, hygiene fixes, and verifying tests.

**Architecture:** Three pure-Python scripts under `scripts/` (no upstream patches to `video-use` or `hyperframes`), wired together by a rewritten `.claude/commands/edit-episode.md` that runs Phase 1 inline, dispatches Phase 2 as a sub-agent (`Agent` tool with verbatim brief), and Phase 3 as a `Skill` invocation (with verbatim brief). Each script is unit-tested with pytest; the scaffold script also has an integration test that exercises real `npx hyperframes init`.

**Tech Stack:** Python 3.11+ (stdlib + pytest), Node.js (`npx hyperframes`), `ffprobe` (PATH), Bash + PowerShell shell-out from the slash command.

---

## File Structure

**Created:**
- `pyproject.toml` — Python project metadata + pytest dev-dep declaration.
- `scripts/__init__.py` — empty marker (makes `scripts` importable for tests).
- `scripts/slugify.py` — pure-functional slug derivation (no I/O), so tests are fast and exhaustive.
- `scripts/pickup.py` — episode pickup CLI: pair video+script in `inbox/`, derive slug, move to `episodes/<slug>/`.
- `scripts/remap_transcript.py` — Scribe `raw.json` + `edl.json` → hyperframes-schema `final.json`.
- `scripts/scaffold_hyperframes.py` — wraps `npx hyperframes init` and applies post-init patches.
- `tests/__init__.py` — empty marker.
- `tests/test_slugify.py` — unit tests for slug derivation.
- `tests/test_pickup.py` — unit tests for pickup using `tmp_path`.
- `tests/test_remap_transcript.py` — golden-file unit tests.
- `tests/test_scaffold_hyperframes.py` — integration test that actually calls `npx hyperframes init`.
- `tests/fixtures/scribe_raw.json` — synthetic Scribe transcript for remap tests.
- `tests/fixtures/sample_edl.json` — synthetic EDL for remap tests.
- `tests/fixtures/expected_final.json` — golden output for remap tests.
- `docs/cheatsheets/hyperframes.md` — moved from `init/hyperframes-cheatsheet.md`.
- `docs/cheatsheets/video-use.md` — moved from `init/video-use-cheatsheet.md`.

**Modified:**
- `.claude/commands/edit-episode.md` — full rewrite (Phase 1 → Phase 2 sub-agent → glue → Phase 3 Skill → studio).
- `.gitignore` — add `*.jsonl`, `scripts/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/`, `.venv/`.
- `.claude/settings.local.json` — add `PYTHONUTF8=1` to env (create file if absent).

**Deleted:**
- `init/` (after cheatsheets moved and `.jsonl` logs removed).

**Why this split:** `slugify.py` is separated from `pickup.py` because it is purely string-functional and benefits from exhaustive tests with no filesystem setup. `pickup.py` is the CLI + filesystem layer on top. The scaffold script is independent of pickup/remap and orchestrated only from the slash command.

---

## Task 1: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `scripts/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "anticodeguy-video-editing-studio"
version = "0.1.0"
description = "Orchestrator for video-use → hyperframes pipeline."
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: Create empty package markers and fixtures dir**

Write empty files:
- `scripts/__init__.py` (empty)
- `tests/__init__.py` (empty)
- `tests/fixtures/.gitkeep` (empty)

- [ ] **Step 3: Update `.gitignore`**

Append these lines (preserve existing content):

```
# Python
*.pyc
__pycache__/
scripts/__pycache__/
tests/__pycache__/
.pytest_cache/
.venv/

# Session logs
*.jsonl
```

- [ ] **Step 4: Verify pytest installs and runs**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest --version
```

Expected: pytest version printed (≥8.0).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml scripts/__init__.py tests/__init__.py tests/fixtures/.gitkeep .gitignore
git commit -m "chore: bootstrap Python project with pytest"
```

---

## Task 2: `scripts/slugify.py` — pure-functional slug derivation

**Files:**
- Create: `scripts/slugify.py`
- Test: `tests/test_slugify.py`

- [ ] **Step 1: Write failing tests**

`tests/test_slugify.py`:

```python
"""Tests for slugify.derive_slug."""
import pytest
from scripts.slugify import derive_slug


def test_simple_english_sentence():
    text = "Desktop software licensing, it turns out, is also a whole story."
    assert derive_slug(text, date="2026-04-30") == (
        "2026-04-30-desktop-software-licensing-it-turns-out-is"
    )


def test_no_terminal_punctuation_uses_first_line():
    text = "Hello world\n\nrest of script"
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-hello-world"


def test_first_paragraph_is_inspected_for_terminal_punct():
    text = "First sentence. Second sentence."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-first-sentence"


def test_question_mark_terminates():
    text = "Why does this work? Because it does."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-why-does-this-work"


def test_exclamation_terminates():
    text = "Wow! This is great."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-wow"


def test_cyrillic_transliteration():
    text = "Привет мир, как дела?"
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-privet-mir-kak-dela"


def test_accented_latin_strips_to_ascii():
    text = "Café résumé naïve."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-cafe-resume-naive"


def test_60_char_cap_with_word_boundary():
    text = "This is a very long sentence that absolutely must be truncated somewhere reasonable."
    slug = derive_slug(text, date="2026-04-30")
    title_part = slug[len("2026-04-30-"):]
    assert len(title_part) <= 60
    assert not title_part.endswith("-")
    assert "-trunc" not in title_part  # backed up before mid-word


def test_empty_input_returns_just_date_with_dash():
    assert derive_slug("", date="2026-04-30") == "2026-04-30-untitled"


def test_only_punctuation_returns_untitled():
    assert derive_slug("...!?,", date="2026-04-30") == "2026-04-30-untitled"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_slugify.py -v
```

Expected: ImportError or all tests fail with module-not-found.

- [ ] **Step 3: Implement `scripts/slugify.py`**

```python
"""Pure-functional slug derivation from author script content.

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §3.2.
"""
import re
import unicodedata

CYRILLIC_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

TITLE_CAP = 45


def _transliterate(text: str) -> str:
    """Cyrillic→ASCII via explicit map, accented Latin→ASCII via NFKD, lowercase."""
    text = text.lower()
    out = []
    for ch in text:
        if ch in CYRILLIC_MAP:
            out.append(CYRILLIC_MAP[ch])
        else:
            decomposed = unicodedata.normalize("NFKD", ch)
            ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
            out.append(ascii_only)
    return "".join(out)


def _slugify_token(text: str) -> str:
    """Reduce to [a-z0-9-], collapse runs, trim ends."""
    text = _transliterate(text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text


def _first_sentence(text: str) -> str:
    """Take everything up to the first .!? — falling back to the first non-empty line."""
    text = text.lstrip()
    if not text:
        return ""
    paragraph = text.split("\n\n", 1)[0]
    match = re.search(r"[.!?]", paragraph)
    if match:
        return paragraph[: match.start()]
    return paragraph.split("\n", 1)[0]


def _cap_at_word_boundary(slug: str, cap: int) -> str:
    if len(slug) <= cap:
        return slug
    truncated = slug[:cap]
    last_dash = truncated.rfind("-")
    if last_dash > 0:
        return truncated[:last_dash]
    return truncated


def derive_slug(script_text: str, date: str) -> str:
    """Derive a slug from the script's first sentence, prefixed with date.

    Args:
        script_text: full content of the user's script.txt.
        date: ISO date string in YYYY-MM-DD format.

    Returns:
        slug like "2026-04-30-desktop-software-licensing-it-turns-out-is".
        Always starts with "<date>-" and ends without a trailing dash.
        If the script yields no usable title, returns "<date>-untitled".
    """
    sentence = _first_sentence(script_text)
    title = _slugify_token(sentence)
    title = _cap_at_word_boundary(title, TITLE_CAP)
    if not title:
        title = "untitled"
    return f"{date}-{title}"
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_slugify.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/slugify.py tests/test_slugify.py
git commit -m "feat(scripts): add pure-functional slug derivation"
```

---

## Task 3: `scripts/pickup.py` — episode pickup CLI

**Files:**
- Create: `scripts/pickup.py`
- Test: `tests/test_pickup.py`

- [ ] **Step 1: Write failing tests**

`tests/test_pickup.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_pickup.py -v
```

Expected: ImportError on `scripts.pickup`.

- [ ] **Step 3: Implement `scripts/pickup.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_pickup.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/pickup.py tests/test_pickup.py
git commit -m "feat(scripts): add episode pickup with script-paired slug derivation"
```

---

## Task 4: `scripts/remap_transcript.py` — Scribe → hyperframes captions schema

**Files:**
- Create: `scripts/remap_transcript.py`
- Create: `tests/fixtures/scribe_raw.json`
- Create: `tests/fixtures/sample_edl.json`
- Create: `tests/fixtures/expected_final.json`
- Test: `tests/test_remap_transcript.py`

- [ ] **Step 1: Write fixture files**

`tests/fixtures/scribe_raw.json` (synthetic Scribe schema — minimal but realistic):

```json
{
  "language_code": "en",
  "language_probability": 0.99,
  "text": "Hello world this is a test",
  "words": [
    {"text": "Hello", "type": "word", "start": 1.0, "end": 1.3, "speaker_id": "S0"},
    {"text": " ", "type": "spacing", "start": 1.3, "end": 1.4, "speaker_id": "S0"},
    {"text": "world", "type": "word", "start": 1.4, "end": 1.8, "speaker_id": "S0"},
    {"text": "(laughs)", "type": "audio_event", "start": 2.0, "end": 2.5, "speaker_id": "S0"},
    {"text": "this", "type": "word", "start": 5.0, "end": 5.2, "speaker_id": "S0"},
    {"text": "is", "type": "word", "start": 5.3, "end": 5.4, "speaker_id": "S0"},
    {"text": "a", "type": "word", "start": 5.5, "end": 5.6, "speaker_id": "S0"},
    {"text": "test", "type": "word", "start": 5.7, "end": 6.0, "speaker_id": "S0"}
  ]
}
```

`tests/fixtures/sample_edl.json`:

```json
{
  "version": 1,
  "sources": {"raw": "/abs/path/raw.mp4"},
  "ranges": [
    {"source": "raw", "start": 1.0, "end": 1.9, "beat": "HOOK", "quote": "Hello world", "reason": ""},
    {"source": "raw", "start": 5.0, "end": 6.1, "beat": "BODY", "quote": "this is a test", "reason": ""}
  ],
  "total_duration_s": 2.0
}
```

`tests/fixtures/expected_final.json`:

```json
[
  {"text": "Hello", "start": 0.0, "end": 0.3},
  {"text": "world", "start": 0.4, "end": 0.8},
  {"text": "this", "start": 0.9, "end": 1.1},
  {"text": "is", "start": 1.2, "end": 1.3},
  {"text": "a", "start": 1.4, "end": 1.5},
  {"text": "test", "start": 1.6, "end": 1.9}
]
```

(Math check: range 0 keeps Hello[1.0-1.3]+world[1.4-1.8], dropped (laughs) outside range. Cumulative offset before range 0 = 0; word output_start = 1.0-1.0+0 = 0.0, end = 1.3-1.0+0 = 0.3. After range 0, offset += (1.9-1.0) = 0.9. Range 1: this[5.0-5.2] → 5.0-5.0+0.9 = 0.9, 5.2-5.0+0.9 = 1.1. test[5.7-6.0] → 0.7+0.9 = 1.6, 1.0+0.9 = 1.9.)

- [ ] **Step 2: Write failing tests**

`tests/test_remap_transcript.py`:

```python
"""Tests for remap_transcript."""
import json
import math
from pathlib import Path

import pytest

from scripts.remap_transcript import remap

FIXTURES = Path(__file__).parent / "fixtures"


def _approx_equal(a: list[dict], b: list[dict]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x["text"] != y["text"]:
            return False
        if not math.isclose(x["start"], y["start"], abs_tol=1e-6):
            return False
        if not math.isclose(x["end"], y["end"], abs_tol=1e-6):
            return False
    return True


def test_golden_remap():
    raw = json.loads((FIXTURES / "scribe_raw.json").read_text(encoding="utf-8"))
    edl = json.loads((FIXTURES / "sample_edl.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "expected_final.json").read_text(encoding="utf-8"))
    actual = remap(raw=raw, edl=edl)
    assert _approx_equal(actual, expected), f"mismatch:\nactual={actual}\nexpected={expected}"


def test_audio_events_dropped():
    raw = {"words": [
        {"text": "(laughs)", "type": "audio_event", "start": 1.0, "end": 1.5, "speaker_id": "S0"},
        {"text": "hi", "type": "word", "start": 2.0, "end": 2.2, "speaker_id": "S0"},
    ]}
    edl = {"sources": {"r": "x"}, "ranges": [{"source": "r", "start": 0.0, "end": 3.0}]}
    out = remap(raw=raw, edl=edl)
    assert out == [{"text": "hi", "start": 2.0, "end": 2.2}]


def test_spacing_dropped():
    raw = {"words": [
        {"text": "hi", "type": "word", "start": 1.0, "end": 1.2, "speaker_id": "S0"},
        {"text": " ", "type": "spacing", "start": 1.2, "end": 1.3, "speaker_id": "S0"},
        {"text": "you", "type": "word", "start": 1.3, "end": 1.5, "speaker_id": "S0"},
    ]}
    edl = {"sources": {"r": "x"}, "ranges": [{"source": "r", "start": 0.0, "end": 2.0}]}
    out = remap(raw=raw, edl=edl)
    assert [w["text"] for w in out] == ["hi", "you"]


def test_word_in_cut_zone_dropped():
    raw = {"words": [
        {"text": "kept", "type": "word", "start": 1.0, "end": 1.5, "speaker_id": "S0"},
        {"text": "cut", "type": "word", "start": 3.0, "end": 3.5, "speaker_id": "S0"},
        {"text": "kept2", "type": "word", "start": 5.0, "end": 5.5, "speaker_id": "S0"},
    ]}
    edl = {"sources": {"r": "x"}, "ranges": [
        {"source": "r", "start": 1.0, "end": 2.0},
        {"source": "r", "start": 5.0, "end": 6.0},
    ]}
    out = remap(raw=raw, edl=edl)
    assert [w["text"] for w in out] == ["kept", "kept2"]


def test_output_only_has_text_start_end():
    raw = {"words": [{"text": "hi", "type": "word", "start": 1.0, "end": 1.2, "speaker_id": "S0"}]}
    edl = {"sources": {"r": "x"}, "ranges": [{"source": "r", "start": 0.0, "end": 2.0}]}
    out = remap(raw=raw, edl=edl)
    assert set(out[0].keys()) == {"text", "start", "end"}
```

- [ ] **Step 3: Run tests to verify they fail**

```powershell
pytest tests/test_remap_transcript.py -v
```

Expected: ImportError on `scripts.remap_transcript`.

- [ ] **Step 4: Implement `scripts/remap_transcript.py`**

```python
"""Remap Scribe word-level transcript to hyperframes captions schema.

Input:  edit/transcripts/raw.json (Scribe nested {words: [...]})
        edit/edl.json             (video-use EDL)
Output: edit/transcripts/final.json (flat [{text,start,end}, ...])

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §4.3.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def remap(*, raw: dict, edl: dict) -> list[dict]:
    """Convert Scribe word-level + EDL ranges → hyperframes captions array.

    Drops `type != "word"` entries (spacing, audio_event, ...).
    Drops words whose source-timeline `start` falls outside any kept range.
    Output timeline = cumulative_output_offset + (word.start - range.start).
    """
    ranges = edl.get("ranges", [])
    output: list[dict] = []
    cumulative = 0.0
    for r in ranges:
        r_start = float(r["start"])
        r_end = float(r["end"])
        for w in raw.get("words", []):
            if w.get("type") != "word":
                continue
            ws = float(w["start"])
            if not (r_start <= ws < r_end):
                continue
            we = float(w["end"])
            output.append({
                "text": w["text"],
                "start": round(cumulative + (ws - r_start), 6),
                "end": round(cumulative + (we - r_start), 6),
            })
        cumulative += (r_end - r_start)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remap Scribe transcript to hyperframes captions schema.")
    parser.add_argument("--raw", type=Path, required=True, help="Path to edit/transcripts/raw.json")
    parser.add_argument("--edl", type=Path, required=True, help="Path to edit/edl.json")
    parser.add_argument("--out", type=Path, required=True, help="Path to write edit/transcripts/final.json")
    args = parser.parse_args(argv)

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    edl = json.loads(args.edl.read_text(encoding="utf-8"))
    result = remap(raw=raw, edl=edl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(result)} word entries to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
pytest tests/test_remap_transcript.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/remap_transcript.py tests/test_remap_transcript.py tests/fixtures/scribe_raw.json tests/fixtures/sample_edl.json tests/fixtures/expected_final.json
git commit -m "feat(scripts): add Scribe→hyperframes captions schema remap"
```

---

## Task 5: `scripts/scaffold_hyperframes.py` — patch helpers (pure functions)

**Files:**
- Create: `scripts/scaffold_hyperframes.py`
- Test: `tests/test_scaffold_hyperframes.py` (unit-test portion)

- [ ] **Step 1: Write failing unit tests**

`tests/test_scaffold_hyperframes.py`:

```python
"""Unit tests for scaffold_hyperframes pure-functional helpers."""
import json
from pathlib import Path

import pytest

from scripts.scaffold_hyperframes import (
    patch_index_html,
    patch_meta_json,
    build_package_json,
)

DEFAULT_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }
      html,
      body {
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: #000;
      }
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="10"
      data-width="1920"
      data-height="1080"
    >
      
      

      <!--
        Add your clips here. Example:
        <div id="title" class="clip" data-start="0" data-duration="5" data-track-index="1"
             style="font-size: 64px; color: #fff; padding: 40px">
          Hello World
        </div>
      -->
    </div>

    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      // Example: tl.from("#title", { opacity: 0, y: -50, duration: 1 }, 0);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def test_patch_index_html_replaces_dimensions_and_duration():
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    assert 'content="width=1080, height=1920"' in out
    assert "width: 1080px" in out
    assert "height: 1920px" in out
    assert 'data-width="1080"' in out
    assert 'data-height="1920"' in out
    assert 'data-duration="58.8"' in out
    # 1920×1080 defaults are gone
    assert "1920, height=1080" not in out
    assert "data-width=\"1920\"" not in out


def test_patch_index_html_injects_video_audio_pair():
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    # canonical pattern: video muted playsinline + separate audio
    assert '<video id="el-video"' in out
    assert 'muted' in out
    assert 'playsinline' in out
    assert '<audio id="el-audio"' in out
    assert out.count('src="../edit/final.mp4"') == 2  # both elements
    # example-clip comment removed
    assert "Add your clips here" not in out


def test_patch_index_html_no_data_has_audio():
    """Canonical pattern uses two-element pair, NOT data-has-audio."""
    out = patch_index_html(DEFAULT_INDEX_HTML, width=1080, height=1920, duration=58.8, video_src="../edit/final.mp4")
    assert "data-has-audio" not in out


def test_patch_meta_json_overwrites_id_and_name():
    src = {"id": "hyperframes", "name": "hyperframes", "createdAt": "2026-04-30T07:58:27.115Z"}
    out = patch_meta_json(src, slug="2026-04-30-hello-world")
    assert out["id"] == "2026-04-30-hello-world"
    assert out["name"] == "2026-04-30-hello-world"
    assert out["createdAt"] == "2026-04-30T07:58:27.115Z"  # preserved


def test_build_package_json_declares_hyperframes_devdep():
    pkg = build_package_json(slug="2026-04-30-hello-world", hyperframes_version="^0.4.39")
    assert pkg["name"] == "2026-04-30-hello-world"
    assert "hyperframes" in pkg["devDependencies"]
    assert pkg["devDependencies"]["hyperframes"] == "^0.4.39"
    assert "private" in pkg and pkg["private"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_scaffold_hyperframes.py -v
```

Expected: ImportError on `scripts.scaffold_hyperframes`.

- [ ] **Step 3: Implement `scripts/scaffold_hyperframes.py` (pure-functional helpers only — orchestration in next task)**

```python
"""Scaffold hyperframes/ project: wrap `npx hyperframes init` and patch outputs.

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §4.2.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_AUDIO_PAIR_TEMPLATE = """      <video id="el-video" data-start="0" data-track-index="0"
             src="{src}" muted playsinline></video>
      <audio id="el-audio" data-start="0" data-track-index="1"
             src="{src}" data-volume="1"></audio>"""


def patch_index_html(html: str, *, width: int, height: int, duration: float, video_src: str) -> str:
    """Apply the four known-wrong-location patches to init's index.html."""
    # 1. <meta name="viewport">
    html = re.sub(
        r'<meta name="viewport" content="width=\d+, height=\d+"\s*/>',
        f'<meta name="viewport" content="width={width}, height={height}" />',
        html,
    )
    # 2. body width/height in inline <style>
    html = re.sub(r"width:\s*\d+px;", f"width: {width}px;", html, count=1)
    html = re.sub(r"height:\s*\d+px;", f"height: {height}px;", html, count=1)
    # 3. root div data-* attrs
    html = re.sub(r'data-width="\d+"', f'data-width="{width}"', html)
    html = re.sub(r'data-height="\d+"', f'data-height="{height}"', html)
    html = re.sub(r'data-duration="[\d.]+"', f'data-duration="{duration}"', html)
    # 4. inject video+audio pair, replace example-clip comment
    pair_html = VIDEO_AUDIO_PAIR_TEMPLATE.format(src=video_src)
    html = re.sub(
        r"(\s*\n\s*\n\s*<!--\s*\n\s*Add your clips here\..*?-->\s*)",
        f"\n      {pair_html.strip()}\n    ",
        html,
        flags=re.DOTALL,
    )
    return html


def patch_meta_json(meta: dict, *, slug: str) -> dict:
    """Overwrite id and name with episode slug; preserve other fields."""
    out = dict(meta)
    out["id"] = slug
    out["name"] = slug
    return out


def build_package_json(*, slug: str, hyperframes_version: str) -> dict:
    """Construct a minimal package.json that pins hyperframes as devDep."""
    return {
        "name": slug,
        "version": "0.1.0",
        "private": True,
        "devDependencies": {"hyperframes": hyperframes_version},
    }
```

- [ ] **Step 4: Run unit tests to verify they pass**

```powershell
pytest tests/test_scaffold_hyperframes.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/scaffold_hyperframes.py tests/test_scaffold_hyperframes.py
git commit -m "feat(scripts): add hyperframes scaffold patch helpers"
```

---

## Task 6: `scaffold_hyperframes.py` — orchestration + integration test

**Files:**
- Modify: `scripts/scaffold_hyperframes.py` (append orchestration)
- Modify: `tests/test_scaffold_hyperframes.py` (append integration test)

- [ ] **Step 1: Append failing integration test**

Append to `tests/test_scaffold_hyperframes.py`:

```python
import shutil


def _have_npx() -> bool:
    return shutil.which("npx") is not None


@pytest.mark.skipif(not _have_npx(), reason="npx not on PATH")
def test_scaffold_end_to_end(tmp_path: Path):
    """Calls real `npx hyperframes init`, applies patches, verifies all artifacts."""
    from scripts.scaffold_hyperframes import scaffold

    episode_dir = tmp_path / "ep"
    episode_dir.mkdir()
    # Place a tiny stand-in for final.mp4. ffprobe needs a real file but we'll
    # bypass ffprobe by passing dimensions explicitly.
    (episode_dir / "edit").mkdir()
    (episode_dir / "edit" / "final.mp4").write_bytes(b"")
    # Place a fake remapped transcript.
    (episode_dir / "edit" / "transcripts").mkdir()
    (episode_dir / "edit" / "transcripts" / "final.json").write_text(
        '[{"text":"hi","start":0,"end":0.2}]', encoding="utf-8"
    )

    scaffold(
        episode_dir=episode_dir,
        slug="2026-04-30-test-episode",
        width=1080,
        height=1920,
        duration=10.0,
        hyperframes_version="^0.4.39",
    )

    hf = episode_dir / "hyperframes"
    assert hf.is_dir()
    # init produces these
    assert (hf / "index.html").exists()
    assert (hf / "meta.json").exists()
    assert (hf / "hyperframes.json").exists()
    # we add these
    assert (hf / "package.json").exists()
    assert (hf / "transcript.json").exists()

    # NO video copy
    assert not (hf / "final.mp4").exists()

    # patches applied
    html = (hf / "index.html").read_text(encoding="utf-8")
    assert 'data-width="1080"' in html
    assert 'data-height="1920"' in html
    assert "<video" in html and "<audio" in html
    assert 'src="../edit/final.mp4"' in html
    assert "data-has-audio" not in html

    meta = json.loads((hf / "meta.json").read_text(encoding="utf-8"))
    assert meta["id"] == "2026-04-30-test-episode"
    assert meta["name"] == "2026-04-30-test-episode"

    pkg = json.loads((hf / "package.json").read_text(encoding="utf-8"))
    assert pkg["devDependencies"]["hyperframes"] == "^0.4.39"

    transcript = json.loads((hf / "transcript.json").read_text(encoding="utf-8"))
    assert transcript == [{"text": "hi", "start": 0, "end": 0.2}]
```

- [ ] **Step 2: Run integration test to verify it fails**

```powershell
pytest tests/test_scaffold_hyperframes.py::test_scaffold_end_to_end -v
```

Expected: ImportError on `scaffold` (not yet defined).

- [ ] **Step 3: Append orchestration to `scripts/scaffold_hyperframes.py`**

```python
def _run_init(episode_dir: Path) -> Path:
    """Run `npx hyperframes init hyperframes --yes` from inside episode_dir.

    Returns path to the created hyperframes/ subdirectory.
    """
    cmd = ["npx", "hyperframes", "init", "hyperframes", "--yes"]
    result = subprocess.run(
        cmd,
        cwd=episode_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=(sys.platform == "win32"),  # npx on Windows resolves via cmd.exe
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"npx hyperframes init failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    hf = episode_dir / "hyperframes"
    if not hf.is_dir():
        raise RuntimeError(f"npx hyperframes init reported success but {hf} does not exist")
    return hf


def _ffprobe_dimensions_and_duration(video: Path) -> tuple[int, int, float]:
    """Read width, height, duration from a video via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration",
        "-of", "json",
        str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    data = json.loads(result.stdout)
    width = int(data["streams"][0]["width"])
    height = int(data["streams"][0]["height"])
    duration = float(data["format"]["duration"])
    return width, height, duration


def scaffold(
    *,
    episode_dir: Path,
    slug: str,
    width: int | None = None,
    height: int | None = None,
    duration: float | None = None,
    hyperframes_version: str = "^0.4.39",
) -> Path:
    """End-to-end scaffold per design spec §4.2.

    Steps 1-6 in order. If width/height/duration are not provided, ffprobe the
    final.mp4 to get them. Returns the hyperframes/ directory path.
    """
    final_mp4 = episode_dir / "edit" / "final.mp4"
    final_json = episode_dir / "edit" / "transcripts" / "final.json"

    if width is None or height is None or duration is None:
        if not final_mp4.exists() or final_mp4.stat().st_size == 0:
            raise FileNotFoundError(
                f"need final.mp4 to ffprobe for dimensions, but {final_mp4} is missing or empty. "
                f"Pass width/height/duration explicitly to bypass."
            )
        width, height, duration = _ffprobe_dimensions_and_duration(final_mp4)

    hf = _run_init(episode_dir)

    # Patch index.html
    index_path = hf / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = patch_index_html(
        html, width=width, height=height, duration=duration,
        video_src="../edit/final.mp4",
    )
    index_path.write_text(html, encoding="utf-8")

    # Patch meta.json
    meta_path = hf / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = patch_meta_json(meta, slug=slug)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Add package.json
    pkg = build_package_json(slug=slug, hyperframes_version=hyperframes_version)
    (hf / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    # Copy transcript
    if final_json.exists():
        shutil.copyfile(final_json, hf / "transcript.json")

    return hf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold hyperframes/ project for an episode.")
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--slug", type=str, required=True)
    parser.add_argument("--hyperframes-version", type=str, default="^0.4.39")
    args = parser.parse_args(argv)
    hf = scaffold(
        episode_dir=args.episode_dir,
        slug=args.slug,
        hyperframes_version=args.hyperframes_version,
    )
    print(json.dumps({"hyperframes_dir": str(hf)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run integration test to verify it passes**

```powershell
pytest tests/test_scaffold_hyperframes.py::test_scaffold_end_to_end -v
```

Expected: 1 passed (takes ~2-5s due to real `npx`).

- [ ] **Step 5: Run full test suite for sanity**

```powershell
pytest -v
```

Expected: all tests pass (~20 total).

- [ ] **Step 6: Commit**

```bash
git add scripts/scaffold_hyperframes.py tests/test_scaffold_hyperframes.py
git commit -m "feat(scripts): orchestration end-to-end for hyperframes scaffold"
```

---

## Task 7: Move cheatsheets and clean `init/`

**Files:**
- Create: `docs/cheatsheets/hyperframes.md`
- Create: `docs/cheatsheets/video-use.md`
- Delete: `init/`

- [ ] **Step 1: Move cheatsheets**

```powershell
New-Item -ItemType Directory -Force -Path docs\cheatsheets | Out-Null
Move-Item -Path init\hyperframes-cheatsheet.md -Destination docs\cheatsheets\hyperframes.md
Move-Item -Path init\video-use-cheatsheet.md -Destination docs\cheatsheets\video-use.md
```

(Bash equivalent: `mkdir -p docs/cheatsheets && mv init/*-cheatsheet.md docs/cheatsheets/` — rename the files to drop `-cheatsheet` suffix.)

- [ ] **Step 2: Remove `init/` directory**

The `.jsonl` session logs in `init/` are not needed; they will be ignored by the new `*.jsonl` rule in `.gitignore` (Task 1) but the directory itself should go.

```powershell
Remove-Item -Recurse -Force init
```

- [ ] **Step 3: Verify**

```powershell
Test-Path docs\cheatsheets\hyperframes.md  # True
Test-Path docs\cheatsheets\video-use.md     # True
Test-Path init                               # False
```

- [ ] **Step 4: Commit**

```bash
git add docs/cheatsheets/hyperframes.md docs/cheatsheets/video-use.md
git rm -r init/  # if init/ was tracked; otherwise just commit
git commit -m "docs: relocate cheatsheets to docs/cheatsheets/, remove init/"
```

(If `init/` was never tracked — only the cheatsheets need adding; the deletion is a no-op for git but the working tree is cleaned.)

---

## Task 8: Configure `PYTHONUTF8=1` globally for this project

**Files:**
- Modify or create: `.claude/settings.local.json`

- [ ] **Step 1: Inspect existing settings**

```powershell
if (Test-Path .claude\settings.local.json) {
  Get-Content .claude\settings.local.json
} else {
  "no existing settings.local.json"
}
```

- [ ] **Step 2: Write `.claude/settings.local.json`**

If file is absent, create it with:

```json
{
  "env": {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8"
  }
}
```

If file exists, merge: add the `env` keys (preserving any existing keys via manual edit; the file may already have `permissions` etc.).

- [ ] **Step 3: Verify environment is applied**

In a new session, run:

```bash
python -c "import sys; print(sys.stdout.encoding)"
```

Expected: `utf-8`.

(In the current session, the env vars apply to subprocesses started by Claude Code's tools; restart of the session may be needed to pick up changes. Note this in the commit message.)

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "chore: enable PYTHONUTF8=1 to fix Windows cp1251 issue (retro 1.4)"
```

---

## Task 9: Rewrite `.claude/commands/edit-episode.md`

**Files:**
- Modify: `.claude/commands/edit-episode.md`

This is the integration step that wires everything together.

- [ ] **Step 1: Read the current file for reference**

```powershell
Get-Content .claude\commands\edit-episode.md
```

- [ ] **Step 2: Rewrite the file**

Replace the entire file content with:

````markdown
---
description: Run the video editing pipeline (pickup → video-use → hyperframes → studio) on an episode from inbox/ or by slug.
argument-hint: "[slug]"
---

You are orchestrating a three-phase video editing pipeline. Follow this recipe exactly. The skills `video-use` and `hyperframes` own all creative decisions; this command provides only structure, glue, and enforcement.

## Inputs

- `$1` (optional): episode slug. If omitted, pick from `inbox/`.

## Project layout (must hold)

```
inbox/<stem>.<video-ext>      -> drop zone, paired with <stem>.txt or .md script
inbox/<stem>.txt|.md          -> author script (optional but recommended)
episodes/<slug>/raw.<ext>     -> moved here at Phase 1
episodes/<slug>/script.txt    -> moved here at Phase 1 (always renamed to .txt)
episodes/<slug>/edit/         -> produced by video-use sub-agent (final.mp4 + raw.json + edl.json + project.md)
episodes/<slug>/edit/transcripts/final.json  -> emitted by orchestrator glue (output-timeline, hyperframes captions schema)
episodes/<slug>/hyperframes/  -> scaffolded by orchestrator + authored by hyperframes Skill
```

All paths passed to skills MUST be absolute. Substitute `<EPISODE_DIR>` etc. at runtime.

---

## Phase 1 — Pickup

Run `scripts/pickup.py` to pair video+script in `inbox/`, derive slug, and move files into `episodes/<slug>/`. Use the appropriate shell for the environment (Windows: PowerShell; otherwise Bash):

**PowerShell:**
```powershell
python scripts\pickup.py --inbox inbox --episodes episodes ${arg}
```
where `${arg}` is `--slug $1` if `$1` was given, otherwise empty.

**Bash:**
```bash
python scripts/pickup.py --inbox inbox --episodes episodes ${arg}
```

Parse the JSON on stdout. Fields: `slug`, `episode_dir`, `raw_path`, `script_path`, `resumed`, `idle`, `warning`.

- If `idle: true`: there is nothing in `inbox/` and no slug arg. Offer to relaunch the studio for the most recently modified `episodes/*/hyperframes/index.html` (run `npx hyperframes preview <that-dir> --port 3002` in the background and report the URL). If no such directory exists, report `nothing to do — drop a video in inbox/` and stop.
- If `warning` is set: display it to the user, then continue.
- Otherwise announce: `Episode: <slug>. Raw at <raw_path>. Script at <script_path or "(none)">.`

Set `EPISODE_DIR = <absolute path to episodes/<slug>>`.

---

## Phase 2 — Video edit (video-use sub-agent)

**Skip if** `<EPISODE_DIR>/edit/final.mp4` exists. Announce `Phase 2 already complete — skipping video-use.` and proceed.

Otherwise dispatch a sub-agent via the `Agent` tool with `subagent_type: general-purpose`. The brief — substitute absolute paths:

> You are the video-use sub-agent. Read `~/.claude/skills/video-use/SKILL.md` first, then edit `<EPISODE_DIR>/raw.<ext>` and write all outputs under `<EPISODE_DIR>/edit/`.
>
> **Author's script** is at `<EPISODE_DIR>/script.txt` (may be absent — check first). Treat it as ground truth for take selection and to verify ASR accuracy. Flag any divergence in your reasoning log.
>
> **Strategy confirmation (canonical resolution of Hard Rule 11 in this orchestrated context):** the user invoked `/edit-episode`, which constitutes pre-approved strategy: "edit `raw.<ext>` per the script at `script.txt`, output a tight talking-head cut to `final.mp4`, default pacing on the tighter end of Hard Rule 7's 30–200ms window, all canonical hygiene." Do not pause for further confirmation. If — and only if — the material clearly does not match this implicit strategy (wrong content type, script unrelated to footage, multi-speaker where solo expected), return early with a single specific question and no edits performed.
>
> **Pacing:** follow the "Cut craft (techniques)" section of the canon — silences ≥400ms cleanest cuts, 150–400ms usable with visual check, <150ms unsafe. Padding stays in 30–200ms (Hard Rule 7). Per Principle 5, the canon's launch-video example values (50ms / 80ms) are a worked example, not a mandate. Default lean for our content: tight end of the window, eliminate retakes/false starts.
>
> **Required outputs (all under `<EPISODE_DIR>/edit/`):**
> - `final.mp4` — rendered video.
> - `transcripts/raw.json` — Scribe word-level on source timeline (cached if exists; **never re-transcribe** per Hard Rule 9).
> - `edl.json` — final EDL per the canon's "EDL format". Functionally required: `ranges`, `sources`. Recommended: `total_duration_s`, `grade`, `subtitles`, `overlays`.
> - `project.md` — append a session block per the canon's "Memory — `project.md`" section.
>
> **Self-eval (canon's 8-step process, step 7):**
> - `helpers/timeline_view.py` on the rendered output at every cut boundary (±1.5s).
> - Sample first 2s, last 2s, 2–3 mid-points.
> - `ffprobe` on `final.mp4` — duration must match EDL `total_duration_s` within 100ms.
> - Cap at 3 self-eval passes.
> - Confirm Hard Rule 12 (outputs in `<edit>/`).
>
> **Environment:** `PYTHONUTF8=1` is set globally; do not override.
>
> Report what you did, what you skipped and why, and any divergence between `script.txt` and ASR.

After the sub-agent returns, verify `<EPISODE_DIR>/edit/final.mp4`, `transcripts/raw.json`, and `edl.json` exist. If any is missing, stop and surface the failure.

---

## Glue between Phase 2 and Phase 3

Run from project root:

```bash
python scripts/remap_transcript.py \
  --raw <EPISODE_DIR>/edit/transcripts/raw.json \
  --edl <EPISODE_DIR>/edit/edl.json \
  --out <EPISODE_DIR>/edit/transcripts/final.json
```

(Skip if `<EPISODE_DIR>/edit/transcripts/final.json` already exists — idempotent.)

---

## Phase 3 — Composition & studio (hyperframes Skill)

**Skip-build if** `<EPISODE_DIR>/hyperframes/index.html` exists. Skip the scaffold and Skill invocation; jump straight to the studio launch.

Otherwise scaffold first:

```bash
python scripts/scaffold_hyperframes.py \
  --episode-dir <EPISODE_DIR> \
  --slug <SLUG>
```

Then invoke the `hyperframes` skill via the `Skill` tool with this verbatim brief:

> Read `~/.agents/skills/hyperframes/SKILL.md` first, then build a HyperFrames composition in `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json` are in place. The video and audio are wired as a canonical `<video muted playsinline> + <audio>` pair both pointing at `../edit/final.mp4`. The word-level transcript (output-timeline, hyperframes captions schema) is at `hyperframes/transcript.json`.
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
>
> **Visual Identity Gate (canonical `<HARD-GATE>`):** before writing any composition HTML, follow the canon's gate order in SKILL.md §"Visual Identity Gate". The user's named style is **"Liquid Glass / iOS frosted glass"** — start at gate step 3: read `~/.agents/skills/hyperframes/visual-styles.md` for a matching named preset and apply it. If no matching preset exists, generate a minimal `DESIGN.md` per the canon's structure. Do not hardcode `#333` / `#3b82f6` / `Roboto`.
>
> **Multi-scene transitions:** if the composition has multiple scenes, the canon's "Scene Transitions (Non-Negotiable)" rules apply: always use transitions, every scene gets entrance animations, never exit animations except on the final scene.
>
> **Output Checklist (canonical):**
> 1. `npx hyperframes lint` — passes.
> 2. `npx hyperframes validate` — passes; built-in WCAG contrast audit produces no warnings.
> 3. `npx hyperframes inspect` — passes, or every reported overflow is intentional and marked.
> 4. `node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon. Read the JSON; check every flag (`offscreen`, `collision`, `invisible`, `paced-fast`, `paced-slow`); fix or justify.
>
> **Extra check we add (not in canon — orchestrator-imposed):** run `node ~/.agents/skills/hyperframes/scripts/contrast-report.mjs <hyperframes-dir>` and open the resulting `contrast-overlay.png` in the output dir. Fix any magenta regions; ideally clear yellow too. If absent or failing, do not block — log "extra check skipped/failed" and proceed.
>
> **Project memory:** append a session block to `<EPISODE_DIR>/edit/project.md` with Strategy / Decisions / Outstanding for this composition.
>
> **Studio launch:** after gates pass, launch the preview server in the background. Run from `<EPISODE_DIR>/hyperframes/`:
> - PowerShell: `Start-Process npx -ArgumentList 'hyperframes','preview','--port','3002' -WindowStyle Hidden`
> - Bash: `npx hyperframes preview --port 3002 &`
>
> Report `http://localhost:3002` to the user.

---

## Studio launch (skip-build path)

If Phase 3 was skipped because `index.html` already existed, run the studio launch above directly (use `--list` first to detect an already-running server and skip if found).

---

## Completion

Announce: `Done. Studio: http://localhost:3002. Episode: <EPISODE_DIR>.`

---

## Idempotency and rebuild guidance

The command is safe to re-run on the same slug. Skip rules:
1. `<EPISODE_DIR>/edit/final.mp4` exists → skip Phase 2.
2. `<EPISODE_DIR>/edit/transcripts/final.json` exists → skip glue remap.
3. `<EPISODE_DIR>/hyperframes/index.html` exists → skip scaffold and Skill, only relaunch studio.

To force re-cut: delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — **no Scribe re-spend**.

To re-compose only: delete `<EPISODE_DIR>/hyperframes/`. Phase 2 skipped; `final.mp4` and transcripts preserved.

---

## Error handling

Each phase is fail-fast. If `pickup.py`, `video-use` sub-agent, `remap_transcript.py`, `scaffold_hyperframes.py`, or `hyperframes` skill returns an error, stop, show what failed, and tell the user to fix and re-run `/edit-episode <slug>`. Do not retry; do not roll back partial outputs. Idempotency rules ensure re-running picks up where it failed.
````

- [ ] **Step 3: Verify the slash command parses**

The slash command is markdown — no programmatic test. Visually inspect that all phase headers are present, all paths are absolute, both verbatim briefs are intact, and the studio-launch protocol matches the verified shell syntax.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "feat: rewrite edit-episode for 3-phase pipeline with verbatim briefs"
```

---

## Task 10: Smoke-test pickup end-to-end

**Files:** none modified.

This is a manual sanity check that exercises Phase 1 only (cheap — no Scribe credits needed).

- [ ] **Step 1: Stage a test episode**

```powershell
# Use ffmpeg to make a 1-second silent test video, or just touch a fake one for pickup smoke
"placeholder" | Out-File -Encoding ascii inbox\smoke.mp4
"This is a smoke test. Body of the script." | Out-File -Encoding utf8 inbox\smoke.txt
```

- [ ] **Step 2: Run pickup directly**

```powershell
python scripts\pickup.py --inbox inbox --episodes episodes
```

Expected stdout (JSON): `slug` matches today's date + `-this-is-a-smoke-test`, `episode_dir` exists, `raw_path` and `script_path` are inside it.

- [ ] **Step 3: Verify filesystem state**

```powershell
Get-ChildItem inbox  # empty (or only has unrelated files)
Get-ChildItem episodes\$(Get-Date -Format yyyy-MM-dd)-this-is-a-smoke-test
```

Expected: directory contains `raw.mp4` and `script.txt`.

- [ ] **Step 4: Clean up**

```powershell
Remove-Item -Recurse -Force episodes\$(Get-Date -Format yyyy-MM-dd)-this-is-a-smoke-test
```

- [ ] **Step 5: No commit needed**

This task produces no artifacts.

---

## Task 11: Final test sweep + spec/plan cross-check

**Files:** none modified.

- [ ] **Step 1: Run the full test suite**

```powershell
pytest -v
```

Expected: all unit tests pass (~20). Integration test for scaffold passes (~2-5s with `npx`).

- [ ] **Step 2: Verify spec coverage**

Open `docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md` next to this plan. Walk each spec section (§3 pickup, §4.1/4.2/4.3 scripts, §4.4 glue order, §5.1/5.2 briefs, §6 idempotency, §7 hygiene, §8 out-of-scope, §9 open questions, §10 success criteria) and confirm a corresponding task implements or addresses it. List any gaps; if found, add tasks before declaring complete.

- [ ] **Step 3: Verify success criteria from spec §10 manually**

The full E2E test (Phase 2+3 with real Scribe + render) is out of scope for this plan because it spends real money. After this plan ships, the next manual run of `/edit-episode` on a real test episode is the success-criteria validation.

- [ ] **Step 4: Final commit**

If any cleanup is needed (stray files, missed `.gitignore` entries, etc.):

```bash
git status
git add -A
git commit -m "chore: final cleanup after pipeline implementation"
```

---

## Self-Review (run after writing the plan)

**Spec coverage:**
- §3 (Episode pickup & naming) → Tasks 2, 3 ✓
- §4.1 (`scripts/pickup.py`) → Task 3 ✓
- §4.2 (`scripts/scaffold_hyperframes.py`) → Tasks 5, 6 ✓
- §4.3 (`scripts/remap_transcript.py`) → Task 4 ✓
- §4.4 (Glue execution order) → Task 9 (edit-episode.md rewrite) ✓
- §5.1, §5.2 (verbatim briefs) → Task 9 ✓
- §6 (Idempotency) → Task 9 ✓
- §7.1 (init/ relocation) → Task 7 ✓
- §7.2 (.gitignore additions) → Task 1 ✓
- §7.3 (PYTHONUTF8) → Task 8 ✓
- §10 (Success criteria) → Task 11 (manual validation step) ✓

**Placeholder scan:** No "TBD", "TODO", "implement later", or vague directives. All code blocks are complete; all commands have expected outputs; all file paths are exact.

**Type consistency:** `scripts.slugify.derive_slug` is referenced consistently. `scripts.pickup.PickupResult` fields match between definition and tests. `scripts.scaffold_hyperframes.{patch_index_html, patch_meta_json, build_package_json, scaffold}` signatures match between unit tests, integration tests, and CLI entry point.

**No spec drifts surfaced.** The plan stays inside the spec's bounds; no new functionality introduced; all canon citations preserved.
