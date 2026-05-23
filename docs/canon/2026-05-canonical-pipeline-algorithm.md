# Canonical Pipeline Algorithm — video-use → HyperFrames

**Date:** 2026-05-23 · **Ticket:** HOM-335 · **Source-set:** [`2026-05-canon-file-index.md`](2026-05-canon-file-index.md)

This doc captures the ordered step-by-step algorithm a *canonical free-form agent* follows
end-to-end for an episode: raw footage in → final rendered video out. The pipeline is two
canonical sub-skills chained at the orchestrator-house boundary:

1. **video-use** (Steps V0–V8) — raw footage to `edit/final.mp4` + transcripts.
2. **Orchestrator handoff** (Step H) — chain video-use's outputs into HyperFrames' inputs.
3. **hyperframes** (Steps H1–H6 + quality gates Q1–Q4) — prompt to rendered composition.

**Hard rule for this doc** — every claim is anchored to a canon `path:line(s)` citation and
quotes canonical text verbatim. Paraphrase rots; this doc is the linear Ctrl-F surface for
the underlying canon, not a competing rewrite. CLAUDE.md §"Decomposition via
brief-references-canon" item 1 mandates the exception that *this* doc uses verbatim quoting
rather than path-only pointers.

For each step: **Name · Canon source · Inputs · Outputs · Conventions · Quality checks ·
Sub-agents · Transition rule · Open questions**.

**Two appendices at the end:**
- **Appendix A** — flat convention/Hard-Rule index (Ctrl-F).
- **Appendix B** — free-form-canonical-step ↔ LangGraph-node mapping (HOM-334 audit seed).

---

## Phase V — video-use (raw → final.mp4 + transcripts)

video-use SKILL.md "The process" enumerates the 8 canonical steps. The steps below preserve
that numbering (V0 added for first-time install, which SKILL.md treats as out-of-band).

### Step V0 — Setup verification (once per cold start)

**Canon source:** `~/.claude/skills/video-use/SKILL.md:58-71` (§"Setup") + full install procedure in `~/.claude/skills/video-use/install.md`.

**Verbatim:**
> First-time install lives in `install.md` (clone, deps, ffmpeg, skill registration, API key). Don't re-run it every session; on cold start just verify:
>
> - `ELEVENLABS_API_KEY` resolves — either in the environment or in `.env` at the video-use repo root. If missing, ask the user to paste one and write it to `.env` (never to the user's `<videos_dir>`).
> - `ffmpeg` + `ffprobe` on PATH.
> - Python deps installed (`uv sync` or `pip install -e .` inside the repo).
> - Node.js + npm available if the session needs HyperFrames or Remotion slots. HyperFrames currently requires Node.js 22+.
> - `yt-dlp`, HyperFrames, Remotion, Manim installed only on first use.
> — `SKILL.md:60-66`

**Inputs:** environment (`ELEVENLABS_API_KEY`, PATH), the skill repo on disk.
**Outputs:** verified readiness; no artifact.
**Conventions:** Symlink-the-whole-directory (helpers must sit next to SKILL.md) — `install.md:155`. Never echo the key back; never commit `.env` — `install.md:116`.
**Quality checks:** `python ~/Developer/video-use/helpers/timeline_view.py --help >/dev/null && echo "helpers OK"` and `ffprobe -version | head -1` — `install.md:133-135`.
**Sub-agents:** None.
**Transition rule:** Once verification passes, proceed to V1 on first user message.
**Open questions / canon ambiguities:** None observed.

---

### Step V1 — Inventory

**Canon source:** `~/.claude/skills/video-use/SKILL.md:85` (§"The process" item 1).

**Verbatim:**
> 1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` to produce `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.

**Inputs:**
- *Mandated:* every raw source file in `<videos_dir>` (canon directs `ffprobe` "every source").
- *Step-output:* none (this is the first step that touches source files).
- *Free-form / organic:* the user's framing of "what are these clips" if volunteered.

**Outputs:**
- `<videos_dir>/edit/transcripts/<name>.json` per source — cached Scribe word-level JSON. Path canon: `SKILL.md:48` (`├── transcripts/<name>.json  ← cached raw Scribe JSON`).
- `<videos_dir>/edit/takes_packed.md` — phrase-level packed transcript. Path canon: `SKILL.md:47`.
- Optionally one or two filmstrip+waveform PNGs under `<videos_dir>/edit/verify/` (canon does not pin the path; sampling is "for a visual first impression").

**Conventions / hard rules at this step:**
- **Hard Rule 8 — Word-level verbatim ASR only:** `SKILL.md:29`
  > 8. **Word-level verbatim ASR only.** Never SRT/phrase mode (loses sub-second gap data). Never normalized fillers (loses editorial signal).
- **Hard Rule 9 — Cache transcripts per source:** `SKILL.md:30`
  > 9. **Cache transcripts per source.** Never re-transcribe unless the source file itself changed.
- **All session outputs in `<videos_dir>/edit/`** (Hard Rule 12): `SKILL.md:33`
  > 12. **All session outputs in `<videos_dir>/edit/`.** Never write inside the `video-use/` project directory.
- `pack_transcripts.py` "breaks on any silence ≥ 0.5s OR speaker change" — `~/repos/video-use/helpers/pack_transcripts.py:4-5`:
  > Groups word-level entries into phrase-level lines, breaking on any silence >= 0.5s OR speaker change.

**Quality checks canon prescribes at this step:**
- `transcribe.py` caches by file-existence and skips on hit (`~/repos/video-use/helpers/transcribe.py:7`: "Cached: if the output file already exists, the upload is skipped").
- `timeline_view` is sampled, not scanned: `timeline_view.py:9-11`:
  > Use this at decision points — ambiguous pauses, retake disambiguation, cut-point sanity checks. Do NOT call it in a scan loop over every utterance; it's an on-demand drill-down, not a background index.

**Sub-agent boundaries canon prescribes:** None for inventory. (Hard Rule 10 parallelism applies later, at animation slots — `SKILL.md:31`.)

**Transition rule to next step:** Implicit. Once `takes_packed.md` exists, V2 reads it.

**Open questions / canon ambiguities:**
- `transcribe_batch.py` is described as "4-worker parallel transcription. Use for multi-take." (`SKILL.md:75`) — canon does not state behavior for single-clip episodes. (Empirically the orchestrator runs single-source canonical fixture through `transcribe.py`, not the batch; canon silent.)

---

### Step V2 — Pre-scan for problems

**Canon source:** `~/.claude/skills/video-use/SKILL.md:86` (§"The process" item 2).

**Verbatim:**
> 2. **Pre-scan for problems.** One pass over `takes_packed.md` to note verbal slips, obvious mis-speaks, or phrasings to avoid. Plain list, feed into the editor brief.

**Inputs:**
- *Step-output:* `takes_packed.md` from V1.
- *Free-form:* nothing.

**Outputs:** A plain in-context list (no file mandated by canon) consumed by the editor sub-agent in V5.

**Conventions / hard rules:** Output is a "plain list" — the editor brief in V5 takes it via the `Verbal slips to avoid: <list from the pre-scan pass>` slot (`SKILL.md:136`).

**Quality checks:** None. This is reading-only.

**Sub-agents:** None — the *main* agent does the pre-scan.

**Transition rule:** Once the list exists in working memory / conversation context, V3 can begin.

**Open questions:** Canon does not specify whether the pre-scan list must be persisted to disk; empirically it lives in conversation context.

---

### Step V3 — Converse

**Canon source:** `~/.claude/skills/video-use/SKILL.md:87` (§"The process" item 3).

**Verbatim:**
> 3. **Converse.** Describe what you see in plain English. Ask questions *shaped by the material*. Collect: content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs. Do not use a fixed checklist — the right questions are different every time.

**Inputs:**
- *Step-output:* `takes_packed.md` + pre-scan list.
- *Free-form / organic:* the entire user conversation thread.

**Outputs:** A coherent-in-context understanding of: content type, target length/aspect, aesthetic, pacing, must-preserve / must-cut, animation prefs, grade prefs, subtitle needs.

**Conventions:** `SKILL.md:13` (Principle 4):
> 4. **Generalize.** Do not assume what kind of video this is. Look at the material, ask the user, then edit.

And `SKILL.md:322`:
> - **Assuming what kind of video it is.** Look first, ask second, edit last.

The "Do not use a fixed checklist" clause forbids template-driven questioning.

**Quality checks:** None canonical.

**Sub-agents:** None.

**Transition rule:** Implicit. Strategy (V4) is proposed once the questions in `SKILL.md:87` are answered.

**Open questions:** Canon silent on what to do when the user is non-responsive. (Free-form agents observed asking once, then proposing a default strategy and explicitly inviting correction.)

---

### Step V4 — Propose strategy

**Canon source:** `~/.claude/skills/video-use/SKILL.md:88` (§"The process" item 4).

**Verbatim:**
> 4. **Propose strategy.** 4–8 sentences: shape, take choices, cut direction, animation plan, grade direction, subtitle style, length estimate. **Wait for confirmation.**

Reinforced by **Hard Rule 11** (`SKILL.md:32`):
> 11. **Strategy confirmation before execution.** Never touch the cut until the user has approved the plain-English plan.

And Principle 3 (`SKILL.md:12`):
> 3. **Ask → confirm → execute → iterate → persist.** Never touch the cut until the user has confirmed the strategy in plain English.

**Inputs:**
- *Step-output:* V3's collected understanding.

**Outputs:** A 4-8 sentence plan in chat. User explicit confirmation (or revision).

**Conventions:** 4-8 sentences covering exactly those 7 dimensions. Plain English, no JSON.

**Quality checks:** "Wait for confirmation" — Hard Rule 11 is the gate.

**Sub-agents:** None.

**Transition rule:** Explicit gate — user confirmation moves to V5.

**Open questions:** Canon silent on the medium of confirmation (chat reply vs. structured tool). The orchestrator implements a LangGraph `interrupt({"type":"strategy_confirmed"})` (`p3_strategy_confirmed_interrupt` node) — canon-compatible specialization.

---

### Step V5 — Execute

**Canon source:** `~/.claude/skills/video-use/SKILL.md:89` (§"The process" item 5) + the editor sub-agent brief at `SKILL.md:123-160`.

**Verbatim (item 5):**
> 5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Apply grade per-segment. Compose via `render.py`.

**Verbatim (editor sub-agent brief, `SKILL.md:123-160`):**
> When the task is "pick the best take of each beat across many clips," spawn a dedicated sub-agent with a brief shaped like this. The structure is load-bearing; the pitch-shape example is not.
>
> ```
> You are editing a <type> video. Pick the best take of each beat and
> assemble them chronologically by beat, not by source clip order.
>
> INPUTS:
>   - takes_packed.md (time-annotated phrase-level transcripts of all takes)
>   - Product/narrative context: <2 sentences from the user>
>   - Speaker(s): <name, role, delivery style note>
>   - Expected structure: <pick an archetype or invent one>
>   - Verbal slips to avoid: <list from the pre-scan pass>
>   - Target runtime: <seconds>
> …
> RULES:
>   - Start/end times must fall on word boundaries from the transcript.
>   - Pad cut boundaries (working window 30–200ms).
>   - Prefer silences ≥ 400ms as cut targets.
>   - Unavoidable slips are kept if no better take exists. Note them in "reason".
>   - If over budget, revise: drop a beat or trim tails. Report total and self-correct.
>
> OUTPUT (JSON array, no prose):
>   [{"source": "C0103", "start": 2.42, "end": 6.85, "beat": "HOOK",
>     "quote": "...", "reason": "..."}, ...]
> ```

**Inputs:**
- *Mandated:* `takes_packed.md`, the user's confirmed strategy, the pre-scan list.
- *Sub-agent brief:* product/narrative context (2 sentences), speakers, expected structure, slips to avoid, target runtime.
- *Free-form:* `timeline_view` PNGs at ambiguous moments.

**Outputs:**
- `<videos_dir>/edit/edl.json` — `SKILL.md:48` (`├── edl.json                 ← cut decisions`). Schema in `SKILL.md:270-287`.
- `<videos_dir>/edit/animations/slot_<id>/render.mp4` (or `.webm` with alpha) — `SKILL.md:50`, `SKILL.md:210` for HF slots, `SKILL.md:212` for Remotion.
- `<videos_dir>/edit/clips_graded/<segment>` — per-segment extracts with grade + fades (`SKILL.md:51`).
- `<videos_dir>/edit/master.srt` — output-timeline SRT, built by `render.py --build-subtitles` (`SKILL.md:52`, `SKILL.md:78`).
- `<videos_dir>/edit/final.mp4` (this is the Step V8 final output; V5 may produce intermediates).

**Conventions / hard rules at this step:**
- **Hard Rule 1 — Subtitles LAST:** `SKILL.md:22`
  > 1. **Subtitles are applied LAST in the filter chain**, after every overlay. Otherwise overlays hide captions. Silent failure.
- **Hard Rule 2 — Per-segment extract → lossless concat:** `SKILL.md:23`
  > 2. **Per-segment extract → lossless `-c copy` concat**, not single-pass filtergraph. Otherwise you double-encode every segment when overlays are added.
- **Hard Rule 3 — 30ms audio fades at every segment boundary:** `SKILL.md:24`
  > 3. **30ms audio fades at every segment boundary** (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut.
- **Hard Rule 4 — Overlay PTS shift:** `SKILL.md:25`
  > 4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window.
- **Hard Rule 5 — Master SRT output-timeline offsets:** `SKILL.md:26`
  > 5. **Master SRT uses output-timeline offsets**: `output_time = word.start - segment_start + segment_offset`. Otherwise captions misalign after segment concat.
- **Hard Rule 6 — Never cut inside a word:** `SKILL.md:27`
  > 6. **Never cut inside a word.** Snap every cut edge to a word boundary from the Scribe transcript.
- **Hard Rule 7 — Pad every cut edge (30-200ms working window):** `SKILL.md:28`
  > 7. **Pad every cut edge.** Working window: 30–200ms. Scribe timestamps drift 50–100ms — padding absorbs the drift. Tighter for fast-paced, looser for cinematic.
- **Hard Rule 10 — Parallel sub-agents for animations:** `SKILL.md:31`
  > 10. **Parallel sub-agents for multiple animations.** Never sequential. Spawn N at once via the `Agent` tool; total wall time ≈ slowest one.

Animation engine choice: `SKILL.md:200-208` — HyperFrames / Remotion / Manim / PIL+ffmpeg, "Pick the engine per animation slot. Do not default to Remotion just because the animation is web-adjacent."

Grade application: `SKILL.md:176`
> Hard rules: apply **per-segment during extraction** (not post-concat, which re-encodes twice). Never go aggressive without testing skin tones.

**Quality checks canon prescribes at this step:** None during execution itself; the eval gate is V7.

**Sub-agent boundaries canon prescribes:**
1. **Editor sub-agent** (single instance) — for "pick the best take of each beat across many clips" (`SKILL.md:123`). Parent gives the brief verbatim shape; child returns the JSON EDL array; parent integrates into `edl.json`.
2. **Animation sub-agents** (parallel, Hard Rule 10) — one per animation slot. Brief shape at `SKILL.md:249-260`:
   > **Parallel sub-agent brief** — each animation is one sub-agent spawned via the `Agent` tool. Each prompt is self-contained (sub-agents have no parent context). Include:
   >
   > 1. One-sentence goal: *"Build ONE animation: [spec]. Nothing else."*
   > 2. Absolute output path (`<edit>/animations/slot_<id>/render.mp4`)
   > 3. Exact technical spec: resolution, fps, codec, pix_fmt, CRF, duration
   > 4. Style palette as concrete values (RGB tuples, hex, or reference to a design system)
   > 5. Font path with index
   > 6. Frame-by-frame timeline (what happens when, with easing)
   > 7. Anti-list ("no chrome, no extras, no titles unless specified")
   > 8. Code pattern reference (copy helpers inline, don't import across slots)
   > 9. Deliverable checklist (script, render, verify duration via ffprobe, report)
   > 10. **"Do not ask questions. If anything is ambiguous, pick the most obvious interpretation and proceed."**
   >
   > One sub-agent = one file (unique filenames, parallel agents don't overwrite each other).

For HyperFrames animation slots, the brief invokes the *full* HF skill (Phase H below) inside `<edit>/animations/slot_<id>/`, scaffolded via `npx --yes hyperframes init . --example blank --non-interactive --skip-skills` (`SKILL.md:210`).

**Transition rule to next step:** Once `edl.json` + every `animations/slot_<id>/render.mp4` exist, V6 (Preview) runs.

**Open questions / canon ambiguities:**
- `SKILL.md:89` says "Build animations in parallel sub-agents" but the orchestrator's current LangGraph pipeline ships *with no animation engine wired into Phase 3* — animation production is deferred to Phase 4 HyperFrames composition layer. Canon-orchestrator divergence is documented in CLAUDE.md §"Decomposition via brief-references-canon" item 2 (orchestrator uses the canonical opt-out: `overlays: []` in EDL).

---

### Step V6 — Preview

**Canon source:** `~/.claude/skills/video-use/SKILL.md:90` (§"The process" item 6).

**Verbatim:**
> 6. **Preview.** `render.py --preview`.

**Inputs:** `<videos_dir>/edit/edl.json` + all referenced sources & animations.
**Outputs:** `<videos_dir>/edit/preview.mp4` (path canon: `SKILL.md:54`). `render.py --preview` is documented at `SKILL.md:78`: "`--preview` for 720p fast."
**Conventions:** 720p, fast. The Hard Rules 1-5 from V5 apply during render.
**Quality checks:** Pre-eval; the real check is V7.
**Sub-agents:** None.
**Transition rule:** Once preview exists, V7 self-eval runs (canon explicitly forbids showing the user before self-eval passes).
**Open questions:** None.

---

### Step V7 — Self-eval (before showing the user)

**Canon source:** `~/.claude/skills/video-use/SKILL.md:91-99` (§"The process" item 7).

**Verbatim:**
> 7. **Self-eval (before showing the user).** Run `timeline_view` on the **rendered output** (not the sources) at every cut boundary (±1.5s window). Check each image for:
>    - Visual discontinuity / flash / jump at the cut
>    - Waveform spike at the boundary (audio pop that slipped past the 30ms fade)
>    - Subtitle hidden behind an overlay (Rule 1 violation)
>    - Overlay misaligned or showing wrong frames (Rule 4 violation)
>
>    Also sample: first 2s, last 2s, and 2–3 mid-points — check grade consistency, subtitle readability, overall coherence. Run `ffprobe` on the output to verify duration matches the EDL expectation.
>
>    If anything fails: fix → re-render → re-eval. **Cap at 3 self-eval passes** — if issues remain after 3, flag them to the user rather than looping forever. Only present the preview once the self-eval passes.

**Inputs:** `<videos_dir>/edit/preview.mp4`, `<videos_dir>/edit/edl.json` (for cut boundaries and duration expectation).
**Outputs:** Pass/fail verdict in conversation; optionally fix-and-rerender artifacts; PNGs under `<videos_dir>/edit/verify/` (path canon `SKILL.md:53`).
**Conventions:** ±1.5s window per cut boundary; explicit check for Hard Rules 1 and 4 violations; cap at 3 passes.
**Quality checks:** `ffprobe` on output for duration vs EDL expectation; visual inspection of `timeline_view` PNGs at every cut + first/last 2s + 2-3 mid-points.
**Sub-agents:** None — main agent walks the boundary list.
**Transition rule:** Pass → V8 iterate+persist. After 3 failed passes, flag remaining issues to the user (do not loop forever).
**Open questions:** Canon silent on whether the 3-pass cap counts across sessions or only per-preview.

---

### Step V8 — Iterate + persist

**Canon source:** `~/.claude/skills/video-use/SKILL.md:100` (§"The process" item 8).

**Verbatim:**
> 8. **Iterate + persist.** Natural-language feedback, re-plan, re-render. Never re-transcribe. Final render on confirmation. Append to `project.md`.

`project.md` schema: `SKILL.md:291-302`
> Append one section per session at `<edit>/project.md`:
>
> ```markdown
> ## Session N — YYYY-MM-DD
>
> **Strategy:** one paragraph describing the approach
> **Decisions:** take choices, cuts, grades, animations + why
> **Reasoning log:** one-line rationale for non-obvious decisions
> **Outstanding:** deferred items
> ```
>
> On startup, read `project.md` if it exists and summarize the last session in one sentence before asking whether to continue.

**Inputs:** User feedback; current preview; current `edl.json`.
**Outputs:**
- `<videos_dir>/edit/final.mp4` — final render (path canon `SKILL.md:55`).
- Appended `<videos_dir>/edit/project.md` (path canon `SKILL.md:46`; schema canon `SKILL.md:291-302`).
**Conventions:** "Never re-transcribe" — Hard Rule 9 (`SKILL.md:30`).
**Quality checks:** Implicit re-eval if any change → re-V7.
**Sub-agents:** None mandated.
**Transition rule:** Once the user confirms, the final render is produced and the session ends (or hands off to HyperFrames per Step H).
**Open questions:** Canon silent on what triggers "Final render on confirmation" — empirically, user message of approval triggers it.

---

## Step H — Orchestrator handoff (video-use final.mp4 + transcripts → HyperFrames inputs)

**Canon source:** This step is **orchestrator-house — canon does not define a video-use ⇄ hyperframes chaining contract.** video-use SKILL.md mentions HyperFrames only as one of four animation-engine choices for *internal animation slots* under `<edit>/animations/slot_<id>/` (`SKILL.md:201`, `SKILL.md:210`), not as a post-V8 stage operating on the *whole* `final.mp4`.

The orchestrator's `/edit-episode` slash command and the LangGraph pipeline both treat HyperFrames as a Phase 4 layer operating on V8's outputs (CLAUDE.md §"Layout convention" — the `episodes/<slug>/hyperframes/` folder is a sibling of `edit/`). This is a deliberate orchestrator-house specialization.

**Inputs (orchestrator-house):**
- `episodes/<slug>/edit/final.mp4` (from V8).
- `episodes/<slug>/edit/transcripts/raw.json` (the Scribe word-level JSON cached at V1).
- The user's framing of the desired composition.

**Outputs:** A scaffolded `episodes/<slug>/hyperframes/` directory ready for HF Step H1 (Design system).

**Conventions / hard rules at this step:**
- Layout per CLAUDE.md §"Layout convention".
- HyperFrames consumes the transcript via its `transcribe` CLI / direct `transcript.json` placement (per `~/.agents/skills/hyperframes/references/transcript-guide.md:6-15` — supported input formats include "whisper.cpp JSON", "OpenAI Whisper API", "SRT subtitles", "VTT subtitles", "Normalized word array").

**Quality checks:** None mandated by canon (the step doesn't exist in canon).
**Sub-agents:** None.
**Transition rule:** Once `episodes/<slug>/hyperframes/` is scaffolded and the transcript is in place at a path HyperFrames recognizes, H1 begins.

**Open questions / canon ambiguities:**
- Canon does not address "video-use produced a final.mp4; now run HyperFrames on the *whole* video as one composition." This is a pure orchestrator decision and the contract is owned by `~/repos/anticodeguy-video-editing-studio/.claude/commands/edit-episode.md`.
- The Scribe JSON format (used by video-use `transcribe.py`) and the formats HyperFrames recognizes (whisper.cpp / OpenAI Whisper API / SRT / VTT / normalized word array — `transcript-guide.md:7-15`) **are not the same shape**. Canon-silent at the handoff; the orchestrator's `glue_remap_transcript` node bridges them (Appendix B).

---

## Phase H — hyperframes (composition prompt → rendered video)

HyperFrames SKILL.md §"Approach" enumerates three sequential steps (Step 1 / Step 2 / Step 3) followed by ongoing rules and quality checks. The numbering below preserves the canon labels.

### Step H1 — Design system

**Canon source:** `~/.agents/skills/hyperframes/SKILL.md:25-37` (§"Step 1: Design system") + the full options at `references/design-picker.md`, `house-style.md`, `visual-styles.md`.

**Verbatim:**
> ### Step 1: Design system
>
> If `design.md` or `DESIGN.md` exists in the project, read it first (check both casings — they're different files on Linux). It's the source of truth for brand colors, fonts, and constraints. Use its exact values — don't invent colors or substitute fonts. Any format works (YAML frontmatter, prose, tables — just extract the values).
>
> If it names fonts you can't find locally (no `fonts/` directory with `.woff2` files, not a built-in font), warn the user before writing HTML: "design.md specifies [font name] but no font files found. Please add .woff2 files to `fonts/` or I'll fall back to [closest built-in alternative]."
>
> If no `design.md` exists, offer the user a choice:
>
> 1. **User named a style or mood?** → Read [visual-styles.md](./visual-styles.md) for the 8 named presets. Pick the closest match.
> 2. **Want to browse options visually?** → Run the design picker: read [references/design-picker.md](references/design-picker.md) for the full workflow. This serves a visual picker page. The user configures mood, palette, typography, and motion in the browser, then copies the generated design.md and pastes it back into the conversation.
> 3. **Want to skip and go fast?** → Ask: mood, light or dark, any brand colors/fonts? Then pick a palette from [house-style.md](./house-style.md).
>
> **design.md defines the brand. It does not define video composition rules.** Those come from [references/video-composition.md](references/video-composition.md) and [house-style.md](./house-style.md). Use brand colors at video-appropriate scale — not at web-UI opacity.

**Inputs:**
- *Mandated:* an existing `design.md` / `DESIGN.md` if present; the user's stated mood / preferences if not.
- *Free-form / organic:* the user conversation thread (mood, brand context).

**Outputs:** `design.md` or `DESIGN.md` in the project root (orchestrator-house: `episodes/<slug>/hyperframes/DESIGN.md`).

**Conventions / hard rules at this step:**
- Use design.md's exact values (no invention).
- Warn before fallback fonts.
- The `<HARD-GATE>` (`SKILL.md:60-62`):
  > <HARD-GATE>
  > Before writing ANY composition HTML — verify you have a visual identity from Step 1. If you're reaching for `#333`, `#3b82f6`, or `Roboto`, you skipped it.
  > </HARD-GATE>
- House-style "Lazy Defaults to Question" (`house-style.md:13-21`): gradient text, left-edge accent stripes, cyan-on-dark / purple-to-blue gradients / neon accents, pure `#000` or `#fff`, identical card grids, centered-with-equal-weight, banned fonts.
- Typography banned-fonts list (`references/typography.md:8-12`):
  > Inter, Roboto, Open Sans, Noto Sans, Arimo, Lato, Source Sans, PT Sans, Nunito, Poppins, Outfit, Sora, Playfair Display, Cormorant Garamond, Bodoni Moda, EB Garamond, Cinzel, Prata, Syne
  >
  > **Syne in particular** is the most overused "distinctive" display font. It is an instant AI design tell.

**Quality checks canon prescribes at this step:**
- Font existence check (`SKILL.md:29`): "If it names fonts you can't find locally (no `fonts/` directory with `.woff2` files, not a built-in font), warn the user before writing HTML".
- Picker UX optionally runs the design-picker (`references/design-picker.md:1-3`): "Two-phase visual picker: mood boards first (pick a complete direction), then fine-tune individual categories."

**Sub-agent boundaries canon prescribes:** None canonically for Step 1, but the design-picker workflow (`references/design-picker.md:25`) mandates "RUN the font discovery script from typography.md BEFORE generating pairings. This is not optional." — a deterministic helper, not a sub-agent.

**Transition rule to next step:** `design.md` exists (or has been confirmed equivalent by the user) → Step H2 begins.

**Open questions / canon ambiguities:**
- The `<HARD-GATE>` (`SKILL.md:60-62`) gates "ANY composition HTML" against design.md existence — but `prompt-expansion.md:5-7` says the expansion (Step 2) "Runs AFTER design direction is established (Step 1). The expansion consumes design.md (if present) and produces output that cites its exact values." Both consistent.

---

### Step H2 — Prompt expansion

**Canon source:** `~/.agents/skills/hyperframes/SKILL.md:39-43` (§"Step 2: Prompt expansion") + full procedure at `~/.agents/skills/hyperframes/references/prompt-expansion.md`.

**Verbatim (SKILL.md):**
> ### Step 2: Prompt expansion
>
> Always run on every composition (except single-scene pieces and trivial edits). This step grounds the user's intent against `design.md` and `house-style.md` and produces a consistent intermediate that every downstream agent reads the same way.
>
> Read [references/prompt-expansion.md](references/prompt-expansion.md) for the full process and output format.

**Verbatim (prompt-expansion.md:35):**
> **Do not skip. Do not pass through.** Single-scene compositions and trivial edits are the only exceptions.

**Verbatim (prompt-expansion.md:60-68):**
> ## Output
>
> Write the expanded prompt to `.hyperframes/expanded-prompt.md` in the project directory. Do NOT dump it into the chat — it will be hundreds of lines.
>
> Tell the user:
>
> > "I've expanded your prompt into a full production breakdown. Review it here: `.hyperframes/expanded-prompt.md`
> >
> > It has [N] scenes across [duration] seconds with specific visual elements, transitions, and pacing. Edit anything you want, then let me know when you're ready to proceed."
>
> Only move to construction after the user approves or says to continue.

**Inputs:**
- *Mandated reads* (`prompt-expansion.md:9-15`): `design.md` (extract brand colors, fonts, mood); `references/beat-direction.md`; `references/video-composition.md`; `house-style.md`.
- *User-supplied:* the seed prompt.

**Outputs:** `.hyperframes/expanded-prompt.md` (canonical filename, canonical path — `prompt-expansion.md:60`).

**Conventions / hard rules at this step:**
- 6-section output spec (`prompt-expansion.md:38-56`):
  > 1. **Title + style block** — cite design.md's exact hex values, font names, and mood. Do NOT invent a palette — quote what the design provides.
  > 2. **Rhythm declaration** — name the scene rhythm before detailing any scene. Example: `hook-PUNCH-breathe-CTA` or `slow-build-BUILD-PEAK-breathe-CTA`. See [beat-direction.md](beat-direction.md) for rhythm templates by video type.
  > 3. **Global rules** — parallax layers, micro-motion requirements, transition style, primary + accent transitions. Match energy to mood (calm → slow eases, high → snappy eases).
  > 4. **Per-scene beats** — for each scene, use the beat-direction format:
  >    - **Concept** — the big idea in 2-3 sentences. What visual WORLD? What metaphor? What should the viewer FEEL?
  >    - **Mood direction** — cultural/design references, not hex codes. ("Bauhaus color studies", "cinematic title sequence", "editorial calm")
  >    - **Depth layers** — BG (2-5 decoratives with ambient motion), MG (content), FG (accents, structural elements, micro-details). 8-10 total elements per scene per video-composition.md.
  >    - **Animation choreography** — specific verbs per element. High: SLAMS, CRASHES. Medium: CASCADE, SLIDES. Low: floats, types on, counts up. Every element gets a verb. If you can't name the verb, the element is not yet designed.
  >    - **Transition out** — shader or CSS, with specific type and parameters. Not "crossfade" but "blur crossfade, 0.4s, power2.inOut."
  > 5. **Recurring motifs** — visual threads across scenes from the brand palette.
  > 6. **Negative prompt** — what to avoid, informed by design.md's constraints if present.

- "**The expansion is never pass-through.**" — `prompt-expansion.md:21`. Even detailed prompts get atmosphere layers, secondary motion, micro-details, transition choreography, pacing beats, exact hex values added.

**Quality checks canon prescribes at this step:** Human review of `.hyperframes/expanded-prompt.md` — "Only move to construction after the user approves or says to continue." (`prompt-expansion.md:68`).

**Sub-agent boundaries canon prescribes:** None at H2 itself. The expansion's per-scene output is the *brief* downstream scene sub-agents will read in H4-Construct.

**Transition rule to next step:** User approval of `.hyperframes/expanded-prompt.md` → Step H3 (Plan).

**Open questions / canon ambiguities:**
- The "Always run on every composition (except single-scene pieces and trivial edits)" clause leaves "single-scene" undefined. Empirically the orchestrator runs prompt-expansion on the canonical fixture (single talking-head scene with caption overlay) — orchestrator-house decision that the expansion's atmosphere/motion adds value even on visually-simple compositions.

---

### Step H3 — Plan

**Canon source:** `~/.agents/skills/hyperframes/SKILL.md:45-62` (§"Step 3: Plan").

**Verbatim:**
> ### Step 3: Plan
>
> Before writing HTML, think at a high level:
>
> 1. **What** — what should the viewer experience? Identify the narrative arc, key moments, and emotional beats.
> 2. **Structure** — how many compositions, which are sub-compositions vs inline, what tracks carry what (video, audio, overlays, captions).
> 3. **Rhythm** — declare your scene rhythm before implementing. Which scenes are quick hits, which are holds, where do shaders land, where does energy peak. Name the pattern: fast-fast-SLOW-fast-SHADER-hold. Read [references/beat-direction.md](references/beat-direction.md) for rhythm templates.
> 4. **Timing** — which clips drive the duration, where do transitions land, what's the pacing.
> 5. **Layout** — build the end-state first. See "Layout Before Animation" below.
> 6. **Animate** — then add motion using the rules below.
>
> **Build what was asked.** A request for "a title card" is not a request for "a title card + 3 supporting scenes + ambient music + captions." Every scene, every element, every tween should earn its place. If additional scenes or elements would genuinely improve the piece, propose them — don't add them.
>
> For small edits (fix a color, adjust timing, add one element), skip straight to the rules.
>
> <HARD-GATE>
> Before writing ANY composition HTML — verify you have a visual identity from Step 1. If you're reaching for `#333`, `#3b82f6`, or `Roboto`, you skipped it.
> </HARD-GATE>

**Inputs:**
- *Mandated:* `.hyperframes/expanded-prompt.md` (from H2), `design.md`, `references/beat-direction.md`, `references/video-composition.md`, `references/motion-principles.md`, `references/typography.md` (the "Always read" references at `SKILL.md:472-475`).
- *Free-form:* user clarifications.

**Outputs:** A planning intent (in-context); no canonical file written at H3. (Some agents write a `PLAN.md` — canon silent on filename / persistence.)

**Conventions / hard rules at this step:**
- The 6 sub-steps (what / structure / rhythm / timing / layout / animate) in order.
- "Build what was asked" — anti-scope-creep.
- `<HARD-GATE>` cited again — gate re-fires before any HTML write.

**Quality checks canon prescribes at this step:** None mechanical at H3; the planning is human-readable reasoning.

**Sub-agent boundaries canon prescribes:**
- *Implicit fan-out:* `references/prompt-expansion.md` references "scene subagents" without explicit dispatching contract (e.g. `prompt-expansion.md:31`: "Expansion front-loads the richness so every scene subagent builds from a rich brief"). The fan-out happens at Step H4 (Construct) — H3 sets up the structure-spec the fan-out consumes.

**Transition rule to next step:** Once the plan and structure (number of scenes, sub-comp vs inline, transition placement) are clear → H4 Construct begins. The `<HARD-GATE>` blocks H4 if Step H1 visual identity is missing.

**Open questions / canon ambiguities:** None observed at H3 itself.

---

### Step H4 — Construct (Layout-Before-Animation + scene fan-out)

**Canon source:** `~/.agents/skills/hyperframes/SKILL.md:64-133` (§"Layout Before Animation"), plus `SKILL.md:134-359` for the rules library (Data Attributes, Composition Structure, Variables, Video and Audio, Timeline Contract, Rules Non-Negotiable, Scene Transitions Non-Negotiable, Animation Guardrails, Typography and Assets), plus `references/motion-principles.md` and `references/beat-direction.md`.

**Verbatim (Layout-Before-Animation §"The process", `SKILL.md:70-75`):**
> ### The process
>
> 1. **Identify the hero frame** for each scene — the moment when the most elements are simultaneously visible. This is the layout you build.
> 2. **Write static CSS** for that frame. The `.scene-content` container MUST fill the full scene using `width: 100%; height: 100%; padding: Npx;` with `display: flex; flex-direction: column; gap: Npx; box-sizing: border-box`. Use padding to push content inward — NEVER `position: absolute; top: Npx` on a content container. Absolute-positioned content containers overflow when content is taller than the remaining space. Reserve `position: absolute` for decoratives only.
> 3. **Add entrances with `gsap.from()`** — animate FROM offscreen/invisible TO the CSS position. The CSS position is the ground truth; the tween describes the journey to get there. (In sub-compositions loaded via `data-composition-src`, prefer `gsap.fromTo()` — see load-bearing GSAP rules in [references/motion-principles.md](references/motion-principles.md).)
> 4. **Add exits with `gsap.to()`** — animate TO offscreen/invisible FROM the CSS position.

**Inputs:**
- *Mandated:* `.hyperframes/expanded-prompt.md` (per-scene briefs from H2); `design.md`; all "Always read" references (`SKILL.md:472-486`): `video-composition.md`, `beat-direction.md`, `typography.md`, `motion-principles.md`, `transitions.md` (for multi-scene compositions).
- *Inputs the agent organically reads:* `house-style.md` when no design.md exists; transcripts under `transcript.json` if captions are part of the composition (`references/transcript-guide.md:99-107`).
- *Step-output:* design.md (H1), expanded-prompt.md (H2), plan (H3).

**Outputs:**
- `index.html` (root composition) at project root. Canon structure rule (`SKILL.md:166-168`):
  > **Standalone compositions (the main index.html) do NOT use `<template>`** — they put the `data-composition-id` div directly in `<body>`. Using `<template>` on a standalone file hides all content from the browser and breaks rendering.
- `compositions/*.html` (sub-compositions) loaded via `data-composition-src`. Canon structure rule (`SKILL.md:170-189`):
  > Sub-compositions loaded via `data-composition-src` use a `<template>` wrapper.
- Optional `captions.html` sub-comp (per `references/captions.md`).
- Optional fonts under `fonts/<name>.woff2` (per `SKILL.md:364`).

**Conventions / hard rules at this step (the bulk of canon lives here):**

**Layout:**
- Hero-frame-first (above).
- `.scene-content` flex pattern; never `position: absolute` for content containers.

**Data Attributes (`SKILL.md:134-165`):** required `id`, `data-start`, `data-duration` (required for img/div/compositions; video/audio defaults to media duration), `data-track-index`; optional `data-media-start`, `data-volume`. `data-track-index` does not affect visual layering — CSS `z-index` does.

**Composition Structure (`SKILL.md:166-192`):** template-wrapped sub-comps, direct-body root comps. Quote at `SKILL.md:168`: "Using `<template>` on a standalone file hides all content from the browser and breaks rendering."

**Video and Audio (`SKILL.md:263-285`):** "Video must be `muted playsinline`. Audio is always a separate `<audio>` element".

**Timeline Contract (`SKILL.md:287-294`):**
> - All timelines start `{ paused: true }` — the player controls playback
> - Register every timeline: `window.__timelines["<composition-id>"] = tl`
> - Framework auto-nests sub-timelines — do NOT manually add them
> - Duration comes from `data-duration`, not from GSAP timeline length
> - Never create empty tweens to set duration

**Rules (Non-Negotiable, 11 items at `SKILL.md:295-319`):** quoted in full as Appendix A items HF-R1..HF-R11.

**Scene Transitions (Non-Negotiable, 4 items at `SKILL.md:321-348`):** quoted in full as Appendix A items HF-T1..HF-T4. Key rule (`SKILL.md:325-328`):
> 1. **ALWAYS use transitions between scenes.** No jump cuts. No exceptions.
> 2. **ALWAYS use entrance animations on every scene.** Every element animates IN via `gsap.from()`. No element may appear fully-formed. If a scene has 5 elements, it needs 5 entrance tweens.
> 3. **NEVER use exit animations** except on the final scene. This means: NO `gsap.to()` that animates opacity to 0, y offscreen, scale to 0, or any other "out" animation before a transition fires. The transition IS the exit. The outgoing scene's content MUST be fully visible at the moment the transition starts.
> 4. **Final scene only:** The last scene may fade elements out (e.g., fade to black). This is the ONLY scene where `gsap.to(..., { opacity: 0 })` is allowed.

**Animation Guardrails (`SKILL.md:350-359`):**
> - Offset first animation 0.1-0.3s (not t=0)
> - Vary eases across entrance tweens — use at least 3 different eases per scene
> - Don't repeat an entrance pattern within a scene
> - Avoid full-screen linear gradients on dark backgrounds (H.264 banding — use radial or solid + localized glow)
> - 60px+ headlines, 20px+ body, 16px+ data labels for rendered video
> - `font-variant-numeric: tabular-nums` on number columns

**Variables (`SKILL.md:194-261`):** three-step pattern (declare via `data-composition-variables`, read via `window.__hyperframes.getVariables()`, override via `--variables` / `data-variable-values`).

**Captions specifics (`references/captions.md`):**
- `.en` language rule non-negotiable (`captions.md:5-9`).
- Caption Exit Guarantee — hard `tl.set` kill at `group.end` (`captions.md:96-118`).
- Per-word styling, positioning, overflow prevention via `window.__hyperframes.fitTextFontSize()`.

**Transitions specifics (`references/transitions.md`):**
- 4 non-negotiable animation rules (mirrored from SKILL.md HF-T1..HF-T4 above, `transitions.md:5-12`).
- Energy → Primary Transition table (`transitions.md:14-22`).
- Mood → Transition Type table (`transitions.md:24-38`).
- Narrative Position table (`transitions.md:40-49`).
- Blur Intensity by Energy (`transitions.md:51-57`).
- Shader-Compatible CSS Rules (6 items, `transitions.md:97-107`).
- Visual Pattern Warning (`transitions.md:109-112`).

**Video-composition rules (always-read, `references/video-composition.md`):**
- Density 8-10 elements per scene (`video-composition.md:13-23`).
- Color presence: "Brand accent should be VISIBLE — not a 5% opacity glow lost in compression. 15-25% for atmospheric, full saturation for focal elements." (`video-composition.md:28`).
- Scale table (web→video, `video-composition.md:35-44`).
- "Two focal points minimum" (`video-composition.md:58`).

**Motion-principles guardrails (always-read, `references/motion-principles.md:5-12`):** vary eases (no more than 2 same-ease tweens per scene); vary speeds (slowest 3× slower than fastest); vary entry directions; vary stagger per scene; vary ambient motion per scene; offset first animation 0.1-0.3s. Plus load-bearing GSAP rules (`motion-principles.md:81-142`): no iframes for captured content; never stack two transform tweens on the same element; prefer `tl.fromTo()` over `tl.from()` inside `.clip` scenes; ambient pulses must attach to seekable `tl`; hard-kill every scene boundary.

**Typography guardrails (always-read, `references/typography.md:6-21`):** banned fonts list; don't pair two sans-serifs; one expressive font per scene; weight contrast extreme (300 vs 900); video sizes not web sizes.

**Quality checks canon prescribes at this step:** None at construction itself; the gates are H5 (Output Checklist) and the four explicit Quality Checks Q1-Q4 below.

**Sub-agent boundaries canon prescribes:**
- *Implicit per-scene fan-out:* `prompt-expansion.md` and `beat-direction.md` together produce per-scene briefs that scene sub-agents read. Canon does not pin a dispatching contract (e.g. "spawn one Agent per scene") the way video-use Hard Rule 10 does for animations — empirically the free-form agent in transcripts sometimes writes scenes serially in one main-agent turn, sometimes fans out via Task tool.
- *Explicit:* `transcript-guide.md:99-107` mandates a "Transcript Quality Check (Mandatory)" before caption authoring (a procedural step, not a sub-agent).

**Transition rule to next step:** Construction complete (every scene authored, all rules satisfied) → run H5 Output Checklist + Q1..Q4 quality checks before serving to user.

**Open questions / canon ambiguities:**
- Scene fan-out: canon describes "scene subagents" (`prompt-expansion.md:31`) without an explicit "spawn one Agent per scene" rule like video-use Hard Rule 10. Whether to fan out vs. serialize is left to the free-form agent's judgment — orchestrator decomposes this into `p4_dispatch_beats` (LangGraph `Send` API) per CLAUDE.md §"LangGraph primitives".
- `<template>` rule for sub-comps (`SKILL.md:168`) has been a recurring source of orchestrator-side bugs (see memory `feedback_hf_subcomp_loader_data_composition_src` — HF 0.4.41+0.4.44 produce black renders even when canon is followed). Canon and behavior diverge on Windows + recent HF versions; canon-side workaround is to author beats inline rather than as sub-comps until upstream #589 lands.

---

### Step H5 — Output Checklist + Q-Gates

**Canon source:** `~/.agents/skills/hyperframes/SKILL.md:376-463` (§"Output Checklist" and §"Quality Checks") + per-check references.

**Verbatim (Output Checklist, `SKILL.md:376-387`):**
> ## Output Checklist
>
> **Fast (run immediately, block on results):**
>
> - [ ] `npx hyperframes lint` and `npx hyperframes validate` both pass
> - [ ] Design adherence verified if design.md exists
>
> **Slow (run in parallel while presenting the preview to the user):**
>
> - [ ] `npx hyperframes inspect` passes, or every reported overflow is intentionally marked
> - [ ] Contrast warnings addressed (see Quality Checks below)
> - [ ] Animation choreography verified (see Quality Checks below)

The Quality Checks subsection then defines Q1..Q4:

#### Q1 — Visual Inspect

**Canon (`SKILL.md:391-404`):**
> ### Visual Inspect
>
> `hyperframes inspect` runs the composition in headless Chrome, seeks through the timeline, and maps visual layout issues with timestamps, selectors, bounding boxes, and fix hints. Run it after `lint` and `validate`:
>
> ```bash
> npx hyperframes inspect
> npx hyperframes inspect --json
> ```
>
> Failures usually mean text is spilling out of a bubble/card, a fixed-size label is clipping dynamic copy, or text has moved off the canvas. Fix by increasing container size or padding, reducing font size or letter spacing, adding a real `max-width` so text wraps inside the container, or using `window.__hyperframes.fitTextFontSize(...)` for dynamic copy.
>
> Use `--samples 15` for dense videos and `--at 1.5,4,7.25` for specific hero frames. Repeated static issues are collapsed by default to avoid flooding agent context. If overflow is intentional for an entrance/exit animation, mark the element or ancestor with `data-layout-allow-overflow`. If a decorative element should never be audited, mark it with `data-layout-ignore`.

#### Q2 — Contrast

**Canon (`SKILL.md:406-422`):**
> ### Contrast
>
> `hyperframes validate` runs a WCAG contrast audit by default. It seeks to 5 timestamps, screenshots the page, samples background pixels behind every text element, and computes contrast ratios. Failures appear as warnings:
> …
> If warnings appear:
>
> - On dark backgrounds: brighten the failing color until it clears 4.5:1 (normal text) or 3:1 (large text, 24px+ or 19px+ bold)
> - On light backgrounds: darken it
> - Stay within the palette family — don't invent a new color, adjust the existing one
> - Re-run `hyperframes validate` until clean
>
> Use `--no-contrast` to skip if iterating rapidly and you'll check later.

#### Q3 — Design Adherence

**Canon (`SKILL.md:424-441`):**
> ### Design Adherence
>
> If a `design.md` exists, verify the composition follows it after authoring. Read the HTML and check:
>
> 1. **Colors** — every hex value in the composition appears in design.md's palette section (however the user labeled it: Colors, Palette, Theme, etc.). Flag any invented colors.
> 2. **Typography** — font families and weights match design.md's type spec. No substitutions.
> 3. **Corners** — border-radius values match the declared corner style, if specified.
> 4. **Spacing** — padding and gap values fall within the declared density range, if specified.
> 5. **Depth** — shadow usage matches the declared depth level, if specified (flat = none, subtle = light, layered = glows).
> 6. **Avoidance rules** — if design.md has a section listing things to avoid (commonly "What NOT to Do", "Don'ts", "Anti-patterns", or "Do's and Don'ts"), verify none are present.
>
> Report violations as a checklist. Fix each one before serving.

For no-design.md path (`SKILL.md:437-441`):
> If no `design.md` exists (house-style-only path), verify:
>
> 1. **Palette consistency** — the same bg, fg, and accent colors are used across all scenes. No per-scene color invention.
> 2. **No lazy defaults** — check the composition against house-style.md's "Lazy Defaults to Question" list. If any appear, they must be a deliberate choice for the content, not a default.

#### Q4 — Animation Map

**Canon (`SKILL.md:443-463`):**
> ### Animation Map
>
> After authoring animations, run the animation map to verify choreography:
>
> ```bash
> node skills/hyperframes/scripts/animation-map.mjs <composition-dir> \
>   --out <composition-dir>/.hyperframes/anim-map
> ```
>
> Outputs a single `animation-map.json` with:
>
> - **Per-tween summaries**: `"#card1 animates opacity+y over 0.50s. moves 23px up. fades in. ends at (120, 200)"`
> - **ASCII timeline**: Gantt chart of all tweens across the composition duration
> - **Stagger detection**: reports actual intervals (`"3 elements stagger at 120ms"`)
> - **Dead zones**: periods over 1s with no animation — intentional hold or missing entrance?
> - **Element lifecycles**: first/last animation time, final visibility
> - **Scene snapshots**: visible element state at 5 key timestamps
> - **Flags**: `offscreen`, `collision`, `invisible`, `paced-fast` (under 0.2s), `paced-slow` (over 2s)
>
> Read the JSON. Scan summaries for anything unexpected. Check every flag — fix or justify. Verify the timeline shows the intended choreography rhythm. Re-run after fixes.
>
> Skip on small edits (fixing a color, adjusting one duration). Run on new compositions and significant animation changes.

**Inputs:** the authored composition under `<project>/`; `design.md` (for Q3); `<project>/.hyperframes/anim-map/animation-map.json` (Q4 output).

**Outputs:** Pass/fail verdicts, lint/validate/inspect JSON when `--json` is used, `animation-map.json`, contrast warnings list, design-adherence checklist.

**Conventions / hard rules at this step:**
- Fast checks block on results; slow checks may run in parallel with preview presentation (`SKILL.md:378-387`).
- "Check every flag — fix or justify" — Q4 flags are advisory-with-justification, not blocking on their own (the canon-aware free-form agent triages them).
- Q3 path forks on `design.md` existence.

**Quality checks:** This *is* the quality-check stack.

**Sub-agent boundaries canon prescribes:** None — all four are deterministic tooling runs the main agent invokes and interprets.

**Transition rule to next step:** All fast checks pass → preview can be presented to user; slow checks complete cleanly or with documented justifications → render (H6).

**Open questions / canon ambiguities:**
- Canon says "Check every flag — fix or justify" for Q4 (`SKILL.md:461`) — *justify* is unqualified. Orchestrator-house gates have historically promoted some Q4 flags to *blocking* (collision/invisible/offscreen) which is canon-divergent — see memory `feedback_gate_carveouts_must_match_canon` and HOM-316/HOM-317 retros. The canon position is: every flag is advisory unless the agent's own triage upgrades it.
- `animation-map.mjs` invocation path: canon at `SKILL.md:447` cites `skills/hyperframes/scripts/animation-map.mjs` — on Windows the runnable copy is the bundled `node_modules/hyperframes/dist/skills/hyperframes/scripts/animation-map.mjs` per CLAUDE.md §"Skill copies: docs vs. runnable". Canon-silent on the Windows divergence.

---

### Step H6 — Render

**Canon source:** Bundled `dist/skills/hyperframes-cli/SKILL.md` (CLI sub-skill) + `~/.agents/skills/hyperframes/SKILL.md:230-237` for variable-driven renders + the per-project `CLAUDE.md` scaffolded by `hyperframes init` (`tests/fixtures/episodes/canonical-portrait-talking-head/hyperframes/CLAUDE.md` system-reminder above shows the canonical commands: `npm run dev`, `npm run check`, `npm run render`).

**Verbatim (per-project CLAUDE.md from the canonical fixture scaffold, system-reminder above):**
> ```bash
> npm run dev          # start the preview server (long-running — keep it alive in background)
> npm run check        # lint + validate + inspect
> npm run render       # render to MP4
> npm run publish      # publish and get a shareable link
> ```

And the post-edit invocation contract:
> ## Linting — ALWAYS RUN AFTER CHANGES
>
> After creating or editing any `.html` composition, **always** run the full check before considering the task complete:
>
> ```bash
> npm run check
> ```
>
> Fix all errors before presenting the result. Inspect warnings should be reviewed before rendering.

**Inputs:** `index.html` + `compositions/` + media + fonts + (optional) `--variables` override JSON.
**Outputs:** rendered MP4 (path is up to the user / `--output`).
**Conventions:** `npm run check` (= `lint + validate + inspect`) must pass first. `npm run dev` is long-running.
**Quality checks:** `npm run check` blocks rendering. Per-project CLAUDE.md item 6: "Only deterministic logic — no `Date.now()`, no `Math.random()`, no network fetches" — mirrors SKILL.md HF-Determinism rule (`SKILL.md:297`).
**Sub-agents:** None.
**Transition rule:** Render success → final video delivered to user.
**Open questions:** None observed at H6.

---

## Cross-cutting canon — applies at every step

### Determinism (HyperFrames)

`SKILL.md:297`:
> **Deterministic:** No `Math.random()`, `Date.now()`, or time-based logic. Use a seeded PRNG if you need pseudo-random values (e.g. mulberry32).

### Read-actual-files when editing (HyperFrames)

`SKILL.md:369-374`:
> ## Editing Existing Compositions
>
> - **Read actual files, don't guess.** When editing, extending, or creating companion compositions, read the existing source. Don't reconstruct hex codes from memory. Don't guess GSAP easing patterns. The composition IS the spec — extract exact values from it.
> - Match existing fonts, colors, animation patterns from what you read
> - Only change what was requested
> - Preserve timing of unrelated clips

### Artistic freedom is the default (video-use)

`SKILL.md:14`:
> 5. **Artistic freedom is the default.** Every specific value, preset, font, color, duration, pitch structure, and technique in this document is a *worked example* from one proven video — not a mandate. Read them to understand what's possible and why each worked. Then make your own taste calls based on what the material actually is and what the user actually wants. **The only things you MUST do are in the Hard Rules section below.** Everything else is yours.

### Verify your own output (video-use)

`SKILL.md:16`:
> 7. **Verify your own output before showing it to the user.** If you wouldn't ship it, don't present it.

---

## Appendix A — Convention index

Flat list of every named Hard Rule and explicit convention across both canons, cross-referenced to source. Use Ctrl-F.

### video-use Hard Rules (12, all from `SKILL.md:22-33`)

- **VU-HR1** Subtitles applied LAST in filter chain — `SKILL.md:22`. Owns Step V5/V6/V7.
- **VU-HR2** Per-segment extract → lossless `-c copy` concat — `SKILL.md:23`. Owns Step V5.
- **VU-HR3** 30ms audio fades at every segment boundary — `SKILL.md:24`. Owns Step V5.
- **VU-HR4** Overlays use `setpts=PTS-STARTPTS+T/TB` — `SKILL.md:25`. Owns Step V5.
- **VU-HR5** Master SRT uses output-timeline offsets — `SKILL.md:26`. Owns Step V5.
- **VU-HR6** Never cut inside a word — `SKILL.md:27`. Owns Step V5 (editor sub-agent).
- **VU-HR7** Pad every cut edge (30-200ms working window) — `SKILL.md:28`. Owns Step V5.
- **VU-HR8** Word-level verbatim ASR only — `SKILL.md:29`. Owns Step V1.
- **VU-HR9** Cache transcripts per source — `SKILL.md:30`. Owns Step V1 / V8.
- **VU-HR10** Parallel sub-agents for multiple animations — `SKILL.md:31`. Owns Step V5 (animation slots).
- **VU-HR11** Strategy confirmation before execution — `SKILL.md:32`. Owns Step V4→V5 gate.
- **VU-HR12** All session outputs in `<videos_dir>/edit/` — `SKILL.md:33`. Owns every step.

### video-use Principles (7, from `SKILL.md:8-16`)

- **VU-P1** LLM reasons from raw transcript + on-demand visuals — `SKILL.md:10`.
- **VU-P2** Audio is primary, visuals follow — `SKILL.md:11`.
- **VU-P3** Ask → confirm → execute → iterate → persist — `SKILL.md:12`.
- **VU-P4** Generalize. Do not assume what kind of video this is — `SKILL.md:13`.
- **VU-P5** Artistic freedom is the default — `SKILL.md:14`.
- **VU-P6** Invent freely — `SKILL.md:15`.
- **VU-P7** Verify your own output before showing it to the user — `SKILL.md:16`.

### HyperFrames Rules — Non-Negotiable (11, from `SKILL.md:295-319`)

- **HF-R1** Forget `window.__timelines` registration is banned — `SKILL.md:309`.
- **HF-R2** Use video for audio — always muted video + separate `<audio>` — `SKILL.md:310`.
- **HF-R3** Nest video inside a timed div — use a non-timed wrapper — `SKILL.md:311`.
- **HF-R4** Use `data-layer` (use `data-track-index`) or `data-end` (use `data-duration`) — `SKILL.md:312`.
- **HF-R5** Animate video element dimensions — animate a wrapper div — `SKILL.md:313`.
- **HF-R6** Call play/pause/seek on media — framework owns playback — `SKILL.md:314`.
- **HF-R7** Create a top-level container without `data-composition-id` — `SKILL.md:315`.
- **HF-R8** Use `repeat: -1` on any timeline or tween — always finite repeats — `SKILL.md:316`. Also `SKILL.md:303`: "**No `repeat: -1`:** Infinite-repeat timelines break the capture engine. Calculate the exact repeat count from composition duration: `repeat: Math.ceil(duration / cycleDuration) - 1`."
- **HF-R9** Build timelines asynchronously (inside `async`, `setTimeout`, `Promise`) — `SKILL.md:317`. Also `SKILL.md:305`: "Synchronous timeline construction: Never build timelines inside `async`/`await`, `setTimeout`, or Promises."
- **HF-R10** Use `gsap.set()` on clip elements from later scenes — they don't exist in the DOM at page load — `SKILL.md:318`.
- **HF-R11** Use `<br>` in content text — `SKILL.md:319`.

Also at the top of §"Rules":
- **HF-Determinism** No `Math.random()`, `Date.now()`, or time-based logic — `SKILL.md:297`.
- **HF-GSAP-Visual** Only animate visual properties (`opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms). Do NOT animate `visibility`, `display`, or call `video.play()`/`audio.play()` — `SKILL.md:299`.
- **HF-AnimConflicts** Never animate the same property on the same element from multiple timelines simultaneously — `SKILL.md:301`.

### HyperFrames Scene Transitions — Non-Negotiable (4, from `SKILL.md:321-348`, mirrored in `references/transitions.md:5-12`)

- **HF-T1** ALWAYS use transitions between scenes. No jump cuts. No exceptions — `SKILL.md:325`.
- **HF-T2** ALWAYS use entrance animations on every scene — `SKILL.md:326`.
- **HF-T3** NEVER use exit animations except on the final scene — `SKILL.md:327`.
- **HF-T4** Final scene only may fade elements out — `SKILL.md:328`.

### HyperFrames Animation Guardrails (from `SKILL.md:350-359`)

- **HF-G1** Offset first animation 0.1-0.3s (not t=0).
- **HF-G2** Vary eases across entrance tweens — use at least 3 different eases per scene.
- **HF-G3** Don't repeat an entrance pattern within a scene.
- **HF-G4** Avoid full-screen linear gradients on dark backgrounds (H.264 banding).
- **HF-G5** 60px+ headlines, 20px+ body, 16px+ data labels for rendered video.
- **HF-G6** `font-variant-numeric: tabular-nums` on number columns.

### HyperFrames Layout-Before-Animation (`SKILL.md:64-133`)

- **HF-L1** Identify the hero frame for each scene first — `SKILL.md:72`.
- **HF-L2** `.scene-content` MUST fill the scene with padding-based positioning; NEVER `position: absolute; top: Npx` on a content container — `SKILL.md:73`.
- **HF-L3** Add entrances with `gsap.from()` (or `gsap.fromTo()` inside `data-composition-src` sub-comps) — `SKILL.md:74`.
- **HF-L4** Add exits with `gsap.to()` — `SKILL.md:75`.

### HyperFrames Timeline Contract (`SKILL.md:287-294`)

- **HF-TL1** All timelines start `{ paused: true }`.
- **HF-TL2** Register every timeline on `window.__timelines["<composition-id>"]`.
- **HF-TL3** Framework auto-nests sub-timelines — do NOT manually add them.
- **HF-TL4** Duration comes from `data-duration`, not GSAP timeline length.
- **HF-TL5** Never create empty tweens to set duration.

### HyperFrames Captions canon (`references/captions.md`)

- **HF-C-LANG** Never use `.en` models unless the user explicitly states the audio is English — `captions.md:5-9`.
- **HF-C-EXIT** Every group must have a hard `tl.set` kill at `group.end` — `captions.md:96-101`, `captions.md:128`.
- **HF-C-ONE-VISIBLE** One caption group visible at a time — `captions.md:73`, `captions.md:130`.
- **HF-C-DETERMINISTIC** Deterministic. No `Math.random()`, no `Date.now()` — `captions.md:128`.
- **HF-C-FITTEXT** Use `window.__hyperframes.fitTextFontSize()` for dynamic copy — `captions.md:77-90`.

### HyperFrames Transitions canon (`references/transitions.md`)

- **HF-TR-RULES1..4** mirrored HF-T1..HF-T4.
- **HF-TR-PRIMARY** Pick ONE primary (60-70% of scene changes) + 1-2 accents. Never use a different transition for every scene — `transitions.md:22`.
- **HF-TR-MIX** When a composition uses shader transitions, ALL transitions in that composition should be shader-based — `transitions.md:95`.
- **HF-TR-CSS-SHADER-RULES** 6 shader-compatible CSS rules (no `transparent` in gradients; no gradient bg on elements <4px; no `var()` on captured elements; mark uncapturable with `data-no-capture`; no gradient opacity <0.15; explicit `background-color` + matching `bgColor` config) — `transitions.md:97-107`.
- **HF-TR-PATTERN** Avoid transitions that create visible repeating geometric patterns — `transitions.md:111-112`.

### HyperFrames Video-composition canon (`references/video-composition.md`, always-read)

- **HF-VC-DENSITY** Aim for 8-10 visual elements per scene — `video-composition.md:23`.
- **HF-VC-BG-LAYER** Every scene needs background texture (radial glow, ghost type, color panel, grain, grid). Never solid flat color — `video-composition.md:19`.
- **HF-VC-COLOR** Brand accent should be VISIBLE — 15-25% atmospheric, full saturation for focal — `video-composition.md:28`.
- **HF-VC-SCALE** Web→video scale table (headlines 64-120px, body 28-42px, decorative opacity 12-25%, borders 2-4px, padding 60-140px) — `video-composition.md:37-44`.
- **HF-VC-FRAME** Two focal points minimum; fill the frame (hero text 60-80% width); anchor to edges — `video-composition.md:58-62`.

### HyperFrames Motion-principles canon (`references/motion-principles.md`, always-read)

- **HF-MP-VARY-EASE** No more than 2 independent tweens with the same ease in a scene — `motion-principles.md:7`.
- **HF-MP-VARY-SPEED** Slowest scene should be 3× slower than the fastest — `motion-principles.md:8`.
- **HF-MP-VARY-DIR** Don't enter everything from the same direction — `motion-principles.md:9`.
- **HF-MP-VARY-STAGGER** Each scene needs its own rhythm — `motion-principles.md:10`.
- **HF-MP-VARY-AMBIENT** Pick different ambient motion per scene — `motion-principles.md:11`.
- **HF-MP-OFFSET-FIRST** Offset the first animation 0.1-0.3s — `motion-principles.md:12` (mirrored HF-G1).
- **HF-MP-EASE-DIR** `.out` for entries, `.in` for exits, `.inOut` for between-positions — `motion-principles.md:22-26`.
- **HF-MP-PHASES** Build (0-30%) / breathe (30-70%) / resolve (70-100%) — `motion-principles.md:38-41`.
- **HF-MP-NO-IFRAME** No iframes for captured content — `motion-principles.md:85`.
- **HF-MP-NO-DOUBLE-TRANSFORM** Never stack two transform tweens on the same element — `motion-principles.md:87`.
- **HF-MP-FROMTO-IN-CLIP** Prefer `tl.fromTo()` over `tl.from()` inside `.clip` scenes — `motion-principles.md:115`.
- **HF-MP-AMBIENT-ON-TL** Ambient pulses must attach to seekable `tl`, never bare `gsap.to()` — `motion-principles.md:125`.
- **HF-MP-HARD-KILL** Hard-kill every scene boundary, not just captions — `motion-principles.md:135`.

### HyperFrames Typography canon (`references/typography.md`, always-read)

- **HF-TY-BAN** Banned: Inter, Roboto, Open Sans, Noto Sans, Arimo, Lato, Source Sans, PT Sans, Nunito, Poppins, Outfit, Sora, Playfair Display, Cormorant Garamond, Bodoni Moda, EB Garamond, Cinzel, Prata, Syne — `typography.md:11`.
- **HF-TY-NO-TWO-SANS** Don't pair two sans-serifs — `typography.md:17`.
- **HF-TY-ONE-EXPRESSIVE** One expressive font per scene — `typography.md:18`.
- **HF-TY-WEIGHT-CONTRAST** Video needs 300 vs 900 — `typography.md:19`.
- **HF-TY-VIDEO-SIZES** Body 20px min, headlines 60px+, data labels 16px — `typography.md:20`.

### HyperFrames House-style canon (`house-style.md`)

- **HF-HS-LAZY** Lazy defaults to question: gradient text, left-edge accent stripes, cyan-on-dark / purple-to-blue gradients / neon accents, pure `#000` or `#fff`, identical card grids, centered-with-equal-weight, banned fonts — `house-style.md:13-21`.
- **HF-HS-COLOR** Match light/dark to content; one accent hue; same background across all scenes; tint neutrals toward accent; declare palette up front — `house-style.md:25-31`.
- **HF-HS-BG** Every scene needs 2-5 decorative elements with slow ambient GSAP animation — `house-style.md:33-47`.

### HyperFrames Output Checklist (`SKILL.md:376-387`)

- **HF-OC-FAST** `lint`, `validate`, design adherence block on results.
- **HF-OC-SLOW** `inspect`, contrast, animation choreography may run in parallel with preview.

### HyperFrames Quality Checks (`SKILL.md:389-463`)

- **HF-Q1** Visual Inspect via `npx hyperframes inspect` — `SKILL.md:391-404`.
- **HF-Q2** Contrast via `npx hyperframes validate` — `SKILL.md:406-422`.
- **HF-Q3** Design Adherence (6-item checklist if design.md; 2-item fallback if not) — `SKILL.md:424-441`.
- **HF-Q4** Animation Map via `animation-map.mjs` — `SKILL.md:443-463`.

### HyperFrames Editing-existing rule (`SKILL.md:369-374`)

- **HF-ED-READ** Read actual files, don't guess. The composition IS the spec.
- **HF-ED-MATCH** Match existing fonts, colors, animation patterns from what you read.
- **HF-ED-ONLY-WHAT** Only change what was requested.
- **HF-ED-PRESERVE** Preserve timing of unrelated clips.

---

## Appendix B — Free-form canonical step ↔ LangGraph node mapping

Seed for HOM-334 context-pass audit. For each canonical step (Phase V + H + handoff) the row names the LangGraph node(s) (under `graph/src/edit_episode_graph/nodes/`) that implement it, or marks "no canonical analog — orchestrator-house" when the node has no canonical counterpart, or "no graph node — canonical step not yet decomposed" when canon has the step but the graph does not.

Brief files (Jinja2) referenced are under `graph/src/edit_episode_graph/briefs/`.

### Phase V — video-use

| Canonical step | LangGraph node(s) | Brief | Notes |
| --- | --- | --- | --- |
| **V0 — Setup verification** | `preflight_canon.py` | (none) | Orchestrator-house preflight; canon's "verify on cold start" mapped to a per-run gate that checks ffmpeg + ELEVENLABS_API_KEY + canon paths. Canon analog: `SKILL.md:60-66`. |
| **V0/V1 — Pickup (orchestrator step)** | `pickup.py` | (none) | Orchestrator-house file-system step: move `inbox/<slug>.<ext>` → `episodes/<slug>/raw.<ext>`. No canonical analog — canon assumes the user `cd`s into the videos folder. |
| **V1 — Inventory (audio isolation)** | `isolate_audio.py` | (none) | Orchestrator-house pre-transcription audio isolation; partial canon analog in `helpers/isolate_and_transcribe.py`. |
| **V1 — Inventory (transcription + pack)** | `p3_inventory.py` | (none, deterministic) | Wraps `transcribe.py`-shaped Scribe call + `pack_transcripts.py`-shaped phrase packing. Canon: `SKILL.md:85`. |
| **V2 — Pre-scan for problems** | `p3_pre_scan.py` (LLM) | `p3_pre_scan.j2` | Canon: `SKILL.md:86`. |
| **V3 — Converse** | (none — orchestrator does not converse; the user's seed prompt is in state) | (none) | **Decomposition gap.** Canon `SKILL.md:87` describes an interactive conversation; the graph's Phase 3 instead packs the user's framing into state at run-creation time and proceeds directly to V4. Acceptable per CLAUDE.md §"Decomposition via brief-references-canon" item 2 (canonical opt-out: brief tells the strategy node what the user already said), but worth surfacing for HOM-334. |
| **V4 — Propose strategy** | `p3_strategy.py` (LLM) + `strategy_confirmed_interrupt.py` | `p3_strategy.j2` | The interrupt node implements VU-HR11 (`SKILL.md:32`) via `langgraph.types.interrupt({"type":"strategy_confirmed"})`. Canon: `SKILL.md:88`. |
| **V5 — Execute (EDL select)** | `p3_edl_select.py` (LLM) + `edl_failure_interrupt.py` | `p3_edl_select.j2` | Implements canon's editor sub-agent brief verbatim shape (`SKILL.md:123-160`). Failure interrupt is orchestrator-house (canon does not specify; canon just retries). |
| **V5 — Execute (animation slots)** | (none — `overlays: []` opt-out used) | (none) | **Decomposition decision.** Canon `SKILL.md:200-262` describes parallel animation sub-agents (VU-HR10). Orchestrator uses the canon opt-out: EDL emits `overlays: []`, and animation production is deferred to Phase 4 HyperFrames (which builds the *whole composition*, not just slot overlays). CLAUDE.md §"Decomposition via brief-references-canon" item 2 explicitly allows this. |
| **V5 — Execute (render via render.py)** | `p3_render_segments.py` | (none, deterministic) | Wraps `render.py` per-segment extract → concat → overlay → subtitles-LAST flow (VU-HR1..VU-HR5). |
| **V6 — Preview** | (folded into V5 render) | (none) | Orchestrator does not separate preview from final render at Phase 3; canon's V6 `--preview` short-circuit is mapped to `--preview`-equivalent flags inside `p3_render_segments`. **Decomposition gap** worth noting for HOM-334. |
| **V7 — Self-eval** | `p3_self_eval.py` (LLM) + `eval_failure_interrupt.py` | `p3_self_eval.j2` | Implements canon `SKILL.md:91-99` cut-boundary inspection. Failure interrupt is orchestrator-house. 3-pass cap (`SKILL.md:99`) — TBD whether graph enforces this verbatim; canon-silent on cross-run cap. |
| **V8 — Iterate + persist** | `p3_persist_session.py` (LLM) + `p3_review_interrupt.py` | `p3_persist_session.j2` | Persists `project.md` per `SKILL.md:291-302`. The review interrupt is orchestrator-house — canon does not specify a human review gate here, but VU-HR11's spirit ("strategy confirmation") generalizes. |

### Handoff (orchestrator-house)

| Step | LangGraph node(s) | Brief | Notes |
| --- | --- | --- | --- |
| **H — Handoff** | `glue_remap_transcript.py` + `rehydrate_skip_phase3.py` | (none, deterministic) | Bridges Scribe JSON shape → HF-recognized transcript shape (`transcript-guide.md:7-15`). `rehydrate_skip_phase3` is the LangGraph mechanism for Phase 3 → Phase 4 short-circuit when final.mp4 exists (CLAUDE.md §"Idempotency" — `route_after_preflight`). No canonical analog — canon does not chain video-use → HF on the *whole* video. |

### Phase H — hyperframes

| Canonical step | LangGraph node(s) | Brief | Notes |
| --- | --- | --- | --- |
| **H1 — Design system** | `p4_design_system.py` (LLM) | `p4_design_system.j2` | Canon: `SKILL.md:25-37`. Brief must reference canon path, not embed (CLAUDE.md item 1). |
| **H2 — Prompt expansion** | `p4_prompt_expansion.py` (LLM) | `p4_prompt_expansion.j2` | Canon: `SKILL.md:39-43` + `references/prompt-expansion.md`. Output to `.hyperframes/expanded-prompt.md` per canon `prompt-expansion.md:60`. State-first persistence per HOM-239 — disk write deferred to `p4_materialize_disk_node`. |
| **H3 — Plan** | `p4_plan.py` (LLM) | `p4_plan.j2` | Canon: `SKILL.md:45-58`. |
| **H3.5 — Scaffold project** | `p4_scaffold.py` | (none, deterministic) | Orchestrator-house: runs `npx hyperframes init ...` equivalent in `episodes/<slug>/hyperframes/`. Canon analog: per-project scaffold contract embedded in bundled `dist/templates/_shared/CLAUDE.md`. |
| **H3.6 — Catalog scan** | `p4_catalog_scan.py` | (none, deterministic) | **Orchestrator-house gate** per memory `feedback_hf_catalog_orchestrator_gate` — per-beat justification of which registry/catalog blocks are referenced; not in HF canon. |
| **H4 — Construct (dispatch beats)** | `p4_dispatch_beats.py` (LangGraph `Send`) | (none, deterministic) | Implements the implicit per-scene fan-out canon describes (`prompt-expansion.md:31` "scene subagents") via the native LangGraph `Send` API (CLAUDE.md §"LangGraph primitives"). |
| **H4 — Construct (beat sub-agent)** | `p4_beat.py` (LLM, parallel via Send) | `p4_beat.j2` | Each invocation builds one scene per canon §"Layout Before Animation" + Rules + Scene Transitions + Animation Guardrails. Canon ref: `SKILL.md:64-359`. |
| **H4 — Construct (transitions layer)** | `p4_transitions.py` | (none, deterministic) | Implements HF-T1..HF-T4 + transitions catalog (canon `transitions.md`). Orchestrator-house decomposition — canon authors transitions inline within scene HTML; orchestrator factors transitions into a separate node for verifiability. |
| **H4 — Construct (captions layer)** | `p4_captions_layer.py` (LLM) | `p4_captions_layer.j2` | Canon: `references/captions.md`. Implements caption-exit guarantee (HF-C-EXIT). |
| **H4 — Construct (assemble index.html)** | `p4_assemble_index.py` | (none, deterministic) | Composes per-beat output + transitions + captions into the root `index.html` per `SKILL.md:166-189` standalone-vs-template rule. |
| **H4 — Redispatch on lint feedback** | `p4_redispatch_beat.py` (LLM) | `p4_redispatch_beat.j2` | Orchestrator-house retry loop for beats that fail gates. No canonical analog — canon expects the free-form agent to triage findings inline; the graph cannot triage inside a single node so it retries with feedback. |
| **H5 — Output Checklist (lint/validate)** | (folded into beat retries + assemble checks) | (none) | **Decomposition gap.** Canon `SKILL.md:380-381` mandates `lint` + `validate` block on results. No dedicated graph node — currently the orchestrator runs these inside `npm run check` at materialization time, after the graph terminates. TBD for HOM-334 whether to lift them into graph nodes. |
| **Q1 — Visual Inspect** | (no graph node yet) | (none) | Canon `SKILL.md:391-404`. Currently run by operator at `npm run check` post-graph. **Decomposition gap.** |
| **Q2 — Contrast** | (no graph node yet) | (none) | Canon `SKILL.md:406-422`. Same as Q1. |
| **Q3 — Design Adherence** | (no graph node yet — implicit in `p4_beat` brief) | (none — design constraints injected into `p4_beat.j2` brief) | Canon `SKILL.md:424-441`. The 6-item checklist is canon-aware-but-not-enforced; orchestrator relies on the brief carrying design.md content into the beat sub-agent. TBD for HOM-334 whether to add a `gate_design_adherence` node. |
| **Q4 — Animation Map (triage)** | `gate_animation_map_classify.py` (LLM, Haiku-tier) | `gate_animation_map_classify.j2` | Implements canon "Check every flag — fix or justify" (`SKILL.md:461`) via cheap LLM triage. Per memory `feedback_finite_allowlists_against_llm_vocab`, the gate restricts hard-blocking to canon-absolute categories (HOM-317). |
| **H4 — Materialize to disk** | `p4_materialize_disk.py` | (none, deterministic, single writer) | Orchestrator-house single-writer per HOM-239 / spec §"Step D2" (CLAUDE.md §"Layout convention" — "single deterministic disk writer"). No canonical analog — canon writes files inline at every step. |
| **H4 — Persist Phase-4 session** | `p4_persist_session.py` (LLM) | `p4_persist_session.j2` | Orchestrator-house session log for Phase 4 (mirrors video-use V8 `project.md` shape). |
| **H4 — Halt LLM boundary** | `halt_llm_boundary.py` | (none, deterministic) | Orchestrator-house halt before render (notifies operator via Studio). No canonical analog — canon assumes the agent renders directly. |
| **H6 — Render** | (no graph node — operator runs `npx hyperframes render` manually inside `episodes/<slug>/hyperframes/`) | (none) | Canon `SKILL.md:230-237` + bundled per-project CLAUDE.md. **Decomposition gap.** Future `p4_final_render` node (HOM-78) per CLAUDE.md §"Studio replay (operator runbook)". |
| **Studio launch (orchestrator UX)** | `studio_launch.py` | (none, deterministic) | Orchestrator-house: opens `langgraph dev` Studio after persist. No canonical analog. |

### Helper / shared nodes (no canonical mapping)

| Node | Purpose |
| --- | --- |
| `_deterministic.py` | Helper wrapper for deterministic (non-LLM) node creation. |
| `_llm.py` | Helper wrapper for LLM node creation + `make_llm_key` cache fingerprinting (CLAUDE.md §"Idempotency" — LLM cache keys include routing-config fingerprint, HOM-157). |
| `_routing.py` | Conditional-edge routing helpers (`route_after_preflight` etc., CLAUDE.md §"Idempotency"). |
| `_compose_materialization.py`, `_materialize_tmpdir.py` | Internal helpers for `p4_materialize_disk`. |

### Decomposition gaps surfaced (for HOM-334)

The graph currently has no analog for:

1. **V3 — Converse.** Canon describes interactive conversation; graph packs user framing at run-creation. Acceptable opt-out, but the audit should confirm `p3_strategy`'s brief carries the user's framing as richly as a converse-turn would.
2. **V6 — Preview vs. final.** Canon distinguishes preview and final render; graph collapses both into `p3_render_segments`. Audit whether 3-pass self-eval cap is enforced.
3. **H5 / Q1 / Q2 / Q3 / H6.** Canon's Output Checklist and Quality Checks are not decomposed into graph nodes — they run at materialization time / by the operator. The `gate_animation_map_classify` node is the lone Q-gate. Audit whether each canonical fast/slow check needs a node.

### Free-form transcript observations (informational)

Free-form `/hyperframes` runs in `docs/clean-skills-usage-examples/hyperframes/*.jsonl` (per CLAUDE.md §"Gates must match canon"):
- The agent triages Q4 flags inline rather than treating them as blocking — see `gate_animation_map_classify` rationale + retro `docs/retros/retro-2026-05-17-gate-animation-map-canonical-false-positives.md` (HOM-316).
- The agent reads canon at decision time (per CLAUDE.md §"Decomposition via brief-references-canon" item 1), which is why briefs must cite canon paths rather than embed canon text.

---

## Document maintenance

This doc is a snapshot dated **2026-05-23**. Canon paths may shift (`~/.agents/skills/hyperframes/` and `~/.claude/skills/video-use/` are auto-updated by Task Scheduler per CLAUDE.md §"External skill canon"). On next major canon update:

1. Re-walk the file index ([`2026-05-canon-file-index.md`](2026-05-canon-file-index.md)) and bump the date.
2. Diff each cited verbatim block against the new canon. Any change → bump the date in this doc's filename to `YYYY-MM-canonical-pipeline-algorithm.md` and update.
3. Surface any new contradictions in the "Open questions" fields of the affected steps.
4. The Appendix B mapping is the orchestrator-coupling surface — re-audit when graph nodes are added/removed (HOM-334 will exercise this).
