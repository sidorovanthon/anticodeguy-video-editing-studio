# video-use canonical algorithm
Canon snapshot: `~/repos/video-use/` @ `cf12ac35143caa48db76efa35b1cb439582333bb` (2026-05-14)
Source root: `SKILL.md`

This document describes, step by step, what the canonical `video-use` agent does inside the framework, in canon's own order and with canon's own conventions. Every claim is anchored to a verbatim quote from canon at `path:line`. The steps under "The process" (`SKILL.md:83-100`) are the spine; multi-action canonical sentences are expanded per the granularity rule (each discrete action gets its own step).

---

## Step 0: Setup verification (canon does not label as a numbered step)

**Canon source:** `SKILL.md:58-70`

**Verbatim canon text:**

```
## Setup

First-time install lives in `install.md` (clone, deps, ffmpeg, skill registration, API key). Don't re-run it every session; on cold start just verify:

- `ELEVENLABS_API_KEY` resolves — either in the environment or in `.env` at the video-use repo root. If missing, ask the user to paste one and write it to `.env` (never to the user's `<videos_dir>`).
- `ffmpeg` + `ffprobe` on PATH.
- Python deps installed (`uv sync` or `pip install -e .` inside the repo).
- Node.js + npm available if the session needs HyperFrames or Remotion slots. HyperFrames currently requires Node.js 22+.
- `yt-dlp`, HyperFrames, Remotion, Manim installed only on first use.
- First-use animation setup happens inside the slot directory, never at the video-use repo root. HyperFrames can be invoked with `npx --yes hyperframes ...`; Remotion can be scaffolded with `npx create-video@latest` or installed as a project-local dependency before using its `remotion render` command.
- This skill vendors `skills/manim-video/`. Read its SKILL.md when building a Manim slot.

Helpers (`helpers/transcribe.py`, `helpers/render.py`, etc.) live alongside this SKILL.md. Resolve their paths relative to the directory containing this file — the skill is typically symlinked at `~/.claude/skills/video-use/` or `~/.codex/skills/video-use/`.
```

**Inputs:** environment (`ELEVENLABS_API_KEY`, PATH entries for `ffmpeg`/`ffprobe`), repo root `.env`, Python deps, optional Node.js (≥22 if external animation engine slots are used), optional first-use installs of the tools named in the verify list (`SKILL.md:62-67`).

**Outputs / artifacts:** if `ELEVENLABS_API_KEY` is missing, a written `.env` at the video-use repo root — never inside `<videos_dir>` (`SKILL.md:62`).

**Conventions / hard rules at this step:**

- Don't re-run `install.md` every session; verify on cold start (`SKILL.md:60`).
- Never write `.env` to `<videos_dir>` (`SKILL.md:62`).
- First-use animation setup happens inside the slot directory, never at the video-use repo root (`SKILL.md:67`).

**Quality checks:** None canonically prescribed beyond the verify list itself.

**Sub-agent dispatches:** None.

**Transition rule to next step:** all verify-list items resolve; proceed to Step 1 (Inventory).

---

## Step 1: Inventory — `ffprobe` every source

**Canon source:** `SKILL.md:85`

**Verbatim canon text:**

```
1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` to produce `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.
```

**Inputs:** the `<videos_dir>` source files (`SKILL.md:39`, `SKILL.md:42-43`).

**Outputs / artifacts:** `ffprobe` results per source file (canon does not specify a written file).

**Conventions / hard rules at this step:** None specific to `ffprobe` at this step.

**Quality checks:** None beyond running `ffprobe`.

**Sub-agent dispatches:** None.

**Transition rule to next step:** every source has been probed; proceed to batch transcription.

---

## Step 2: Inventory — batch transcription

**Canon source:** `SKILL.md:85`, `SKILL.md:74-75`

**Verbatim canon text:**

```
1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` to produce `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.
```

And from the Helpers section:

```
- **`transcribe.py <video>`** — single-file Scribe call. `--num-speakers N` optional. Cached.
- **`transcribe_batch.py <videos_dir>`** — 4-worker parallel transcription. Use for multi-take.
```

**Inputs:** `<videos_dir>` source files (`SKILL.md:75`).

**Outputs / artifacts:** cached raw Scribe JSON at `<videos_dir>/edit/transcripts/<name>.json` (`SKILL.md:48`).

**Conventions / hard rules at this step:**

- Hard Rule 8: "Word-level verbatim ASR only. Never SRT/phrase mode (loses sub-second gap data). Never normalized fillers (loses editorial signal)." (`SKILL.md:29`)
- Hard Rule 9: "Cache transcripts per source. Never re-transcribe unless the source file itself changed." (`SKILL.md:30`)
- Transcribe is 4-worker parallel for multi-take material (`SKILL.md:75`).

**Quality checks:** None canonically prescribed at this step beyond cache hits.

**Sub-agent dispatches:** None.

**Transition rule to next step:** every source has a cached transcript JSON; proceed to packing.

---

## Step 3: Inventory — pack transcripts

**Canon source:** `SKILL.md:85`, `SKILL.md:76`, `SKILL.md:112-121`

**Verbatim canon text:**

```
1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` to produce `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.
```

From Helpers:

```
- **`pack_transcripts.py --edit-dir <dir>`** — `transcripts/*.json` → `takes_packed.md` (phrase-level, break on silence ≥ 0.5s).
```

From "The packed transcript (primary reading view)":

> `pack_transcripts.py` reads all `transcripts/*.json` and produces one markdown file where each take is a list of phrase-level lines, each prefixed with its `[start-end]` time range. Phrases break on any silence ≥ 0.5s OR speaker change. This is the artifact the editor sub-agent reads to pick cuts — it gives word-boundary precision from text alone at 1/10 the tokens of raw JSON.

Example line:

```
## C0103  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

**Inputs:** `transcripts/*.json` under `<videos_dir>/edit/` (`SKILL.md:76`, `SKILL.md:48`).

**Outputs / artifacts:** `<videos_dir>/edit/takes_packed.md` — phrase-level lines prefixed with `[start-end]` time range, breaking on any silence ≥ 0.5s OR speaker change (`SKILL.md:46`, `SKILL.md:114`).

**Conventions / hard rules at this step:**

- Hard Rule 12: "All session outputs in `<videos_dir>/edit/`. Never write inside the `video-use/` project directory." (`SKILL.md:33`)
- Phrase break rule: silence ≥ 0.5s OR speaker change (`SKILL.md:114`).

**Quality checks:** None canonically prescribed.

**Sub-agent dispatches:** None.

**Transition rule to next step:** `takes_packed.md` exists; proceed to sampling visuals.

---

## Step 4: Inventory — sample `timeline_view`s for first visual impression

**Canon source:** `SKILL.md:85`, `SKILL.md:77`

**Verbatim canon text:**

```
1. **Inventory.** `ffprobe` every source. `transcribe_batch.py` on the directory. `pack_transcripts.py` to produce `takes_packed.md`. Sample one or two `timeline_view`s for a visual first impression.
```

From Helpers:

```
- **`timeline_view.py <video> <start> <end>`** — filmstrip + waveform PNG. On-demand visual drill-down. **Not a scan tool** — use it at decision points, not constantly.
```

**Inputs:** one or two source videos, plus `<start>` and `<end>` ranges chosen by the agent.

**Outputs / artifacts:** filmstrip + waveform PNGs written under `<videos_dir>/edit/verify/` (`SKILL.md:53`).

**Conventions / hard rules at this step:**

- `timeline_view` is "Not a scan tool — use it at decision points, not constantly." (`SKILL.md:77`)
- Only "one or two" samples at the inventory step (`SKILL.md:85`).

**Quality checks:** None canonically prescribed.

**Sub-agent dispatches:** None.

**Transition rule to next step:** the agent has formed a visual first impression; proceed to pre-scan.

---

## Step 5: Pre-scan for problems

**Canon source:** `SKILL.md:86`

**Verbatim canon text:**

```
2. **Pre-scan for problems.** One pass over `takes_packed.md` to note verbal slips, obvious mis-speaks, or phrasings to avoid. Plain list, feed into the editor brief.
```

**Inputs:** `takes_packed.md` (`SKILL.md:86`).

**Outputs / artifacts:** a "plain list" of verbal slips, obvious mis-speaks, or phrasings to avoid — fed into the editor brief at Step 9 (`SKILL.md:86`, `SKILL.md:136`).

**Conventions / hard rules at this step:**

- One pass — not iterative (`SKILL.md:86`).

**Quality checks:** None canonically prescribed.

**Sub-agent dispatches:** None — canon says "one pass" by the main agent.

**Transition rule to next step:** the plain list exists; proceed to converse.

---

## Step 6: Converse

**Canon source:** `SKILL.md:87`

**Verbatim canon text:**

```
3. **Converse.** Describe what you see in plain English. Ask questions *shaped by the material*. Collect: content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs. Do not use a fixed checklist — the right questions are different every time.
```

**Inputs:** `takes_packed.md`, the sample `timeline_view`s from Step 4, the pre-scan list, the live user conversation.

**Outputs / artifacts:** conversation context covering content type, target length/aspect, aesthetic/brand direction, pacing feel, must-preserve moments, must-cut moments, animation and grade preferences, subtitle needs (`SKILL.md:87`).

**Conventions / hard rules at this step:**

- "Do not use a fixed checklist — the right questions are different every time." (`SKILL.md:87`)
- Principle 4: "Generalize. Do not assume what kind of video this is. Look at the material, ask the user, then edit." (`SKILL.md:13`)
- Delivery-format default — "Match the source unless the user asked for something specific." (`SKILL.md:264`)
- Delivery-format prompt — "Worth asking the user which delivery format matters." (`SKILL.md:266`)

**Quality checks:** None canonically prescribed.

**Sub-agent dispatches:** None.

**Transition rule to next step:** the user has answered enough that the agent can propose a strategy; proceed.

---

## Step 7: Propose strategy and wait for confirmation

**Canon source:** `SKILL.md:88`

**Verbatim canon text:**

```
4. **Propose strategy.** 4–8 sentences: shape, take choices, cut direction, animation plan, grade direction, subtitle style, length estimate. **Wait for confirmation.**
```

**Inputs:** the conversation context from Step 6.

**Outputs / artifacts:** a 4–8 sentence plain-English strategy covering shape, take choices, cut direction, animation plan, grade direction, subtitle style, and length estimate (`SKILL.md:88`).

**Conventions / hard rules at this step:**

- Hard Rule 11: "Strategy confirmation before execution. Never touch the cut until the user has approved the plain-English plan." (`SKILL.md:32`)
- Principle 3: "Ask → confirm → execute → iterate → persist. Never touch the cut until the user has confirmed the strategy in plain English." (`SKILL.md:12`)

**Quality checks:** None canonically prescribed.

**Sub-agent dispatches:** None.

**Transition rule to next step:** "Wait for confirmation" — the user explicitly approves; proceed to Step 8.

---

## Step 8: Execute — produce `edl.json` via the editor sub-agent

**Canon source:** `SKILL.md:89`, `SKILL.md:123-160`

**Verbatim canon text:**

```
5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Apply grade per-segment. Compose via `render.py`.
```

From "Editor sub-agent brief (for multi-take selection)":

```
When the task is "pick the best take of each beat across many clips," spawn a dedicated sub-agent with a brief shaped like this. The structure is load-bearing; the pitch-shape example is not.

```
You are editing a <type> video. Pick the best take of each beat and 
assemble them chronologically by beat, not by source clip order.

INPUTS:
  - takes_packed.md (time-annotated phrase-level transcripts of all takes)
  - Product/narrative context: <2 sentences from the user>
  - Speaker(s): <name, role, delivery style note>
  - Expected structure: <pick an archetype or invent one>
  - Verbal slips to avoid: <list from the pre-scan pass>
  - Target runtime: <seconds>

Common structural archetypes (pick, adapt, or invent):
  - Tech launch / demo:   HOOK → PROBLEM → SOLUTION → BENEFIT → EXAMPLE → CTA
  - Tutorial:             INTRO → SETUP → STEPS → GOTCHAS → RECAP
  - Interview:            (QUESTION → ANSWER → FOLLOWUP) repeat
  - Travel / event:       ARRIVAL → HIGHLIGHTS → QUIET MOMENTS → DEPARTURE
  - Documentary:          THESIS → EVIDENCE → COUNTERPOINT → CONCLUSION
  - Music / performance:  INTRO → VERSE → CHORUS → BRIDGE → OUTRO
  - Or invent your own.

RULES:
  - Start/end times must fall on word boundaries from the transcript.
  - Pad cut boundaries (working window 30–200ms).
  - Prefer silences ≥ 400ms as cut targets.
  - Unavoidable slips are kept if no better take exists. Note them in "reason".
  - If over budget, revise: drop a beat or trim tails. Report total and self-correct.

OUTPUT (JSON array, no prose):
  [{"source": "C0103", "start": 2.42, "end": 6.85, "beat": "HOOK",
    "quote": "...", "reason": "..."}, ...]

Return the final EDL and a one-line total runtime check.
```
```

**Inputs (per the brief, `SKILL.md:131-137`):** `takes_packed.md`, 2-sentence product/narrative context, speaker info, expected structure (archetype or invented), the pre-scan verbal-slips list, target runtime.

**Outputs / artifacts:** `edl.json` — a JSON array per the brief's OUTPUT block, plus a one-line total runtime check returned by the sub-agent (`SKILL.md:155-159`). The on-disk EDL format is `<videos_dir>/edit/edl.json` (`SKILL.md:47`) with the full schema at `SKILL.md:269-287`.

**Conventions / hard rules at this step:**

- Hard Rule 6: "Never cut inside a word. Snap every cut edge to a word boundary from the Scribe transcript." (`SKILL.md:27`)
- Hard Rule 7: "Pad every cut edge. Working window: 30–200ms. Scribe timestamps drift 50–100ms — padding absorbs the drift. Tighter for fast-paced, looser for cinematic." (`SKILL.md:28`)
- Brief rule: "Start/end times must fall on word boundaries from the transcript." (`SKILL.md:149`)
- Brief rule: "Pad cut boundaries (working window 30–200ms)." (`SKILL.md:150`)
- Brief rule: "Prefer silences ≥ 400ms as cut targets." (`SKILL.md:151`)
- Brief rule: "Unavoidable slips are kept if no better take exists. Note them in 'reason'." (`SKILL.md:152`)
- Brief rule: "If over budget, revise: drop a beat or trim tails. Report total and self-correct." (`SKILL.md:153`)
- "The structure is load-bearing; the pitch-shape example is not." (`SKILL.md:125`)
- Cut craft: "Audio-first. Candidate cuts from word boundaries and silence gaps." (`SKILL.md:104`)
- Cut craft: "Silences ≥400ms are usually the cleanest. 150–400ms phrase boundaries are usable with a visual check. <150ms is unsafe (mid-phrase)." (`SKILL.md:108`)
- Cut craft: "Never reason audio and video independently. Every cut must work on both tracks." (`SKILL.md:110`)

**Quality checks:** the brief itself instructs "Report total and self-correct" if over budget (`SKILL.md:153`); the sub-agent returns "a one-line total runtime check" (`SKILL.md:159`).

**Sub-agent dispatches:**

- **Dispatch:** editor sub-agent, spawned via the `Agent` tool (`SKILL.md:123-160`).
- **Brief:** the verbatim block quoted above (`SKILL.md:128-160`).
- **What the child returns:** "the final EDL and a one-line total runtime check" (`SKILL.md:159`).
- **What the parent does with the result:** writes `edl.json` to `<videos_dir>/edit/` for downstream steps (`SKILL.md:47`).

**Transition rule to next step:** `edl.json` exists with word-boundary, padded cuts; proceed to timeline drill-down at ambiguous moments.

---

## Step 9: Execute — drill into `timeline_view` at ambiguous moments

**Canon source:** `SKILL.md:89`, `SKILL.md:77`

**Verbatim canon text:**

```
5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Apply grade per-segment. Compose via `render.py`.
```

From Helpers:

```
- **`timeline_view.py <video> <start> <end>`** — filmstrip + waveform PNG. On-demand visual drill-down. **Not a scan tool** — use it at decision points, not constantly.
```

**Inputs:** specific `<video>`, `<start>`, `<end>` ranges chosen at ambiguous moments in the EDL.

**Outputs / artifacts:** filmstrip + waveform PNG under `<videos_dir>/edit/verify/` (`SKILL.md:53`).

**Conventions / hard rules at this step:**

- "Not a scan tool — use it at decision points, not constantly." (`SKILL.md:77`)

**Quality checks:** the agent visually inspects the filmstrip/waveform at the ambiguous moment to resolve the cut.

**Sub-agent dispatches:** None.

**Transition rule to next step:** all ambiguous cut moments resolved; proceed to animations.

---

## Step 10: Execute — build animations in parallel sub-agents

**Canon source:** `SKILL.md:89`, `SKILL.md:198-262`

**Verbatim canon text:**

```
5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Apply grade per-segment. Compose via `render.py`.
```

From "Animations (when requested)":

```
For animations, create `<edit>/animations/slot_<id>/` with `Bash` and spawn a sub-agent via the `Agent` tool.
```

(`SKILL.md:81`)

And the parallel sub-agent brief contract (`SKILL.md:249-262`):

```
**Parallel sub-agent brief** — each animation is one sub-agent spawned via the `Agent` tool. Each prompt is self-contained (sub-agents have no parent context). Include:

1. One-sentence goal: *"Build ONE animation: [spec]. Nothing else."*
2. Absolute output path (`<edit>/animations/slot_<id>/render.mp4`)
3. Exact technical spec: resolution, fps, codec, pix_fmt, CRF, duration
4. Style palette as concrete values (RGB tuples, hex, or reference to a design system)
5. Font path with index
6. Frame-by-frame timeline (what happens when, with easing)
7. Anti-list ("no chrome, no extras, no titles unless specified")
8. Code pattern reference (copy helpers inline, don't import across slots)
9. Deliverable checklist (script, render, verify duration via ffprobe, report)
10. **"Do not ask questions. If anything is ambiguous, pick the most obvious interpretation and proceed."**

One sub-agent = one file (unique filenames, parallel agents don't overwrite each other).
```

**Inputs:** the strategy's animation plan, agreed palette/font/visual language from conversation (`SKILL.md:199`), per-slot specs.

**Outputs / artifacts:** one `<edit>/animations/slot_<id>/render.mp4` per slot (`SKILL.md:50`, `SKILL.md:252`). Animation source + reasoning live in the same slot directory (`SKILL.md:50`). For HyperFrames slots the final render alpha branches per slot:

- Opaque overlay: `npx --yes hyperframes render . -o render.mp4` (`SKILL.md:210`).
- Alpha-required overlay: `npx --yes hyperframes render . --format webm -o render.webm` (`SKILL.md:210`).

**Conventions / hard rules at this step:**

- Hard Rule 10: "Parallel sub-agents for multiple animations. Never sequential. Spawn N at once via the `Agent` tool; total wall time ≈ slowest one." (`SKILL.md:31`)
- "Get the palette, font, and visual language from the conversation — never assume a default. If the user hasn't told you, propose a palette in the strategy phase and wait for confirmation before building anything." (`SKILL.md:199`)
- Tool-options rule: "Pick the engine per animation slot. Do not default to Remotion just because the animation is web-adjacent." (`SKILL.md:203`)
- Engine selection criteria — four canon bullets (verbatim, `SKILL.md:205-208`):
  - **HyperFrames** — "Browser-native HTML/CSS/GSAP video compositions: product UI motion, website-to-video or mockup-to-video captures, kinetic typography, landing-page/storyboard promos, data-driven UI states, transparent WebM overlays, and clips that need deterministic frame capture plus HyperFrames lint/validate/render checks. Best when the animation should be authored and verified like a web composition instead of a React component tree." (`SKILL.md:205`)
  - **Remotion** — "React/CSS compositions with component state, reusable React primitives, or an existing Remotion brand system. Best when the user specifically asks for React/Remotion or when React composition is the simpler authoring model." (`SKILL.md:206`)
  - **Manim** — "formal diagrams, state machines, equation derivations, graph morphs. Read `skills/manim-video/SKILL.md` and its references for depth." (`SKILL.md:207`)
  - **PIL + PNG sequence + ffmpeg** — "simple overlay cards: counters, typewriter text, single bar reveals, progressive draws. Fast to iterate, any aesthetic you want. The launch video used this." (`SKILL.md:208`)
- HyperFrames slot setup (verbatim, `SKILL.md:210`): "scaffold the slot inside `edit/animations/slot_<id>/` with `npx --yes hyperframes init . --example blank --non-interactive --skip-skills`, build the HTML composition there, run the HyperFrames checks that fit the slot (`lint`, `validate`, and a draft render when practical), then produce the final overlay video with `npx --yes hyperframes render . -o render.mp4` or `--format webm -o render.webm` when alpha is required. Point the EDL overlay `file` at the actual rendered path."
- Remotion slot setup (verbatim, `SKILL.md:212`): "keep the Remotion project isolated inside the same slot directory, scaffold with `npx create-video@latest` or install Remotion locally there, render the composition to `render.mp4` with the project-local `remotion render` command, and verify duration and dimensions with `ffprobe`."
- Hybrid invention clause: "None is mandatory. Invent hybrids if useful (e.g., PIL background with a HyperFrames or Remotion layer on top)." (`SKILL.md:214`)
- Easing rule: "Easing (universal — never `linear`, it looks robotic)" with `ease_out_cubic` for single reveals, `ease_in_out_cubic` for continuous draws (`SKILL.md:226-235`).
- Duration thumb-rules (sync-to-narration vs beat-synced vs over voiceover), "Hold the final frame ≥ 1s before the cut (universal)", "Over voiceover: total duration ≥ narration_length + 1s (universal)", "Never parallel-reveal independent elements" (`SKILL.md:216-222`).
- Animation payoff timing: "get the payoff word's timestamp. Start the overlay `reveal_duration` seconds earlier so the landing frame coincides with the spoken payoff word." (`SKILL.md:224`)
- Typing text anchor trick: "center on the FULL string's width, not the partial-string width — otherwise text slides left during reveal." (`SKILL.md:237`)
- "One sub-agent = one file (unique filenames, parallel agents don't overwrite each other)." (`SKILL.md:262`)

**Quality checks:**

- Universal sub-agent brief item 9 — "Deliverable checklist (script, render, verify duration via ffprobe, report)" (`SKILL.md:259`).
- HyperFrames slot Quality Check — "run the HyperFrames checks that fit the slot (`lint`, `validate`, and a draft render when practical)" before producing the final overlay (`SKILL.md:210`).
- Remotion slot Quality Check — "verify duration and dimensions with `ffprobe`" after `remotion render` (`SKILL.md:212`).

**Sub-agent dispatches:**

- **Dispatch:** one sub-agent per animation slot, spawned in parallel via the `Agent` tool (`SKILL.md:31`, `SKILL.md:249`).
- **Brief:** the 10-item self-contained block above (`SKILL.md:249-261`). Each prompt is self-contained — "sub-agents have no parent context" (`SKILL.md:249`).
- **What the child returns:** the rendered `<edit>/animations/slot_<id>/render.mp4` plus a verification report per item 9 (`SKILL.md:252`, `SKILL.md:259`).
- **What the parent does with the result:** points the EDL `overlays[].file` at each rendered path (`SKILL.md:281-283`).

**Transition rule to next step:** every requested animation slot has a rendered `render.mp4`; proceed to grading.

---

## Step 11: Execute — apply grade per-segment

**Canon source:** `SKILL.md:89`, `SKILL.md:79`, `SKILL.md:162-176`

**Verbatim canon text:**

```
5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Apply grade per-segment. Compose via `render.py`.
```

From Helpers:

```
- **`grade.py <in> -o <out>`** — ffmpeg filter chain grade. Presets + `--filter '<raw>'` for custom.
```

From "Color grade (when requested)":

```
Your job is to **reason about the image**, not apply a preset. Look at a frame (via `timeline_view`), decide what's wrong, adjust one thing, look again.

Mental model is ASC CDL. Per channel: `out = (in * slope + offset) ** power`, then global saturation. `slope` → highlights, `offset` → shadows, `power` → midtones.

**Example filter chains** (`grade.py` has `--list-presets`; use them as starting points or mix your own):

- **`warm_cinematic`** — retro/technical, subtle teal/orange split, desaturated. Shipped in a real launch video. Safe for talking heads.
- **`neutral_punch`** — minimal corrective: contrast bump + gentle S-curve. No hue shifts.
- **`none`** — straight copy. Default when the user hasn't asked.

For anything else — portraiture, nature, product, music video, documentary — invent your own chain. `grade.py --filter '<raw ffmpeg>'` accepts any filter string.

Hard rules: apply **per-segment during extraction** (not post-concat, which re-encodes twice). Never go aggressive without testing skin tones.
```

**Inputs:** the source segments referenced in `edl.json`, the chosen preset name or raw filter string (stored as the EDL's `grade` field — `SKILL.md:280`, `SKILL.md:289`).

**Outputs / artifacts:** per-segment graded extracts under `<videos_dir>/edit/clips_graded/` (`SKILL.md:51`).

**Conventions / hard rules at this step:**

- "apply per-segment during extraction (not post-concat, which re-encodes twice)" (`SKILL.md:176`).
- "Never go aggressive without testing skin tones." (`SKILL.md:176`)
- Hard Rule 2: "Per-segment extract → lossless `-c copy` concat, not single-pass filtergraph. Otherwise you double-encode every segment when overlays are added." (`SKILL.md:23`)
- "Your job is to reason about the image, not apply a preset." (`SKILL.md:164`)

**Quality checks:** sample a frame via `timeline_view`, decide what's wrong, adjust one thing, look again (`SKILL.md:164`).

**Sub-agent dispatches:** None canonically prescribed.

**Transition rule to next step:** every segment in the EDL has its graded extract; proceed to compose via `render.py`.

---

## Step 12: Execute — compose via `render.py`

**Canon source:** `SKILL.md:89`, `SKILL.md:78`

**Verbatim canon text:**

```
5. **Execute.** Produce `edl.json` via the editor sub-agent brief. Drill into `timeline_view` at ambiguous moments. Build animations in parallel sub-agents. Apply grade per-segment. Compose via `render.py`.
```

From Helpers:

```
- **`render.py <edl.json> -o <out>`** — per-segment extract → concat → overlays (PTS-shifted) → subtitles LAST. `--preview` for 720p fast. `--build-subtitles` to generate master.srt inline.
```

**Inputs:** `<videos_dir>/edit/edl.json` (with `sources`, `ranges`, `grade`, `overlays`, optional `subtitles` — `SKILL.md:269-287`), the graded extracts from Step 11, the animation renders from Step 10, optional `master.srt`.

**Outputs / artifacts:** composed video — by default `final.mp4` at `<videos_dir>/edit/final.mp4` (`SKILL.md:55`); also `master.srt` at `<videos_dir>/edit/master.srt` when `--build-subtitles` is passed (`SKILL.md:52`, `SKILL.md:78`).

**Conventions / hard rules at this step:**

- Hard Rule 1: "Subtitles are applied LAST in the filter chain, after every overlay. Otherwise overlays hide captions. Silent failure." (`SKILL.md:22`)
- Hard Rule 2: "Per-segment extract → lossless `-c copy` concat, not single-pass filtergraph. Otherwise you double-encode every segment when overlays are added." (`SKILL.md:23`)
- Hard Rule 3: "30ms audio fades at every segment boundary (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut." (`SKILL.md:24`)
- Hard Rule 4: "Overlays use `setpts=PTS-STARTPTS+T/TB` to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window." (`SKILL.md:25`)
- Hard Rule 5: "Master SRT uses output-timeline offsets: `output_time = word.start - segment_start + segment_offset`. Otherwise captions misalign after segment concat." (`SKILL.md:26`)
- Subtitle reasoning axes (canon): "Subtitles have three dimensions worth reasoning about: **chunking** (1/2/3/sentence per line), **case** (UPPER/Title/Natural), and **placement** (margin from bottom). The right combo depends on content." (`SKILL.md:180`)
- `bold-overlay` worked style — "short-form tech launch, fast-paced social. 2-word chunks, UPPERCASE, break on punctuation, Helvetica 18 Bold, white-on-outline, `MarginV=35`. `render.py` ships with this as `SUB_FORCE_STYLE`." (`SKILL.md:184`) Verbatim ASS force_style block:

  ```
  FontName=Helvetica,FontSize=18,Bold=1,
  PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,
  BorderStyle=1,Outline=2,Shadow=0,
  Alignment=2,MarginV=35
  ```
  (`SKILL.md:186-191`)
- `natural-sentence` alternative style (if invented): "narrative, documentary, education. 4–7 word chunks, sentence case, break on natural pauses, `MarginV=60–80`, larger font for readability, slightly wider max-width. No shipped force_style — design one if you need it." (`SKILL.md:193`)
- "Invent a third style if neither fits. Hard rules: subtitles LAST (Rule 1), output-timeline offsets (Rule 5)." (`SKILL.md:194-195`)
- Output spec defaults: `render.py` defaults the scale to 1080p from any source (`SKILL.md:266`).

**Quality checks:** none additional beyond `render.py`'s own execution — explicit verification happens at Step 14 (Self-eval).

**Sub-agent dispatches:** None.

**Transition rule to next step:** the composed render exists; proceed to preview.

---

## Step 13: Preview

**Canon source:** `SKILL.md:90`, `SKILL.md:78`

**Verbatim canon text:**

```
6. **Preview.** `render.py --preview`.
```

From Helpers:

```
- **`render.py <edl.json> -o <out>`** — per-segment extract → concat → overlays (PTS-shifted) → subtitles LAST. `--preview` for 720p fast. `--build-subtitles` to generate master.srt inline.
```

**Inputs:** `<videos_dir>/edit/edl.json` plus the per-segment extracts and overlays from prior steps.

**Outputs / artifacts:** `<videos_dir>/edit/preview.mp4` — "720p fast" (`SKILL.md:78`, `SKILL.md:54`).

**Conventions / hard rules at this step:** All hard rules 1-5 still apply (they are properties of `render.py`); `--preview` adjusts scale/quality, not the filter contract.

**Quality checks:** none here — the prescribed verification is the self-eval at Step 14.

**Sub-agent dispatches:** None.

**Transition rule to next step:** `preview.mp4` exists; proceed to self-eval.

---

## Step 14: Self-eval (before showing the user)

**Canon source:** `SKILL.md:91-99`

**Verbatim canon text:**

```
7. **Self-eval (before showing the user).** Run `timeline_view` on the **rendered output** (not the sources) at every cut boundary (±1.5s window). Check each image for:
   - Visual discontinuity / flash / jump at the cut
   - Waveform spike at the boundary (audio pop that slipped past the 30ms fade)
   - Subtitle hidden behind an overlay (Rule 1 violation)
   - Overlay misaligned or showing wrong frames (Rule 4 violation)

   Also sample: first 2s, last 2s, and 2–3 mid-points — check grade consistency, subtitle readability, overall coherence. Run `ffprobe` on the output to verify duration matches the EDL expectation.

   If anything fails: fix → re-render → re-eval. **Cap at 3 self-eval passes** — if issues remain after 3, flag them to the user rather than looping forever. Only present the preview once the self-eval passes.
```

**Inputs:** the rendered preview (`preview.mp4`), the EDL's expected `total_duration_s`, the list of cut boundaries from `ranges`.

**Outputs / artifacts:** filmstrip + waveform PNGs under `<videos_dir>/edit/verify/` (`SKILL.md:53`), plus an internal pass/fail per criterion.

**Conventions / hard rules at this step:**

- Run on the rendered output, NOT the sources (`SKILL.md:91`).
- Window: ±1.5s around every cut boundary (`SKILL.md:91`).
- Check list explicitly cross-references Hard Rule 1 (subtitle hiding) and Hard Rule 4 (overlay alignment) (`SKILL.md:94-95`).
- Also sample first 2s, last 2s, and 2-3 mid-points for grade consistency, subtitle readability, overall coherence (`SKILL.md:97`).
- `ffprobe` the output to verify duration matches the EDL expectation (`SKILL.md:97`).
- Cap at 3 self-eval passes; if issues remain, flag to the user rather than loop forever (`SKILL.md:99`).
- Principle 7: "Verify your own output before showing it to the user. If you wouldn't ship it, don't present it." (`SKILL.md:16`)

**Quality checks:** all of the above are the checks.

**Sub-agent dispatches:** None.

**Transition rule to next step:** self-eval passes (or after 3 passes the agent flags remaining issues to the user); proceed to iterate + persist.

---

## Step 15: Iterate + persist

**Canon source:** `SKILL.md:100`, `SKILL.md:291-304`

**Verbatim canon text:**

```
8. **Iterate + persist.** Natural-language feedback, re-plan, re-render. Never re-transcribe. Final render on confirmation. Append to `project.md`.
```

From "Memory — `project.md`":

```
Append one section per session at `<edit>/project.md`:

```markdown
## Session N — YYYY-MM-DD

**Strategy:** one paragraph describing the approach
**Decisions:** take choices, cuts, grades, animations + why
**Reasoning log:** one-line rationale for non-obvious decisions
**Outstanding:** deferred items
```

On startup, read `project.md` if it exists and summarize the last session in one sentence before asking whether to continue.
```

**Inputs:** the user's natural-language feedback on the preview, the prior strategy and EDL.

**Outputs / artifacts:**

- Updated `edl.json` and re-rendered outputs (`preview.mp4`, ultimately `final.mp4` on confirmation).
- A new appended session section in `<videos_dir>/edit/project.md` (`SKILL.md:46`, `SKILL.md:293`).

**Conventions / hard rules at this step:**

- "Never re-transcribe." (`SKILL.md:100`) — reinforces Hard Rule 9 (`SKILL.md:30`).
- "Final render on confirmation." (`SKILL.md:100`)
- Session memory shape: `Strategy / Decisions / Reasoning log / Outstanding` (`SKILL.md:295-301`).
- Startup convention: "read `project.md` if it exists and summarize the last session in one sentence before asking whether to continue." (`SKILL.md:304`)
- Principle 3: "Ask → confirm → execute → iterate → persist." (`SKILL.md:12`)

**Quality checks:** the iteration loop re-uses Step 14 self-eval; no new checks introduced.

**Sub-agent dispatches:** None.

**Transition rule to next step:** N/A — this is the terminal step. The next session begins by reading `project.md` on startup (`SKILL.md:304`), returning to Step 0.

---

## Appendix — Conventions index

Cross-reference of every Hard Rule and named convention to the step that introduces or applies it.

### Hard Rules (`SKILL.md:18-33`)

- **Hard Rule 1** — Subtitles applied LAST in the filter chain (`SKILL.md:22`). Applied at Step 12.
- **Hard Rule 2** — Per-segment extract → lossless `-c copy` concat (`SKILL.md:23`). Applied at Steps 11, 12.
- **Hard Rule 3** — 30ms audio fades at every segment boundary (`SKILL.md:24`). Applied at Step 12.
- **Hard Rule 4** — Overlays use `setpts=PTS-STARTPTS+T/TB` (`SKILL.md:25`). Applied at Step 12.
- **Hard Rule 5** — Master SRT uses output-timeline offsets (`SKILL.md:26`). Applied at Step 12.
- **Hard Rule 6** — Never cut inside a word; snap to Scribe word boundaries (`SKILL.md:27`). Applied at Step 8.
- **Hard Rule 7** — Pad every cut edge, working window 30–200ms (`SKILL.md:28`). Applied at Step 8.
- **Hard Rule 8** — Word-level verbatim ASR only; never SRT/phrase mode; never normalized fillers (`SKILL.md:29`). Applied at Step 2.
- **Hard Rule 9** — Cache transcripts per source; never re-transcribe unless source changed (`SKILL.md:30`). Applied at Steps 2, 15.
- **Hard Rule 10** — Parallel sub-agents for multiple animations; never sequential (`SKILL.md:31`). Applied at Step 10.
- **Hard Rule 11** — Strategy confirmation before execution (`SKILL.md:32`). Applied at Step 7.
- **Hard Rule 12** — All session outputs in `<videos_dir>/edit/`; never write inside the `video-use/` project directory (`SKILL.md:33`). Applied at Steps 2, 3, 8, 10, 11, 12, 13, 15.

### Principles (`SKILL.md:8-16`)

- **Principle 1** — LLM reasons from raw transcript + on-demand visuals; `takes_packed.md` is the only derived artifact (`SKILL.md:10`). Applied at Steps 3, 4, 8, 9.
- **Principle 2** — Audio is primary, visuals follow; drill into visuals only at decision points (`SKILL.md:11`). Applied at Steps 4, 9.
- **Principle 3** — Ask → confirm → execute → iterate → persist (`SKILL.md:12`). Applied at Steps 6, 7, 15.
- **Principle 4** — Generalize; look, ask, then edit (`SKILL.md:13`). Applied at Step 6.
- **Principle 5** — Artistic freedom is the default; only the Hard Rules are mandatory (`SKILL.md:14`). Applied at every taste-call step.
- **Principle 6** — Invent freely (`SKILL.md:15`). Applied at Steps 10, 11, 12 (any technique format supports).
- **Principle 7** — Verify your own output before showing it to the user (`SKILL.md:16`). Applied at Step 14.

### Cut craft conventions (`SKILL.md:102-110`)

- Audio-first candidate cuts from word boundaries and silence gaps (`SKILL.md:104`). Step 8.
- Preserve peaks; extend past punchlines (`SKILL.md:105`). Step 8.
- Speaker handoffs: 400–600ms air, taste-dependent (`SKILL.md:106`). Step 8.
- Audio events `(laughs)`/`(sighs)`/`(applause)` mark beats (`SKILL.md:107`). Step 8.
- Silence gaps ≥400ms cleanest; 150–400ms usable with visual check; <150ms unsafe (`SKILL.md:108`). Step 8.
- Example launch padding 50ms/80ms inside the 30–200ms window (`SKILL.md:109`). Step 8.
- "Never reason audio and video independently." (`SKILL.md:110`). Step 8.

### Animation conventions (`SKILL.md:216-237`)

- Sync-to-narration: 3s floor, 5–7s simple cards, 8–14s complex (`SKILL.md:218`). Step 10.
- Beat-synced accents: 0.5–2s, recognizable rather than fully parseable (`SKILL.md:219`). Step 10.
- Hold the final frame ≥ 1s before the cut (universal) (`SKILL.md:220`). Step 10.
- Over voiceover: total duration ≥ narration_length + 1s (universal) (`SKILL.md:221`). Step 10.
- Never parallel-reveal independent elements (`SKILL.md:222`). Step 10.
- Animation payoff timing: start overlay `reveal_duration` earlier so landing coincides with payoff word (`SKILL.md:224`). Step 10.
- Easing: never `linear`; `ease_out_cubic` for single reveals, `ease_in_out_cubic` for continuous draws (`SKILL.md:226-235`). Step 10.
- Typing text anchor: center on FULL string width, not partial (`SKILL.md:237`). Step 10.

### Subtitle conventions (`SKILL.md:178-195`)

- Three dimensions: chunking, case, placement (`SKILL.md:180`). Step 12.
- `bold-overlay` style ships in `render.py` as `SUB_FORCE_STYLE` (`SKILL.md:184`). Step 12.
- Subtitles LAST (Rule 1), output-timeline offsets (Rule 5) (`SKILL.md:195`). Step 12.

### Grade conventions (`SKILL.md:164-176`)

- Reason about the image, not apply a preset (`SKILL.md:164`). Step 11.
- ASC CDL mental model: per channel `out = (in * slope + offset) ** power`, then global saturation (`SKILL.md:166`). Step 11.
- Apply per-segment during extraction, not post-concat (`SKILL.md:176`). Step 11.
- Never go aggressive without testing skin tones (`SKILL.md:176`). Step 11.

### Anti-patterns (`SKILL.md:306-322`)

- Hierarchical pre-computed codec formats (`SKILL.md:310`).
- Hand-tuned moment-scoring functions (`SKILL.md:311`).
- Whisper SRT / phrase-level output (`SKILL.md:312`).
- Running Whisper locally on CPU (`SKILL.md:313`).
- Burning subtitles into base before compositing overlays (`SKILL.md:314`).
- Single-pass filtergraph with overlays (`SKILL.md:315`).
- Linear animation easing (`SKILL.md:316`).
- Hard audio cuts at segment boundaries (`SKILL.md:317`).
- Typing text centered on the partial string (`SKILL.md:318`).
- Sequential sub-agents for multiple animations (`SKILL.md:319`).
- Editing before confirming the strategy (`SKILL.md:320`).
- Re-transcribing cached sources (`SKILL.md:321`).
- Assuming what kind of video it is (`SKILL.md:322`).
