---
description: Run the video editing pipeline (video-use → hyperframes → studio) on an episode from inbox/ or by slug.
argument-hint: "[slug]"
---

You are orchestrating a two-stage video editing pipeline. Follow this recipe exactly. Do not improvise creative decisions — the `video-use` and `hyperframes` skills own those.

## Inputs

- `$1` (optional): episode slug. If omitted, pick from `inbox/`.

## Project layout (must hold)

```
inbox/<slug>.<ext>            -> drop zone (extensions: mp4, mov, mkv, webm)
episodes/<slug>/raw.<ext>     -> moved here at Phase 0
episodes/<slug>/edit/         -> produced by video-use (final.mp4 + transcripts/raw.json)
episodes/<slug>/hyperframes/  -> produced by hyperframes (index.html + package.json + ...)
```

All paths passed to skills MUST be absolute — derive them from the project root via `pwd` once at the start.

## Phase 0 — Resolve slug and pickup

1. Capture `PROJECT_ROOT` = `pwd`.
2. Ensure `inbox/` and `episodes/` exist (`mkdir -p`).
3. Resolve slug:
   - **If `$1` given:**
     - If `inbox/$1.<ext>` exists for some supported ext → SLUG=$1, RAW_SRC=`inbox/$1.<ext>`.
     - Else if `episodes/$1/raw.<ext>` exists → SLUG=$1, RAW_SRC already in place (skip move).
     - Else stop with: `no episode named "$1" — no file in inbox/ and no episodes/$1/raw.* found`.
   - **If `$1` omitted:**
     - List files in `inbox/` matching `*.mp4 *.mov *.mkv *.webm`.
     - If empty: list `episodes/*/hyperframes/index.html`. If any exist, ask the user whether to relaunch the studio for the most recently modified one. Otherwise report "nothing to do — drop a video in inbox/".
     - Otherwise pick the file with the oldest mtime → SLUG = filename stem, RAW_SRC = that path.
4. If RAW_SRC is in `inbox/`:
   - `mkdir -p episodes/<SLUG>`
   - `mv <RAW_SRC> episodes/<SLUG>/raw.<ext>` (preserve original extension)
5. Set `EPISODE_DIR = <PROJECT_ROOT>/episodes/<SLUG>` (absolute).
6. Announce to the user: `Episode: <SLUG>. Raw at <EPISODE_DIR>/raw.<ext>.`

## Phase 1 — Video Use

**Skip if** `<EPISODE_DIR>/edit/final.mp4` exists. In that case announce `Phase 1 already complete — skipping video-use.` and proceed to Phase 2.

Otherwise invoke the `video-use` skill (via the Skill tool) with this verbatim instruction, substituting absolute paths:

> Edit the video at `<EPISODE_DIR>/raw.<ext>`. Write all outputs to `<EPISODE_DIR>/edit/`. Use your standard cutting/grading defaults — no creative direction from me. Produce `final.mp4` and the transcript JSON in the conventional location (`<EPISODE_DIR>/edit/transcripts/raw.json`).

After the skill returns:
- Verify `<EPISODE_DIR>/edit/final.mp4` exists. If not, stop and surface the failure.
- Verify a transcript JSON exists under `<EPISODE_DIR>/edit/transcripts/`. If not, stop.

## Phase 2 — Hyperframes (with studio launch)

**Skip-build if** `<EPISODE_DIR>/hyperframes/index.html` exists. In that case skip composition build and only launch the studio (see "Studio launch" below).

Otherwise invoke the `hyperframes` skill (via the Skill tool) with this verbatim instruction, substituting absolute paths:

> Build a HyperFrames composition from the video at `<EPISODE_DIR>/edit/final.mp4` and the transcript at `<EPISODE_DIR>/edit/transcripts/raw.json`. Write the project to `<EPISODE_DIR>/hyperframes/`.
>
> Style is fixed:
> - frosted-glass overlays (last-iOS aesthetic)
> - synchronized word-level captions
> - contextual illustrative animations driven by the transcript content (one per beat / key idea)
>
> When the composition is ready, launch the preview studio (`hyperframes preview`) and report the local URL.

If the skill does not launch the studio itself, do it manually after verifying `index.html` exists:

```bash
cd <EPISODE_DIR>/hyperframes && hyperframes preview
```

Run that in the **background** so the studio keeps serving while the command returns. Capture the printed URL and show it to the user.

### Studio launch (skip-build path)

If you skipped the build because `index.html` already existed, just run the preview command above and report the URL.

## Completion

Announce to the user: `Done. Studio: <URL>. Episode: <EPISODE_DIR>.`

## Error handling

Each phase is fail-fast. If `video-use` or `hyperframes` returns an error, stop immediately, show what failed, and tell the user to fix and re-run `/edit-episode <SLUG>`. Do NOT retry, do NOT roll back partial outputs. Idempotency rules ensure re-running picks up where it failed.
