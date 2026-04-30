# Edit-Episode Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/edit-episode` slash command that orchestrates the existing `video-use` and `hyperframes` skills end-to-end, picking raw video from `inbox/` and producing a Hyperframes preview studio for the result.

**Architecture:** Pure prompt-encoded orchestration. No code, no scripts, no config files. Three artifacts: `.claude/commands/edit-episode.md` (the recipe), `CLAUDE.md` (layout convention so any session — including ones the user opens without typing the command — knows the rules), and `.gitignore` (keep `inbox/` and `episodes/` out of git). The in-session agent reads the command body and follows it deterministically, invoking the two skills with absolute paths.

**Tech Stack:** Markdown (slash command + CLAUDE.md), git. Skills `video-use` and `hyperframes` are already installed globally and not modified.

**Spec reference:** `docs/superpowers/specs/2026-04-30-edit-episode-pipeline-design.md`

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `.gitignore` | create | Exclude `inbox/`, `episodes/`, and OS noise from git |
| `CLAUDE.md` | create | Project-level convention: layout, slug rule, point at `/edit-episode` |
| `.claude/commands/edit-episode.md` | create | The orchestrator command body — full deterministic recipe |
| `docs/superpowers/plans/2026-04-30-edit-episode-pipeline.md` | this plan | — |

No tests in the unit-test sense — this is prompt content for an LLM agent. Verification is end-to-end against a real raw video (Task 5), which is the only meaningful test.

---

## Task 1: .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Write `.gitignore`**

```
# Video pipeline working directories
inbox/
episodes/

# OS / editor noise
.DS_Store
Thumbs.db
*.swp
.vscode/
.idea/
```

- [ ] **Step 2: Verify**

Run: `git status --short`
Expected: clean tree (no new untracked files surfacing). The file `.gitignore` itself shows as untracked.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore inbox/, episodes/, and editor noise"
```

---

## Task 2: CLAUDE.md (project convention)

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`**

````markdown
# anticodeguy-video-editing-studio

This project is an orchestrator for a two-stage video editing pipeline that chains the
globally-installed `video-use` and `hyperframes` skills into a single command.

## Layout convention

```
inbox/                  # drop zone (gitignored). User places raw video here as <slug>.<ext>.
episodes/               # processed archive (gitignored). One folder per episode.
  <slug>/
    raw.<ext>           # moved here from inbox/ by the orchestrator
    edit/               # produced by video-use: final.mp4, transcripts/raw.json
    hyperframes/        # produced by hyperframes: index.html, package.json, ...
```

**Slug:** filename stem of the raw video. `inbox/launch-promo.mp4` → `episodes/launch-promo/raw.mp4`.

**Supported raw extensions:** `.mp4`, `.mov`, `.mkv`, `.webm`.

## Entry point

The pipeline is invoked exclusively via the slash command `/edit-episode` (defined in
`.claude/commands/edit-episode.md`). Do not invoke `video-use` or `hyperframes` skills
directly from the user's prompt — go through the command so layout and idempotency rules
are honored.

If the user says "edit this video", "process the inbox", "обработай видео", or anything
semantically equivalent, invoke `/edit-episode` (with a slug argument if they named one).

## Idempotency

The command is safe to re-run on the same slug. It resumes from the first missing
artifact: `episodes/<slug>/edit/final.mp4`, then `episodes/<slug>/hyperframes/index.html`,
then studio launch. Skipping Phase 1 when `final.mp4` exists is important — it avoids
re-spending ElevenLabs Scribe credits.
````

- [ ] **Step 2: Verify**

Run: `cat CLAUDE.md | head -5`
Expected: shows the title and first lines.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: project CLAUDE.md with pipeline layout convention"
```

---

## Task 3: `/edit-episode` slash command

**Files:**
- Create: `.claude/commands/edit-episode.md`

- [ ] **Step 1: Create the command directory**

```bash
mkdir -p .claude/commands
```

- [ ] **Step 2: Write the command body**

````markdown
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
````

- [ ] **Step 3: Verify shape**

Run: `head -3 .claude/commands/edit-episode.md`
Expected: starts with frontmatter `---` and a `description:` line.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/edit-episode.md
git commit -m "feat: /edit-episode slash command orchestrating video-use + hyperframes"
```

---

## Task 4: Smoke-test the command surface (no skill invocation)

This task validates the slash command is discoverable and its no-input branch works without burning Scribe credits or rendering anything.

**Files:**
- None modified.

- [ ] **Step 1: Confirm directories exist after first run**

In a fresh Claude Code session (or `/clear` the current one), run `/edit-episode`.
Expected: agent runs `mkdir -p inbox/ episodes/`, then reports `nothing to do — drop a video in inbox/`. No skill is invoked.

Verify directories now exist:
```bash
ls -la inbox episodes
```
Expected: both directories present (empty).

- [ ] **Step 2: Confirm error path for unknown slug**

Run: `/edit-episode nonexistent-slug`
Expected: agent reports `no episode named "nonexistent-slug" — no file in inbox/ and no episodes/nonexistent-slug/raw.* found`. No skill invoked.

- [ ] **Step 3: No commit**

These are runtime checks; the only filesystem effect is empty `inbox/` and `episodes/` directories, which are gitignored. Nothing to commit.

---

## Task 5: End-to-end verification with a real raw video

This is the only meaningful integration test. It costs ElevenLabs Scribe credits and several minutes of ffmpeg time. Run it once per major change to the command body.

**Files:**
- None modified. Working data lives in gitignored `episodes/`.

- [ ] **Step 1: Drop a short raw vertical clip in `inbox/`**

Use a 30–90s vertical talking-head clip. Name it descriptively, e.g. `inbox/smoke-test.mp4`.

- [ ] **Step 2: Run the command**

```
/edit-episode
```

Expected sequence (agent narrates each):
1. Phase 0: announces slug `smoke-test`, moves the file to `episodes/smoke-test/raw.mp4`.
2. Phase 1: invokes `video-use` skill; eventually reports `final.mp4` and transcript exist.
3. Phase 2: invokes `hyperframes` skill; eventually launches `hyperframes preview` and prints a URL.

- [ ] **Step 3: Verify artifacts on disk**

```bash
ls episodes/smoke-test/edit/final.mp4
ls episodes/smoke-test/edit/transcripts/
ls episodes/smoke-test/hyperframes/index.html
```
Expected: all three exist.

- [ ] **Step 4: Open the studio URL**

Open the URL in a browser. Expected: composition renders with frosted-glass overlays, synced captions, and at least one contextual illustrative animation.

- [ ] **Step 5: Re-run to verify idempotency**

```
/edit-episode smoke-test
```
Expected: agent skips Phase 1 (`Phase 1 already complete — skipping video-use.`) and Phase 2 build, just relaunches the studio. Total runtime: seconds, not minutes. No new Scribe charge.

- [ ] **Step 6: Cleanup (optional)**

Delete `episodes/smoke-test/` if you don't want it in the archive.

```bash
rm -rf episodes/smoke-test
```

---

## Self-review notes

- Spec coverage: layout (Task 1+2), slug derivation (Task 3 Phase 0), no-arg pickup (Task 3 Phase 0 + Task 4), known-slug resume (Task 3 Phase 0 + Task 5 Step 5), Phase 1 (Task 3), Phase 2 + studio (Task 3), idempotency rules (Task 3 + Task 5 Step 5), error fail-fast (Task 3 final section), all `.gitignore` entries (Task 1).
- The "supported extensions" list (`mp4 mov mkv webm`) is consistent across CLAUDE.md and the command body.
- Phase numbers and skip-conditions in Task 3 match the spec verbatim.
- No TBDs, no "similar to above", no placeholder code.
