# Spec A — Pipeline & Enforcement

**Date:** 2026-04-30
**Source:** `retro.md` (pilot run of `/edit-episode` on `desktop-licensing-story`, 2026-04-30)
**Scope:** First of two specs derived from the retro. This spec covers pipeline contract, skill-canon enforcement, manual hyperframes scaffold, output-timeline transcript, and the new episode pickup/naming convention. **Audio Isolation is deferred to Spec B.**

---

## 1. Context and motivation

The pilot run of `/edit-episode` produced a usable video, but the retro surfaced ~15 distinct issues across three layers: (i) skills' internal canons were silently skipped because the orchestrator's verbatim brief did not enforce them, (ii) the Phase 1↔Phase 2 contract leaked source-timeline timestamps into output-timeline consumers, and (iii) `npx hyperframes init` is incompatible with our use case — it forces a Whisper run, hardcodes 1920×1080, and duplicates ~33 MB of media.

Root architectural cause: `video-use` and `hyperframes` are skill files (markdown injected into the executor's context), not agents with their own runtime. There is no enforcer that watches the executor uphold a skill's internal rules. So enforcement = the orchestrator either (a) writes the rules verbatim into the brief, or (b) isolates the phase into a sub-agent with fresh context and budget.

We chose **C — hybrid**: Phase 2 (video-use) runs as an isolated sub-agent because cuts are discipline-heavy and re-running them costs ElevenLabs Scribe credits; Phase 3 (hyperframes) stays as a `Skill` invocation in the main session because design iteration benefits from live conversation. Both phases get explicit verbatim checklists as backup.

This is a pre-condition for shipping more episodes through the pipeline reliably; without it, every run depends on the executor's mood.

---

## 2. Phase numbering

Phases are renumbered to natural integers (no `0`, no `0.5`):

| # | Name | Owner | Tool |
|---|---|---|---|
| 1 | Pickup | orchestrator | inline (Bash/PowerShell + scripts) |
| 2 | Video edit | `video-use` | `Agent` (sub-agent) |
| 3 | Composition + studio | `hyperframes` | `Skill` (main session) |

Spec B will insert "Audio isolation" between 1 and 2, renumbering 2→3, 3→4.

---

## 3. Episode pickup & naming convention

### 3.1 Inbox layout

User drops **two files with the same stem** into `inbox/`:

```
inbox/<stem>.<video-ext>   # mp4|mov|mkv|webm
inbox/<stem>.txt           # author script (md also accepted; .txt preferred)
```

`<stem>` is arbitrary (`raw`, `take1`, `2026-04-launch`, …) — the orchestrator does not parse it. It only uses the stem to pair the two files.

If the script file is missing, pickup falls back to legacy behavior (slug = video stem) with a warning. Pipeline still runs; Phase 2/3 briefs simply omit the "ground truth script" line.

### 3.2 Slug derivation

When a script file is paired with the video, slug is derived deterministically:

1. **Date prefix:** today's date in `YYYY-MM-DD` (PowerShell `Get-Date -Format 'yyyy-MM-dd'`).
2. **Title source:** first sentence of the script — text up to the first `.`, `!`, or `?`. If none exist within the first paragraph, take the entire first non-empty line.
3. **Slugify:** lowercase; transliterate non-ASCII (cyrillic, accents) to ASCII; replace runs of non-`[a-z0-9]` with `-`; trim leading/trailing `-`.
4. **Cap:** truncate to 60 characters total *after* the date prefix and the joining `-`. If truncation falls inside a word, back up to the previous `-`.
5. **Collision:** if `episodes/<slug>/` already exists, append `-2`, `-3`, ... and retry. Increment until free.

Example: script starts with `"Desktop software licensing, it turns out, is also a whole story."` on 2026-04-30 → slug `2026-04-30-desktop-software-licensing-it-turns-out-is`.

### 3.3 Slug validation (legacy stem fallback path only)

When fallback is used (no script file), the video stem must match `^[a-z0-9._-]+$`. On mismatch the pipeline stops with a clear message asking the user to rename the inbox file (with a kebab-case suggestion). This catches the retro 3.1 risk for auto-mode (`/loop`, cron) where the user is not present to catch ambiguous filenames.

### 3.4 Pickup steps

1. Resolve `PROJECT_ROOT` (absolute).
2. Ensure `inbox/` and `episodes/` exist.
3. If `$1` (slug arg) given: try to resume from `episodes/$1/raw.*`. Same as today's logic.
4. Otherwise scan `inbox/` for video files (`mp4|mov|mkv|webm`, case-insensitive). Pick the **oldest by mtime** (FIFO). If none, offer studio re-launch on the latest `episodes/*/hyperframes/index.html` and exit.
5. Look for a script file with the **same stem**: `inbox/<stem>.txt`, then `.md`. If found → derive slug per §3.2. If not → use `<stem>` as slug, run §3.3 validation.
6. **Collision guard:** if `episodes/<slug>/raw.*` already exists, apply numeric suffix (`-2`, `-3`, ...).
7. Create `episodes/<slug>/`. Move video to `episodes/<slug>/raw.<ext>` (preserving original extension). Move script to `episodes/<slug>/script.txt` (always renamed to `script.txt`, regardless of source extension; `.md` content is fine in a `.txt`).
8. `inbox/` is empty for this episode after move.

### 3.5 FIFO clarification

When multiple inbox videos exist, FIFO by mtime stands (retro 3.5 risk of "year-old archive file beats fresh drop" is real but rare; documenting it is enough — explicit `$1` arg is always available).

---

## 4. Glue scripts (this repo, not upstream)

All scripts live in `scripts/` at repo root. They are owned by the orchestrator and have **no dependency on internal video-use or hyperframes APIs** beyond their documented file outputs. `video-use` and `hyperframes` remain read-only external products updated daily by the user's Task Scheduler.

### 4.1 `scripts/pickup.py`

Implements §3 above. Single entry point invoked from `edit-episode.md` Phase 1. Outputs the resolved `EPISODE_DIR` and `SLUG` to stdout (machine-parseable, e.g. JSON).

Reasoning for Python over PowerShell: slug derivation needs Unicode transliteration and regex on file content; cross-shell consistency matters because the user runs Bash and PowerShell interchangeably (per project conventions).

### 4.2 `scripts/scaffold_hyperframes.py`

**Approach: canonical `init` + targeted post-init patches.** Verified empirically (2026-04-30) that `npx hyperframes init <name> --yes` **without** `--video`:
- Does not invoke whisper (fixes retro 1.2).
- Does not copy any media (fixes retro 3.2).
- Produces 5 canonical files in <2s: `index.html`, `meta.json`, `hyperframes.json`, `AGENTS.md`, `CLAUDE.md`.

This keeps the scaffold canonical — future hyperframes versions that add new fields to `meta.json`/`hyperframes.json` will be picked up automatically when our daily `npm` cache pulls the latest package. We only patch what we know is wrong for our use case.

**Steps:**

1. `cd episodes/<slug>` and run `npx hyperframes init hyperframes --yes`. Produces `episodes/<slug>/hyperframes/{index.html, meta.json, hyperframes.json, AGENTS.md, CLAUDE.md}`.
2. Read `episodes/<slug>/edit/final.mp4` via `ffprobe` to get `width × height × duration`.
3. **Patch `index.html`** — exactly 4 known-wrong locations (init defaults to 1920×1080×10s):
   - `<meta name="viewport" content="width=W, height=H" />`
   - `body { width: Wpx; height: Hpx }` in the inline `<style>` block.
   - Root div `data-width="W" data-height="H" data-duration="D"`.
   - Inject `<video id="el-video" class="clip" data-start="0" data-track-index="0" data-has-audio="true" src="../edit/final.mp4" muted playsinline></video>` inside the root div (replaces the example-clip comment).
4. **Patch `meta.json`** — overwrite `id` and `name` from the literal `"hyperframes"` (init's default from the dir argument) to the episode slug.
5. **Add `hyperframes/package.json`** — init does not generate one. We add it ourselves with `hyperframes` pinned as devDependency. `npm install` runs once at scaffold; subsequent `npx hyperframes` calls hit the local cache (fixes retro 3.6).
6. **Add `hyperframes/DESIGN.md`** — init does not generate one (cheatsheet §19 marks it "optional"), but Hard Rule 14 requires it before any HTML authoring. The stub points the executor to `~/.agents/skills/hyperframes/visual-styles.md` for the "Liquid Glass / iOS frosted glass" identity if a matching named identity exists, otherwise leaves the standard 3-question prompt.
7. **Copy transcript** — copy `episodes/<slug>/edit/transcripts/final.json` (output-timeline word-level, see §4.3) to `hyperframes/transcript.json`. A copy, not a reference, because hyperframes treats it as a project-local asset.

**Video reference rationale:** `<video src="../edit/final.mp4">` is used instead of copying or symlinking the file. Chrome resolves the relative path from the HTML location; verified to work in studio preview. If hyperframes' renderer turns out to copy assets into a sandboxed temp dir during `render`, the relative path will break — see §9 open question. Symlink + UAC elevation prompt remains the fallback.

Replaces retro fixes 1.2, 1.3, 2.4, 3.2, 3.3, 3.6 in one script.

### 4.3 `scripts/remap_transcript.py`

Reads `episodes/<slug>/edit/transcripts/raw.json` (Scribe word-level, source-timeline) and `episodes/<slug>/edit/edl.json` (cut decisions emitted by video-use). Produces `episodes/<slug>/edit/transcripts/final.json`: same Scribe schema, but timestamps remapped to output-timeline using EDL ranges.

Algorithm: for each word in `raw.json`, find the EDL range containing its source-timeline `start`. Words in cut-out regions are dropped. Words inside a kept range get `output_start = word.start - range.start + cumulative_output_offset`, same shift for `end`. `cumulative_output_offset` accumulates across kept ranges in EDL order.

Mirrors the math `helpers/render.py` already does internally for `master.srt` (cheatsheet §11, Hard Rule 5), but emits word-level JSON instead of phrase-level SRT — that is the artifact hyperframes captions code wants.

Invoked by `edit-episode.md` after Phase 2 sub-agent returns and before Phase 3 starts.

### 4.4 Glue execution order in `edit-episode.md`

```
Phase 1 — pickup
  scripts/pickup.py → SLUG, EPISODE_DIR

Phase 2 — video-use (sub-agent via Agent tool)
  Returns: edit/final.mp4, edit/transcripts/raw.json, edit/edl.json, edit/project.md (appended)

Post-Phase-2 glue (orchestrator inline)
  scripts/remap_transcript.py → edit/transcripts/final.json
  scripts/scaffold_hyperframes.py → hyperframes/{index.html,package.json,...}

Phase 3 — hyperframes (Skill in main session)
  Reads: hyperframes/index.html (scaffolded), hyperframes/transcript.json (final.json copy)
  Runs full quality-gate checklist
  Appends to <edit>/project.md
  Launches studio
```

---

## 5. Verbatim briefs (the enforcement layer)

The following are the canonical instructions written into `edit-episode.md`. They are deliberately explicit because skills are advisory — the orchestrator is the only place that can require behavior.

### 5.1 Phase 2 brief (video-use sub-agent)

Substitute absolute paths at runtime.

> You are the video-use sub-agent. Edit `<EPISODE_DIR>/raw.<ext>` and write all outputs under `<EPISODE_DIR>/edit/`. The author's script is at `<EPISODE_DIR>/script.txt` — read it as ground truth for take selection and to verify ASR accuracy (flag any divergence in your reasoning log).
>
> **Pacing:** apply your skill's standard cut-target rules from §6 of your canon — silences ≥400ms are clean targets, 150–400ms usable with visual check, padding 30–200ms per Hard Rule 7. Aim aggressively: trim every inter-phrase silence to ~120ms, eliminate retakes/false starts, target ~25–35% runtime reduction unless material is too sparse.
>
> **Required outputs (all under `<EPISODE_DIR>/edit/`):**
> - `final.mp4` — rendered video.
> - `transcripts/raw.json` — Scribe word-level on source timeline (cached if exists; do not re-run Scribe).
> - `edl.json` — your final EDL with `ranges`, `sources`, `total_duration_s`.
> - `project.md` — append a session block per your skill's §15 convention (Strategy / Decisions / Reasoning log / Outstanding).
>
> **Self-eval (rigid, do all):**
> - Run `helpers/timeline_view.py` on the first 2s, last 2s, and at minimum 2 mid-points of `final.mp4`. Verify cut boundaries.
> - Run `ffprobe` on `final.mp4`; compare actual duration to `total_duration_s` in your EDL — they must match within 100ms.
> - Confirm Hard Rule 11 (strategy confirmation) and Hard Rule 12 (outputs in `<edit>/`).
>
> **Environment:** `PYTHONUTF8=1` is set globally; do not override. If a helper script crashes on encoding, that is a genuine bug — surface it.
>
> Report what you did, what you skipped and why, and any divergence you spotted between `script.txt` and ASR.

### 5.2 Phase 3 brief (hyperframes Skill in main session)

> Build a HyperFrames composition for `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json`, `DESIGN.md` are in place; the video reference is `<video src="../edit/final.mp4">` and the word-level transcript is at `hyperframes/transcript.json` (output-timeline, ready to use directly with `final.mp4`).
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
>
> **Style:** "Liquid Glass / iOS frosted glass" — first check `~/.agents/skills/hyperframes/visual-styles.md` for a matching named identity and follow it. If not present, follow Hard Rule 14: generate a minimal `DESIGN.md` (3-question pattern) before writing any HTML. Do not hardcode `#333` / `#3b82f6` / `Roboto` etc.
>
> **Quality gates (rigid, run all in order, fix all errors and contrast warnings):**
> 1. `npx hyperframes lint`
> 2. `npx hyperframes validate`
> 3. `npx hyperframes inspect`
> 4. `node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir>` — review output for degenerate/offscreen/collision flags.
> 5. `node ~/.agents/skills/hyperframes/scripts/contrast-report.mjs <hyperframes-dir>` — open `contrast-overlay.png`, fix any magenta (fail AA) regions; ideally clear yellow too. **This is critical for our content** (white captions on light backgrounds).
> 6. `npx hyperframes snapshot --at 0,2,5,10,...` at one snapshot per ~5s of `final.mp4`.
>
> **Project memory:** append a session block to `<EPISODE_DIR>/edit/project.md` (the same file video-use writes to — extend the existing log) with Strategy / Decisions / Outstanding for this composition.
>
> **Studio launch:** after gates pass, run `npx hyperframes preview` in the background; capture and report the URL.

---

## 6. Idempotency and re-runs

Existing checkpoints in `edit-episode.md`:

1. `episodes/<slug>/edit/final.mp4` exists → skip Phase 2.
2. `episodes/<slug>/hyperframes/index.html` exists → skip scaffold + Phase 3 build, only relaunch studio.

New checkpoint added:

3. `episodes/<slug>/edit/transcripts/final.json` exists → skip `remap_transcript.py`.

Rebuild guidance (documented in `edit-episode.md`):

- **Re-cut (apply §5.1 pacing changes):** delete `episodes/<slug>/edit/final.mp4` AND `episodes/<slug>/hyperframes/`. `transcripts/raw.json` stays — **no re-spend on Scribe**.
- **Re-compose only (apply §4.2 scaffold changes):** delete `episodes/<slug>/hyperframes/`. Phase 2 skipped, `final.mp4` and transcripts preserved.

What is always reused: `raw.<ext>`, `script.txt`, `transcripts/raw.json`, `takes_packed.md`.
What runs again on re-cut: ffmpeg extract+concat+loudnorm (~30s CPU, no API cost).

---

## 7. Repository hygiene

### 7.1 `init/` directory

Currently untracked. Contains the cheatsheets used as ground truth for this design (`hyperframes-cheatsheet.md`, `video-use-cheatsheet.md`) and `.jsonl` session logs.

Action:
- Commit `init/hyperframes-cheatsheet.md` and `init/video-use-cheatsheet.md` as `docs/cheatsheets/hyperframes.md` and `docs/cheatsheets/video-use.md`. The orchestrator `edit-episode.md` references them by path for verbatim-brief construction (e.g., the §6 cut-targets in §5.1 above).
- Add `*.jsonl` to `.gitignore`. Existing logs can stay locally or be deleted; not committed.
- Empty `init/` is removed.

### 7.2 `.gitignore` additions

- `inbox/` — already ignored per CLAUDE.md.
- `episodes/` — already ignored.
- `*.jsonl` — new.
- `scripts/__pycache__/` — new (Python compile artifacts).

### 7.3 UTF-8 on Windows

No upstream patch to `video-use`. Instead, the orchestrator sets `PYTHONUTF8=1` in the environment when invoking the Phase 2 sub-agent, and globally in `.claude/settings.local.json` so it is in effect for any Bash/PowerShell shell-out from Claude Code. This makes the cp1251 default irrelevant.

---

## 8. Out of scope

Tracked here so reviewers know what is intentionally absent:

- **Audio Isolation phase** — Spec B, separate brainstorm.
- **`grade.py` Windows auto-mode bug** (cheatsheet §22) — workaround documented (use preset, not `auto`); upstream fix not our job.
- **`render.py` vertical scale fix** (cheatsheet §22, PR #23) — already applied locally via rebase, no orchestrator change needed.
- **Custom resolution argument in `render.py`** — not blocking.
- **Machine diff between `script.txt` and ASR** — punted. Phase 2 sub-agent reads both and judges in-LLM. If next retro shows this is unreliable, add a helper.
- **`init` lockfile** (retro 3.6) — fixes itself once `hyperframes` is a `package.json` devDependency (§4.2).

---

## 9. Open questions for plan-writing phase

Items where the design above has a defensible default but implementation may surface a better answer:

1. **`Agent` sub-agent type for Phase 2.** `general-purpose` is the obvious choice (it has full tool access and can read SKILL.md from `~/.claude/skills/video-use`). The brief in §5.1 should explicitly tell it to read the SKILL.md before starting. If a more specific sub-agent type fits, swap during implementation.
2. **Cheatsheet path in briefs.** §5.1 references "your skill's §6". If video-use's actual `SKILL.md` does not have a §6 (the cheatsheet is our compression of it), the brief should reference the live SKILL.md path (`~/.claude/skills/video-use/SKILL.md`) and the executor reads it directly.
3. **`scaffold_hyperframes.py` symlink vs relative-src.** Decision in §4.2 is relative-src (`<video src="../edit/final.mp4">`). If hyperframes' renderer turns out to copy the asset into a sandboxed temp dir, the relative path will break. Verify on first re-run; fall back to symlink+elevation prompt if needed.

---

## 10. Success criteria

The spec is implemented when, on a fresh episode dropped into `inbox/`:

- Slug is derived from the script file, dated, and stored consistently.
- Phase 2 runs as a sub-agent, returns `final.mp4` + `raw.json` + `edl.json` + appends to `project.md`, and visibly performs at least 4 timeline-view self-eval points.
- `final.json` (output-timeline) is emitted by `remap_transcript.py`.
- `hyperframes/` is scaffolded by `scaffold_hyperframes.py` with correct dimensions and no media duplication.
- Phase 3 runs all six gates and contrast-overlay shows zero magenta regions.
- Both phases append to `edit/project.md`.
- A second episode dropped immediately afterwards runs without manual intervention and produces a unique, readable slug.
