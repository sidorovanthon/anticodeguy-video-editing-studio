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

TBD — recorded in Task 3 smoke test.

For reference, the Scribe JSON structure is accessed in `pack_transcripts.py` as:
```json
{
  "words": [
    { "type": "word", "text": "Hello", "start": 1.23, "end": 1.56, "speaker_id": "speaker_0" },
    { "type": "spacing", "start": 1.56, "end": 1.80 },
    { "type": "audio_event", "text": "(laughter)", "start": 2.10, "end": 2.40 }
  ]
}
```
Full schema will be confirmed in Task 3 with a real Scribe response.

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
