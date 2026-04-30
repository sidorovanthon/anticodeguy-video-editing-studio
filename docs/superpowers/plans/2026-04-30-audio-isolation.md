# Audio Isolation Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a new Phase 2 (Audio Isolation via ElevenLabs) between Pickup and the video-use sub-agent in `/edit-episode`, so Scribe transcribes a clean track and `final.mp4` carries studio-grade audio without an upstream patch to `video-use`.

**Architecture:** A single inline orchestrator script `scripts/isolate_audio.py` that (a) checks an ffmpeg metadata tag on `raw.<ext>`'s audio stream for full no-op idempotency, (b) checks a cached WAV at `episodes/<slug>/audio/raw.cleaned.wav` to skip the paid API call, (c) extracts → calls ElevenLabs Audio Isolation → caches → muxes the cleaned audio into `raw.<ext>` in place, stamping the audio stream with `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1`. Fail-fast on any error; no retries; no skip flag. The script is invoked from `.claude/commands/edit-episode.md` between pickup and the video-use sub-agent. Phases renumber to **1=pickup, 2=isolation, 3=video-use, 4=hyperframes**.

**Tech Stack:** Python 3.11+, `requests` (HTTP to ElevenLabs), `subprocess` (ffmpeg/ffprobe), `pathlib`, `json`, `pytest` for tests. Reuses `ELEVENLABS_API_KEY` resolution mirrored from `~/.claude/skills/video-use/helpers/transcribe.py` (project `.env` → video-use repo `.env` → environment).

**Spec:** `docs/superpowers/specs/2026-04-30-audio-isolation-design.md`. Read before starting; this plan implements that spec verbatim.

---

## File Structure

**Create:**
- `scripts/isolate_audio.py` — the new glue script (orchestration `main` + pure helpers).
- `tests/test_isolate_audio.py` — unit tests for pure helpers + integration tests for orchestration via dependency injection.
- `tests/fixtures/elevenlabs_response_tiny.wav` — small valid PCM WAV for fake API responses (test fixture, generated in Task 0).

**Modify:**
- `.claude/commands/edit-episode.md` — insert the new Phase 2 block, add the one-sentence pre-cleaned-audio note to the video-use brief, expand the idempotency checkpoint list.

**No changes to** `scripts/pickup.py`, `scripts/remap_transcript.py`, `scripts/scaffold_hyperframes.py`, or anything under `~/.claude/skills/video-use/` or `~/.agents/skills/hyperframes/` (canon, read-only).

---

## Decomposition strategy

`isolate_audio.py` is decomposed into **pure functions** (testable without subprocess or network) plus a thin orchestration layer:

- `find_raw_video(episode_dir)` — pure, scans for the unique `raw.<ext>`, raises on 0 or >1 matches.
- `audio_stream_has_clean_tag(ffprobe_json)` — pure, takes the parsed ffprobe JSON, returns bool.
- `load_api_key(*, project_env, video_use_env, environ)` — pure, takes mappings/paths, returns the key or raises.
- `extract_audio_cmd(src, dst)` — pure, returns the ffmpeg argv list.
- `mux_cmd(src_video, src_wav, dst, tag_value)` — pure, returns the ffmpeg argv list.
- `call_isolation_api(api_key, wav_bytes, *, post=requests.post)` — thin wrapper, takes injected `post` for tests.
- `isolate(*, episode_dir, runner, post, key_loader, now=...)` — the orchestrator function. Takes injected `runner` (a callable wrapping `subprocess.run`) and `post` (for the API). This is what `main()` calls; tests instantiate it with fakes.
- `main(argv)` — argparse + JSON stdout + exit codes only.

Why dependency injection: existing tests in `tests/test_scaffold_hyperframes.py` test pure helpers, not subprocess-driven `main`. The same approach lets us test orchestration without spawning ffmpeg or hitting the network.

---

### Task 0: Repository scaffolding and test fixture

**Files:**
- Create: `scripts/isolate_audio.py` (stub)
- Create: `tests/test_isolate_audio.py` (empty test file)
- Create: `tests/fixtures/elevenlabs_response_tiny.wav` (1-frame silent PCM WAV)

- [ ] **Step 1: Create stub script**

Create `scripts/isolate_audio.py` with only:

```python
"""Phase 2: Audio Isolation via ElevenLabs.

Per docs/superpowers/specs/2026-04-30-audio-isolation-design.md.
"""
from __future__ import annotations
```

- [ ] **Step 2: Create empty test file**

Create `tests/test_isolate_audio.py`:

```python
"""Tests for scripts.isolate_audio."""
```

- [ ] **Step 3: Generate the test fixture WAV**

Run from project root:

```bash
ffmpeg -y -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=48000" -t 0.1 -c:a pcm_s16le tests/fixtures/elevenlabs_response_tiny.wav
```

Expected: file `tests/fixtures/elevenlabs_response_tiny.wav` exists, ~19 KB, valid PCM WAV. Verify with:

```bash
ffprobe -v error -show_streams tests/fixtures/elevenlabs_response_tiny.wav | grep codec_name
```

Expected output contains `codec_name=pcm_s16le`.

- [ ] **Step 4: Verify pytest discovers the new test file**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: `no tests ran in 0.0Xs` (file exists but empty — pytest exits 5).

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py tests/fixtures/elevenlabs_response_tiny.wav
git commit -m "chore(isolate-audio): scaffold stub + test fixture"
```

---

### Task 1: `find_raw_video` — locate the unique raw.<ext>

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
from pathlib import Path

import pytest

from scripts.isolate_audio import find_raw_video, IsolationError


def test_find_raw_video_picks_unique_match(tmp_path: Path):
    (tmp_path / "raw.mp4").write_bytes(b"")
    assert find_raw_video(tmp_path) == tmp_path / "raw.mp4"


def test_find_raw_video_case_insensitive(tmp_path: Path):
    (tmp_path / "raw.MOV").write_bytes(b"")
    assert find_raw_video(tmp_path) == tmp_path / "raw.MOV"


def test_find_raw_video_errors_on_zero_matches(tmp_path: Path):
    with pytest.raises(IsolationError, match="not found"):
        find_raw_video(tmp_path)


def test_find_raw_video_errors_on_ambiguous(tmp_path: Path):
    (tmp_path / "raw.mp4").write_bytes(b"")
    (tmp_path / "raw.mov").write_bytes(b"")
    with pytest.raises(IsolationError, match="ambiguous"):
        find_raw_video(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 4 errors, all `ImportError: cannot import name 'find_raw_video'`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
from pathlib import Path

SUPPORTED_EXTS = (".mp4", ".mov", ".mkv", ".webm")
TAG_KEY = "ANTICODEGUY_AUDIO_CLEANED"
TAG_VALUE = "elevenlabs-v1"


class IsolationError(Exception):
    """Raised when isolation cannot proceed; surfaced verbatim to the user."""


def find_raw_video(episode_dir: Path) -> Path:
    """Locate the single raw.<ext> in episode_dir. Raises on 0 or >1 matches."""
    matches = [
        p for p in episode_dir.iterdir()
        if p.is_file() and p.stem == "raw" and p.suffix.lower() in SUPPORTED_EXTS
    ]
    if not matches:
        raise IsolationError(f"raw.<ext> not found in {episode_dir}")
    if len(matches) > 1:
        raise IsolationError(
            f"raw.<ext> ambiguous in {episode_dir}: matched {sorted(p.name for p in matches)}"
        )
    return matches[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): find_raw_video helper with unique-match validation"
```

---

### Task 2: `audio_stream_has_clean_tag` — idempotency layer 1 (tag detection)

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
from scripts.isolate_audio import audio_stream_has_clean_tag


def test_tag_detected_when_present_on_audio_stream():
    ffprobe_out = {
        "streams": [
            {"codec_type": "video"},
            {"codec_type": "audio", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v1"}},
        ]
    }
    assert audio_stream_has_clean_tag(ffprobe_out) is True


def test_tag_absent_when_no_tags_dict():
    ffprobe_out = {"streams": [{"codec_type": "audio"}]}
    assert audio_stream_has_clean_tag(ffprobe_out) is False


def test_tag_absent_when_wrong_value():
    ffprobe_out = {
        "streams": [{"codec_type": "audio", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v0"}}]
    }
    assert audio_stream_has_clean_tag(ffprobe_out) is False


def test_tag_ignored_on_video_stream():
    ffprobe_out = {
        "streams": [{"codec_type": "video", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v1"}}]
    }
    assert audio_stream_has_clean_tag(ffprobe_out) is False


def test_tag_absent_when_no_streams_key():
    assert audio_stream_has_clean_tag({}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate_audio.py::test_tag_detected_when_present_on_audio_stream -v`
Expected: ImportError on `audio_stream_has_clean_tag`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
def audio_stream_has_clean_tag(ffprobe_json: dict) -> bool:
    """Return True iff any audio stream carries ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1."""
    for stream in ffprobe_json.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue
        tags = stream.get("tags") or {}
        if tags.get(TAG_KEY) == TAG_VALUE:
            return True
    return False
```

- [ ] **Step 4: Run all isolate-audio tests**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 9 passed (4 from Task 1 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): audio_stream_has_clean_tag for idempotency check"
```

---

### Task 3: `load_api_key` — reproduce video-use's resolution ladder

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
from scripts.isolate_audio import load_api_key


def test_load_api_key_from_environ_when_no_files(tmp_path: Path):
    project_env = tmp_path / "p.env"
    video_use_env = tmp_path / "v.env"
    key = load_api_key(
        project_env=project_env,
        video_use_env=video_use_env,
        environ={"ELEVENLABS_API_KEY": "k-from-env"},
    )
    assert key == "k-from-env"


def test_load_api_key_project_env_takes_precedence(tmp_path: Path):
    project_env = tmp_path / "p.env"
    project_env.write_text('ELEVENLABS_API_KEY="k-project"\n', encoding="utf-8")
    video_use_env = tmp_path / "v.env"
    video_use_env.write_text("ELEVENLABS_API_KEY=k-video-use\n", encoding="utf-8")
    key = load_api_key(
        project_env=project_env,
        video_use_env=video_use_env,
        environ={"ELEVENLABS_API_KEY": "k-environ"},
    )
    assert key == "k-project"


def test_load_api_key_falls_back_to_video_use_env(tmp_path: Path):
    project_env = tmp_path / "p.env"  # absent
    video_use_env = tmp_path / "v.env"
    video_use_env.write_text("ELEVENLABS_API_KEY=k-video-use\n", encoding="utf-8")
    key = load_api_key(project_env=project_env, video_use_env=video_use_env, environ={})
    assert key == "k-video-use"


def test_load_api_key_strips_quotes_and_whitespace(tmp_path: Path):
    project_env = tmp_path / "p.env"
    project_env.write_text("  ELEVENLABS_API_KEY = '  k-quoted  '  \n", encoding="utf-8")
    key = load_api_key(project_env=project_env, video_use_env=tmp_path / "absent", environ={})
    assert key == "k-quoted"


def test_load_api_key_raises_when_nowhere(tmp_path: Path):
    with pytest.raises(IsolationError, match="ELEVENLABS_API_KEY not found"):
        load_api_key(
            project_env=tmp_path / "absent1",
            video_use_env=tmp_path / "absent2",
            environ={},
        )


def test_load_api_key_ignores_comments_and_blank_lines(tmp_path: Path):
    project_env = tmp_path / "p.env"
    project_env.write_text(
        "# comment\n\nOTHER=1\nELEVENLABS_API_KEY=k-real\n", encoding="utf-8"
    )
    key = load_api_key(project_env=project_env, video_use_env=tmp_path / "absent", environ={})
    assert key == "k-real"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate_audio.py -v -k load_api_key`
Expected: 6 errors, ImportError on `load_api_key`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal .env file. Mirrors video-use/helpers/transcribe.py:load_api_key."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'").strip()
    return out


def load_api_key(
    *,
    project_env: Path,
    video_use_env: Path,
    environ: dict[str, str],
) -> str:
    """Resolve ELEVENLABS_API_KEY using the same ladder as video-use's transcribe.py."""
    for source in (project_env, video_use_env):
        parsed = _read_env_file(source)
        if "ELEVENLABS_API_KEY" in parsed and parsed["ELEVENLABS_API_KEY"]:
            return parsed["ELEVENLABS_API_KEY"]
    if environ.get("ELEVENLABS_API_KEY"):
        return environ["ELEVENLABS_API_KEY"]
    raise IsolationError("ELEVENLABS_API_KEY not found in .env or environment")
```

Note the precedence: project `.env` → video-use `.env` → environment. This matches video-use's order (it scans both .env files first, then falls back to env).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 15 passed (9 from earlier + 6 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): load_api_key with project/video-use/env ladder"
```

---

### Task 4: ffmpeg command builders (`extract_audio_cmd`, `mux_cmd`)

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
from scripts.isolate_audio import extract_audio_cmd, mux_cmd


def test_extract_audio_cmd_shape():
    cmd = extract_audio_cmd(Path("/ep/raw.mp4"), Path("/tmp/source.wav"))
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-i" in cmd and "/ep/raw.mp4" in [str(x) for x in cmd]
    assert "-vn" in cmd
    assert "-ac" in cmd and "2" in cmd
    assert "-ar" in cmd and "48000" in cmd
    assert "-c:a" in cmd and "pcm_s16le" in cmd
    assert str(cmd[-1]) == "/tmp/source.wav"


def test_mux_cmd_includes_metadata_tag():
    cmd = mux_cmd(
        Path("/ep/raw.mp4"),
        Path("/ep/audio/raw.cleaned.wav"),
        Path("/ep/raw.muxed.mp4"),
        tag_value="elevenlabs-v1",
    )
    assert cmd[0] == "ffmpeg"
    cmd_str = [str(x) for x in cmd]
    # both inputs present, in order
    i_indices = [i for i, x in enumerate(cmd_str) if x == "-i"]
    assert len(i_indices) == 2
    assert cmd_str[i_indices[0] + 1] == "/ep/raw.mp4"
    assert cmd_str[i_indices[1] + 1] == "/ep/audio/raw.cleaned.wav"
    # video copy, audio re-encoded
    assert "-c:v" in cmd_str and "copy" in cmd_str
    assert "-c:a" in cmd_str and "aac" in cmd_str
    # mapping: video from input 0, audio from input 1
    assert "0:v" in cmd_str
    assert "1:a" in cmd_str
    # metadata tag
    assert any(
        x == "ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1" for x in cmd_str
    ), f"tag missing in {cmd_str}"
    # output last
    assert cmd_str[-1] == "/ep/raw.muxed.mp4"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate_audio.py -v -k cmd`
Expected: ImportError on `extract_audio_cmd` / `mux_cmd`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
def extract_audio_cmd(src: Path, dst: Path) -> list[str]:
    """ffmpeg argv to extract stereo 48kHz PCM WAV from src into dst."""
    return [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",
        "-ac", "2",
        "-ar", "48000",
        "-c:a", "pcm_s16le",
        str(dst),
    ]


def mux_cmd(src_video: Path, src_wav: Path, dst: Path, *, tag_value: str) -> list[str]:
    """ffmpeg argv to mux src_video's video stream with src_wav's audio, stamping the tag."""
    return [
        "ffmpeg", "-y",
        "-i", str(src_video),
        "-i", str(src_wav),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-metadata:s:a:0", f"{TAG_KEY}={tag_value}",
        str(dst),
    ]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): ffmpeg argv builders for extract and mux"
```

---

### Task 5: `call_isolation_api` — HTTP wrapper with injectable `post`

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
from scripts.isolate_audio import call_isolation_api, ISOLATION_URL


class _FakeResponse:
    def __init__(self, *, status_code: int, content: bytes = b"", text: str = ""):
        self.status_code = status_code
        self.content = content
        self.text = text or content.decode("latin-1", errors="replace")


def test_call_isolation_api_posts_to_endpoint_with_key_and_audio():
    captured = {}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["files"] = files
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200, content=b"OK_BYTES")

    out = call_isolation_api("api-key-xyz", b"WAV_BYTES", post=fake_post)
    assert out == b"OK_BYTES"
    assert captured["url"] == ISOLATION_URL
    assert captured["headers"]["xi-api-key"] == "api-key-xyz"
    assert "audio" in captured["files"]
    # files["audio"] is a tuple of (filename, bytes, content_type) per requests convention
    name, payload, *_ = captured["files"]["audio"]
    assert payload == b"WAV_BYTES"
    assert captured["timeout"] is not None and captured["timeout"] > 0


def test_call_isolation_api_raises_on_non_200():
    def fake_post(*a, **kw):
        return _FakeResponse(status_code=429, text="rate limited")

    with pytest.raises(IsolationError, match="429"):
        call_isolation_api("k", b"x", post=fake_post)


def test_call_isolation_api_raises_on_empty_body():
    def fake_post(*a, **kw):
        return _FakeResponse(status_code=200, content=b"")

    with pytest.raises(IsolationError, match="empty"):
        call_isolation_api("k", b"x", post=fake_post)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate_audio.py -v -k call_isolation_api`
Expected: ImportError on `call_isolation_api` and `ISOLATION_URL`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
ISOLATION_URL = "https://api.elevenlabs.io/v1/audio-isolation"


def call_isolation_api(api_key: str, wav_bytes: bytes, *, post) -> bytes:
    """POST wav_bytes to ElevenLabs Audio Isolation; return cleaned audio bytes."""
    headers = {"xi-api-key": api_key}
    files = {"audio": ("source.wav", wav_bytes, "audio/wav")}
    try:
        resp = post(ISOLATION_URL, headers=headers, files=files, timeout=300)
    except Exception as e:
        raise IsolationError(f"Network error: {e}") from e
    if resp.status_code != 200:
        snippet = (resp.text or "")[:200]
        raise IsolationError(f"Audio Isolation API returned {resp.status_code}: {snippet}")
    if not resp.content:
        raise IsolationError("Audio Isolation API returned empty body")
    return resp.content
```

Note: §9 of the spec flags that the actual endpoint name and request shape must be verified at implementation time. If the live ElevenLabs docs reveal a different field name (e.g., `file` instead of `audio`) or a different URL path, change only the constants here; tests use injection and stay valid.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): call_isolation_api with injectable post for tests"
```

---

### Task 6: API response normalization to PCM WAV

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

Spec §9 question 2: the API may return `audio/mpeg` instead of `audio/wav`. The cache file MUST be PCM WAV regardless. This task adds a helper that normalizes the response bytes to PCM WAV by writing them to a temp file and re-encoding via ffmpeg if needed.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
from scripts.isolate_audio import normalize_to_pcm_wav_cmd


def test_normalize_cmd_re_encodes_to_pcm_wav():
    cmd = normalize_to_pcm_wav_cmd(Path("/tmp/api.bin"), Path("/tmp/cleaned.wav"))
    cmd_str = [str(x) for x in cmd]
    assert cmd_str[0] == "ffmpeg"
    assert "-y" in cmd_str
    assert cmd_str[cmd_str.index("-i") + 1] == "/tmp/api.bin"
    assert "-c:a" in cmd_str and "pcm_s16le" in cmd_str
    assert "-vn" in cmd_str
    assert cmd_str[-1] == "/tmp/cleaned.wav"
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_isolate_audio.py -v -k normalize`
Expected: ImportError on `normalize_to_pcm_wav_cmd`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
def normalize_to_pcm_wav_cmd(src: Path, dst: Path) -> list[str]:
    """ffmpeg argv to re-encode whatever container/codec the API returned into PCM WAV."""
    return [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",
        "-c:a", "pcm_s16le",
        str(dst),
    ]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): normalize_to_pcm_wav_cmd for non-WAV API responses"
```

---

### Task 7: `isolate()` orchestrator — happy path with all dependencies injected

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

This is the integration of all helpers under a single function with injected `runner` (subprocess wrapper) and `post` (HTTP). The result type is the JSON-shape dict that `main()` will print.

- [ ] **Step 1: Write failing test for the full happy path**

Append to `tests/test_isolate_audio.py`:

```python
from scripts.isolate_audio import isolate, IsolateResult


def _make_runner(*, ffprobe_json: dict, fixture_wav: bytes):
    """Build a runner stub that inspects argv and writes outputs as ffmpeg/ffprobe would."""
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, capture_output: bool = False, check: bool = True):
        calls.append(list(cmd))
        if cmd[0] == "ffprobe":
            class R:
                returncode = 0
                stdout = json.dumps(ffprobe_json).encode("utf-8")
                stderr = b""
            return R()
        if cmd[0] == "ffmpeg":
            # write output file (last argv) so downstream existence checks pass
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(fixture_wav if out.suffix == ".wav" else b"\x00")
            class R:
                returncode = 0
                stdout = b""
                stderr = b""
            return R()
        raise AssertionError(f"unexpected cmd: {cmd[0]}")

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def test_isolate_happy_path_calls_api_and_muxes(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"FAKE_VIDEO")

    fixture = (Path(__file__).parent / "fixtures" / "elevenlabs_response_tiny.wav").read_bytes()
    runner = _make_runner(
        ffprobe_json={"streams": [{"codec_type": "audio"}]},  # no tag → must call API
        fixture_wav=fixture,
    )

    posts: list[tuple] = []

    def post(url, headers=None, files=None, timeout=None):
        posts.append((url, headers, files, timeout))
        class R:
            status_code = 200
            content = fixture  # API returns valid WAV bytes
            text = ""
        return R()

    result = isolate(
        episode_dir=ep,
        runner=runner,
        post=post,
        key_loader=lambda: "test-key",
    )

    assert result.cached is False
    assert result.api_called is True
    assert result.wav_path == ep / "audio" / "raw.cleaned.wav"
    assert result.wav_path.exists()
    assert result.raw_path == ep / "raw.mp4"

    # API was called once
    assert len(posts) == 1
    # Three ffmpeg invocations: extract, (no normalize because response is WAV bytes — but our
    # implementation normalizes unconditionally for safety), mux. Allow either 2 or 3.
    ffmpegs = [c for c in runner.calls if c[0] == "ffmpeg"]
    assert 2 <= len(ffmpegs) <= 3
    # mux invocation includes the metadata tag
    mux = next(c for c in ffmpegs if any("ANTICODEGUY_AUDIO_CLEANED=" in str(x) for x in c))
    assert mux is not None
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_isolate_audio.py::test_isolate_happy_path_calls_api_and_muxes -v`
Expected: ImportError on `isolate` / `IsolateResult`.

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
import json
import os
import tempfile
from dataclasses import dataclass


@dataclass
class IsolateResult:
    cached: bool
    api_called: bool
    raw_path: Path
    wav_path: Path
    reason: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "cached": self.cached,
                "api_called": self.api_called,
                "raw_path": str(self.raw_path),
                "wav_path": str(self.wav_path),
                "reason": self.reason,
            },
            ensure_ascii=False,
        )


def _run(runner, cmd: list[str]) -> None:
    """Run a subprocess; raise IsolationError on failure with a useful tail."""
    try:
        result = runner(cmd, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise IsolationError(f"executable not found: {cmd[0]}") from e
    if getattr(result, "returncode", 0) != 0:
        tail = (getattr(result, "stderr", b"") or b"").decode("utf-8", errors="replace")[-400:]
        raise IsolationError(f"{cmd[0]} failed: {tail}")


def _ffprobe_json(runner, video: Path) -> dict:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(video)]
    try:
        result = runner(cmd, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise IsolationError("ffprobe not found on PATH") from e
    if getattr(result, "returncode", 0) != 0:
        raise IsolationError(f"ffprobe failed on {video}")
    raw = getattr(result, "stdout", b"") or b""
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise IsolationError(f"ffprobe returned non-JSON: {e}") from e


def isolate(
    *,
    episode_dir: Path,
    runner,
    post,
    key_loader,
) -> IsolateResult:
    """Phase 2 orchestration. Pure I/O; all side-effecting deps injected."""
    raw = find_raw_video(episode_dir)
    audio_dir = episode_dir / "audio"
    wav_path = audio_dir / "raw.cleaned.wav"

    # Layer 1: tag check (full no-op).
    probe = _ffprobe_json(runner, raw)
    if audio_stream_has_clean_tag(probe):
        return IsolateResult(
            cached=True, api_called=False, raw_path=raw, wav_path=wav_path,
            reason="tag-present",
        )

    audio_dir.mkdir(parents=True, exist_ok=True)

    # Layer 2: WAV cache check.
    api_called = False
    if not wav_path.exists():
        api_key = key_loader()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            extracted = tmp / "source.wav"
            _run(runner, extract_audio_cmd(raw, extracted))
            wav_bytes = extracted.read_bytes()
            cleaned_bytes = call_isolation_api(api_key, wav_bytes, post=post)
            api_called = True
            # Normalize whatever came back into PCM WAV in the cache slot, atomically.
            api_blob = tmp / "api.bin"
            api_blob.write_bytes(cleaned_bytes)
            tmp_wav = tmp / "cleaned.wav"
            _run(runner, normalize_to_pcm_wav_cmd(api_blob, tmp_wav))
            tmp_dest = wav_path.with_suffix(".wav.tmp")
            tmp_dest.write_bytes(tmp_wav.read_bytes())
            os.replace(tmp_dest, wav_path)

    # Mux (always runs when tag absent — cheap and stamps the tag).
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        muxed = tmp / f"raw.muxed{raw.suffix}"
        _run(runner, mux_cmd(raw, wav_path, muxed, tag_value=TAG_VALUE))
        tmp_dest = raw.with_suffix(raw.suffix + ".tmp")
        tmp_dest.write_bytes(muxed.read_bytes())
        os.replace(tmp_dest, raw)

    return IsolateResult(
        cached=False, api_called=api_called, raw_path=raw, wav_path=wav_path,
        reason="api-cache-hit" if not api_called else "isolated",
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: 22 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): isolate() orchestrator with happy path"
```

---

### Task 8: `isolate()` — tag-present short-circuit

**Files:**
- Test: `tests/test_isolate_audio.py`

This verifies the layer-1 idempotency check: when raw.<ext>'s audio stream is already tagged, no API call, no ffmpeg mux, no audio dir created.

- [ ] **Step 1: Write the test**

Append to `tests/test_isolate_audio.py`:

```python
def test_isolate_short_circuits_when_tag_present(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")

    runner = _make_runner(
        ffprobe_json={
            "streams": [
                {"codec_type": "audio", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v1"}}
            ]
        },
        fixture_wav=b"",
    )

    posts: list = []

    def post(*a, **kw):
        posts.append(1)
        raise AssertionError("must not call API when tag present")

    result = isolate(
        episode_dir=ep, runner=runner, post=post, key_loader=lambda: "k",
    )
    assert result.cached is True
    assert result.api_called is False
    assert result.reason == "tag-present"
    # Only ffprobe ran; no ffmpeg
    assert all(c[0] == "ffprobe" for c in runner.calls)
    # audio/ dir not created
    assert not (ep / "audio").exists()
    assert posts == []
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_isolate_audio.py::test_isolate_short_circuits_when_tag_present -v`
Expected: PASS (the orchestrator from Task 7 already implements this — this test is the regression guard).

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolate_audio.py
git commit -m "test(isolate-audio): tag-present short-circuit regression guard"
```

---

### Task 9: `isolate()` — WAV cache hit, no API call

**Files:**
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_isolate_audio.py`:

```python
def test_isolate_skips_api_when_wav_cached(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")
    audio_dir = ep / "audio"
    audio_dir.mkdir()
    fixture = (Path(__file__).parent / "fixtures" / "elevenlabs_response_tiny.wav").read_bytes()
    (audio_dir / "raw.cleaned.wav").write_bytes(fixture)

    runner = _make_runner(
        ffprobe_json={"streams": [{"codec_type": "audio"}]},  # tag absent → mux still runs
        fixture_wav=fixture,
    )

    def post(*a, **kw):
        raise AssertionError("must not call API when WAV cached")

    result = isolate(
        episode_dir=ep, runner=runner, post=post, key_loader=lambda: "k",
    )
    assert result.cached is False
    assert result.api_called is False
    assert result.reason == "api-cache-hit"
    # Mux ran (one ffmpeg call), no extract, no normalize
    ffmpegs = [c for c in runner.calls if c[0] == "ffmpeg"]
    assert len(ffmpegs) == 1
    assert any("ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1" in str(x) for x in ffmpegs[0])
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_isolate_audio.py::test_isolate_skips_api_when_wav_cached -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolate_audio.py
git commit -m "test(isolate-audio): WAV cache hit skips API"
```

---

### Task 10: `isolate()` — failure surfaces propagate as IsolationError

**Files:**
- Test: `tests/test_isolate_audio.py`

Verify the four major failure modes from spec §4.2 each raise `IsolationError` with the right message fragment, so `main()`'s exit-code path has all the wiring it needs.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_isolate_audio.py`:

```python
def test_isolate_raises_when_no_raw_file(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()

    def runner(*a, **kw):
        raise AssertionError("should not run")

    with pytest.raises(IsolationError, match="not found"):
        isolate(episode_dir=ep, runner=runner, post=None, key_loader=lambda: "k")


def test_isolate_raises_on_api_non_200(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")

    runner = _make_runner(
        ffprobe_json={"streams": [{"codec_type": "audio"}]},
        fixture_wav=(Path(__file__).parent / "fixtures" / "elevenlabs_response_tiny.wav").read_bytes(),
    )

    def post(*a, **kw):
        class R:
            status_code = 500
            content = b""
            text = "boom"
        return R()

    with pytest.raises(IsolationError, match="500"):
        isolate(episode_dir=ep, runner=runner, post=post, key_loader=lambda: "k")


def test_isolate_raises_on_missing_api_key(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")

    runner = _make_runner(
        ffprobe_json={"streams": [{"codec_type": "audio"}]},
        fixture_wav=b"",
    )

    def bad_loader():
        raise IsolationError("ELEVENLABS_API_KEY not found in .env or environment")

    def post(*a, **kw):
        raise AssertionError("must not call API without key")

    with pytest.raises(IsolationError, match="ELEVENLABS_API_KEY not found"):
        isolate(episode_dir=ep, runner=runner, post=post, key_loader=bad_loader)


def test_isolate_raises_on_ffmpeg_failure(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")

    def runner(cmd: list[str], *, capture_output=True, check=False):
        if cmd[0] == "ffprobe":
            class R:
                returncode = 0
                stdout = b'{"streams":[{"codec_type":"audio"}]}'
                stderr = b""
            return R()

        class R:
            returncode = 1
            stdout = b""
            stderr = b"ffmpeg: synthetic failure for test"
        return R()

    def post(*a, **kw):
        # This won't be reached — extract fails first.
        raise AssertionError("API should not be called")

    with pytest.raises(IsolationError, match="ffmpeg failed"):
        isolate(episode_dir=ep, runner=runner, post=post, key_loader=lambda: "k")
```

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/test_isolate_audio.py -v -k "raises or no_raw"`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolate_audio.py
git commit -m "test(isolate-audio): failure modes propagate as IsolationError"
```

---

### Task 11: `main()` — argparse, JSON stdout, exit codes

**Files:**
- Modify: `scripts/isolate_audio.py`
- Test: `tests/test_isolate_audio.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_isolate_audio.py`:

```python
import io
import sys

from scripts import isolate_audio as ia


def test_main_returns_2_and_writes_stderr_on_isolation_error(tmp_path, capsys, monkeypatch):
    # episode_dir does not contain raw.<ext> → IsolationError
    ep = tmp_path / "ep"
    ep.mkdir()
    rc = ia.main(["--episode-dir", str(ep)])
    assert rc == 2
    out = capsys.readouterr()
    assert "isolation error:" in out.err
    assert "not found" in out.err
    assert out.out.strip() == ""  # nothing on stdout


def test_main_prints_json_on_success(tmp_path, capsys, monkeypatch):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")

    fixture = (Path(__file__).parent / "fixtures" / "elevenlabs_response_tiny.wav").read_bytes()

    def fake_isolate(*, episode_dir, runner, post, key_loader):
        # exercise key_loader so test catches accidental removal
        _ = key_loader()
        return ia.IsolateResult(
            cached=False,
            api_called=True,
            raw_path=episode_dir / "raw.mp4",
            wav_path=episode_dir / "audio" / "raw.cleaned.wav",
            reason="isolated",
        )

    monkeypatch.setattr(ia, "isolate", fake_isolate)
    monkeypatch.setattr(ia, "load_api_key", lambda **kw: "test-key")

    rc = ia.main(["--episode-dir", str(ep)])
    assert rc == 0
    out = capsys.readouterr()
    payload = json.loads(out.out.strip())
    assert payload["cached"] is False
    assert payload["api_called"] is True
    assert payload["reason"] == "isolated"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_isolate_audio.py -v -k main`
Expected: AttributeError on `main` (not yet defined).

- [ ] **Step 3: Implement**

Append to `scripts/isolate_audio.py`:

```python
import argparse
import subprocess
import sys

import requests


def _default_runner(cmd, *, capture_output=False, check=False):
    return subprocess.run(cmd, capture_output=capture_output, check=check)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2: ElevenLabs Audio Isolation.")
    parser.add_argument("--episode-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    project_env = Path(".env").resolve()
    video_use_env = (Path.home() / ".claude" / "skills" / "video-use" / ".env").resolve()

    try:
        result = isolate(
            episode_dir=args.episode_dir,
            runner=_default_runner,
            post=requests.post,
            key_loader=lambda: load_api_key(
                project_env=project_env,
                video_use_env=video_use_env,
                environ=dict(os.environ),
            ),
        )
    except IsolationError as e:
        print(f"isolation error: {e}", file=sys.stderr)
        return 2

    print(result.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_isolate_audio.py -v`
Expected: all tests pass (28 total: 21 + 4 + 1 short-circuit + 1 wav-cache + 1 main-success).

Re-count check: Tasks 1–6 added 17 tests, Task 7 added 1, Task 8 added 1, Task 9 added 1, Task 10 added 4, Task 11 added 2 → 26 total. Expected: 26 passed.

- [ ] **Step 5: Verify the script runs as a module from project root**

Run: `python -m scripts.isolate_audio --help`
Expected: argparse help is printed and exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/isolate_audio.py tests/test_isolate_audio.py
git commit -m "feat(isolate-audio): main() with argparse, JSON stdout, exit codes"
```

---

### Task 12: Full test suite green

**Files:** none (verification step).

- [ ] **Step 1: Run the entire pytest suite**

Run: `python -m pytest -v`
Expected: all tests in `tests/` pass — including the existing `test_pickup.py`, `test_remap_transcript.py`, `test_scaffold_hyperframes.py`, `test_slugify.py`, plus the new `test_isolate_audio.py`. No regressions.

- [ ] **Step 2: If any unrelated test fails**

Investigate before proceeding. Likely cause: import-time side effects from `scripts/isolate_audio.py` (e.g., `requests` import failing in a clean env). Fix and re-run.

If the failure is genuinely unrelated to this work, surface it to the user; do not paper over with skip markers.

- [ ] **Step 3: Commit if any cleanup needed**

If Step 2 produced fixes, commit them with a clear message; otherwise no commit.

---

### Task 13: Wire `isolate_audio.py` into `.claude/commands/edit-episode.md`

**Files:**
- Modify: `.claude/commands/edit-episode.md`

- [ ] **Step 1: Read the current file end-to-end**

Run: `cat .claude/commands/edit-episode.md` (or open in editor). Locate the Phase 2 (video-use sub-agent) heading at line ~55.

- [ ] **Step 2: Insert the new Phase 2 block**

Insert this section between current Phase 1 and current Phase 2, and renumber the existing Phase 2 → Phase 3 and existing Phase 3 → Phase 4. Use the Edit tool with surrounding context to avoid ambiguity.

The new section content:

```markdown
## Phase 2 — Audio isolation

Run inline:

**Bash:**
```bash
python -m scripts.isolate_audio --episode-dir <EPISODE_DIR>
```

**PowerShell:**
```powershell
python -m scripts.isolate_audio --episode-dir <EPISODE_DIR>
```

Parse the JSON on stdout. Fields: `cached`, `api_called`, `wav_path`, `raw_path`, `reason`.

- If `cached: true` (`reason: "tag-present"`): announce `Phase 2 already complete (audio stream tagged) — skipping isolation.` and proceed.
- If `cached: false, api_called: false` (`reason: "api-cache-hit"`): announce `Phase 2 used cached WAV (audio/raw.cleaned.wav) — remuxed into raw.<ext>.`
- Otherwise (`reason: "isolated"`): announce `Phase 2 done — audio isolated and muxed into raw.<ext>. Cache at <wav_path>.`

On non-zero exit: stop the pipeline, surface the stderr message verbatim to the user, and tell them to fix the underlying issue (typically API key or network) and re-run `/edit-episode <slug>`. Do not retry. There is no `--skip-isolation` flag — running without isolation is not a supported mode.
```

- [ ] **Step 3: Renumber sections**

After insertion:
- Old `## Phase 2 — Video edit (video-use sub-agent)` → `## Phase 3 — Video edit (video-use sub-agent)`
- Old `## Phase 3 — Composition & studio (hyperframes Skill)` → `## Phase 4 — Composition & studio (hyperframes Skill)`

Use Edit with replace_all=false; the heading strings are unique.

- [ ] **Step 4: Add the pre-cleaned-audio sentence to the Phase 3 brief**

In the (now) Phase 3 verbatim brief, locate the strategy-confirmation paragraph (the one starting with `**Strategy confirmation`). Insert this paragraph immediately after it:

```markdown
> **Pre-cleaned audio:** the audio track of `raw.<ext>` has already been processed by ElevenLabs Audio Isolation in Phase 2 — treat it as a studio-grade source. Do not apply additional noise-suppression filters; loudnorm and the per-segment 30ms fades from Hard Rule 3 are still required.
```

(Keep the leading `> ` blockquote prefix consistent with the surrounding brief.)

- [ ] **Step 5: Update the idempotency block**

Locate the section `## Idempotency and rebuild guidance` near the bottom of the file. Replace the numbered skip-rules with:

```markdown
1. `<EPISODE_DIR>/raw.<ext>` audio stream tagged `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1` → skip Phase 2 entirely.
2. `<EPISODE_DIR>/edit/final.mp4` exists → skip Phase 3.
3. `<EPISODE_DIR>/edit/transcripts/final.json` exists → skip glue remap.
4. `<EPISODE_DIR>/hyperframes/index.html` exists → skip scaffold and Skill, only relaunch studio.
```

And add this fourth bullet to the rebuild-guidance list (which already has re-cut and re-compose):

```markdown
- **Re-isolate audio:** delete `<EPISODE_DIR>/audio/raw.cleaned.wav` AND restore `raw.<ext>` to its un-tagged state (re-pickup from `inbox/`, or git/manual restore). Costs ElevenLabs Audio Isolation credits — almost never needed.
```

- [ ] **Step 6: Update the error-handling list**

In the bottom `## Error handling` section, the list "If `pickup.py`, `video-use` sub-agent, `remap_transcript.py`, `scaffold_hyperframes.py`, or `hyperframes` skill returns an error..." gains one more entry: include `isolate_audio.py` after `pickup.py`.

- [ ] **Step 7: Sanity-check the final file**

Read the file end-to-end again. Verify:
- Phase headings read 1, 2, 3, 4 in order.
- Old "Phase 2" / "Phase 3" references in body text (e.g. "skip Phase 2") are consistent with new numbering.
- The pre-cleaned-audio sentence appears in the (new) Phase 3 brief.
- The error-handling section mentions `isolate_audio.py`.

- [ ] **Step 8: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "feat(edit-episode): wire Phase 2 audio isolation into pipeline"
```

---

### Task 14: End-to-end smoke check (manual, no commit)

**Files:** none.

This is a real-API verification step. Run only when an episode is available locally and you want to validate before merging.

- [ ] **Step 1: Pick a small test episode**

Either reuse `episodes/desktop-licensing-story` (delete its current state — see retro §4 — or duplicate to a new slug for a clean run) or drop a fresh short clip (~30 s) into `inbox/`.

- [ ] **Step 2: Confirm the API key resolves**

Run a one-liner from project root:

```bash
python -c "from scripts.isolate_audio import load_api_key; from pathlib import Path; import os; print(bool(load_api_key(project_env=Path('.env'), video_use_env=Path.home()/'.claude/skills/video-use/.env', environ=dict(os.environ))))"
```

Expected: `True`. If `False`/error: fix `.env` placement before continuing.

- [ ] **Step 3: Run pickup + isolation only**

```bash
python -m scripts.pickup --inbox inbox --episodes episodes
# Note the SLUG and EPISODE_DIR from JSON output, then:
python -m scripts.isolate_audio --episode-dir episodes/<SLUG>
```

Expected: JSON on stdout with `cached: false, api_called: true`. Exit 0. The file `episodes/<SLUG>/audio/raw.cleaned.wav` exists. `ffprobe -show_streams episodes/<SLUG>/raw.<ext> | grep ANTICODEGUY` shows the tag.

- [ ] **Step 4: Run again — must be a no-op**

```bash
python -m scripts.isolate_audio --episode-dir episodes/<SLUG>
```

Expected: JSON `cached: true, api_called: false, reason: "tag-present"`. No second API charge.

- [ ] **Step 5: Listen check (optional but high-value)**

Open `episodes/<SLUG>/audio/raw.cleaned.wav` in any audio player. The track should be audibly cleaner than the audio inside the original video. If not, the API call may have silently degraded the audio — investigate before merging.

- [ ] **Step 6: Run `/edit-episode <SLUG>` end to end**

Verify all four phases run, video-use receives the cleaned audio (it has no way to know it was cleaned — but Scribe accuracy on this run should be observably better than the pilot if the source had room noise).

- [ ] **Step 7: No commit for this task**

Smoke testing is verification, not a code change.

---

## Self-review against the spec

Spec coverage check:

- §3.1 (inline, not sub-agent) → Task 11 (`main()` is plain script invoked from `edit-episode.md`).
- §3.2 (in-place overwrite of raw.<ext>) → Task 7 (`isolate()` mux step writes to a temp then `os.replace` over `raw.<ext>`).
- §3.3 (two-level cache: WAV file + audio-stream tag) → Tasks 2, 7, 8, 9.
- §3.4 (Phase 3 brief gets one pre-cleaned-audio sentence) → Task 13 step 4.
- §3.5 (API key reuses video-use ladder) → Task 3.
- §4.1 steps 1–6 (tag check, WAV check, extract, API, mux+tag, JSON stdout) → Tasks 2, 7, 4, 5, 6, 7, 11.
- §4.2 failure modes → Task 10 covers no-key, non-200, ffmpeg failure, missing raw. Disk-full and ambiguous-raw covered by Task 1 plus the `_run` helper's stderr propagation.
- §4.3 UTF-8 hygiene → all `read_text`/`write_text` use `encoding="utf-8"`; no shell strings; verified inline as written.
- §5.1, §5.2, §5.3 (edit-episode.md changes) → Task 13 covers all three.
- §6 cost model — documented in spec; no code change needed.
- §10 success criteria → Task 14 smoke checks each one.

Placeholder scan: no TBDs, no TODOs, no "implement later". §9 of the spec flags the API endpoint name as needing live-doc verification — that is reflected in Task 5's note (the constant `ISOLATION_URL` is the only line that may need a one-character change at execution time). Not a placeholder; it's a known unknown with a sized impact.

Type consistency:
- `IsolationError` introduced in Task 1, raised consistently throughout.
- `IsolateResult` introduced in Task 7, returned by `isolate()`, serialized by `to_json()` in Task 11.
- `runner` callable signature (`runner(cmd, *, capture_output, check)`) consistent across `_run`, `_ffprobe_json`, and all test stubs.
- `post` callable signature (`post(url, headers=..., files=..., timeout=...)`) consistent between Task 5's `call_isolation_api`, Task 7's orchestrator, and `requests.post` in Task 11's `main`.
- Tag constant `TAG_KEY = "ANTICODEGUY_AUDIO_CLEANED"`, `TAG_VALUE = "elevenlabs-v1"`, defined once in Task 1, referenced throughout.
- WAV cache path `episodes/<slug>/audio/raw.cleaned.wav` consistent in Tasks 7, 8, 9, 11, 13, 14.
