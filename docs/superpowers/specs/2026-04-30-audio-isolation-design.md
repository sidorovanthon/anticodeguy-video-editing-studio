# Spec B — Audio Isolation Phase

**Date:** 2026-04-30
**Source:** `retro.md` §1.6 (proposal from pilot run of `/edit-episode`, 2026-04-30)
**Scope:** Insert an Audio Isolation phase (ElevenLabs) between Pickup and the video-use sub-agent so that Scribe transcribes a clean audio track and `final.mp4` is rendered with studio-grade sound without an explicit grading step.
**Predecessor:** Spec A (`2026-04-30-pipeline-enforcement-design.md`) — pipeline contract, sub-agent dispatch, manual scaffold, output-timeline transcript, episode pickup. This spec adds one phase; everything else from Spec A stands.

---

## 1. Context and motivation

Phase 1 of the pilot run (Spec A's `video-use` Phase 2, now renumbered) sent the raw camera audio straight to ElevenLabs Scribe. Three downstream consequences:

1. **Scribe accuracy.** Room reverb and HVAC noise produce mid-word `(silence)` artifacts and timestamp drift, which cascades into worse cut boundaries and worse caption sync.
2. **Final audio.** Even after `loudnorm` in `helpers/render.py`, the noise floor is audible. Loudnorm normalizes against a noisy signal, inflating LRA and yielding a washy mix.
3. **No grading escape hatch.** `video-use` does not provide an audio-grading step beyond loudnorm + per-segment fades; cleaning has to happen *before* video-use sees the file.

Inserting Audio Isolation as a dedicated phase before `video-use` solves all three. It is mechanically the cheapest fix because both ElevenLabs services share an API key we already have, the work is a single deterministic API call + ffmpeg mux (no creative judgment), and the existing canon-respect rule (CLAUDE.md §"External skill canon — non-negotiable") is preserved — `video-use` is unmodified and unaware of isolation.

---

## 2. Phase numbering

Audio isolation slots between Pickup and Video edit. Phases are renumbered (natural integers, no `0.5`):

| # | Name | Owner | Tool | Cost |
|---|---|---|---|---|
| 1 | Pickup | orchestrator | inline script | free |
| 2 | **Audio isolation** | orchestrator | inline script | **ElevenLabs Audio Isolation API** |
| 3 | Video edit | `video-use` | `Agent` (sub-agent) | ElevenLabs Scribe |
| 4 | Composition + studio | `hyperframes` | `Skill` (main session) | free |

Spec A's Phase 2 / Phase 3 references shift by one — `edit-episode.md` is updated accordingly.

---

## 3. Design decisions (the five user-approved points)

### 3.1 Phase 2 runs inline, not as a sub-agent

The work is fully deterministic — call the API, write the response to disk, mux into the video container — with no creative judgment. Following Spec A's pattern (Phase 1 / `pickup.py` is inline; Phase 3 / `video-use` is a sub-agent because cuts are discipline-heavy), Phase 2 is an inline script invoked from `edit-episode.md`.

This avoids a sub-agent cold-start for a step that takes one HTTP call and one ffmpeg invocation, and keeps stdout/exit-code semantics simple for the orchestrator.

### 3.2 In-place overwrite of `raw.<ext>`, no `.cleaned` postfix

The cleaned audio is muxed back into `raw.<ext>` (replacing only the audio stream; video stream is `-c:v copy`). After Phase 2, `raw.<ext>` is the canonical input for the rest of the pipeline; `video-use` is pointed at it exactly as today, and the Scribe cache slot remains `transcripts/raw.json` (Hard Rule 9 cache key is the input video stem; unchanged file name → unchanged cache slot).

Rejected alternatives:
- **Sibling `raw.cleaned.<ext>`.** Adds ~33 MB per episode and a divergent path threaded through every downstream brief. Rollback to "compare cleaned vs original" is a speculative feature not requested in retro §1.6.
- **Side-channel `audio/raw.cleaned.wav` consumed by video-use directly.** Would require an upstream patch to `video-use/helpers/transcribe.py` and `render.py` to accept a separate audio path. Forbidden by CLAUDE.md §"External skill canon — non-negotiable".

### 3.3 API-response cache as `episodes/<slug>/audio/raw.cleaned.wav`, with idempotency tag on the muxed stream

Two-level cache:

1. **API cache.** `episodes/<slug>/audio/raw.cleaned.wav` is the raw bytes of the API response. Presence of this file → skip the API call on re-runs. This is the expensive cache (avoids re-spending Audio Isolation credits).
2. **Mux idempotency tag.** When step 5 of §4.1 muxes the cleaned audio into `raw.<ext>`, it also sets an ffmpeg metadata tag at the **container/format level**: `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1` via `-movflags use_metadata_tags -metadata`. On any future run, `ffprobe -show_format` reads this tag — if present, the script is a full no-op (no API call, no mux). (The tag was originally placed at the per-stream level via `-metadata:s:a:0`; real-API smoke testing revealed mp4 silently drops custom per-stream metadata keys, so the design moved to container-level. mp4 lowercases the key on write while mkv preserves case — the read path is therefore case-insensitive.)

The version suffix (`-v1`) lets us invalidate later if isolation parameters change (e.g., switching to a paid model that produces a different mix). To force re-isolation: delete `audio/raw.cleaned.wav` AND drop the tag (or restore raw.<ext> from inbox / source).

The cleaned WAV is also useful as an audit artifact — the user can listen to the isolated track in isolation (pun intended) without the muxed-video context.

### 3.4 Phase 3 (video-use) brief: one added sentence about pre-cleaned audio

The verbatim brief for the `video-use` sub-agent (Spec A §5.1) gets one sentence prepended after the strategy-confirmation paragraph:

> The audio track of `raw.<ext>` has already been processed by ElevenLabs Audio Isolation in Phase 2 — treat it as a studio-grade source. Do not apply additional noise-suppression filters; loudnorm and the per-segment 30ms fades from Hard Rule 3 are still required.

No other change to the Phase 3 brief. Hard Rule 9's transcript cache key remains `raw.<ext>`'s stem — unchanged file name means unchanged cache slot, so re-running Phase 3 after Phase 2 finishes does not pay for Scribe twice.

### 3.5 API key reuses `ELEVENLABS_API_KEY` via the video-use lookup ladder

`video-use/helpers/transcribe.py` resolves the key in this order: (1) `<video-use-repo>/.env`, (2) project-cwd `.env`, (3) environment variable. Spec B's `isolate_audio.py` mirrors that exactly so a single key drives both Audio Isolation and Scribe. No new secret to provision.

---

## 4. Glue script — `scripts/isolate_audio.py`

### 4.1 Behavior

**CLI:** `python -m scripts.isolate_audio --episode-dir <EPISODE_DIR>`.

The script discovers `raw.<ext>` itself by scanning `<EPISODE_DIR>` for the supported extensions (`mp4|mov|mkv|webm`, case-insensitive, exactly one match expected — error if zero or more than one).

**Steps:**

1. **Tag check.** Run `ffprobe -v quiet -print_format json -show_format raw.<ext>`. If `format.tags` contains a key matching `ANTICODEGUY_AUDIO_CLEANED` (case-insensitive — mp4 lowercases container metadata keys, mkv preserves case) with value `elevenlabs-v1`, exit 0 immediately with stdout `{"cached": true, "api_called": false, "reason": "tag-present", "wav_path": "...", "raw_path": "..."}`. Full no-op.

2. **WAV cache check.** If `<EPISODE_DIR>/audio/raw.cleaned.wav` exists, skip step 3 (API call); jump to step 5 (mux).

3. **Audio extraction.** ffmpeg into a temp file: `ffmpeg -y -i raw.<ext> -vn -ac 2 -ar 48000 -c:a pcm_s16le <tmp>/source.wav`. (Stereo 48 kHz PCM is the lossless ingest format; the API may downsample server-side, that is fine.)

4. **API call.** `POST https://api.elevenlabs.io/v1/audio-isolation` with `xi-api-key: <KEY>` header and the WAV as multipart `audio` field. Response body is the cleaned audio bytes. Atomic write to `<EPISODE_DIR>/audio/raw.cleaned.wav` via temp + rename.

   The exact endpoint name, request multipart shape, and response content type are pinned at implementation time against the live ElevenLabs docs (it is plausible the response is `audio/mpeg` rather than `audio/wav`; if so, decode-then-re-encode to PCM WAV before writing the cache — the cache file MUST be PCM WAV regardless of what the API returns, so the mux step's command line is stable).

   Failure modes that exit non-zero with a single specific message: missing API key, non-200 response, network error, response body empty/malformed. No retries.

5. **Mux.** ffmpeg combines the original video stream with the cleaned WAV, stamping the idempotency tag:

   ```
   ffmpeg -y -i raw.<ext> -i audio/raw.cleaned.wav \
     -map 0:v -map 1:a \
     -c:v copy -c:a aac -b:a 192k \
     -metadata:s:a:0 ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1 \
     <tmp>/raw.muxed.<ext>
   ```

   Then atomically rename `<tmp>/raw.muxed.<ext>` over `raw.<ext>`. The video stream is not re-encoded (`-c:v copy`).

6. **Stdout.** JSON line: `{"cached": false, "api_called": true_or_false, "wav_path": "<abs>", "raw_path": "<abs>"}`. `api_called` is `false` when step 2 hit the WAV cache.

### 4.2 Failure handling

Fail-fast on every error. The script returns a non-zero exit code and a single specific reason on stderr:

- `ELEVENLABS_API_KEY not found` (no key in `.env` or env)
- `Audio Isolation API returned <status>: <body-snippet>`
- `Network error: <message>` (connect/read timeout, DNS, etc.)
- `ffmpeg failed at extract|mux step: <stderr-tail>`
- `raw.<ext> ambiguous in <EPISODE_DIR>: matched [...]`
- `raw.<ext> not found in <EPISODE_DIR>`
- `Disk full / write error: <path>`

`edit-episode.md` reads the exit code; on non-zero, it stops the pipeline and surfaces the message to the user. There is no `--skip-isolation` flag — running without isolation is not a supported mode.

### 4.3 UTF-8 / Windows hygiene

Same as Spec A §7.3. `PYTHONUTF8=1` is set globally; the script uses `pathlib` for all path operations and never depends on cp1251. ffmpeg subprocesses are invoked with `subprocess.run(..., check=True)` — no shell interpolation.

---

## 5. `edit-episode.md` integration

### 5.1 New phase block (between current Phase 1 and Phase 2)

```
## Phase 2 — Audio isolation

Run inline:

```bash
python -m scripts.isolate_audio --episode-dir <EPISODE_DIR>
```

Parse the JSON on stdout. Fields: `cached`, `api_called`, `wav_path`, `raw_path`.

- If `cached: true`: announce `Phase 2 already complete (container tagged) — skipping isolation.` and proceed.
- If `cached: false, api_called: false`: announce `Phase 2 used cached WAV (audio/raw.cleaned.wav) — remuxed into raw.<ext>.`
- Otherwise announce `Phase 2 done — audio isolated and muxed into raw.<ext>. Cache at <wav_path>.`

On non-zero exit: stop the pipeline, surface stderr to the user, instruct them to fix the underlying issue (typically API key or network) and re-run `/edit-episode <slug>`. Do not retry.
```

### 5.2 Phase 3 brief addition

Spec A §5.1 / §5 of `edit-episode.md` Phase 2 brief gets the sentence from §3.4 above, inserted directly after the strategy-confirmation paragraph.

### 5.3 Idempotency block update

The skip-rules list in `edit-episode.md` (Spec A §6, "Idempotency and rebuild guidance") expands from three checkpoints to four:

1. `<EPISODE_DIR>/raw.<ext>` container tagged `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1` → skip Phase 2 entirely. *(new)*
2. `<EPISODE_DIR>/edit/final.mp4` exists → skip Phase 3 (video-use).
3. `<EPISODE_DIR>/edit/transcripts/final.json` exists → skip glue remap.
4. `<EPISODE_DIR>/hyperframes/index.html` exists → skip scaffold + Skill, only relaunch studio.

Rebuild guidance gets a fourth bullet:

- **Re-isolate audio.** Delete `<EPISODE_DIR>/audio/raw.cleaned.wav` AND restore `raw.<ext>` to its un-tagged state (re-pickup from `inbox/`, or `git`/manual restore). Costs ElevenLabs Audio Isolation credits. Almost never needed; documented for completeness.

The existing re-cut and re-compose paths from Spec A do **not** trigger Phase 2 re-spend, because the container tag survives those operations:

- **Re-cut** (delete `edit/final.mp4` and `hyperframes/`): Phase 2 no-ops on tag, Phase 3 sees the cleaned audio it expects.
- **Re-compose** (delete `hyperframes/`): Phase 2 and Phase 3 both no-op.

---

## 6. Cost model — what spends ElevenLabs credits

Two paid steps, each cached on a per-source basis:

| Phase | Service | Cache artifact | Per-source key |
|---|---|---|---|
| 2 | Audio Isolation | `episodes/<slug>/audio/raw.cleaned.wav` + container tag on `raw.<ext>` | `raw.<ext>` (immutable after pickup) |
| 3 | Scribe (transcribe) | `episodes/<slug>/edit/transcripts/raw.json` | `raw.<ext>` stem |

Deleting `episodes/<slug>/` deletes both caches; re-running on a fresh pickup of the same source pays both. No other operations re-spend credits.

---

## 7. Repository hygiene

- `scripts/isolate_audio.py` — new file, alongside the other glue scripts. Same `from scripts.slugify import ...`-style package layout (Spec A §4.1 rationale).
- `episodes/<slug>/audio/` — new subdirectory under each episode; covered by the existing `episodes/` `.gitignore` entry. No new ignore rules needed.
- No new dependencies. The existing Python stack (`requests`, `pathlib`, `subprocess`) is sufficient. ffmpeg is already required by `video-use`.

---

## 8. Out of scope

- **Isolation intensity / preserve-ambience tuning.** Use the API default. Add knobs only if a future retro shows the default is wrong for our content.
- **Multi-track / 5.1 audio.** We mux whatever the API returns (presumed mono or stereo). Source files with surround tracks downmix to stereo at extraction. No special handling.
- **Local fallback (RNNoise, demucs, etc.).** ElevenLabs only. Fail-fast if unavailable; the user re-runs when the API is back.
- **Pre-isolation noise gate / loudness pre-emphasis.** None. Send the raw extracted WAV to the API as-is.
- **Inbox-side preview** (let the user listen to cleaned audio before committing to the rest of the pipeline). YAGNI; if needed, the cached `audio/raw.cleaned.wav` is right there and any audio player will open it.
- **Upstream patches to `video-use`.** Forbidden by CLAUDE.md.

---

## 9. Verified API contract

All items below were resolved during implementation by reading the live ElevenLabs docs and the official Python SDK source (`elevenlabs-python/src/elevenlabs/audio_isolation/raw_client.py`).

1. **Endpoint and request shape — confirmed.** `POST https://api.elevenlabs.io/v1/audio-isolation`. Auth: `xi-api-key` header. Body: `multipart/form-data` with field `audio` (binary). Optional form fields: `file_format` (`pcm_s16le_16` or `other`, default `other`), `preview_b64` (we omit). API limits: 500 MB / 1 hour per call. Cost: 1000 characters per minute of audio (same per-minute pricing tier as Scribe).
2. **Response content type — confirmed.** With default `file_format="other"`, the response body is **streamed MP3 bytes** (`Content-Type` audio stream, consumed via `iter_bytes` in the SDK). The script receives the full body via `requests`'s `resp.content`; for sources beyond ~10 minutes a switch to `iter_content` would avoid holding the full body in RAM. `normalize_to_pcm_wav_cmd` re-encodes the MP3 into PCM WAV before the cache write, giving the mux step a stable input shape regardless of the API's output codec.
3. **AAC on remux — confirmed safe.** `mux_cmd` emits `-c:a aac -b:a 192k`. Verified compatible with all supported source extensions (`.mp4`, `.mov`, `.mkv`, `.webm`). If a future source codec rejects AAC the codec choice can become container-conditional, but no current codec does.

---

## 10. Success criteria

The spec is implemented when, on a fresh episode dropped into `inbox/`:

- Phase 2 runs after pickup, calls Audio Isolation once, writes `audio/raw.cleaned.wav`, and stamps `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1` in `raw.<ext>`'s container/format metadata.
- Phase 3 (video-use sub-agent) sees the cleaned `raw.<ext>` as input, transcribes via Scribe once (no extra spend), and produces a `final.mp4` audibly cleaner than the pilot run on the same material.
- Re-running `/edit-episode <slug>` does not call the Audio Isolation API a second time (tag short-circuit).
- Re-running with `audio/raw.cleaned.wav` deleted but the tag still present: Phase 2 still no-ops on the tag (correct — the tag is the authoritative idempotency signal; the WAV cache is for explicit re-mux scenarios).
- Re-running with the tag removed but `audio/raw.cleaned.wav` present: Phase 2 skips the API call, re-muxes from cache, restamps the tag.
- Failure of the API stops the pipeline with a specific stderr message and a non-zero exit; no partial state is written (atomic rename guarantees this).
- Spec A's success criteria continue to hold unchanged.
