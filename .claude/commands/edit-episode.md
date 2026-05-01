---
description: Run the video editing pipeline (pickup → audio-isolation → video-use → hyperframes → studio) on an episode from inbox/ or by slug.
argument-hint: "[slug]"
---

You are orchestrating a four-phase video editing pipeline. Follow this recipe exactly. The skills `video-use` and `hyperframes` own all creative decisions; this command provides only structure, glue, and enforcement.

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

Use `python -m` invocation (not `python <path>`) because `scripts/pickup.py` does `from scripts.slugify import ...` — running it as a path bypasses the package machinery and breaks the import.

**PowerShell:**
```powershell
python -m scripts.pickup --inbox inbox --episodes episodes ${arg}
```
where `${arg}` is `--slug $1` if `$1` was given, otherwise empty.

**Bash:**
```bash
python -m scripts.pickup --inbox inbox --episodes episodes ${arg}
```

Parse the JSON on stdout. Fields: `slug`, `episode_dir`, `raw_path`, `script_path`, `resumed`, `idle`, `warning`.

- If `idle: true`: there is nothing in `inbox/` and no slug arg. Offer to relaunch the studio for the most recently modified `episodes/*/hyperframes/index.html` (run `npx hyperframes preview <that-dir> --port 3002` in the background and report the URL). If no such directory exists, report `nothing to do — drop a video in inbox/` and stop.
- If `warning` is set: display it to the user, then continue.
- Otherwise announce: `Episode: <slug>. Raw at <raw_path>. Script at <script_path or "(none)">.`

Set `EPISODE_DIR = <absolute path to episodes/<slug>>`.

---

## Phase 2 — Audio isolation

Run inline:

**Bash:**
```bash
python -m scripts.isolate_audio --episode-dir <EPISODE_DIR>
```

**PowerShell:**
```powershell
python -m scripts.isolate_audio --episode-dir <EPISODE_DIR>
```

Parse the JSON on stdout. Fields: `cached`, `api_called`, `wav_path`, `raw_path`, `reason`.

- If `cached: true` (`reason: "tag-present"`): announce `Phase 2 already complete (container tagged) — skipping isolation.` and proceed.
- If `cached: false, api_called: false` (`reason: "api-cache-hit"`): announce `Phase 2 used cached WAV (audio/raw.cleaned.wav) — remuxed into raw.<ext>.`
- Otherwise (`reason: "isolated"`): announce `Phase 2 done — audio isolated and muxed into raw.<ext>. Cache at <wav_path>.`

On non-zero exit: stop the pipeline, surface the stderr message verbatim to the user, and tell them to fix the underlying issue (typically API key or network) and re-run `/edit-episode <slug>`. Do not retry. There is no `--skip-isolation` flag — running without isolation is not a supported mode.

---

## Phase 3 — Video edit (video-use sub-agent)

**Skip if** `<EPISODE_DIR>/edit/final.mp4` exists. Announce `Phase 3 already complete — skipping video-use.` and proceed.

Otherwise dispatch a sub-agent via the `Agent` tool with `subagent_type: general-purpose`. The brief — substitute absolute paths:

> You are the video-use sub-agent. Read `~/.claude/skills/video-use/SKILL.md` first, then edit `<EPISODE_DIR>/raw.<ext>` and write all outputs under `<EPISODE_DIR>/edit/`.
>
> **Author's script** is at `<EPISODE_DIR>/script.txt` (may be absent — check first). Treat it as ground truth for take selection and to verify ASR accuracy. Flag any divergence in your reasoning log.
>
> **Strategy confirmation (canonical resolution of Hard Rule 11 in this orchestrated context):** the user invoked `/edit-episode`, which constitutes pre-approved strategy: "edit `raw.<ext>` per the script at `script.txt`, output a tight talking-head cut to `final.mp4`, default pacing on the tighter end of Hard Rule 7's 30–200ms window, all canonical hygiene." Do not pause for further confirmation. If — and only if — the material clearly does not match this implicit strategy (wrong content type, script unrelated to footage, multi-speaker where solo expected), return early with a single specific question and no edits performed.
>
> **Pre-cleaned audio:** the audio track of `raw.<ext>` has already been processed by ElevenLabs Audio Isolation in Phase 2 — treat it as a studio-grade source. Do not apply additional noise-suppression filters; loudnorm and the per-segment 30ms fades from Hard Rule 3 are still required.
>
> **Pacing target.** Aim for **25–35% runtime reduction** from source. Treat any inter-phrase silence > 300ms as a cut candidate (canon: silences ≥ 400ms are cleanest cut targets, 150–400ms usable with visual check, < 150ms unsafe — mid-phrase). Cut padding stays in 30–200ms (Hard Rule 7 — absorbs Scribe's 50–100ms drift; this rule is about cut-edge padding, NOT inter-phrase silence). Remove all retakes and false starts. If final runtime > 75% of source, append a one-line note in `project.md` explaining why tighter cuts were not possible.
>
> **Subtitles.** Do NOT burn subtitles into `final.mp4`. Omit the `subtitles` field from EDL **and** pass `--no-subtitles` to `helpers/render.py` (defense in depth — canon §8 of `docs/cheatsheets/video-use.md`). Do not pass `--build-subtitles`. Captions are produced downstream by Phase 4 (HyperFrames `references/captions.md`).
>
> **Retake selection.** When the same beat is recorded multiple times (false-starts, retakes within a single take or across takes), pick the cleanest delivery — fewer slips, better energy, completed thought. If two takes are roughly equal, prefer the **later** one (the speaker is usually warmed up). Note the choice briefly in EDL `reason`, e.g. `"Last take, first had stutter"` (canon EDL example uses this `reason` shape).
>
> **Required outputs (all under `<EPISODE_DIR>/edit/`):**
> - `final.mp4` — rendered video.
> - `transcripts/raw.json` — Scribe word-level on source timeline (cached if exists; **never re-transcribe** per Hard Rule 9).
> - `edl.json` — final EDL per the canon's "EDL format". Functionally required: `ranges`, `sources`. Recommended: `total_duration_s`, `grade`, `overlays`. **Do NOT** include `subtitles` — HF owns captions (see Subtitles block above).
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

## Glue between Phase 3 and Phase 4

Run from project root:

```bash
python -m scripts.remap_transcript \
  --raw <EPISODE_DIR>/edit/transcripts/raw.json \
  --edl <EPISODE_DIR>/edit/edl.json \
  --out <EPISODE_DIR>/edit/transcripts/final.json
```

(Skip if `<EPISODE_DIR>/edit/transcripts/final.json` already exists AND its stored `edl_hash` matches the current `edl.json` content. `scripts/remap_transcript.py` self-checks and short-circuits on hash match, so calling it unconditionally is safe and idempotent.)

---

## Phase 4 — Composition & studio (hyperframes Skill)

**Skip-build if** `<EPISODE_DIR>/hyperframes/index.html` exists. Skip the scaffold and Skill invocation; jump straight to the studio launch.

Otherwise scaffold first:

```bash
python -m scripts.scaffold_hyperframes \
  --episode-dir <EPISODE_DIR> \
  --slug <SLUG>
```

Then invoke the `hyperframes` skill via the `Skill` tool with this verbatim brief:

> Read `~/.agents/skills/hyperframes/SKILL.md` first, then build a HyperFrames composition in `<EPISODE_DIR>/hyperframes/`. The project is **already scaffolded** — do not run `npx hyperframes init`. The scaffolded `index.html`, `package.json`, `hyperframes.json`, `meta.json` are in place. The video and audio are wired as a canonical `<video muted playsinline data-has-audio="false"> + <audio>` pair both pointing at `final.mp4` (sibling hardlink). The word-level transcript (output-timeline, hyperframes captions schema) is at `hyperframes/transcript.json`.
>
> The author's script is at `<EPISODE_DIR>/script.txt` — use it as the source of truth for caption wording when it diverges from the transcript.
>
> **Required reading before composing — verbatim list.** Read these in order, then confirm in your first response which files were read. Empty confirmation = stop, do not proceed.
> 1. `~/.agents/skills/hyperframes/SKILL.md` (you already opened this — re-confirm).
> 2. `~/.agents/skills/hyperframes/references/video-composition.md` — *Always read* (canon).
> 3. `~/.agents/skills/hyperframes/references/typography.md` — *Always read* (canon).
> 4. `~/.agents/skills/hyperframes/references/motion-principles.md` — *Always read* (canon).
> 5. `~/.agents/skills/hyperframes/references/beat-direction.md` — *Always read for multi-scene compositions* (canon).
> 6. `~/.agents/skills/hyperframes/references/transitions.md` — *Always read for multi-scene compositions* (canon).
> 7. `~/.agents/skills/hyperframes/references/captions.md` — orchestrator-house addition. Canon treats captions as conditional ("when adding any text synced to audio"); this orchestrator's pipeline always produces audio-synced text, so the conditional trigger always fires, making it effectively mandatory here.
> 8. `~/.agents/skills/hyperframes/references/transcript-guide.md` — orchestrator-house addition for the same reason.
>
> **Step 2 — Prompt expansion (mandatory for multi-scene).** After reading the canon, run Step 2 per `references/prompt-expansion.md`. Output goes to `<EPISODE_DIR>/hyperframes/.hyperframes/expanded-prompt.md` (canonical path and name per `references/prompt-expansion.md:57-68`). This artifact MUST exist before any composition HTML is written. If it does not exist after Step 2, you have not run Step 2.
>
> **Catalog discovery — orchestrator-house gate.** Before writing any custom HTML for a beat, run `npx hyperframes catalog --json > .hyperframes/catalog.json` from `<EPISODE_DIR>/hyperframes/`. For each narrative beat, write one sentence in `DESIGN.md` → `Beat→Visual Mapping`: which catalog block was considered (or installed via `npx hyperframes add <name>`), and why custom HTML is justified. Empty per-beat justification list = stop. (Note: this is an orchestrator productivity rule, not HF canon — canon mentions `catalog` only in Step 1 / Design Picker context.)
>
> **Visual Identity Gate (canonical `<HARD-GATE>`).** Before writing any composition HTML, follow the canon's gate order in SKILL.md §"Visual Identity Gate". The user's named style is **"Liquid Glass / iOS frosted glass"** — start at gate step 3: read `~/.agents/skills/hyperframes/visual-styles.md` for a matching named preset and apply it. If no matching preset exists, generate a `DESIGN.md` per the canon's structure. Do not hardcode `#333` / `#3b82f6` / `Roboto`.
>
> **DESIGN.md substance.** The generated `DESIGN.md` must contain — not as a template, but as real authored content:
> - **Style Prompt** — one-paragraph mood statement.
> - **Colors** — 3–5 hex values with named roles.
> - **Typography** — 1–2 font families.
> - **Visual References** — name ≥ 2 specific real-world references (e.g., "iOS 17 Control Center frosted panels", "Vision Pro spatial UI"). Generic references like "modern minimalist" do not count.
> - **Alternatives Considered** — describe ≥ 1 alternative direction and why it was rejected.
> - **What NOT to Do** — 3–5 anti-patterns specific to this episode.
> - **Beat→Visual Mapping** — from the multi-scene block above.
>
> **WCAG fail handling.** WCAG fails are resolved by adjusting hue within the palette family (HF SKILL.md §"Contrast": "On dark backgrounds: brighten until clears 4.5:1 ... Stay within palette family — don't invent a new color, adjust the existing one"). Try ≥ 2 darker/brighter variants of the same hue before considering structural changes. Removing color in favor of weight-only emphasis is a last resort and requires a one-line justification in `DESIGN.md`.
>
> **Multi-scene narrative composition (mandatory).** Read `<EPISODE_DIR>/script.txt` and identify ≥ 3 narrative beats. Compositions MUST be multi-scene with ≥ 3 beat-derived scenes. Apply Scene Transitions canon (HF SKILL.md §"Scene Transitions" — non-negotiable: always use transitions, every scene gets entrance animations, never exit animations except on the final scene). For each beat, choose either (a) a registry block (run `npx hyperframes catalog` to browse before authoring custom HTML; install via `npx hyperframes add <name>`) or (b) custom motion / overlay justified by the script content. Single-scene caption-only compositions are not acceptable. Document the beat→visual mapping in `DESIGN.md` alongside palette and typography decisions.
>
> **Output Checklist (canonical):**
> 1. `npx hyperframes lint` — passes.
> 2. `npx hyperframes validate` — passes; built-in WCAG contrast audit produces no warnings.
> 3. `npx hyperframes inspect` — passes, or every reported overflow is intentional and marked.
> 4. `node <hyperframes-dir>/node_modules/hyperframes/dist/skills/hyperframes/scripts/animation-map.mjs <hyperframes-dir> --out <hyperframes-dir>/.hyperframes/anim-map` — required for new compositions per canon. Read the JSON. **Do not invoke `~/.agents/skills/hyperframes/scripts/animation-map.mjs`** — that copy is documentation-only and fails to bootstrap because its `package-loader.mjs` walks ancestors of the script's own location for a `hyperframes`/`@hyperframes/cli` `package.json`, which doesn't exist above the global skill dir. The bundled copy under the project's `node_modules/hyperframes/dist/...` resolves the version probe via the package's own manifest.
>
> **Extra check we add (not in canon — orchestrator-imposed):** run `node <hyperframes-dir>/node_modules/hyperframes/dist/skills/hyperframes/scripts/contrast-report.mjs <hyperframes-dir>` (same bundled-path rule as animation-map — never use the `~/.agents/skills/...` copy) and open the resulting `contrast-overlay.png` in the output dir. Fix any magenta regions; ideally clear yellow too. If absent or failing, do not block — log "extra check skipped/failed" and proceed.
>
> **Visual verification (mandatory before announcing Done).** Use canonical HF tools — no ffmpeg shell-out.
>
> 1. **Canonical layout audit at beat boundaries.** Run `npx hyperframes inspect --at <beat_timestamps>` from `<EPISODE_DIR>/hyperframes/`, where `<beat_timestamps>` are the comma-separated start times of each beat from the §"Beat→Visual Mapping" of `DESIGN.md`. Re-uses the canonical layout/overflow audit on the timestamps that matter narratively.
> 2. **Canonical screenshots at beat boundaries.** Run `npx hyperframes snapshot --at <beat_timestamps>` (canonical PNG screenshots without full render — see `docs/cheatsheets/hyperframes.md` §"snapshot"). Include `1`, every beat boundary, and `<duration - 1>` in the timestamp list.
> 3. **Three explicit questions per snapshot** — answer in writing in your final report, before the studio launch:
>    a. Is the expected beat element visible (registry block / scene card / overlay from §"Multi-scene narrative composition")?
>    b. Any unintended z-overlap (caption covering a key element, scene exit leaving residue)?
>    c. Is the A-roll video accidentally occluded by a semi-transparent overlay?
> 4. Only after this list is in your report, proceed to the studio launch.
>
> **Project memory:** append a session block to `<EPISODE_DIR>/edit/project.md` with Strategy / Decisions / Outstanding for this composition.
>
> **Studio launch:** after gates pass, launch the preview server in the background. Run from `<EPISODE_DIR>/hyperframes/`. Logs go to `.hyperframes/preview.log` (canonical scratch dir):
> - Bash: `mkdir -p .hyperframes && npx hyperframes preview --port 3002 > .hyperframes/preview.log 2>&1 &`
> - PowerShell: `New-Item -ItemType Directory -Force -Path .hyperframes | Out-Null; Start-Process npx -ArgumentList 'hyperframes','preview','--port','3002' -RedirectStandardOutput .hyperframes\preview.log -RedirectStandardError .hyperframes\preview.err.log -WindowStyle Hidden`
>
> Report `http://localhost:3002` to the user.

---

## Studio launch (skip-build path)

If Phase 4 was skipped because `index.html` already existed, run the studio launch above directly (use `--list` first to detect an already-running server and skip if found).

---

## Completion

Announce: `Done. Studio: http://localhost:3002. Episode: <EPISODE_DIR>.`

---

## Idempotency and rebuild guidance

The command is safe to re-run on the same slug. Skip rules:
1. `<EPISODE_DIR>/raw.<ext>` container tagged `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1` → skip Phase 2 entirely.
2. `<EPISODE_DIR>/edit/final.mp4` exists → skip Phase 3.
3. `<EPISODE_DIR>/edit/transcripts/final.json` exists **and its `edl_hash` matches the current `edl.json`** → skip glue remap. (The glue script self-checks this — calling it always is safe.)
4. `<EPISODE_DIR>/hyperframes/index.html` exists → skip scaffold and Skill, only relaunch studio.

Rebuild paths:

- **Re-cut:** delete `<EPISODE_DIR>/edit/final.mp4` AND `<EPISODE_DIR>/hyperframes/`. `transcripts/raw.json` stays — **no Scribe re-spend**. The audio tag on `raw.<ext>` survives — **no Audio Isolation re-spend either**. `transcripts/final.json` does NOT need manual deletion — `scripts/remap_transcript.py` self-checks the EDL hash and regenerates automatically when EDL changes (per the envelope schema introduced in 2026-05-01).
- **Re-compose only:** delete `<EPISODE_DIR>/hyperframes/`. Phase 3 skipped; `final.mp4` and transcripts preserved.
- **Re-isolate audio:** delete `<EPISODE_DIR>/audio/raw.cleaned.wav` AND restore `raw.<ext>` to its un-tagged state (re-pickup from `inbox/`, or git/manual restore). Costs ElevenLabs Audio Isolation credits — almost never needed.

---

## Error handling

Each phase is fail-fast. If `pickup.py`, `isolate_audio.py`, `video-use` sub-agent, `remap_transcript.py`, `scaffold_hyperframes.py`, or `hyperframes` skill returns an error, stop, show what failed, and tell the user to fix and re-run `/edit-episode <slug>`. Do not retry; do not roll back partial outputs. Idempotency rules ensure re-running picks up where it failed.
