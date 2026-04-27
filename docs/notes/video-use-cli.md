# video-use CLI reference

> Frozen against vendored SHA: 87f00c6b9b4199dadf3c3b7a75bf818f3df0695e
> Upstream: https://github.com/browser-use/video-use
> Captured: 2026-04-27 by Phase 2 Task 2.

## Invocation

video-use has **no top-level CLI command**. There is no `video-use` binary and no
`python -m video_use` entry point. The project exposes five individual Python
scripts in `helpers/`. All are invoked as:

```bash
# CWD must be tools/video-use/ so that helpers can import each other (e.g.
# transcribe_batch imports from transcribe).
cd tools/video-use

uv run python helpers/transcribe.py        <video>
uv run python helpers/transcribe_batch.py  <videos_dir>
uv run python helpers/pack_transcripts.py  --edit-dir <edit_dir>
uv run python helpers/render.py            <edl.json> -o <output.mp4>
uv run python helpers/grade.py             <input> -o <output>
uv run python helpers/timeline_view.py     <video> <start> <end>
```

No `[project.scripts]` table exists in `pyproject.toml`. The install docs
(install.md) confirm: "No console scripts — helpers are invoked directly as
`python helpers/<name>.py`."

## Required environment variables

| Variable             | Used by                     | Purpose                                                     |
|----------------------|-----------------------------|-------------------------------------------------------------|
| `ELEVENLABS_API_KEY` | `transcribe.py`, `transcribe_batch.py` | ElevenLabs Scribe API for word-level transcription with diarization. Required at transcription time; not needed for render/grade/pack steps. |

Key resolution order (see `transcribe.py:load_api_key`):
1. File `tools/video-use/.env` — line `ELEVENLABS_API_KEY=<value>`
2. Environment variable `ELEVENLABS_API_KEY`

If neither is present, `transcribe.py` calls `sys.exit()` with the message:
`"ELEVENLABS_API_KEY not found in .env or environment"`.

Template: copy `tools/video-use/.env.example` (contains only `ELEVENLABS_API_KEY=`)
and fill in the key.

## CLI flags / arguments

### transcribe.py

```
usage: transcribe.py [-h] [--edit-dir EDIT_DIR] [--language LANGUAGE]
                     [--num-speakers NUM_SPEAKERS]
                     video

positional arguments:
  video                 Path to video file

options:
  --edit-dir EDIT_DIR   Edit output directory (default: <video_parent>/edit)
  --language LANGUAGE   Optional ISO language code (e.g., 'en'). Omit to auto-detect.
  --num-speakers NUM_SPEAKERS
                        Optional number of speakers. Improves diarization accuracy.
```

### transcribe_batch.py

```
usage: transcribe_batch.py [-h] [--edit-dir EDIT_DIR] [--workers WORKERS]
                           [--language LANGUAGE] [--num-speakers NUM_SPEAKERS]
                           videos_dir

positional arguments:
  videos_dir            Directory containing source videos

options:
  --edit-dir EDIT_DIR   Edit output directory (default: <videos_dir>/edit)
  --workers WORKERS     Parallel workers (default: 4)
  --language LANGUAGE   Optional ISO language code. Omit to auto-detect per file.
  --num-speakers NUM_SPEAKERS
                        Optional number of speakers. Improves diarization when known.
```

### pack_transcripts.py

```
usage: pack_transcripts.py [-h] --edit-dir EDIT_DIR
                           [--silence-threshold SILENCE_THRESHOLD] [-o OUTPUT]

options:
  --edit-dir EDIT_DIR   Edit directory containing transcripts/  [REQUIRED]
  --silence-threshold SILENCE_THRESHOLD
                        Break phrases on silences >= this (seconds). Default 0.5.
  -o OUTPUT, --output OUTPUT
                        Output path (default: <edit-dir>/takes_packed.md)
```

### render.py

```
usage: render.py [-h] -o OUTPUT [--preview] [--draft] [--build-subtitles]
                 [--no-subtitles] [--no-loudnorm]
                 edl

positional arguments:
  edl                   Path to edl.json

options:
  -o OUTPUT, --output OUTPUT    Output video path  [REQUIRED]
  --preview             Preview mode: 1080p, CRF 22 — faster, evaluable for QC.
  --draft               Draft mode: 720p ultrafast CRF 28 — cut-point check only.
  --build-subtitles     Build master.srt from transcripts + EDL offsets before compositing.
  --no-subtitles        Skip subtitles even if the EDL references one.
  --no-loudnorm         Skip loudness normalization. Default is on (-14 LUFS, -1 dBTP, LRA 11).
```

### grade.py

```
usage: grade.py [-h] [-o OUTPUT]
                [--preset {subtle,neutral_punch,warm_cinematic,none}]
                [--filter FILTER] [--analyze ANALYZE]
                [--print-preset PRINT_PRESET] [--list-presets]
                [input]

positional arguments:
  input                 Input video

options:
  -o OUTPUT, --output OUTPUT    Output video
  --preset {subtle,neutral_punch,warm_cinematic,none}
                        Grade preset. Omit for auto mode (default).
  --filter FILTER       Raw ffmpeg filter string. Overrides --preset.
  --analyze ANALYZE     Analyze clip and print auto-grade filter. No output written.
  --print-preset PRINT_PRESET   Print filter string for a preset and exit.
  --list-presets        List available presets and exit.
```

### timeline_view.py

```
usage: timeline_view.py [-h] [-o OUTPUT] [--n-frames N_FRAMES]
                        [--transcript TRANSCRIPT] [--edl EDL]
                        [video] [start] [end]

positional arguments:
  video                 Source video
  start                 Start time in seconds
  end                   End time in seconds

options:
  -o OUTPUT, --output OUTPUT    Output PNG path
  --n-frames N_FRAMES   Number of frames in filmstrip (default 10)
  --transcript TRANSCRIPT
                        Path to transcript.json for word labels + silence shading.
                        Auto-resolves to <video_parent>/edit/transcripts/<stem>.json if omitted.
```

## Inputs

There is no single invocation that takes a raw folder and produces a final video
end-to-end. The pipeline is orchestrated in steps:

1. **Source videos** — any common video extension (`.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`).
   Pass a single file to `transcribe.py` or a directory to `transcribe_batch.py`.

2. **edit directory** — output staging area. Defaults to `<videos_dir>/edit/`.
   All intermediates and outputs land here. Helpers auto-create it.

3. **edl.json** — cut decision list produced by the LLM agent. `render.py` reads this.
   Schema: `{ "sources": {"name": "path"}, "ranges": [...], "grade": "auto"|preset|filter_str,
   "subtitles": "path-or-null", "overlays": [...] }`.

4. **transcripts/<name>.json** — cached raw Scribe JSON per source, in `edit/transcripts/`.
   Written by `transcribe.py`. Read by `pack_transcripts.py` and `render.py --build-subtitles`.

## Outputs

All session outputs land in `<videos_dir>/edit/`:

| File / Directory              | Produced by            | Description                                                     |
|-------------------------------|------------------------|-----------------------------------------------------------------|
| `transcripts/<name>.json`     | transcribe.py          | Raw Scribe JSON (word-level timestamps, diarization, events). Cached per source. |
| `takes_packed.md`             | pack_transcripts.py    | Human-readable phrase-level transcript, ~12 KB for one hour of footage. Primary reading surface for the LLM. |
| `edl.json`                    | LLM agent (not a helper) | Cut decisions: sources, ranges, grade, overlays, subtitle path. |
| `clips_graded/seg_NN_<src>.mp4` | render.py            | Per-segment extracts with grade + 30ms audio fades. |
| `clips_preview/` or `clips_draft/` | render.py (--preview/--draft) | Same, at lower quality. |
| `base.mp4` / `base_preview.mp4` / `base_draft.mp4` | render.py | Lossless concat of all graded segments. |
| `master.srt`                  | render.py --build-subtitles | Output-timeline SRT (2-word UPPERCASE chunks). |
| `preview.mp4`                 | render.py (by naming convention) | Intermediate preview (no hard-coded name; caller names the output via `-o`). |
| `final.mp4`                   | render.py (by naming convention) | Finished output video; caller names via `-o final.mp4`. |
| `verify/`                     | timeline_view.py       | Debug PNGs from self-eval passes. |
| `animations/slot_<id>/`       | LLM agent sub-agents   | Manim/Remotion/PIL animation source + renders. |
| `project.md`                  | LLM agent              | Persistent session memory; appended each session. |
| `downloads/`                  | yt-dlp (optional)      | Remote source downloads. |

Note: `final.mp4` and `preview.mp4` are **naming conventions only** — the caller
passes the path to `render.py -o <path>`. No helper hardcodes these names.

## Burned-in captions

**`--no-subtitles` flag exists in `render.py`** (`render.py:ap.add_argument('--no-subtitles', ...)`).

Subtitle behavior:
- **Default**: captions are applied only if `edl.json` has a `"subtitles"` key pointing to an SRT.
- **`--build-subtitles`**: generates `master.srt` from transcripts + EDL offsets inline, then burns it in.
- **`--no-subtitles`**: explicitly skips subtitle compositing even if the EDL references an SRT.

Default caption style (hardcoded in `render.py:SUB_FORCE_STYLE`):
```
FontName=Helvetica, FontSize=18, Bold=1, white text, black outline,
2-word UPPERCASE chunks, MarginV=90 (platform safe-zone, ~30% up from bottom)
```

There is no flag to change the style at call-time; the `force_style` string is a
constant in `render.py`. To change style, edit `SUB_FORCE_STYLE` in that file.

## Overlay / motion graphics generation

**No `--no-overlay` flag exists.** Overlay control is via the EDL.

Overlays are read from the `"overlays"` array in `edl.json`. If the array is absent
or empty, `render.py` skips the overlay compositing step entirely (see
`render.py:build_final_composite`). To suppress overlays, produce an `edl.json`
with no `"overlays"` key or an empty list.

Overlay types supported (via LLM-orchestrated sub-agents, not helpers directly):
- **Manim** — `skills/manim-video/` sub-skill; see `SKILL.md`.
- **Remotion** — mentioned in README; no helper script provided.
- **PIL** — image compositing via Pillow; no dedicated helper.

## Color grading control

Controlled via the `"grade"` field in `edl.json` **or** directly via `grade.py`.

| `edl.json` `"grade"` value | Behaviour |
|----------------------------|-----------|
| `"auto"` (default)         | Per-segment data-driven correction via `auto_grade_for_clip()`. Samples frames with ffmpeg `signalstats`, adjusts contrast/gamma/saturation ≤ ±8%. No creative color shift. |
| `"subtle"` / `"neutral_punch"` / `"warm_cinematic"` / `"none"` | Named presets applied uniformly to every segment. |
| Any other string           | Treated as a raw ffmpeg `-vf` filter string. |

Available named presets (from `grade.py:PRESETS`):

| Preset           | Filter chain (abbreviated)                          |
|------------------|-----------------------------------------------------|
| `subtle`         | `eq=contrast=1.03:saturation=0.98`                  |
| `neutral_punch`  | eq contrast+S-curve, no color shift                 |
| `warm_cinematic` | +12% contrast, crushed blacks, -12% sat, warm/cool colorbalance, filmic curve |
| `none`           | No filter (copy)                                    |

`grade.py --filter '<raw>'` overrides presets with an arbitrary ffmpeg filter string.

## Transcript schema

The Scribe API response is a JSON object. Top-level keys (observed 2026-04-27):

| Key                    | Type    | Description |
|------------------------|---------|-------------|
| `"language_code"`      | string  | ISO 639-3 code, e.g. `"eng"` |
| `"language_probability"` | float | Detection confidence, 0–1 |
| `"text"`               | string  | Full flat transcript text |
| `"words"`              | array   | Per-token entries (words, spacing, audio events) |
| `"transcription_id"`   | string  | Unique Scribe job ID |
| `"audio_duration_secs"` | float  | Length of the audio submitted (seconds) |

Each element of `"words"` is one of three typed entries:

| `type`        | Fields present                                          | Notes |
|---------------|---------------------------------------------------------|-------|
| `"word"`      | `type`, `text`, `start` (float s), `end` (float s), `speaker_id` (string), `logprob` (float) | Actual spoken word. `speaker_id` is `"speaker_0"`, `"speaker_1"`, etc. |
| `"spacing"`   | `type`, `text` (space char), `start` (float s), `end` (float s), `speaker_id`, `logprob` | Gap between words; gap duration = `end - start`. Used by `pack_transcripts.py` to break phrases on silences >= threshold. |
| `"audio_event"` | `type`, `text` (e.g. `"(laughter)"`), `start` (float s), `end` (float s) | Non-speech sound event. `speaker_id` may be absent. |

Real snippet from smoke test (2026-04-27, first 4 entries of `raw.json`):

```json
{
  "language_code": "eng",
  "language_probability": 0.9712164402008057,
  "text": "Hello, this is a smoke test for video use. Let's see what happens.",
  "transcription_id": "xuesod2C5O2VuxKe2h6T",
  "audio_duration_secs": 4.2260625,
  "words": [
    { "text": "Hello,", "start": 0.099, "end": 0.439, "type": "word",    "speaker_id": "speaker_0", "logprob": -0.0805 },
    { "text": " ",      "start": 0.439, "end": 0.560, "type": "spacing", "speaker_id": "speaker_0", "logprob": -0.0039 },
    { "text": "this",   "start": 0.560, "end": 0.659, "type": "word",    "speaker_id": "speaker_0", "logprob": -0.0039 },
    { "text": " ",      "start": 0.659, "end": 0.699, "type": "spacing", "speaker_id": "speaker_0", "logprob": -0.0007 }
  ]
}
```

Key parsing notes (from `pack_transcripts.py` and `render.py`):
- Only `"word"` entries are used for subtitle generation (`render.py:_words_in_range`).
- `"spacing"` entries are used only for phrase-break detection (gap = `end - start`).
- `"audio_event"` entries are included in `takes_packed.md` text but skipped for subtitle chunks.
- All timestamps are **floating-point seconds** from the start of the source audio.
- The full response from ElevenLabs Scribe is written verbatim to
  `edit/transcripts/<stem>.json` — no transformation before caching.
- Note: `"spacing"` entries DO have a `text` field (a space character) and `speaker_id`
  in practice — the schema docs previously said they had no `text`, but observed output
  shows they carry `" "` and `speaker_id` alongside `logprob`.

## Packed transcript shape (takes_packed.md)

`pack_transcripts.py` groups word-level entries into phrase-level lines, breaking on
any silence >= 0.5s OR speaker change. Each phrase gets a `[start-end]` prefix, a
speaker tag (`SN`), and the phrase text.

Real output from smoke test (2026-04-27, 6s input, 1 speaker):

```markdown
# Packed transcripts

Phrase-level, grouped on silences >= 0.5s or speaker change.
Use `[start-end]` ranges to address cuts in the EDL.

## raw  (duration: 3.8s, 1 phrases)
  [000.10-003.90] S0 Hello, this is a smoke test for video use. Let's see what happens.
```

Format details:
- `[NNN.NN-NNN.NN]` — start/end in seconds, 2 decimal places, zero-padded to 6 chars.
- `SN` — speaker suffix; `"speaker_0"` → `S0`, `"speaker_1"` → `S1`, etc.
- One phrase per line; phrases separated by blank lines between takes (video files).
- File header: `## <stem>  (duration: Xs, N phrases)`.
- Windows encoding note: the `>=` in the header is a Unicode `>=` (U+2265); on Windows
  with a non-UTF-8 locale, `PYTHONUTF8=1` must be set or `write_text(encoding='utf-8')`
  used, otherwise `pack_transcripts.py` raises `UnicodeEncodeError` for `cp1251`.

## EDL schema

`edl.json` is hand-authored by the LLM agent and consumed by `render.py`. The schema
is inferred definitively from `render.py` source (lines 218–243, 310–320, 619–625).

### Top-level keys

| Key              | Type          | Required | Description |
|------------------|---------------|----------|-------------|
| `"sources"`      | object        | YES      | Map of logical source name → path string. |
| `"ranges"`       | array         | YES      | Ordered list of cut segments. |
| `"grade"`        | string        | NO       | Grade spec: preset name, `"auto"`, `"none"`, or raw ffmpeg filter string. Defaults to no-op if absent. |
| `"overlays"`     | array         | NO       | List of overlay objects. Omit or use `[]` for no overlays. |
| `"subtitles"`    | string        | NO       | Path to SRT file. Omit or `null` for no subtitles. |
| `"version"`      | integer       | NO       | Schema version sentinel (value `1`). Present in SKILL.md example; not read by `render.py`. |
| `"total_duration_s"` | number   | NO       | Documentation field only; not read by `render.py`. |

### `"sources"` object

Keys are arbitrary logical names (used as `r["source"]` references in ranges and as
the segment filename stem). Values are path strings — either absolute or relative
to the **directory containing `edl.json`** (i.e. the `edit/` dir). Resolution:

```python
# render.py:resolve_path
p = Path(maybe_path)
if p.is_absolute():
    return p
return (base / p).resolve()   # base = edl_path.parent (the edit/ dir)
```

Example:
```json
"sources": {
  "raw": "/abs/path/to/raw.mp4",
  "b_roll": "../footage/broll.mp4"
}
```

### Per-range (clip) fields

Each element of `"ranges"` is an object:

| Field      | Type    | Required | Units   | Description |
|------------|---------|----------|---------|-------------|
| `"source"` | string  | YES      | —       | Must match a key in `"sources"`. |
| `"start"`  | number  | YES      | seconds (float) | Inclusive start time in source file. Cast via `float()`. |
| `"end"`    | number  | YES      | seconds (float) | Exclusive end time in source file. `duration = end - start`. |
| `"beat"`   | string  | NO       | —       | Narrative label (e.g. `"HOOK"`). Logged to console; not used in render. |
| `"quote"`  | string  | NO       | —       | Representative quote. Logged to console; not used in render. |
| `"note"`   | string  | NO       | —       | Alternative to `"beat"` for log label. |
| `"reason"` | string  | NO       | —       | Editorial note. Not read by `render.py`. |

Time format: **decimal seconds as a JSON number** (or numeric string — `render.py`
wraps in `float()`). Not milliseconds, not frames. E.g. `2.42`, `28.900`.

### `"overlays"` array

Each overlay object:

| Field               | Type   | Required | Units   | Description |
|---------------------|--------|----------|---------|-------------|
| `"file"`            | string | YES      | —       | Path to overlay video. Resolved relative to `edit/` dir (same rules as sources). |
| `"start_in_output"` | number | YES      | seconds | Output-timeline position where overlay frame 0 lands. |
| `"duration"`        | number | YES      | seconds | How long overlay is visible. `end = start_in_output + duration`. |

To express "no overlays": omit the key entirely, or set `"overlays": []`.
`render.py` does `overlays = edl.get("overlays") or []`.

### `"subtitles"` field

String path to an SRT file (absolute or relative to `edit/` dir). If the file does
not exist at render time, `render.py` logs a warning and skips subtitles silently.
To suppress: omit the key, set to `null`, or pass `--no-subtitles` at the CLI.

### `"grade"` field

| Value               | Behaviour |
|---------------------|-----------|
| omitted / `null`    | No filter applied (empty string passed to ffmpeg `-vf`). |
| `"auto"`            | Per-segment data-driven analysis via `auto_grade_for_clip()`. Each segment analyzed separately. |
| `"subtle"`          | `eq=contrast=1.03:saturation=0.98` |
| `"neutral_punch"`   | Contrast + gentle S-curve, no color shift. |
| `"warm_cinematic"`  | +12% contrast, crushed blacks, teal/orange colorbalance, filmic curve. |
| `"none"`            | Explicit no-op (empty filter, copy pass). |
| Any other string    | Treated as raw ffmpeg `-vf` filter string. |

To express "do not grade" in the JSON: use `"grade": "none"` or omit the key.
The `--no-loudnorm` CLI flag is audio-only and unrelated to the grade field.

### Output resolution / fps

**NOT controlled by `edl.json`.** Hardcoded in `render.py:extract_segment`:

- Final mode: `scale=1920:-2`, `-r 24`, `-c:v libx264 -preset fast -crf 20`
- Preview mode: `scale=1920:-2`, `-r 24`, `-c:v libx264 -preset medium -crf 22`
- Draft mode: `scale=1280:-2`, `-r 24`, `-c:v libx264 -preset ultrafast -crf 28`

**Target mismatch with our spec (1440×2560 @ 60fps Rec.709 SDR):** `render.py`
hardcodes `scale=1920:-2` (landscape 1080p), `-r 24` fps, and `yuv420p` (SDR). For
our 1440×2560 vertical 60fps target:
- The `scale` filter would need to be changed to `scale=1440:2560` (or `scale=-2:2560`).
- The `-r 24` would need to be `-r 60`.
- Rec.709 SDR is naturally produced (yuv420p + HDR→SDR tonemap chain). No extra flag needed.
- These parameters are hardcoded constants, not EDL fields. The `edl.json` cannot
  override them. **Either patch `render.py` or pass a custom `"grade"` filter that
  includes a scale override** (the grade field is injected into the `-vf` chain,
  so `"grade": "scale=1440:2560,eq=contrast=1.03"` would override resolution).
  UNCLEAR — see `render.py:extract_segment` lines 158–193 for the exact vf assembly
  order; a `scale` baked into the grade field would conflict with the hardcoded scale.
  Recommend patching `extract_segment` directly for our pipeline.

### Minimal valid `edl.json` example

Concatenates two segments from `raw.mp4` (0–2s and 3–5s), no overlays, no
subtitles, no grading:

```json
{
  "version": 1,
  "sources": {
    "raw": "/abs/path/to/edit/../raw.mp4"
  },
  "ranges": [
    {
      "source": "raw",
      "start": 0.0,
      "end": 2.0,
      "beat": "seg1",
      "reason": "first two seconds"
    },
    {
      "source": "raw",
      "start": 3.0,
      "end": 5.0,
      "beat": "seg2",
      "reason": "seconds 3-5"
    }
  ],
  "grade": "none",
  "overlays": [],
  "subtitles": null
}
```

Invocation (CWD = `tools/video-use/`, edl.json lives in the `edit/` dir):

```bash
uv run python helpers/render.py /abs/path/to/edit/edl.json \
  -o /abs/path/to/edit/stage1.mp4 \
  --no-subtitles \
  --no-loudnorm
```

Notes on the minimal example:
- `"sources"` value must be an absolute path or a path relative to the **`edit/` dir**
  (the directory containing `edl.json`), NOT relative to `tools/video-use/` and NOT
  relative to the caller's CWD.
- `"grade": "none"` and `"overlays": []` are both safe explicit no-ops. Omitting
  `"grade"` also works (resolves to empty filter).
- `"subtitles": null` is equivalent to omitting the key; `--no-subtitles` CLI flag
  provides a belt-and-suspenders override.
- `"version"` and `"reason"` fields are not read by `render.py`; they are
  documentation-only conventions from SKILL.md.

## grade.py behavior

### CLI invocation

```bash
# CWD = tools/video-use/
uv run python helpers/grade.py <input> -o <output>                     # auto mode (default)
uv run python helpers/grade.py <input> -o <output> --preset warm_cinematic
uv run python helpers/grade.py <input> -o <output> --filter 'eq=contrast=1.1:saturation=0.95'
uv run python helpers/grade.py --analyze <input>                       # print auto-grade filter, no output
uv run python helpers/grade.py --print-preset warm_cinematic           # print filter string and exit
uv run python helpers/grade.py --list-presets                          # list all presets and exit
```

### What it does

`grade.py` is a thin CLI wrapper around an ffmpeg `-vf` filter chain. It has two
operating modes:

**1. Auto mode (default when neither `--preset` nor `--filter` is passed):**
Calls `auto_grade_for_clip()`, which samples N frames from the clip using
`ffmpeg signalstats` to measure mean luma (`YAVG`), luma range (`YMIN`/`YMAX`),
and mean saturation (`SATAVG`). It then emits an `eq=contrast=X:gamma=Y:saturation=Z`
filter string bounded to ±8% on every axis. Goals: correct underexposure, flatness,
mild desaturation. Explicitly avoids color shifts, LUTs, and creative grade.

**2. Preset mode (`--preset`) / raw filter mode (`--filter`):**
Applies a fixed filter string. Presets are:

| Preset           | Filter string |
|------------------|---------------|
| `subtle`         | `eq=contrast=1.03:saturation=0.98` |
| `neutral_punch`  | `eq=contrast=1.06:brightness=0.0:saturation=1.0,curves=master='0/0 0.25/0.23 0.75/0.77 1/1'` |
| `warm_cinematic` | `eq=contrast=1.12:brightness=-0.02:saturation=0.88,colorbalance=rs=0.02:gs=0.0:bs=-0.03:rm=0.04:gm=0.01:bm=-0.02:rh=0.08:gh=0.02:bh=-0.05,curves=master='0/0 0.25/0.22 0.75/0.78 1/1'` |
| `none`           | (empty — copy pass) |

### Configurability

No config file. Grade is controlled only by CLI flags (`--preset`, `--filter`) or
by the `"grade"` field in `edl.json` (which `render.py` resolves to a filter string
before calling the same internal functions). No persistent state between invocations.

### Resolution, fps, color metadata

`grade.py` always re-encodes video when a filter is applied:
```
ffmpeg -vf <filter> -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a copy
```
- **Resolution**: preserved (no scale filter added).
- **FPS**: preserved (no `-r` flag in `apply_grade`).
- **Color metadata**: output is `yuv420p` 8-bit. No `-colorspace`, `-color_primaries`,
  or `-color_trc` flags are set. If the input carries Rec.709 metadata, it is
  **preserved passively** by libx264 (it copies stream metadata unless overridden).
  If the input is HDR, `grade.py` alone does NOT tonemap — that is only done inside
  `render.py:extract_segment` (the `TONEMAP_CHAIN`). `grade.py` is not HDR-aware.

When the filter is empty (`"none"` preset), `grade.py` uses `-c copy` (no re-encode,
all metadata preserved exactly).

### Verdict: does grade.py replace our planned `tools/compositor/grade.json` + ffmpeg pass?

**Partial replacement — different concerns, complementary.**

`grade.py` / the `"grade"` field in `edl.json` handles **corrective and
stylistic video grade** (contrast, gamma, saturation, S-curve, color balance).
It does this at segment-extract time, baked into each `clips_graded/seg_NN.mp4`.

Our planned `tools/compositor/grade.json` + ffmpeg pass was intended to apply
**post-composite corrections** (eq + vignette) after concat and overlay compositing.
That use-case is NOT covered by `grade.py`, which operates per-segment before concat.

Specifically:
- **Vignette**: no vignette filter in any `grade.py` preset or auto-grade path.
  If we want a vignette, we must add it ourselves (either by injecting it into the
  `"grade"` field as a raw filter, e.g. `"grade": "eq=contrast=1.03,vignette"`, or
  as a post-composite ffmpeg pass).
- **Post-composite eq**: `grade.py` does not run on the concatenated output. Any
  whole-video correction must be a separate step.
- **Color metadata tagging** (explicit Rec.709 primaries/transfer): neither
  `grade.py` nor `render.py` explicitly tag `-colorspace bt709 -color_primaries bt709
  -color_trc bt709` on the output. If strict Rec.709 container metadata is required
  for delivery, a post-processing ffmpeg pass with those flags is still needed.

**Conclusion:** for stage-1 (cut assembly only, no creative grade, no vignette):
- Set `"grade": "none"` in `edl.json` and pass `--no-loudnorm` to render.py to get
  a clean ungraded cut.
- The `tools/compositor/grade.json` + ffmpeg pass is still needed for vignette,
  post-composite eq, and explicit Rec.709 metadata tagging.
- If we want `grade.py`-style auto-correction without a separate pass, use
  `"grade": "auto"` in the EDL — this is the simplest integration point.

## Notes & gotchas

1. **No top-level CLI binary.** `uv run video-use` will fail — there is no
   console_scripts entry. Always invoke as `uv run python helpers/<name>.py`.

2. **CWD must be `tools/video-use/`** when running helpers that import each other
   (`transcribe_batch.py` imports `transcribe`). Absolute paths for the video/dir
   args are fine; the CWD requirement is for the Python import resolution.

3. **ffmpeg and ffprobe are hard requirements.** Must be on `PATH`. The helpers
   call `ffmpeg`/`ffprobe` as bare commands via `subprocess.run`. No Python
   wrapper; if they are absent the helpers crash immediately.

4. **ElevenLabs Scribe makes API calls.** `transcribe.py` and `transcribe_batch.py`
   hit `https://api.elevenlabs.io/v1/speech-to-text`. This costs credits and
   requires a live network connection. Transcripts are cached — if
   `edit/transcripts/<name>.json` exists the upload is skipped.

5. **HDR source handling.** `render.py` auto-detects HLG/PQ sources via `ffprobe`
   and prepends a `zscale+tonemap` chain (Rec.2020 → Rec.709 SDR) before grading.
   No flag needed; it is automatic.

6. **Loudness normalization is on by default.** `render.py` always runs a two-pass
   `loudnorm` (-14 LUFS / -1 dBTP / LRA 11) unless `--no-loudnorm` is passed.
   This doubles render time on long videos. Use `--draft` to skip for cut-point
   checks.

7. **No GPU acceleration.** All encoding uses libx264 (CPU). Slow for 4K sources;
   1080p final encode is typically fast enough on modern laptops.

8. **No model downloads.** No ML models are bundled. The only remote service is
   ElevenLabs Scribe. grade/render/pack/timeline_view all run fully offline once
   deps are installed.

9. **manim is an optional dependency.** `pyproject.toml` lists it under
   `[project.optional-dependencies] animations`. It is not installed by default
   with `uv sync`. Install with `uv sync --extra animations` only when Manim
   overlays are needed.

10. **yt-dlp is optional.** Not in `pyproject.toml`; referenced in README/install.md
    only. Install separately if online source downloads are needed.

11. **Subtitle style is hardcoded.** `SUB_FORCE_STYLE` in `render.py` (Helvetica 18
    Bold, 2-word UPPERCASE, MarginV=90) cannot be changed via CLI flags. Edit the
    constant directly to change the style.

12. **The LLM produces edl.json, not a helper.** `render.py` consumes the EDL but
    does not create it. The EDL is an artifact of the agent's editing session.
    For automated pipelines (`run-stage1.sh`), the EDL must be produced by a
    separate LLM invocation before `render.py` is called.

13. **Windows UTF-8 encoding required for pack_transcripts.py.** The packed markdown
    contains Unicode characters (>=, U+2265). On Windows with a cp1251 locale, running
    without `PYTHONUTF8=1` raises `UnicodeEncodeError`. Always set `PYTHONUTF8=1` (or
    `PYTHONIOENCODING=utf-8`) before invoking `pack_transcripts.py` on Windows.

## Observed smoke test (2026-04-27)

- Working dir: /tmp/video-use-smoke
- Inputs: raw.mp4 (6s nominal / 4.2s actual audio, 1440x2560 60fps, blue background, ElevenLabs TTS Rachel voice)
- speech.mp3: 68,589 bytes (ElevenLabs TTS, eleven_turbo_v2, Rachel voice ID 21m00Tcm4TlvDq8ikWAM)
- raw.mp4: 129,996 bytes (h264 High, yuv420p, 1440x2560, 60fps, bt709, aac 44.1kHz mono)
- transcribe.py produced: /tmp/video-use-smoke/edit/transcripts/raw.json, 4,741 bytes, 25 word-tokens, completed in 1.4s
- pack_transcripts.py produced: /tmp/video-use-smoke/edit/takes_packed.md, 269 bytes, 1 phrase
- API spend: ~150 TTS credits (eleven_turbo_v2, ~70 chars) + ~6 Scribe credits (4.2s audio)
- PYTHONUTF8=1 required on Windows to avoid UnicodeEncodeError in pack_transcripts.py (cp1251 locale)
