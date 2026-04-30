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
   - Inject the canonical **video + audio pair** inside the root div (replaces the example-clip comment). Per live `~/.agents/skills/hyperframes/SKILL.md` §"Video and Audio": "Video must be `muted playsinline`. Audio is **always a separate `<audio>` element**." Two elements, same `src`:
     ```html
     <video id="el-video" data-start="0" data-track-index="0"
            src="../edit/final.mp4" muted playsinline></video>
     <audio id="el-audio" data-start="0" data-track-index="1"
            src="../edit/final.mp4" data-volume="1"></audio>
     ```
     (Earlier drafts of this spec used `data-has-audio="true"` — that pattern appears in the cheatsheet but **not** in the live SKILL.md, so we follow canon and use the two-element pair.)
4. **Patch `meta.json`** — overwrite `id` and `name` from the literal `"hyperframes"` (init's default from the dir argument) to the episode slug.
5. **Add `hyperframes/package.json`** — init does not generate one. We add it ourselves with `hyperframes` pinned as devDependency. `npm install` runs once at scaffold; subsequent `npx hyperframes` calls hit the local cache (fixes retro 3.6).
6. **Copy transcript** — copy `episodes/<slug>/edit/transcripts/final.json` (output-timeline word-level, see §4.3) to `hyperframes/transcript.json`. A copy, not a reference, because hyperframes treats it as a project-local asset.

**`DESIGN.md` is intentionally NOT generated by the scaffold.** Per live `~/.agents/skills/hyperframes/SKILL.md` §"Visual Identity Gate" (a `<HARD-GATE>`), authoring `DESIGN.md` is the responsibility of the Phase 3 Skill executor at the very start of composition work — checking `visual-styles.md` for a matching named identity (e.g., "Liquid Glass") first, and falling back to the 3-question generation pattern only if no match. Pre-creating a stub here would short-circuit that canonical gate and let the executor skip the correct identity-matching step. The Phase 3 brief in §5.2 enforces this explicitly.

**Video reference rationale:** `<video src="../edit/final.mp4">` is used instead of copying or symlinking the file. Chrome resolves the relative path from the HTML location; verified to work in studio preview. If hyperframes' renderer turns out to copy assets into a sandboxed temp dir during `render`, the relative path will break — see §9 open question. Symlink + UAC elevation prompt remains the fallback.

Replaces retro fixes 1.2, 1.3, 3.2, 3.3, 3.6 in one script. Retro 2.4 (DESIGN.md presence) is enforced by the Phase 3 brief, not by the scaffold.

### 4.3 `scripts/remap_transcript.py`

Reads `episodes/<slug>/edit/transcripts/raw.json` (Scribe word-level, source-timeline) and `episodes/<slug>/edit/edl.json` (cut decisions emitted by video-use). Produces `episodes/<slug>/edit/transcripts/final.json` in the **hyperframes captions schema** — verified against `~/.agents/skills/hyperframes/references/captions.md` §"Transcript Source":

```json
[
  { "text": "Hello", "start": 0.0, "end": 0.5 },
  { "text": "world.", "start": 0.6, "end": 1.2 }
]
```

**Critical:** this is a flat array of word objects, **not** Scribe's nested `{words: [...]}` schema. Earlier draft of this spec said "same Scribe schema, but timestamps remapped" — that would have produced an artifact hyperframes captions cannot consume. The schema mismatch was caught by reading `references/captions.md` directly during the canon audit. The Scribe-format raw transcript stays at `transcripts/raw.json` for any consumer that wants it; `final.json` is purpose-built for hyperframes.

Algorithm: walk every word in `raw.json` (Scribe schema: object with `words` array, each word has `text`/`start`/`end`/`type`/`speaker_id`). For each `type: "word"` entry, find the EDL range containing its source-timeline `start`. Words in cut-out regions are dropped. Words inside a kept range get:
- `output_start = word.start - range.start + cumulative_output_offset`
- `output_end = word.end - range.start + cumulative_output_offset`

`cumulative_output_offset` accumulates across kept ranges in EDL order. Audio events (`type: "audio_event"` like `(laughs)`) are dropped from caption output — they are not spoken text. Speaker labels are also dropped (captions schema has no speaker field).

Output emits one object per word with only `text`/`start`/`end` fields, in time order.

This is the same output-timeline math `helpers/render.py` performs internally for `master.srt` (per video-use Hard Rule 5: `output_time = word.start - segment_start + segment_offset`), but emits word-level JSON in the hyperframes captions schema instead of phrase-level SRT.

**Filename `transcript.json` in `hyperframes/`** is our orchestrator-side convention — `references/captions.md` does not specify one. The Phase 3 brief tells the executor exactly where to load it from, so executor + scaffold agree by contract.

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

Substitute absolute paths at runtime. Section names and rule numbers below match the live `~/.claude/skills/video-use/SKILL.md` (verified 2026-04-30) — the executor reads canon directly.

> You are the video-use sub-agent. Read `~/.claude/skills/video-use/SKILL.md` first, then edit `<EPISODE_DIR>/raw.<ext>` and write all outputs under `<EPISODE_DIR>/edit/`.
>
> **Author's script** is at `<EPISODE_DIR>/script.txt`. Treat it as ground truth for take selection and to verify ASR accuracy. Flag any divergence in your reasoning log.
>
> **Strategy confirmation (canonical resolution of Hard Rule 11 in this orchestrated context):** the user invoked `/edit-episode`, which constitutes pre-approved strategy: "edit `raw.<ext>` per the script at `script.txt`, output a tight talking-head cut to `final.mp4`, default pacing on the tighter end of Hard Rule 7's 30–200ms window, all canonical hygiene." **Do not pause for further confirmation.** If — and only if — the material clearly does not match this implicit strategy (wrong content type, script unrelated to footage, multi-speaker where solo expected, etc.), return early with a single specific question and no edits performed.
>
> **Pacing:** follow the "Cut craft (techniques)" section of the canon — silences ≥400ms are the cleanest cut targets, 150–400ms usable with a visual check, <150ms unsafe (mid-phrase). Padding stays in the 30–200ms working window per Hard Rule 7. Per Principle 5, the specific padding values in the canon's launch-video example (50ms / 80ms) are a worked example, not a mandate — pick what the material wants. Default lean for our content (talking-head launch): tight end of the window, eliminate retakes/false starts, drop weak takes when alternatives exist.
>
> **Required outputs (all under `<EPISODE_DIR>/edit/`):**
> - `final.mp4` — rendered video.
> - `transcripts/raw.json` — Scribe word-level on source timeline (cached if exists; **never re-transcribe** per Hard Rule 9).
> - `edl.json` — final EDL per the canon's "EDL format" section. Functionally required: `ranges`, `sources`. Recommended when applicable: `total_duration_s` (used by orchestrator for the duration check below), `grade`, `subtitles`, `overlays`.
> - `project.md` — append a session block per the canon's "Memory — `project.md`" section (Strategy / Decisions / Reasoning log / Outstanding).
>
> **Self-eval (the canon's 8-step process, step 7):**
> - Run `helpers/timeline_view.py` on the **rendered output** at every cut boundary (±1.5s window) — check for visual discontinuity, waveform spikes, subtitle hiding (Rule 1), overlay misalignment (Rule 4).
> - Sample first 2s, last 2s, and 2–3 mid-points for grade consistency, subtitle readability, overall coherence.
> - `ffprobe` on `final.mp4` — duration must match EDL `total_duration_s` within 100ms.
> - **Cap at 3 self-eval passes.** If issues remain after 3, surface them rather than looping.
> - Confirm Hard Rule 12 (outputs in `<edit>/`, not in `video-use/` repo).
>
> **Environment:** `PYTHONUTF8=1` is set globally; do not override. If a helper script crashes on encoding, that is a genuine bug — surface it.
>
> Report what you did, what you skipped and why, and any divergence between `script.txt` and ASR.

### 5.2 Phase 3 brief (hyperframes Skill in main session)

Section names below match the live `~/.agents/skills/hyperframes/SKILL.md` (verified 2026-04-30).

> Read `~/.agents/skills/hyperframes/SKILL.md` first, then build a HyperFrames composition in `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json` are in place. The video and audio are wired as a canonical `<video muted playsinline> + <audio>` pair both pointing at `../edit/final.mp4`. The word-level transcript (output-timeline, ready to use directly with `final.mp4`) is at `hyperframes/transcript.json`.
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
>
> **Visual Identity Gate (canonical `<HARD-GATE>`):** before writing any composition HTML, follow the canon's gate order in `SKILL.md` §"Visual Identity Gate". The user's named style is **"Liquid Glass / iOS frosted glass"** — start at gate step 3: read `~/.agents/skills/hyperframes/visual-styles.md` for a matching named preset and apply it. If no matching preset exists, generate a minimal `DESIGN.md` per the canon's structure (`## Style Prompt`, `## Colors`, `## Typography`, `## What NOT to Do`). Do not hardcode `#333` / `#3b82f6` / `Roboto`.
>
> **Multi-scene transitions:** if the composition has multiple scenes (caption groups across the video), the canon's "Scene Transitions (Non-Negotiable)" rules apply: always use transitions, every scene gets entrance animations, never exit animations except on the final scene.
>
> **Output Checklist (canonical, from SKILL.md §"Output Checklist"):**
> 1. `npx hyperframes lint` — passes.
> 2. `npx hyperframes validate` — passes; built-in WCAG contrast audit produces no warnings (or all warnings are addressed).
> 3. `npx hyperframes inspect` — passes, or every reported overflow is intentional and marked.
> 4. `node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon (skip only on small edits, not applicable here). Read the JSON; check every flag (`offscreen`, `collision`, `invisible`, `paced-fast`, `paced-slow`); fix or justify.
>
> **Extra check we add (not in canon — orchestrator-imposed):** run `node ~/.agents/skills/hyperframes/scripts/contrast-report.mjs <hyperframes-dir>` and open `contrast-overlay.png`. The pilot run highlighted a real white-captions-on-light-background risk that `validate`'s 5-timestamp sampling can miss; `contrast-report.mjs` is denser. Fix any magenta regions; ideally clear yellow too. If absent or failing, do not block — log as "extra check skipped/failed" and proceed.
>
> **Project memory:** append a session block to `<EPISODE_DIR>/edit/project.md` (the same file video-use writes to — extend the existing log) with Strategy / Decisions / Outstanding for this composition.
>
> **Studio launch:** after gates pass, launch the preview server in the background. Verified protocol from `npx hyperframes preview --help` (v0.4.39): the command takes a `[DIR]` argument and a `--port=3002` default. Run from the `hyperframes/` directory with shell-appropriate background syntax (PowerShell: `Start-Process npx -ArgumentList 'hyperframes','preview','--port','3002' -WindowStyle Hidden`; Bash: `npx hyperframes preview --port 3002 &`). Report `http://localhost:3002` to the user. If a server is already running on the same project, the orchestrator can use `npx hyperframes preview --list` to detect it and skip re-launch (idempotency).

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
- Commit `init/hyperframes-cheatsheet.md` and `init/video-use-cheatsheet.md` as `docs/cheatsheets/hyperframes.md` and `docs/cheatsheets/video-use.md`. They are reference summaries for orientation only — every claim used to construct verbatim briefs must still be verified against the live `SKILL.md` per the canon-respect rule (CLAUDE.md §"External skill canon — non-negotiable"). The pilot retro and this spec's audit each surfaced cases where cheatsheet content drifted from canon (`data-has-audio="true"`, fabricated section numbers, Scribe-vs-captions schema confusion); cheatsheets are bait-trapped if used as ground truth.
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

1. **`Agent` sub-agent type for Phase 2.** `general-purpose` is the obvious choice (it has full tool access and can read SKILL.md from `~/.claude/skills/video-use`). The brief in §5.1 already tells it to read the SKILL.md first. If a more specific sub-agent type fits, swap during implementation.
2. **`scaffold_hyperframes.py` symlink vs relative-src.** Decision in §4.2 is relative-src (`<video src="../edit/final.mp4">`). Verified to work in studio preview; not yet verified in the final `npx hyperframes render` path. If the renderer copies assets into a sandboxed temp dir, the relative path will break — fall back to symlink+elevation prompt at that point.
3. **Audio mix at render time.** Canon mandates the `<video muted playsinline> + <audio>` two-element pattern but the live SKILL.md does not document what `npx hyperframes render` does with the second `<audio src=>` (Puppeteer screenshot loop + ffmpeg image2pipe doesn't obviously read audio). Logically the renderer must support it (otherwise canon is self-contradictory), but worth verifying on first end-to-end render that the output `.mp4` actually has audio.

---

## 10. Success criteria

The spec is implemented when, on a fresh episode dropped into `inbox/`:

- Slug is derived from the script file, dated, and stored consistently.
- Phase 2 runs as a sub-agent, returns `final.mp4` + `raw.json` + `edl.json` + appends to `project.md`, and visibly performs at least 4 timeline-view self-eval points.
- `final.json` (output-timeline) is emitted by `remap_transcript.py`.
- `hyperframes/` is scaffolded by `scaffold_hyperframes.py` with correct dimensions and no media duplication.
- Phase 3 runs the four canonical gates (`lint`, `validate`, `inspect`, `animation-map`) cleanly. `contrast-report.mjs` (extra) shows zero magenta regions; if not run or failing, that is logged but does not block.
- Both phases append to `edit/project.md`.
- A second episode dropped immediately afterwards runs without manual intervention and produces a unique, readable slug.
