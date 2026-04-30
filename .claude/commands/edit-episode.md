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

All paths passed to skills MUST be absolute — derive them from the project root at the start of execution. Throughout this recipe, use whichever shell/tool fits your environment (Bash, PowerShell, Read, Glob, etc.); the steps describe outcomes, not literal commands. Match the syntax to the shell you actually invoke.

## Phase 0 — Resolve slug and pickup

1. Determine `PROJECT_ROOT` (the absolute path of the working directory).
2. Ensure directories `inbox/` and `episodes/` exist; create them if not.
3. Define `SUPPORTED_EXTS = [mp4, mov, mkv, webm]` (lowercase; check case-insensitively).
4. Resolve slug:
   - **If `$1` given:**
     - Search `inbox/` for files named `$1.<ext>` where `<ext>` is in `SUPPORTED_EXTS`. Try extensions in the order listed (`mp4` first, then `mov`, `mkv`, `webm`); use the first match. If you find a match → SLUG=$1, RAW_SRC=that file.
     - Else if `episodes/$1/raw.<ext>` exists for some `<ext>` in `SUPPORTED_EXTS` → SLUG=$1, RAW_SRC already in place (skip move). If multiple `raw.*` files exist in `episodes/$1/`, stop with: `ambiguous: multiple raw.* in episodes/$1/`.
     - Else stop with: `no episode named "$1" — no file in inbox/ and no episodes/$1/raw.* found`.
   - **If `$1` omitted:**
     - List files in `inbox/` whose extension is in `SUPPORTED_EXTS`.
     - If empty: list `episodes/*/hyperframes/index.html`. If any exist, ask the user whether to relaunch the studio for the most recently modified one. Otherwise report `nothing to do — drop a video in inbox/`.
     - Otherwise pick the file with the **oldest mtime** (FIFO queue — first dropped, first processed). SLUG = filename without its final extension (everything before the last `.`; e.g. `foo.bar.mp4` → `foo.bar`). RAW_SRC = that path.
5. If RAW_SRC is in `inbox/` (i.e. we are picking up, not resuming):
   - **Collision guard:** if `episodes/<SLUG>/` already contains a `raw.*` file, stop with: `collision: episodes/<SLUG>/raw.* already exists — rename the inbox file or delete the stale episode dir`. Do NOT overwrite.
   - Create `episodes/<SLUG>/` if missing.
   - Move `RAW_SRC` to `episodes/<SLUG>/raw.<ext>` (preserve original extension; this is a move, not a copy — `inbox/` should be empty for this slug afterwards).
6. Set `EPISODE_DIR = <PROJECT_ROOT>/episodes/<SLUG>` (absolute path).
7. Announce to the user: `Episode: <SLUG>. Raw at <EPISODE_DIR>/raw.<ext>.`

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
> - frosted-glass overlays (latest iOS / "Liquid Glass" aesthetic)
> - synchronized word-level captions
> - contextual illustrative animations driven by the transcript content (one per beat / key idea)
>
> When the composition is ready, launch the preview studio (`hyperframes preview`) and report the local URL.

If the skill does not launch the studio itself, do it manually after verifying `index.html` exists: from the directory `<EPISODE_DIR>/hyperframes/`, run `hyperframes preview` **in the background** (so the studio keeps serving while the command returns). Use the appropriate background-execution mechanism for the shell you invoke. Capture the printed URL and show it to the user.

### Studio launch (skip-build path)

If you skipped the build because `index.html` already existed, just run the preview command above and report the URL.

## Completion

Announce to the user: `Done. Studio: <URL>. Episode: <EPISODE_DIR>.`

## Error handling

Each phase is fail-fast. If `video-use` or `hyperframes` returns an error, stop immediately, show what failed, and tell the user to fix and re-run `/edit-episode <SLUG>`. Do NOT retry, do NOT roll back partial outputs. Idempotency rules ensure re-running picks up where it failed.
