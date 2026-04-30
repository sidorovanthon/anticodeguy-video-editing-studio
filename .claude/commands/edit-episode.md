---
description: Run the video editing pipeline (pickup → video-use → hyperframes → studio) on an episode from inbox/ or by slug.
argument-hint: "[slug]"
---

You are orchestrating a three-phase video editing pipeline. Follow this recipe exactly. The skills `video-use` and `hyperframes` own all creative decisions; this command provides only structure, glue, and enforcement.

## Inputs

- `$1` (optional): episode slug. If omitted, pick from `inbox/`.

## Project layout (must hold)

```
inbox/<stem>.<video-ext>      -> drop zone, paired with <stem>.txt or .md script
inbox/<stem>.txt|.md          -> author script (optional but recommended)
episodes/<slug>/raw.<ext>     -> moved here at Phase 1
episodes/<slug>/script.txt    -> moved here at Phase 1 (always renamed to .txt)
episodes/<slug>/edit/         -> produced by video-use sub-agent (final.mp4 + raw.json + edl.json + project.md)
episodes/<slug>/edit/transcripts/final.json  -> emitted by orchestrator glue (output-timeline, hyperframes captions schema)
episodes/<slug>/hyperframes/  -> scaffolded by orchestrator + authored by hyperframes Skill
```

All paths passed to skills MUST be absolute. Substitute `<EPISODE_DIR>` etc. at runtime.

---

## Phase 1 — Pickup

Run `scripts/pickup.py` to pair video+script in `inbox/`, derive slug, and move files into `episodes/<slug>/`. Use the appropriate shell for the environment (Windows: PowerShell; otherwise Bash):

**PowerShell:**
```powershell
python scripts\pickup.py --inbox inbox --episodes episodes ${arg}
```
where `${arg}` is `--slug $1` if `$1` was given, otherwise empty.

**Bash:**
```bash
python scripts/pickup.py --inbox inbox --episodes episodes ${arg}
```

Parse the JSON on stdout. Fields: `slug`, `episode_dir`, `raw_path`, `script_path`, `resumed`, `idle`, `warning`.

- If `idle: true`: there is nothing in `inbox/` and no slug arg. Offer to relaunch the studio for the most recently modified `episodes/*/hyperframes/index.html` (run `npx hyperframes preview <that-dir> --port 3002` in the background and report the URL). If no such directory exists, report `nothing to do — drop a video in inbox/` and stop.
- If `warning` is set: display it to the user, then continue.
- Otherwise announce: `Episode: <slug>. Raw at <raw_path>. Script at <script_path or "(none)">.`

Set `EPISODE_DIR = <absolute path to episodes/<slug>>`.

---

## Phase 2 — Video edit (video-use sub-agent)

**Skip if** `<EPISODE_DIR>/edit/final.mp4` exists. Announce `Phase 2 already complete — skipping video-use.` and proceed.

Otherwise dispatch a sub-agent via the `Agent` tool with `subagent_type: general-purpose`. The brief — substitute absolute paths:

> You are the video-use sub-agent. Read `~/.claude/skills/video-use/SKILL.md` first, then edit `<EPISODE_DIR>/raw.<ext>` and write all outputs under `<EPISODE_DIR>/edit/`.
>
> **Author's script** is at `<EPISODE_DIR>/script.txt` (may be absent — check first). Treat it as ground truth for take selection and to verify ASR accuracy. Flag any divergence in your reasoning log.
>
> **Strategy confirmation (canonical resolution of Hard Rule 11 in this orchestrated context):** the user invoked `/edit-episode`, which constitutes pre-approved strategy: "edit `raw.<ext>` per the script at `script.txt`, output a tight talking-head cut to `final.mp4`, default pacing on the tighter end of Hard Rule 7's 30–200ms window, all canonical hygiene." Do not pause for further confirmation. If — and only if — the material clearly does not match this implicit strategy (wrong content type, script unrelated to footage, multi-speaker where solo expected), return early with a single specific question and no edits performed.
>
> **Pacing:** follow the "Cut craft (techniques)" section of the canon — silences ≥400ms cleanest cuts, 150–400ms usable with visual check, <150ms unsafe. Padding stays in 30–200ms (Hard Rule 7). Per Principle 5, the canon's launch-video example values (50ms / 80ms) are a worked example, not a mandate. Default lean for our content: tight end of the window, eliminate retakes/false starts.
>
> **Required outputs (all under `<EPISODE_DIR>/edit/`):**
> - `final.mp4` — rendered video.
> - `transcripts/raw.json` — Scribe word-level on source timeline (cached if exists; **never re-transcribe** per Hard Rule 9).
> - `edl.json` — final EDL per the canon's "EDL format". Functionally required: `ranges`, `sources`. Recommended: `total_duration_s`, `grade`, `subtitles`, `overlays`.
> - `project.md` — append a session block per the canon's "Memory — `project.md`" section.
>
> **Self-eval (canon's 8-step process, step 7):**
> - `helpers/timeline_view.py` on the rendered output at every cut boundary (±1.5s).
> - Sample first 2s, last 2s, 2–3 mid-points.
> - `ffprobe` on `final.mp4` — duration must match EDL `total_duration_s` within 100ms.
> - Cap at 3 self-eval passes.
> - Confirm Hard Rule 12 (outputs in `<edit>/`).
>
> **Environment:** `PYTHONUTF8=1` is set globally; do not override.
>
> Report what you did, what you skipped and why, and any divergence between `script.txt` and ASR.

After the sub-agent returns, verify `<EPISODE_DIR>/edit/final.mp4`, `transcripts/raw.json`, and `edl.json` exist. If any is missing, stop and surface the failure.

---

## Glue between Phase 2 and Phase 3

Run from project root:

```bash
python scripts/remap_transcript.py \
  --raw <EPISODE_DIR>/edit/transcripts/raw.json \
  --edl <EPISODE_DIR>/edit/edl.json \
  --out <EPISODE_DIR>/edit/transcripts/final.json
```

(Skip if `<EPISODE_DIR>/edit/transcripts/final.json` already exists — idempotent.)

---

## Phase 3 — Composition & studio (hyperframes Skill)

**Skip-build if** `<EPISODE_DIR>/hyperframes/index.html` exists. Skip the scaffold and Skill invocation; jump straight to the studio launch.

Otherwise scaffold first:

```bash
python scripts/scaffold_hyperframes.py \
  --episode-dir <EPISODE_DIR> \
  --slug <SLUG>
```

Then invoke the `hyperframes` skill via the `Skill` tool with this verbatim brief:

> Read `~/.agents/skills/hyperframes/SKILL.md` first, then build a HyperFrames composition in `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json` are in place. The video and audio are wired as a canonical `<video muted playsinline> + <audio>` pair both pointing at `../edit/final.mp4`. The word-level transcript (output-timeline, hyperframes captions schema) is at `hyperframes/transcript.json`.
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
>
> **Visual Identity Gate (canonical `<HARD-GATE>`):** before writing any composition HTML, follow the canon's gate order in SKILL.md §"Visual Identity Gate". The user's named style is **"Liquid Glass / iOS frosted glass"** — start at gate step 3: read `~/.agents/skills/hyperframes/visual-styles.md` for a matching named preset and apply it. If no matching preset exists, generate a minimal `DESIGN.md` per the canon's structure. Do not hardcode `#333` / `#3b82f6` / `Roboto`.
>
> **Multi-scene transitions:** if the composition has multiple scenes, the canon's "Scene Transitions (Non-Negotiable)" rules apply: always use transitions, every scene gets entrance animations, never exit animations except on the final scene.
>
> **Output Checklist (canonical):**
> 1. `npx hyperframes lint` — passes.
> 2. `npx hyperframes validate` — passes; built-in WCAG contrast audit produces no warnings.
> 3. `npx hyperframes inspect` — passes, or every reported overflow is intentional and marked.
> 4. `node ~/.agents/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon. Read the JSON; check every flag (`offscreen`, `collision`, `invisible`, `paced-fast`, `paced-slow`); fix or justify.
>
> **Extra check we add (not in canon — orchestrator-imposed):** run `node ~/.agents/skills/hyperframes/scripts/contrast-report.mjs <hyperframes-dir>` and open the resulting `contrast-overlay.png` in the output dir. Fix any magenta regions; ideally clear yellow too. If absent or failing, do not block — log "extra check skipped/failed" and proceed.
>
> **Project memory:** append a session block to `<EPISODE_DIR>/edit/project.md` with Strategy / Decisions / Outstanding for this composition.
>
> **Studio launch:** after gates pass, launch the preview server in the background. Run from `<EPISODE_DIR>/hyperframes/`:
> - PowerShell: `Start-Process npx -ArgumentList 'hyperframes','preview','--port','3002' -WindowStyle Hidden`
> - Bash: `npx hyperframes preview --port 3002 &`
>
> Report `http://localhost:3002` to the user.

---

## Studio launch (skip-build path)

If Phase 3 was skipped because `index.html` already existed, run the studio launch above directly (use `--list` first to detect an already-running server and skip if found).

---

## Completion

Announce: `Done. Studio: http://localhost:3002. Episode: <EPISODE_DIR>.`

---

## Idempotency and rebuild guidance

The command is safe to re-run on the same slug. Skip rules:
1. `<EPISODE_DIR>/edit/final.mp4` exists → skip Phase 2.
2. `<EPISODE_DIR>/edit/transcripts/final.json` exists → skip glue remap.
3. `<EPISODE_DIR>/hyperframes/index.html` exists → skip scaffold and Skill, only relaunch studio.

To force re-cut: delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — **no Scribe re-spend**.

To re-compose only: delete `<EPISODE_DIR>/hyperframes/`. Phase 2 skipped; `final.mp4` and transcripts preserved.

---

## Error handling

Each phase is fail-fast. If `pickup.py`, `video-use` sub-agent, `remap_transcript.py`, `scaffold_hyperframes.py`, or `hyperframes` skill returns an error, stop, show what failed, and tell the user to fix and re-run `/edit-episode <slug>`. Do not retry; do not roll back partial outputs. Idempotency rules ensure re-running picks up where it failed.
