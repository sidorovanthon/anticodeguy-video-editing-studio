# Edit-Episode Pipeline Design

**Date:** 2026-04-30
**Status:** Approved for planning

## Goal

Single-command, in-session orchestration of the existing `video-use` and `hyperframes` skills, so a raw vertical video dropped into `inbox/` is processed end-to-end and the Hyperframes preview studio is launched — without the user switching between two separate agent sessions.

## Background

Two prior sessions established the manual workflow:

1. **Video Use session** — raw `.mp4` → transcribe (ElevenLabs Scribe) → strategy/EDL → grade → render → `edit/final.mp4` + `edit/transcripts/raw.json`. Fully autonomous given the prompt "edit this video"; cutting standards live inside the skill.
2. **Hyperframes session** — `final.mp4` + transcript → composition with frosted-glass overlays, word-synced captions, and contextual illustrative animations → `hyperframes preview` studio in browser.

Both skills are already installed globally. This project is the orchestrator that chains them.

## Non-goals

- No new processing logic. All editing/composition decisions live inside `video-use` and `hyperframes`.
- No watcher/daemon. The user explicitly triggers a slash command.
- No per-episode style overrides. Default style is hardcoded; override mechanism deferred until needed.
- No batch mode. One episode per command invocation.

## Architecture

The orchestrator is a single slash-command file: `.claude/commands/edit-episode.md`. Its body is a deterministic recipe the in-session agent follows, invoking the `video-use` and `hyperframes` skills with absolute paths derived from the project layout.

No code. No scripts. No config files. Just a prompt-encoded protocol plus a layout convention documented in `CLAUDE.md`.

### Directory layout

```
<project>/
  .claude/commands/edit-episode.md
  CLAUDE.md                       # layout + invocation conventions
  .gitignore                      # inbox/, episodes/
  docs/superpowers/specs/         # this doc and future specs
  inbox/                          # drop zone, ignored
    <slug>.mp4                    # user places raw video here
  episodes/                       # processed archive, ignored
    <slug>/
      raw.mp4                     # moved from inbox
      edit/                       # produced by video-use
        final.mp4
        transcripts/raw.json
      hyperframes/                # produced by hyperframes
        index.html
        package.json
        ...
```

**Slug derivation:** filename stem of the raw video. `inbox/launch-promo.mp4` → `episodes/launch-promo/raw.mp4`.

## Command surface

### `/edit-episode` (no argument)

1. List video files in `inbox/` matching extensions `.mp4`, `.mov`, `.mkv`, `.webm`.
2. Pick the file with the oldest mtime.
3. Derive slug from filename stem; proceed with that slug.
4. If `inbox/` has no matching files, list episodes that have `hyperframes/index.html` and offer to relaunch the most recent one's studio. Otherwise, report nothing to do.

### `/edit-episode <slug>`

1. If `inbox/<slug>.<ext>` exists, use that.
2. Else if `episodes/<slug>/raw.<ext>` exists, resume from current state (idempotency rules below).
3. Else, error: "no episode named `<slug>`".

## Execution phases

### Phase 0 — Pickup

If the raw is in `inbox/`:
- Create `episodes/<slug>/` if absent.
- **Move** (not copy) `inbox/<slug>.<ext>` to `episodes/<slug>/raw.<ext>`.

This empties the inbox slot before processing begins, so a re-run of `/edit-episode <slug>` resumes from `episodes/<slug>/` even if Phase 1 fails.

### Phase 1 — Video Use

**Skip condition:** `episodes/<slug>/edit/final.mp4` already exists.

Invoke the `video-use` skill with a prompt that supplies the absolute paths:
- input: `<abs>/episodes/<slug>/raw.<ext>`
- output directory: `<abs>/episodes/<slug>/edit/`

The skill's internal standards (cut padding, grade preset, transcription model, etc.) apply unchanged. The orchestrator does not pass creative direction.

On success, expects `edit/final.mp4` and `edit/transcripts/raw.json` to exist.

### Phase 2 — Hyperframes (with studio launch)

**Skip-build condition:** `episodes/<slug>/hyperframes/index.html` already exists. In that case, only launch the studio.

Invoke the `hyperframes` skill with a prompt that supplies:
- video: `<abs>/episodes/<slug>/edit/final.mp4`
- transcript: `<abs>/episodes/<slug>/edit/transcripts/raw.json`
- output directory: `<abs>/episodes/<slug>/hyperframes/`
- style instruction: "frosted-glass overlays, word-synced captions, contextual illustrative animations driven by transcript content"
- terminal action: launch `hyperframes preview` and report the local URL

Studio launch is part of this phase, not a separate step. The slash command completes when the URL is visible to the user.

## Idempotency rules

- Raw already in `episodes/<slug>/`, inbox slot empty → skip Phase 0.
- `edit/final.mp4` present → skip Phase 1 (avoids re-spending Scribe credits and re-rendering).
- `hyperframes/index.html` present → skip composition build, still launch studio.

Re-running `/edit-episode <slug>` is always safe and resumes from the first incomplete artifact. A future `--force` flag can override; not in scope now.

## Error handling

Each phase is fail-fast. If `video-use` or `hyperframes` fails, the orchestrator stops, surfaces the failure to the user, and leaves the episode directory in whatever partial state it reached. The user fixes the cause and re-runs `/edit-episode <slug>`; idempotency rules ensure no work is duplicated.

No automatic retries. No rollback of partial outputs (the user may want to inspect them).

## Affected/created files

- `.claude/commands/edit-episode.md` — new; the orchestrator command body.
- `CLAUDE.md` — new; documents the `inbox/` → `episodes/<slug>/` convention and points the agent at the slash command.
- `.gitignore` — new; ignores `inbox/`, `episodes/`.
- `docs/superpowers/specs/2026-04-30-edit-episode-pipeline-design.md` — this document.

## Open questions / deferred

- Per-episode style override via `episodes/<slug>/STYLE.md` — deferred until a real need arises.
- `--force` flag to bypass idempotency — deferred.
- Multi-file batch mode — deferred; current scope is one episode per invocation.
- Non-mp4 raw extensions (`.mov`, `.mkv`) — supported by file-extension preservation in the move step; no special handling.
