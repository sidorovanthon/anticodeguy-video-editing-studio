# hyperframes canonical algorithm
Canon snapshot: `~/repos/hyperframes/` @ `a4c4b2ff033cecd0bb50dae3b56e2c4a38b08d68` (2026-05-23)
Source root: `skills/hyperframes/SKILL.md`

This document describes, step by step, what the canonical `hyperframes` agent does inside the framework, in canon's own order and with canon's own conventions. Every claim is anchored to a verbatim quote from canon at `path:line`. The spine is `skills/hyperframes/SKILL.md` "Approach" + numbered Steps + "Output Checklist" + "Quality Checks". Multi-action canonical sentences are expanded per the granularity rule (each discrete action gets its own step).

All path citations are relative to the snapshot commit. `SKILL.md` in citations refers to `skills/hyperframes/SKILL.md`. Reference files cited from SKILL.md are quoted at `skills/hyperframes/references/<file>.md:line`.

---

## Step 0: Discovery (exploratory requests only)

**Canon source:** `SKILL.md:12-23`

**Verbatim canon text:**

```
### Discovery (exploratory requests only)

For open-ended requests ("make me a product launch video", "create something for our brand") where the user hasn't committed to a direction, understand intent before picking colors:

- **Audience** — who watches this? Developers? Executives? General consumers?
- **Platform** — where does it play? Social (15s), website hero, product demo, internal?
- **Priority** — what matters most? Motion quality? Content accuracy? Brand fidelity? Speed?
- **Variations** — does the user want options, or a single best shot?

For specific requests ("add a title card", "fix the timing on scene 3"), skip discovery.

For exploratory requests, consider offering 2-3 variations that differ meaningfully — not just color swaps, but different pacing, energy levels, or structural approaches. One safe/expected, one ambitious. Don't mandate this — it's a tool available when appropriate.
```

**Inputs:** the user's prompt (its specificity determines whether discovery runs).

**Outputs / artifacts:** answers to Audience / Platform / Priority / Variations recorded in conversation context (`SKILL.md:16-19`).

**Conventions / hard rules at this step:**

- Discovery only runs for open-ended requests; "For specific requests… skip discovery." (`SKILL.md:21`)
- Optional 2-3 meaningfully-different variations may be offered for exploratory requests; not mandated (`SKILL.md:23`).

**Quality checks:** None canonically prescribed.

**Sub-agent dispatches:** None.

**Transition rule to next step:** intent is clear enough to begin; proceed to Step 1.

---

## Step 1: Design system — read existing `design.md` if present

**Canon source:** `SKILL.md:25-29`

**Verbatim canon text:**

```
### Step 1: Design system

If `design.md` or `DESIGN.md` exists in the project, read it first (check both casings — they're different files on Linux). It's the source of truth for brand colors, fonts, and constraints. Use its exact values — don't invent colors or substitute fonts. Any format works (YAML frontmatter, prose, tables — just extract the values).

If it names fonts you can't find locally (no `fonts/` directory with `.woff2` files, not a built-in font), warn the user before writing HTML: "design.md specifies [font name] but no font files found. Please add .woff2 files to `fonts/` or I'll fall back to [closest built-in alternative]."
```

**Inputs:** project root — checked for both `design.md` and `DESIGN.md` (`SKILL.md:27`).

**Outputs / artifacts:** extracted brand values (colors, fonts, constraints) held in agent context. If a named font lacks `.woff2` files, a pre-HTML warning to the user (`SKILL.md:29`).

**Conventions / hard rules at this step:**

- "Check both casings — they're different files on Linux." (`SKILL.md:27`)
- "Use its exact values — don't invent colors or substitute fonts." (`SKILL.md:27`)
- Pre-HTML font warning is mandatory when named fonts are not locally available (`SKILL.md:29`).
- "design.md defines the brand. It does not define video composition rules. Those come from [references/video-composition.md](references/video-composition.md) and [house-style.md](./house-style.md). Use brand colors at video-appropriate scale — not at web-UI opacity." (`SKILL.md:37`)

**Quality checks:** None at this step; design adherence is verified later — see Step 20.

**Sub-agent dispatches:** None.

**Transition rule to next step:** `design.md` is read (or confirmed absent); proceed to Step 2 if present, or to Step 1b otherwise.

---

## Step 1b: Design system — offer choice when no `design.md` exists

**Canon source:** `SKILL.md:31-37`

**Verbatim canon text:**

```
If no `design.md` exists, offer the user a choice:

1. **User named a style or mood?** → Read [visual-styles.md](./visual-styles.md) for the 8 named presets. Pick the closest match.
2. **Want to browse options visually?** → Run the design picker: read [references/design-picker.md](references/design-picker.md) for the full workflow. This serves a visual picker page. The user configures mood, palette, typography, and motion in the browser, then copies the generated design.md and pastes it back into the conversation.
3. **Want to skip and go fast?** → Ask: mood, light or dark, any brand colors/fonts? Then pick a palette from [house-style.md](./house-style.md).

**design.md defines the brand. It does not define video composition rules.** Those come from [references/video-composition.md](references/video-composition.md) and [house-style.md](./house-style.md). Use brand colors at video-appropriate scale — not at web-UI opacity.
```

**Inputs:** the user's answer to the three-way choice.

**Outputs / artifacts:** either a matched preset from `visual-styles.md` (8 named presets — `SKILL.md:33`), a freshly-pasted `design.md` from the visual picker (`SKILL.md:34`), or an in-conversation palette selection backed by `house-style.md` (`SKILL.md:35`).

**Conventions / hard rules at this step:**

- The three paths are the canon-prescribed branches; do not invent a fourth (`SKILL.md:31-35`).
- `house-style.md` is the no-design.md fallback for aesthetic defaults: "If no `design.md` exists, follow [house-style.md](./house-style.md) for aesthetic defaults." (`SKILL.md:359`)

**Quality checks:** None.

**Sub-agent dispatches:** None.

**Transition rule to next step:** a visual identity is established; proceed to Step 2.

---

## Step 2: Prompt expansion

**Canon source:** `SKILL.md:39-43`

**Verbatim canon text:**

```
### Step 2: Prompt expansion

Always run on every composition (except single-scene pieces and trivial edits). This step grounds the user's intent against `design.md` and `house-style.md` and produces a consistent intermediate that every downstream agent reads the same way.

Read [references/prompt-expansion.md](references/prompt-expansion.md) for the full process and output format.
```

**Inputs:** the user's intent (from prompt + Discovery answers), plus four prerequisite reads required before generating (`references/prompt-expansion.md:9-16`):

- **Pre-action 1** — read `DESIGN.md` (if it exists): "extract brand colors, fonts, mood, and constraints. The expansion cites these exact values (hex codes, font names); it does not invent new ones." (`prompt-expansion.md:11`)
- **Pre-action 2** — read `beat-direction.md`: "per-beat planning format (concept, mood, choreography verbs, transitions, depth layers, rhythm). The expansion outputs each scene using this format." (`prompt-expansion.md:12`)
- **Pre-action 3** — read `video-composition.md`: "video-medium rules for density, scale, and color presence. The expansion applies these automatically." (`prompt-expansion.md:13`)
- **Pre-action 4** — read `../house-style.md`: "its rules for Background Layer (2-5 decoratives), Color, Motion, Typography apply to every scene. The expansion writes output that conforms to them." (`prompt-expansion.md:14`)

If `DESIGN.md` doesn't exist yet, run Step 1 (Design system) first — "Expansion without a design context produces generic scene breakdowns that later agents ignore." (`prompt-expansion.md:16`)

**Outputs / artifacts:** the expanded prompt is written to `.hyperframes/expanded-prompt.md` in the project directory — the canonical output path (`prompt-expansion.md:58-60`): "Write the expanded prompt to `.hyperframes/expanded-prompt.md` in the project directory. Do NOT dump it into the chat — it will be hundreds of lines." The file contains six required sections (`prompt-expansion.md:38-56`):

- **Output section 1 — Title + style block.** "cite design.md's exact hex values, font names, and mood. Do NOT invent a palette — quote what the design provides." (`prompt-expansion.md:41`)
- **Output section 2 — Rhythm declaration.** "name the scene rhythm before detailing any scene. Example: `hook-PUNCH-breathe-CTA` or `slow-build-BUILD-PEAK-breathe-CTA`. Derive the rhythm from the brand and the storyboard's emotional arc — see [beat-direction.md] for the considerations that drive this decision." (`prompt-expansion.md:43`)
- **Output section 3 — Global rules.** "parallax layers, micro-motion requirements, transition style, primary + accent transitions. Match energy to mood (calm → slow eases, high → snappy eases)." (`prompt-expansion.md:45`)
- **Output section 4 — Per-scene beats in beat-direction format.** Each scene includes (`prompt-expansion.md:48-52`):
  - **Concept** — "the big idea in 2-3 sentences. What visual WORLD? What metaphor? What should the viewer FEEL?"
  - **Mood direction** — "cultural/design references, not hex codes. (\"Bauhaus color studies\", \"cinematic title sequence\", \"editorial calm\")"
  - **Depth layers** — "BG (2-5 decoratives with ambient motion), MG (content), FG (accents, structural elements, micro-details). 8-10 total elements per scene per video-composition.md."
  - **Animation choreography** — "specific verbs per element. High: SLAMS, CRASHES. Medium: CASCADE, SLIDES. Low: floats, types on, counts up. Every element gets a verb. If you can't name the verb, the element is not yet designed."
  - **Transition out** — "shader or CSS, with specific type and parameters. Not \"crossfade\" but \"blur crossfade, 0.4s, power2.inOut.\""
- **Output section 5 — Recurring motifs.** "visual threads across scenes from the brand palette." (`prompt-expansion.md:54`)
- **Output section 6 — Negative prompt.** "what to avoid, informed by design.md's constraints if present." (`prompt-expansion.md:56`)

**Conventions / hard rules at this step:**

- "Always run on every composition (except single-scene pieces and trivial edits)." (`SKILL.md:41`)
- "Do not skip. Do not pass through. Single-scene compositions and trivial edits are the only exceptions." (`prompt-expansion.md:35`)
- "The expansion is never pass-through. Every user prompt — no matter how detailed — is a _seed_." (`prompt-expansion.md:20`)
- Canonical output path is `.hyperframes/expanded-prompt.md` — "Do NOT dump it into the chat — it will be hundreds of lines." (`prompt-expansion.md:60`)

**Quality checks:** None mechanical; verification is the user-approval gate at Step 2b.

**Sub-agent dispatches:** None explicitly named in SKILL.md at this step; the expansion's role is to give downstream agents a shared intermediate (`SKILL.md:41`).

**Transition rule to next step:** the expanded intermediate exists on disk at `.hyperframes/expanded-prompt.md`; proceed to Step 2b (await approval).

---

## Step 2b: Await prompt-expansion approval

**Canon source:** `references/prompt-expansion.md:58-68`

**Verbatim canon text:**

```
Write the expanded prompt to `.hyperframes/expanded-prompt.md` in the project directory. Do NOT dump it into the chat — it will be hundreds of lines.

Tell the user:

> "I've expanded your prompt into a full production breakdown. Review it here: `.hyperframes/expanded-prompt.md`
>
> It has [N] scenes across [duration] seconds with specific visual elements, transitions, and pacing. Edit anything you want, then let me know when you're ready to proceed."

Only move to construction after the user approves or says to continue.
```

**Inputs:** the just-written `.hyperframes/expanded-prompt.md` from Step 2.

**Outputs / artifacts:** an explicit user approval (or edits + approval). No new file produced; the gate is a conversational checkpoint.

**Conventions / hard rules at this step:**

- The verbatim approval message above is the canonical hand-off — quote `.hyperframes/expanded-prompt.md` by path, state `[N] scenes` and `[duration] seconds`, invite edits (`prompt-expansion.md:64-66`).
- "Only move to construction after the user approves or says to continue." (`prompt-expansion.md:68`) — WAIT for approval; do not proceed.

**Quality checks:** the user's review serves as the check.

**Sub-agent dispatches:** None.

**Transition rule to next step:** user approves (or says continue); proceed to Step 3.

---

## Step 3: Plan — What

**Canon source:** `SKILL.md:45-56` (item 1)

**Verbatim canon text:**

```
### Step 3: Plan

Before writing HTML, think at a high level:

1. **What** — what should the viewer experience? Identify the narrative arc, key moments, and emotional beats.
```

**Inputs:** the prompt-expansion intermediate from Step 2, the brand identity from Step 1/1b.

**Outputs / artifacts:** an identified narrative arc, key moments, and emotional beats — held in plan notes (`SKILL.md:49`).

**Conventions / hard rules at this step:**

- "Build what was asked. A request for 'a title card' is not a request for 'a title card + 3 supporting scenes + ambient music + captions.' Every scene, every element, every tween should earn its place. If additional scenes or elements would genuinely improve the piece, propose them — don't add them." (`SKILL.md:56`)

**Quality checks:** None.

**Sub-agent dispatches:** None.

**Transition rule to next step:** the narrative shape is clear; proceed to Structure.

---

## Step 4: Plan — Structure

**Canon source:** `SKILL.md:50`

**Verbatim canon text:**

```
2. **Structure** — how many compositions, which are sub-compositions vs inline, what tracks carry what (video, audio, overlays, captions).
```

**Inputs:** the narrative arc from Step 3.

**Outputs / artifacts:** decisions about composition count, sub-composition vs inline, and what each track carries.

**Conventions / hard rules at this step:**

- Sub-compositions loaded via `data-composition-src` use a `<template>` wrapper; standalone compositions (the main `index.html`) do NOT use `<template>` — they put the `data-composition-id` div directly in `<body>` (`SKILL.md:168`).
- Track convention: `data-track-index` is Integer; "Same-track clips cannot overlap." (`SKILL.md:143`)
- "`data-track-index` does **not** affect visual layering — use CSS `z-index`." (`SKILL.md:147`)

**Quality checks:** None at this step.

**Sub-agent dispatches:** None.

**Transition rule to next step:** structure decided; proceed to Rhythm.

---

## Step 5: Plan — Rhythm

**Canon source:** `SKILL.md:51`

**Verbatim canon text:**

```
3. **Rhythm** — declare your scene rhythm before implementing. Which scenes are quick hits, which are holds, where do shaders land, where does energy peak. Name the pattern: fast-fast-SLOW-fast-SHADER-hold. Read [references/beat-direction.md](references/beat-direction.md) for rhythm templates.
```

**Inputs:** the structure decisions from Step 4.

**Outputs / artifacts:** a named rhythm pattern (e.g. "fast-fast-SLOW-fast-SHADER-hold") (`SKILL.md:51`).

**Conventions / hard rules at this step:**

- "Declare your scene rhythm before implementing." (`SKILL.md:51`)
- "Always read for multi-scene compositions" applies to `references/beat-direction.md` (`SKILL.md:473`).

**Quality checks:** None.

**Sub-agent dispatches:** None.

**Transition rule to next step:** rhythm pattern declared; proceed to Timing.

---

## Step 6: Plan — Timing

**Canon source:** `SKILL.md:52`

**Verbatim canon text:**

```
4. **Timing** — which clips drive the duration, where do transitions land, what's the pacing.
```

**Inputs:** the rhythm from Step 5, plus the set of clips/scenes from Step 4.

**Outputs / artifacts:** assignment of duration drivers per clip; transition landing positions; pacing decisions.

**Conventions / hard rules at this step:**

- Timeline contract: "Duration comes from `data-duration`, not from GSAP timeline length" (`SKILL.md:292`).
- Composition clips: "`data-duration` Yes Takes precedence over GSAP timeline duration" (`SKILL.md:155`).

**Quality checks:** None at this step.

**Sub-agent dispatches:** None.

**Transition rule to next step:** timing/transition landings planned; proceed to Layout.

---

## Step 7: Plan — Layout (build end-state first)

**Canon source:** `SKILL.md:53`, `SKILL.md:64-132`

**Verbatim canon text:**

```
5. **Layout** — build the end-state first. See "Layout Before Animation" below.
```

From "Layout Before Animation":

```
Position every element where it should be at its **most visible moment** — the frame where it's fully entered, correctly placed, and not yet exiting. Write this as static HTML+CSS first. No GSAP yet.

**Why this matters:** If you position elements at their animated start state (offscreen, scaled to 0, opacity 0) and tween them to where you think they should land, you're guessing the final layout. Overlaps are invisible until the video renders. By building the end state first, you can see and fix layout problems before adding any motion.

### The process

1. **Identify the hero frame** for each scene — the moment when the most elements are simultaneously visible. This is the layout you build.
2. **Write static CSS** for that frame. The `.scene-content` container MUST fill the full scene using `width: 100%; height: 100%; padding: Npx;` with `display: flex; flex-direction: column; gap: Npx; box-sizing: border-box`. Use padding to push content inward — NEVER `position: absolute; top: Npx` on a content container. Absolute-positioned content containers overflow when content is taller than the remaining space. Reserve `position: absolute` for decoratives only.
3. **Add entrances with `gsap.from()`** — animate FROM offscreen/invisible TO the CSS position. The CSS position is the ground truth; the tween describes the journey to get there. (In sub-compositions loaded via `data-composition-src`, prefer `gsap.fromTo()` — see load-bearing GSAP rules in [references/motion-principles.md](references/motion-principles.md).)
4. **Add exits with `gsap.to()`** — animate TO offscreen/invisible FROM the CSS position.
```

**Inputs:** the per-scene "most visible moment" — the hero frame.

**Outputs / artifacts:** static HTML+CSS for each scene's hero frame. No GSAP yet (`SKILL.md:66`).

**Conventions / hard rules at this step:**

- Identify the hero frame per scene (`SKILL.md:72`).
- `.scene-content` MUST fill the full scene with `width: 100%; height: 100%; padding: Npx; display: flex; flex-direction: column; gap: Npx; box-sizing: border-box`. Use padding — NEVER `position: absolute; top: Npx` on a content container. "Reserve `position: absolute` for decoratives only." (`SKILL.md:73`)
- "The CSS position is the ground truth; the tween describes the journey to get there." (`SKILL.md:74`)
- "If element A exits before element B enters in the same area, both should have correct CSS positions for their respective hero frames." (`SKILL.md:128`)
- Intentional overlap is layered effects (glow, shadow, background patterns) and z-stacked designs; the layout step catches unintentional overlap (`SKILL.md:132`).
- **Scene structure: build, breathe, resolve** (`motion-principles.md:39-46`): "Every scene has three phases. The most common failure is dumping everything into the build and leaving nothing for the other two."
  - **Build (0–30%)** — "elements enter, staggered. Not all at once." (`motion-principles.md:43`)
  - **Breathe (30–70%)** — "content visible, alive with one ambient motion. The viewer reads, registers, settles." (`motion-principles.md:44`)
  - **Resolve (70–100%)** — "exit or decisive end. Exits are faster than entrances (see Asymmetry below)." (`motion-principles.md:45`)

**Quality checks:** None until the inspect/validate phase (Steps 17-19); the layout-step rationale is that overlap is invisible until render unless caught here (`SKILL.md:68`).

**Sub-agent dispatches:** None.

**Transition rule to next step:** every scene has a static hero-frame layout; proceed to Animate.

---

## Step 8: Plan — Animate — entrances with `gsap.from()`

**Canon source:** `SKILL.md:54`, `SKILL.md:74`, `SKILL.md:114-124`

**Verbatim canon text:**

```
6. **Animate** — then add motion using the rules below.
```

From the layout-process step 3:

```
3. **Add entrances with `gsap.from()`** — animate FROM offscreen/invisible TO the CSS position. The CSS position is the ground truth; the tween describes the journey to get there. (In sub-compositions loaded via `data-composition-src`, prefer `gsap.fromTo()` — see load-bearing GSAP rules in [references/motion-principles.md](references/motion-principles.md).)
```

Example:

```js
// Step 3: Animate INTO those positions
tl.from(".title", { y: 60, opacity: 0, duration: 0.6, ease: "power3.out" }, 0);
tl.from(".subtitle", { y: 40, opacity: 0, duration: 0.5, ease: "power3.out" }, 0.2);
tl.from(".logo", { scale: 0.8, opacity: 0, duration: 0.4, ease: "power2.out" }, 0.3);
```

**Inputs:** the static layouts from Step 7.

**Outputs / artifacts:** entrance tweens added to the GSAP timeline.

**Conventions / hard rules at this step:**

- "Every element animates IN via `gsap.from()`. No element may appear fully-formed. If a scene has 5 elements, it needs 5 entrance tweens." (`SKILL.md:326`)
- In sub-compositions loaded via `data-composition-src`, prefer `gsap.fromTo()` (`SKILL.md:74`).
- "Offset first animation 0.1-0.3s (not t=0)" (`SKILL.md:352`).
- "Vary eases across entrance tweens — use at least 3 different eases per scene" (`SKILL.md:353`).
- "Don't repeat an entrance pattern within a scene" (`SKILL.md:354`).
- All timelines start `{ paused: true }` — the player controls playback (`SKILL.md:289`).
- Register every timeline: `window.__timelines["<composition-id>"] = tl` (`SKILL.md:290`).
- Framework auto-nests sub-timelines — do NOT manually add them (`SKILL.md:291`).
- "Never create empty tweens to set duration" (`SKILL.md:293`).
- Deterministic: "No `Math.random()`, `Date.now()`, or time-based logic. Use a seeded PRNG if you need pseudo-random values (e.g. mulberry32)." (`SKILL.md:297`)
- GSAP: "Only animate visual properties (`opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms). Do NOT animate `visibility`, `display`, or call `video.play()`/`audio.play()`." (`SKILL.md:299`)
- "Never animate the same property on the same element from multiple timelines simultaneously." (`SKILL.md:301`)
- No `repeat: -1`: "Infinite-repeat timelines break the capture engine. Calculate the exact repeat count from composition duration: `repeat: Math.ceil(duration / cycleDuration) - 1`." (`SKILL.md:303`)
- Synchronous timeline construction: "Never build timelines inside `async`/`await`, `setTimeout`, or Promises. The capture engine reads `window.__timelines` synchronously after page load." (`SKILL.md:305`)
- **Load-Bearing GSAP Rule 1 — No iframes for captured content** (`motion-principles.md:93`): "Iframes do not seek deterministically with the timeline — the capture engine cannot scrub inside them, so they appear frozen (or blank) in the rendered output. If the source you're stylizing is a live web app, use the screenshots from `capture/` as stacked panels or layered images, not live embeds."
- **Load-Bearing GSAP Rule 2 — Never stack two transform tweens on the same element** (`motion-principles.md:95`): "A common failure: a `y` entrance plus a `scale` Ken Burns on the same `<img>`. The second tween's `immediateRender: true` writes the element's initial state at construction time, overwriting whatever the first tween set — leaving the element invisible or offscreen with no lint warning. A secondary mechanism: `tl.from()` resets to its declared 'from' state when the playhead is seeked past the timeline's end." Fix by combining into one `tl.fromTo()` or splitting across parent + child (`motion-principles.md:97-121`).
- **Load-Bearing GSAP Rule 3 — Prefer `tl.fromTo()` over `tl.from()` inside `.clip` scenes** (`motion-principles.md:123`): "`gsap.from()` sets `immediateRender: true` by default, which writes the 'from' state at timeline construction — before the `.clip` scene's `data-start` is active. Elements can flash visible, start from the wrong position, or skip their entrance entirely when the scene is seeked non-linearly (which the capture engine does). Explicit `fromTo` makes the state at every timeline position deterministic."

  ```js
  // BRITTLE: immediateRender interacts badly with scene boundaries
  tl.from(el, { opacity: 0, y: 50, duration: 0.6 }, t);

  // DETERMINISTIC: state is defined at both ends, no immediateRender surprise
  tl.fromTo(el, { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.6 }, t);
  ```
- **Load-Bearing GSAP Rule 4 — Ambient pulses must attach to the seekable `tl`, never bare `gsap.to()`** (`motion-principles.md:133`): "Auras, shimmers, gentle float loops, logo breathing — all of these must be added to the scene's timeline, not fired standalone. Standalone tweens run on wallclock time and do not scrub with the capture engine, so the effect is absent in the rendered video even though it looks correct in the studio preview."

  ```js
  // BAD: lives outside the timeline, never renders in capture
  gsap.to(".aura", { scale: 1.08, yoyo: true, repeat: 5, duration: 1.2 });

  // GOOD: seekable, deterministic, renders
  tl.to(".aura", { scale: 1.08, yoyo: true, repeat: 5, duration: 1.2 }, 0);
  ```
- **Hard-kill at every scene boundary** (`motion-principles.md:143`): "The same hard-kill pattern from `captions.md` generalizes to all elements with exit animations: any element whose visibility changes at a beat boundary needs a deterministic `tl.set()` kill after its fade, because later tweens on the same element (or `immediateRender` from a sibling tween) can resurrect it."

  ```js
  tl.to(el, { opacity: 0, duration: 0.3 }, beatEnd);
  tl.set(el, { opacity: 0, visibility: "hidden" }, beatEnd + 0.3); // deterministic kill
  ```

**Quality checks:** Animation Map run later (Step 21) verifies choreography.

**Sub-agent dispatches:** None.

**Transition rule to next step:** entrances exist for every element in every scene; proceed to exits and transitions.

---

## Step 9: Plan — Animate — exits (final scene only)

**Canon source:** `SKILL.md:75`, `SKILL.md:321-348`

**Verbatim canon text:**

```
4. **Add exits with `gsap.to()`** — animate TO offscreen/invisible FROM the CSS position.
```

From "Scene Transitions (Non-Negotiable)":

```
Every multi-scene composition MUST follow ALL of these rules. Violating any one of them is a broken composition.

1. **ALWAYS use transitions between scenes.** No jump cuts. No exceptions.
2. **ALWAYS use entrance animations on every scene.** Every element animates IN via `gsap.from()`. No element may appear fully-formed. If a scene has 5 elements, it needs 5 entrance tweens.
3. **NEVER use exit animations** except on the final scene. This means: NO `gsap.to()` that animates opacity to 0, y offscreen, scale to 0, or any other "out" animation before a transition fires. The transition IS the exit. The outgoing scene's content MUST be fully visible at the moment the transition starts.
4. **Final scene only:** The last scene may fade elements out (e.g., fade to black). This is the ONLY scene where `gsap.to(..., { opacity: 0 })` is allowed.
```

**Inputs:** the timeline with entrances from Step 8.

**Outputs / artifacts:** exit tweens added ONLY for the final scene; for non-final scenes, scene change is left entirely to the transition (Step 10).

**Conventions / hard rules at this step:**

- Rule 3 — NEVER use exit animations except on the final scene. "The transition IS the exit. The outgoing scene's content MUST be fully visible at the moment the transition starts." (`SKILL.md:327`)
- Rule 4 — Final scene only may fade out (`SKILL.md:328`).
- Wrong example: exit tweens before transition empty the scene (`SKILL.md:332-336`).

**Quality checks:** Animation Map run later (Step 21) flags choreography issues.

**Sub-agent dispatches:** None.

**Transition rule to next step:** exits exist only on the final scene; proceed to transitions.

---

## Step 10: Plan — Animate — transitions between scenes

**Canon source:** `SKILL.md:321-348`, `SKILL.md:487-489`

**Verbatim canon text:**

```
## Scene Transitions (Non-Negotiable)

Every multi-scene composition MUST follow ALL of these rules. Violating any one of them is a broken composition.

1. **ALWAYS use transitions between scenes.** No jump cuts. No exceptions.
2. **ALWAYS use entrance animations on every scene.** Every element animates IN via `gsap.from()`. No element may appear fully-formed. If a scene has 5 elements, it needs 5 entrance tweens.
3. **NEVER use exit animations** except on the final scene. This means: NO `gsap.to()` that animates opacity to 0, y offscreen, scale to 0, or any other "out" animation before a transition fires. The transition IS the exit. The outgoing scene's content MUST be fully visible at the moment the transition starts.
4. **Final scene only:** The last scene may fade elements out (e.g., fade to black). This is the ONLY scene where `gsap.to(..., { opacity: 0 })` is allowed.
```

From the references list:

```
- **[references/transitions.md](references/transitions.md)** — Scene transitions: crossfades, wipes, reveals, shader transitions. Energy/mood selection, CSS vs WebGL guidance. **Always read for multi-scene compositions** — scenes without transitions feel like jump cuts.
  - [transitions/catalog.md](references/transitions/catalog.md) — Hard rules, scene template, and routing to per-type implementation code.
  - Shader transitions are in `@hyperframes/shader-transitions` (`packages/shader-transitions/`) — read package source, not skill files.
```

**Inputs:** the multi-scene timeline from Steps 8-9.

**Outputs / artifacts:** transition definitions placed between consecutive scenes; final RIGHT example pattern is entrance-only with the transition at the boundary (`SKILL.md:341-348`).

**Conventions / hard rules at this step:**

- Rule 1 — ALWAYS use transitions between scenes (`SKILL.md:325`).
- "Always read for multi-scene compositions" applies to `references/transitions.md` (`SKILL.md:487`).
- Shader transitions live in `@hyperframes/shader-transitions` package source, not skill files (`SKILL.md:489`).
- **Energy → Transition character calibration — three ranges** (`transitions.md:18-22`):
  - **Soft/organic character** — "transitions that breathe, dissolve, or drift. Nothing sharp, mechanical, or percussive. Duration 0.5–0.8s, smooth easing curves." (`transitions.md:18`)
  - **Directional/purposeful character** — "transitions that move content decisively. Clear direction, readable momentum. Duration 0.3–0.5s, clean deceleration." (`transitions.md:20`)
  - **Percussive/instant character** — "transitions that hit like a cut. Immediate, almost hard-cut energy. Duration 0.15–0.3s, aggressive or near-instant easing." (`transitions.md:22`)

  "Pick ONE character that defines the video's primary transitions, then use 1–2 contrasting moments as intentional accents." (`transitions.md:24`)

- **Mood → Motion quality — nine moods** (`transitions.md:30-40`). Verbatim table:

  | Mood                     | Motion quality that fits                                                                    | Why                                                                                 |
  | ------------------------ | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
  | **Warm / inviting**      | Soft edges, dissolving, color-temperature washes — nothing sharp, mechanical, or percussive | Warmth reads as continuity and flow; hard cuts or compression feel cold             |
  | **Cold / clinical**      | Mechanical transformation — compression, slicing, gridding, precision                       | The content appears to be processed or structured, reinforcing a systematic quality |
  | **Editorial / magazine** | Clean directional movement — like turning a page                                            | Feels like content is being browsed or curated, not revealed                        |
  | **Tech / futuristic**    | Data-like fragmentation, digital displacement, scan artifacts                               | Transition feels computational rather than physical                                 |
  | **Tense / edgy**         | Instability, distortion, displacement — something slightly wrong about the image            | Introduces friction where smooth transitions would release tension                  |
  | **Playful / fun**        | Overshoot, expansion, rotation — motion with personality and bounce                         | Transitions that feel like objects rather than effects                              |
  | **Dramatic / cinematic** | Scale, weight, light extremes — the cut is an event, not a bridge                           | Every shader and every hard cut carries narrative gravity                           |
  | **Premium / luxury**     | Restraint — transitions that are barely visible, or invisible                               | Luxury communicates through what it withholds                                       |
  | **Retro / analog**       | Organic imperfection — light bleed, scan lines, color wash                                  | Physical film artifacts; imperfection as authenticity                               |

- **Narrative Position — six named positions** (`transitions.md:48-53`):
  - **Opening** — "establishes the motion language for the entire video. Make a deliberate choice; whatever you pick here sets the viewer's expectation for everything that follows." (`transitions.md:48`)
  - **Between related points** — "should be almost invisible. The content is continuing; the transition shouldn't draw attention to itself. Consistency matters more than distinctiveness here." (`transitions.md:49`)
  - **Topic change** — "needs enough contrast from your primary that it signals 'something different is starting.' The contrast is in motion character, not just duration." (`transitions.md:50`)
  - **Climax / hero reveal** — "this is the moment the video has been building to. The transition should feel earned by what came before. 'Use your boldest transition here' is a default, not a rule — the climax of a restrained editorial piece might be a hard cut." (`transitions.md:51`)
  - **Wind-down** — "returns to a motion character that allows the viewer to exhale. Matches the opening in tone, not necessarily in technique." (`transitions.md:52`)
  - **Outro** — "no new energy. Slowest and simplest in the video. Closure." (`transitions.md:53`)
- **Blur and motion intensity — three calibration ranges** (`transitions.md:62-66`):
  - Soft/organic: blur 20–30px, duration 0.8–1.2s, hold 0.3–0.5s (`transitions.md:64`).
  - Directional/purposeful: blur 8–15px, duration 0.4–0.6s, hold 0.1–0.2s (`transitions.md:65`).
  - Percussive/instant: blur 3–6px, duration 0.2–0.3s, no hold (`transitions.md:66`).
- **Shader-Compatible CSS Rules — six** (`transitions.md:124-134`, apply only to shader-transition compositions):
  1. "No `transparent` keyword in gradients. Canvas interpolates `transparent` as `rgba(0,0,0,0)` (black at zero alpha), creating dark fringes. Always use the target color at zero alpha: `rgba(200,117,51,0)` not `transparent`." (`transitions.md:127`)
  2. "No gradient backgrounds on elements thinner than 4px. Canvas can't match CSS gradient rendering on 1-2px elements. Use solid `background-color` on thin accent lines." (`transitions.md:128`)
  3. "No CSS variables (`var()`) on elements visible during capture. html2canvas doesn't reliably resolve custom properties. Use literal color values in inline styles." (`transitions.md:129`)
  4. "Mark uncapturable decorative elements with `data-no-capture`. The capture function skips these. They're present on the live DOM but absent from the shader texture. Use for elements that can't follow the rules above." (`transitions.md:130`)
  5. "No gradient opacity below 0.15. Gradient elements below 10% opacity render differently in canvas vs CSS. Increase to 0.15+ or use a solid color at equivalent brightness." (`transitions.md:131`)
  6. "Every `.scene` div must have explicit `background-color`, AND pass the same color as `bgColor` in the `init()` config. The package captures scene elements via html2canvas. Both the CSS `background-color` on `.scene` and the `bgColor` config must match. Without either, the texture renders as black." (`transitions.md:132`)
- **Velocity-Matched Transitions** (`beat-direction.md:169-171`): "Exit the outgoing beat with an accelerating ease (power2.in or power3.in) plus a blur ramp. Enter the incoming beat with a decelerating ease (power2.out or power3.out) plus blur clear. The fastest point of both easing curves meets at the cut — the viewer perceives continuous camera motion, not two discrete animations. Match exit velocity to entry velocity within ~5% tolerance."
- **Catalog Hard Rule — Scene visibility** (`catalog.md:9`): "Scene 1 visible by default (no `opacity: 0`). Scenes 2+ have `opacity: 0` on the CONTAINER div. GSAP reveals them. No visibility shim (`timedEls`)."
- **Catalog Hard Rule — Fonts** (`catalog.md:11`): "Just write the `font-family` you want — the compiler embeds supported fonts automatically via `@font-face` with inline data URIs. No need for `<link>` tags or `@import`. Works in all contexts including sandboxed iframes."
- **Catalog Hard Rule — Element structure** (`catalog.md:13`): "No `class=\"clip\"` on scene divs in standalone compositions. Only the root div gets `data-composition-id`/`data-start`/`data-duration`."
- **Catalog Hard Rule — Overlay elements** (`catalog.md:15`): "Staggered blocks = full-screen 1920x1080, NOT thin strips. Glitch RGB overlays = normal blending at 35% opacity, NOT `mix-blend-mode: multiply` (invisible on dark backgrounds). Light leak overlays = larger than the frame (2400px+), never a visible shape. Overexposure = use `filter: brightness()` on the scene, not just a white overlay."
- **Catalog Hard Rule — VHS tape** (`catalog.md:17`): "Clone actual scene content with `cloneNode(true)`, NOT colored bars. Each strip: wider than frame (2020px at left:-50px). Red+blue chromatic copies at z-index above main strip. Seeded PRNG for deterministic random offsets."
- **Catalog Hard Rule — Z-index** (`catalog.md:19`): "Gravity drop, zoom out, diagonal split need outgoing scene ON TOP (`zIndex: 10`) so it exits while revealing the new scene behind (`zIndex: 1`)."
- **Catalog Hard Rule — Page burn** (`catalog.md:21`): "Content burns with the page — no falling debris. Hide scene1 via `tl.set` at burn end, NEVER `onComplete` (not reversible). `onUpdate` must restore `clipPath: \"none\"` when `wp <= 0` for rewind support. Incoming scene fades from black at 90% through burn."
- **Catalog Hard Rule — Clock wipe** (`catalog.md:23`): "9-point polygon with intermediate edge positions. Step through 4 quadrants with separate tweens."
- **Catalog Hard Rule — Grid dissolve** (`catalog.md:25`): "Cycle 5 palette colors per cell, not monochrome."
- **Catalog Hard Rule — Blinds count by energy** (`catalog.md:27`): "Calm: 4h/6v. Medium: 6-8h/8v. High: 12-16h/16v."
- **Catalog Hard Rule — Don't use** (`catalog.md:29`): "Star iris (polygon interpolation broken), tilt-shift (no selective CSS blur), lens flare (visible shape, not optical), hinge/door (distorts too fast)."

**Quality checks:** None at this step; Output Checklist (Step 16) and Animation Map (Step 21) verify downstream.

**Sub-agent dispatches:** None.

**Transition rule to next step:** all scene boundaries have transitions; proceed to the visual-identity HARD-GATE.

---

## Step 10b: Verify visual identity (HARD-GATE)

**Canon source:** `SKILL.md:60-62`

**Verbatim canon text:**

```
<HARD-GATE>
Before writing ANY composition HTML — verify you have a visual identity from Step 1. If you're reaching for `#333`, `#3b82f6`, or `Roboto`, you skipped it.
</HARD-GATE>
```

**Inputs:** the outputs of Step 1 / Step 1b (extracted brand values: colors, fonts, mood, constraints) and the planning artifacts from Steps 3-10.

**Outputs / artifacts:** an internal pass — confirmation that a concrete brand identity exists and will be used in the HTML about to be written; OR a halt with a return to Step 1/1b if the check fails.

**Conventions / hard rules at this step:**

- This gate fires "Before writing ANY composition HTML" — it is the last checkpoint before Step 11 (`SKILL.md:61`).
- Three canonical failure-tells indicating Step 1 was skipped (verbatim): `#333`, `#3b82f6`, `Roboto` (`SKILL.md:61`). Reaching for any of these means halt and return to Step 1/1b.
- The gate references "a visual identity from Step 1" — i.e., the design.md extraction (Step 1) or the no-design.md three-way choice (Step 1b).

**Quality checks:** the self-check is mechanical — scan the planned colors, the planned `font-family`, and any inline style values against the three failure-tells; if any match, the gate fails.

**Sub-agent dispatches:** None.

**Transition rule to next step:** gate passes (visual identity confirmed, no failure-tells present); proceed to Step 11.

---

## Step 11: Write composition HTML — data attributes and timeline contract

**Canon source:** `SKILL.md:134-165`, `SKILL.md:287-293`

**Verbatim canon text (All Clips data-attributes table):**

```
### All Clips

| Attribute          | Required                          | Values                                                 |
| ------------------ | --------------------------------- | ------------------------------------------------------ |
| `id`               | Yes                               | Unique identifier                                      |
| `data-start`       | Yes                               | Seconds or clip ID reference (`"el-1"`, `"intro + 2"`) |
| `data-duration`    | Required for img/div/compositions | Seconds. Video/audio defaults to media duration.       |
| `data-track-index` | Yes                               | Integer. Same-track clips cannot overlap.              |
| `data-media-start` | No                                | Trim offset into source (seconds)                      |
| `data-volume`      | No                                | 0-1 (default 1)                                        |

`data-track-index` does **not** affect visual layering — use CSS `z-index`.
```

Composition clips:

```
| Attribute                    | Required | Values                                                            |
| ---------------------------- | -------- | ----------------------------------------------------------------- |
| `data-composition-id`        | Yes      | Unique composition ID                                             |
| `data-start`                 | Yes      | Start time (root composition: use `"0"`)                          |
| `data-duration`              | Yes      | Takes precedence over GSAP timeline duration                      |
| `data-width` / `data-height` | Yes      | Pixel dimensions (1920x1080 or 1080x1920)                         |
| `data-composition-src`       | No       | Path to external HTML file                                        |
| `data-variable-values`       | No       | JSON object of per-instance variable overrides on a sub-comp host |
```

Timeline contract:

```
## Timeline Contract

- All timelines start `{ paused: true }` — the player controls playback
- Register every timeline: `window.__timelines["<composition-id>"] = tl`
- Framework auto-nests sub-timelines — do NOT manually add them
- Duration comes from `data-duration`, not from GSAP timeline length
- Never create empty tweens to set duration
```

**Inputs:** the planned layouts (Step 7), timings (Step 6), animations (Steps 8-10).

**Outputs / artifacts:** the composition HTML — for the root, `data-composition-id` div placed directly in `<body>`; for sub-compositions loaded via `data-composition-src`, the `<template>` wrapper shape (`SKILL.md:168`, `SKILL.md:172-189`).

**Conventions / hard rules at this step:**

- Standalone (root) `index.html` does NOT use `<template>`; sub-compositions loaded via `data-composition-src` DO (`SKILL.md:168`).
- Sub-composition required structure shown at `SKILL.md:172-189` includes scoped style by `data-composition-id` selector, GSAP CDN script, and `window.__timelines["my-comp"] = tl` registration.
- Root `<html>` `data-composition-variables` attribute drives Studio editing UI and provides defaults for `getVariables()` (`SKILL.md:163`).
- All four "Required: Yes" attributes per the table must be present per clip (`SKILL.md:140-145`).

**Quality checks:** Output Checklist Fast items (Step 16) run `lint` and `validate`.

**Sub-agent dispatches:** None.

**Transition rule to next step:** the HTML body is in place; proceed to optional variables wiring (Step 12) and media (Step 13).

---

## Step 12: Variables (parametrized compositions, when requested)

**Canon source:** `SKILL.md:194-262`

**Verbatim canon text:**

```
## Variables (Parametrized Compositions)

Render the same composition with different content — title, theme color, prices, captions — without editing the source HTML.

**Three-step pattern:**

1. **Declare** variables on the composition's `<html>` root with `data-composition-variables`. Each entry needs `id`, `type` (one of `string`, `number`, `color`, `boolean`, `enum`), `label`, and `default`. Enum entries also need `options: [{value, label}, ...]`.
2. **Read** the resolved values inside the composition's script with `window.__hyperframes.getVariables()`. Returns the merged result of declared defaults + per-instance overrides + CLI overrides.
3. **Override** at render time with `npx hyperframes render --variables '{...}'` (top-level) or with `data-variable-values='{...}'` on the host element (per-instance for sub-comps).
```

Rules of thumb:

```
**Rules of thumb:**

- Always provide a sensible `default` for every declared variable. Dev preview uses defaults — without them, the composition won't render correctly until `--variables` is provided.
- Read variables once at the top of the script (`const { title } = ...`), not inside frame loops or event handlers — `getVariables()` allocates a fresh object per call.
- Use `--strict-variables` in CI to fail fast on undeclared keys or type mismatches.
- Variable types are validated at render time. `string`, `number`, `boolean`, and `color` (hex string) check `typeof`; `enum` checks the value is in the declared `options`.
```

**Inputs:** the set of values that should vary at render time (title, theme, prices, captions, etc.).

**Outputs / artifacts:** `data-composition-variables` JSON array on root `<html>`; `getVariables()` reads inside the composition script; per-instance `data-variable-values` on sub-comp hosts (`SKILL.md:200-202`).

**Conventions / hard rules at this step:**

- Allowed types: `string`, `number`, `color`, `boolean`, `enum`. Enum entries also need `options: [{value, label}, ...]` (`SKILL.md:200`).
- Always provide a sensible `default` (`SKILL.md:258`).
- Read variables once at the top of the script (`SKILL.md:259`).
- Use `--strict-variables` in CI (`SKILL.md:260`).
- Per-instance values are layered over sub-comp declared defaults (`SKILL.md:254`).

**Quality checks:** `--strict-variables` is the canonical CI check (`SKILL.md:260`); types validated at render time (`SKILL.md:261`).

**Sub-agent dispatches:** None.

**Transition rule to next step:** variables wired (or skipped); proceed to media wiring.

---

## Step 13: Video and audio wiring

**Canon source:** `SKILL.md:263-285`

**Verbatim canon text:**

```
## Video and Audio

Video must be `muted playsinline`. Audio is always a separate `<audio>` element:

```html
<video
  id="el-v"
  data-start="0"
  data-duration="30"
  data-track-index="0"
  src="video.mp4"
  muted
  playsinline
></video>
<audio
  id="el-a"
  data-start="0"
  data-duration="30"
  data-track-index="2"
  src="video.mp4"
  data-volume="1"
></audio>
```
```

**Inputs:** any media assets (video/audio files) referenced by the composition.

**Outputs / artifacts:** `<video>` and `<audio>` elements with required attributes and the muted-video + separate-audio pattern.

**Conventions / hard rules at this step:**

- "Video must be `muted playsinline`." (`SKILL.md:265`)
- "Audio is always a separate `<audio>` element." (`SKILL.md:265`)
- Never-do #2: "Use video for audio — always muted video + separate `<audio>`" (`SKILL.md:309`).
- Never-do #3: "Nest video inside a timed div — use a non-timed wrapper" (`SKILL.md:310`).
- Never-do #5: "Animate video element dimensions — animate a wrapper div" (`SKILL.md:312`).
- Never-do #6: "Call play/pause/seek on media — framework owns playback" (`SKILL.md:313`).
- Typography and Assets: "Add `crossorigin='anonymous'` to external media" (`SKILL.md:365`).

**Quality checks:** None at this step.

**Sub-agent dispatches:** None.

**Transition rule to next step:** media is wired; proceed to typography/assets.

---

## Step 14: Typography and assets

**Canon source:** `SKILL.md:362-367`

**Verbatim canon text:**

```
## Typography and Assets

- **Built-in fonts:** Write the `font-family` you want in CSS — the compiler embeds supported fonts automatically.
- **Custom fonts:** If design.md names a font that isn't built-in, the user must provide `.woff2` files in a `fonts/` directory. If missing, warn before writing HTML. When files exist, add `@font-face` declarations pointing to the local files.
- Add `crossorigin="anonymous"` to external media
- For dynamic text overflow, use `window.__hyperframes.fitTextFontSize(text, { maxWidth, fontFamily, fontWeight })`
- All files live at the project root alongside `index.html`; sub-compositions use `../`
```

**Inputs:** the font and asset list implied by the design system.

**Outputs / artifacts:** correct `font-family` declarations, `@font-face` entries for custom fonts when files exist in `fonts/`, `crossorigin="anonymous"` on external media (`SKILL.md:364-365`).

**Conventions / hard rules at this step:**

- Pre-HTML font warning is reiterated here (`SKILL.md:364`) — same hard rule as Step 1.
- "All files live at the project root alongside `index.html`; sub-compositions use `../`" (`SKILL.md:367`).
- Animation Guardrails: "60px+ headlines, 20px+ body, 16px+ data labels for rendered video" (`SKILL.md:356`).
- "`font-variant-numeric: tabular-nums` on number columns" (`SKILL.md:357`).

**Quality checks:** Inspect (`SKILL.md:393`) catches text spilling/clipping at Step 18.

**Sub-agent dispatches:** None.

**Transition rule to next step:** typography and assets in place; proceed to apply the cross-cutting "Rules (Non-Negotiable)" review.

---

## Step 15: Apply non-negotiable rules across the composition

**Canon source:** `SKILL.md:295-319`

**Verbatim canon text:**

```
## Rules (Non-Negotiable)

**Deterministic:** No `Math.random()`, `Date.now()`, or time-based logic. Use a seeded PRNG if you need pseudo-random values (e.g. mulberry32).

**GSAP:** Only animate visual properties (`opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms). Do NOT animate `visibility`, `display`, or call `video.play()`/`audio.play()`.

**Animation conflicts:** Never animate the same property on the same element from multiple timelines simultaneously.

**No `repeat: -1`:** Infinite-repeat timelines break the capture engine. Calculate the exact repeat count from composition duration: `repeat: Math.ceil(duration / cycleDuration) - 1`.

**Synchronous timeline construction:** Never build timelines inside `async`/`await`, `setTimeout`, or Promises. The capture engine reads `window.__timelines` synchronously after page load. Fonts are embedded by the compiler, so they're available immediately — no need to wait for font loading.

**Never do:**

1. Forget `window.__timelines` registration
2. Use video for audio — always muted video + separate `<audio>`
3. Nest video inside a timed div — use a non-timed wrapper
4. Use `data-layer` (use `data-track-index`) or `data-end` (use `data-duration`)
5. Animate video element dimensions — animate a wrapper div
6. Call play/pause/seek on media — framework owns playback
7. Create a top-level container without `data-composition-id`
8. Use `repeat: -1` on any timeline or tween — always finite repeats
9. Build timelines asynchronously (inside `async`, `setTimeout`, `Promise`)
10. Use `gsap.set()` on clip elements from later scenes — they don't exist in the DOM at page load. Use `tl.set(selector, vars, timePosition)` inside the timeline at or after the clip's `data-start` time instead.
11. Use `<br>` in content text — forced line breaks don't account for actual rendered font width. Text that wraps naturally + a `<br>` produces an extra unwanted break, causing overlap. Let text wrap via `max-width` instead. Exception: short display titles where each word is deliberately on its own line (e.g., "THE\nIMMORTAL\nGAME" at 130px).
```

**Inputs:** the authored composition HTML so far.

**Outputs / artifacts:** edits that bring every Non-Negotiable into compliance — no `Math.random()`/`Date.now()`, only visual GSAP properties, no `repeat: -1`, synchronous timeline construction, no `<br>` in content text (except permitted display-title exception), etc.

**Conventions / hard rules at this step:** sixteen named non-negotiables — five Rules + eleven Never-do items. Each is enumerated below with its canon anchor (see also the Conventions index "Rules (Non-Negotiable)" appendix entry that lists every one with the same anchors).

- **Rule 1 — Deterministic** (`SKILL.md:297`). No `Math.random()`, `Date.now()`, or time-based logic. Use a seeded PRNG if you need pseudo-random values (e.g. mulberry32).
- **Rule 2 — GSAP visual-properties-only** (`SKILL.md:299`). Only animate visual properties (`opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms). Do NOT animate `visibility`, `display`, or call `video.play()`/`audio.play()`.
- **Rule 3 — Animation conflicts** (`SKILL.md:301`). Never animate the same property on the same element from multiple timelines simultaneously.
- **Rule 4 — No `repeat: -1`** (`SKILL.md:303`). Infinite-repeat timelines break the capture engine. Calculate the exact repeat count from composition duration: `repeat: Math.ceil(duration / cycleDuration) - 1`.
- **Rule 5 — Synchronous timeline construction** (`SKILL.md:305`). Never build timelines inside `async`/`await`, `setTimeout`, or Promises. The capture engine reads `window.__timelines` synchronously after page load.
- **Never-do 1** (`SKILL.md:309`). Forget `window.__timelines` registration.
- **Never-do 2** (`SKILL.md:310`). Use video for audio — always muted video + separate `<audio>`.
- **Never-do 3** (`SKILL.md:311`). Nest video inside a timed div — use a non-timed wrapper.
- **Never-do 4** (`SKILL.md:312`). Use `data-layer` (use `data-track-index`) or `data-end` (use `data-duration`).
- **Never-do 5** (`SKILL.md:313`). Animate video element dimensions — animate a wrapper div.
- **Never-do 6** (`SKILL.md:314`). Call play/pause/seek on media — framework owns playback.
- **Never-do 7** (`SKILL.md:315`). Create a top-level container without `data-composition-id`.
- **Never-do 8** (`SKILL.md:316`). Use `repeat: -1` on any timeline or tween — always finite repeats.
- **Never-do 9** (`SKILL.md:317`). Build timelines asynchronously (inside `async`, `setTimeout`, `Promise`).
- **Never-do 10** (`SKILL.md:318`). Use `gsap.set()` on clip elements from later scenes — they don't exist in the DOM at page load. Use `tl.set(selector, vars, timePosition)` inside the timeline at or after the clip's `data-start` time instead.
- **Never-do 11** (`SKILL.md:319`). Use `<br>` in content text — forced line breaks don't account for actual rendered font width. Exception: short display titles where each word is deliberately on its own line.

**Quality checks:** `lint` catches many of these mechanically at Step 17.

**Sub-agent dispatches:** None.

**Transition rule to next step:** the composition is non-negotiable-compliant by review; proceed to Output Checklist execution.

---

## Step 16: Output Checklist — orchestrate Fast and Slow checks

**Canon source:** `SKILL.md:376-387`

**Verbatim canon text:**

```
## Output Checklist

**Fast (run immediately, block on results):**

- [ ] `npx hyperframes lint` and `npx hyperframes validate` both pass
- [ ] Design adherence verified if design.md exists

**Slow (run in parallel while presenting the preview to the user):**

- [ ] `npx hyperframes inspect` passes, or every reported overflow is intentionally marked
- [ ] Contrast warnings addressed (see Quality Checks below)
- [ ] Animation choreography verified (see Quality Checks below)
```

**Inputs:** the authored composition.

**Outputs / artifacts:** orchestration decisions — which checks run "immediately, block on results" versus "in parallel while presenting the preview to the user" (`SKILL.md:378`, `SKILL.md:383`).

**Conventions / hard rules at this step:**

- Fast checks block (`SKILL.md:378`).
- Slow checks run in parallel with preview presentation (`SKILL.md:383`).
- Fast includes lint+validate + design adherence (`SKILL.md:380-381`).
- Slow includes inspect + contrast + animation choreography (`SKILL.md:385-387`).

**Quality checks:** the checklist itself routes to Steps 17-21.

**Sub-agent dispatches:** None.

**Transition rule to next step:** start Step 17 (Fast: lint + validate) immediately and block on its result.

---

## Step 17: Fast — `npx hyperframes lint` and `npx hyperframes validate`

**Canon source:** `SKILL.md:380`, `SKILL.md:408-422`

**Verbatim canon text (Fast item):**

```
- [ ] `npx hyperframes lint` and `npx hyperframes validate` both pass
```

From "Contrast":

```
### Contrast

`hyperframes validate` runs a WCAG contrast audit by default. It seeks to 5 timestamps, screenshots the page, samples background pixels behind every text element, and computes contrast ratios. Failures appear as warnings:

```
⚠ WCAG AA contrast warnings (3):
  · .subtitle "secondary text" — 2.67:1 (need 4.5:1, t=5.3s)
```

If warnings appear:

- On dark backgrounds: brighten the failing color until it clears 4.5:1 (normal text) or 3:1 (large text, 24px+ or 19px+ bold)
- On light backgrounds: darken it
- Stay within the palette family — don't invent a new color, adjust the existing one
- Re-run `hyperframes validate` until clean

Use `--no-contrast` to skip if iterating rapidly and you'll check later.
```

**Inputs:** the composition source on disk.

**Outputs / artifacts:** lint pass; validate pass including WCAG contrast audit (or warnings to address) (`SKILL.md:408`).

**Conventions / hard rules at this step:**

- "Both pass" is the bar (`SKILL.md:380`).
- WCAG AA targets: 4.5:1 normal text, 3:1 large text (24px+ or 19px+ bold) (`SKILL.md:417`).
- "Stay within the palette family — don't invent a new color, adjust the existing one" (`SKILL.md:419`).
- "Re-run `hyperframes validate` until clean" (`SKILL.md:420`).
- `--no-contrast` is an explicit opt-out for rapid iteration (`SKILL.md:422`).

**Quality checks:** lint + validate themselves; iterate to clean.

**Sub-agent dispatches:** None.

**Transition rule to next step:** both passes are clean; proceed to design-adherence (Step 20 logically follows but is grouped under Fast; running in any order within Fast is permitted).

---

## Step 18: Slow — `npx hyperframes inspect`

**Canon source:** `SKILL.md:385`, `SKILL.md:391-404`

**Verbatim canon text (Slow item):**

```
- [ ] `npx hyperframes inspect` passes, or every reported overflow is intentionally marked
```

From "Visual Inspect":

```
### Visual Inspect

`hyperframes inspect` runs the composition in headless Chrome, seeks through the timeline, and maps visual layout issues with timestamps, selectors, bounding boxes, and fix hints. Run it after `lint` and `validate`:

```bash
npx hyperframes inspect
npx hyperframes inspect --json
```

Failures usually mean text is spilling out of a bubble/card, a fixed-size label is clipping dynamic copy, or text has moved off the canvas. Fix by increasing container size or padding, reducing font size or letter spacing, adding a real `max-width` so text wraps inside the container, or using `window.__hyperframes.fitTextFontSize(...)` for dynamic copy.

Use `--samples 15` for dense videos and `--at 1.5,4,7.25` for specific hero frames. Repeated static issues are collapsed by default to avoid flooding agent context. If overflow is intentional for an entrance/exit animation, mark the element or ancestor with `data-layout-allow-overflow`. If a decorative element should never be audited, mark it with `data-layout-ignore`.

`hyperframes layout` is the compatibility alias for the same check.
```

**Inputs:** the composition source, optional `--samples` / `--at` / `--json` flags.

**Outputs / artifacts:** a report of timestamps, selectors, bounding boxes, and fix hints (or a clean run) (`SKILL.md:393`).

**Conventions / hard rules at this step:**

- Run after `lint` and `validate` (`SKILL.md:393`).
- Acceptable outcome: passes, OR every reported overflow is intentionally marked (`SKILL.md:385`).
- Intentional overflow → mark with `data-layout-allow-overflow` (`SKILL.md:402`).
- Decorative never-audit → mark with `data-layout-ignore` (`SKILL.md:402`).
- `hyperframes layout` is a compatibility alias (`SKILL.md:404`).

**Quality checks:** inspect itself.

**Sub-agent dispatches:** None.

**Transition rule to next step:** inspect passes or all flags justified; proceed to contrast follow-up if validate flagged any.

---

## Step 19: Slow — contrast warnings addressed

**Canon source:** `SKILL.md:386`, `SKILL.md:408-422`

**Verbatim canon text (Slow item):**

```
- [ ] Contrast warnings addressed (see Quality Checks below)
```

(Full Contrast section quoted in Step 17 above — same source.)

**Inputs:** validate's contrast warnings list.

**Outputs / artifacts:** color adjustments staying within palette family until `hyperframes validate` is clean (`SKILL.md:419-420`).

**Conventions / hard rules at this step:**

- 4.5:1 normal text / 3:1 large text targets (`SKILL.md:417`).
- "Stay within the palette family — don't invent a new color, adjust the existing one" (`SKILL.md:419`).

**Quality checks:** re-run `hyperframes validate` until clean (`SKILL.md:420`).

**Sub-agent dispatches:** None.

**Transition rule to next step:** validate is clean; proceed to design adherence (or animation map).

---

## Step 20: Design adherence (Fast — verified after authoring if `design.md` exists)

**Canon source:** `SKILL.md:381`, `SKILL.md:424-441`

**Verbatim canon text (Fast item):**

```
- [ ] Design adherence verified if design.md exists
```

From "Design Adherence":

```
### Design Adherence

If a `design.md` exists, verify the composition follows it after authoring. Read the HTML and check:

1. **Colors** — every hex value in the composition appears in design.md's palette section (however the user labeled it: Colors, Palette, Theme, etc.). Flag any invented colors.
2. **Typography** — font families and weights match design.md's type spec. No substitutions.
3. **Corners** — border-radius values match the declared corner style, if specified.
4. **Spacing** — padding and gap values fall within the declared density range, if specified.
5. **Depth** — shadow usage matches the declared depth level, if specified (flat = none, subtle = light, layered = glows).
6. **Avoidance rules** — if design.md has a section listing things to avoid (commonly "What NOT to Do", "Don'ts", "Anti-patterns", or "Do's and Don'ts"), verify none are present.

Report violations as a checklist. Fix each one before serving.

If no `design.md` exists (house-style-only path), verify:

1. **Palette consistency** — the same bg, fg, and accent colors are used across all scenes. No per-scene color invention.
2. **No lazy defaults** — check the composition against house-style.md's "Lazy Defaults to Question" list. If any appear, they must be a deliberate choice for the content, not a default.
```

**Inputs:** the authored composition HTML; `design.md` if present, otherwise `house-style.md`.

**Outputs / artifacts:** a violation checklist (when violations exist) and fixes applied before serving (`SKILL.md:435`).

**Conventions / hard rules at this step:**

- Six checks when `design.md` exists: Colors / Typography / Corners / Spacing / Depth / Avoidance rules (`SKILL.md:428-433`).
- House-style-only path: Palette consistency + No lazy defaults (`SKILL.md:439-441`).
- "Fix each one before serving." (`SKILL.md:435`)

**Quality checks:** the checklist itself.

**Sub-agent dispatches:** None.

**Transition rule to next step:** all violations fixed; proceed to Animation Map (Slow).

---

## Step 21: Slow — Animation Map

**Canon source:** `SKILL.md:387`, `SKILL.md:443-463`

**Verbatim canon text (Slow item):**

```
- [ ] Animation choreography verified (see Quality Checks below)
```

From "Animation Map":

```
### Animation Map

After authoring animations, run the animation map to verify choreography:

```bash
node skills/hyperframes/scripts/animation-map.mjs <composition-dir> \
  --out <composition-dir>/.hyperframes/anim-map
```

Outputs a single `animation-map.json` with:

- **Per-tween summaries**: `"#card1 animates opacity+y over 0.50s. moves 23px up. fades in. ends at (120, 200)"`
- **ASCII timeline**: Gantt chart of all tweens across the composition duration
- **Stagger detection**: reports actual intervals (`"3 elements stagger at 120ms"`)
- **Dead zones**: periods over 1s with no animation — intentional hold or missing entrance?
- **Element lifecycles**: first/last animation time, final visibility
- **Scene snapshots**: visible element state at 5 key timestamps
- **Flags**: `offscreen`, `collision`, `invisible`, `paced-fast` (under 0.2s), `paced-slow` (over 2s)

Read the JSON. Scan summaries for anything unexpected. Check every flag — fix or justify. Verify the timeline shows the intended choreography rhythm. Re-run after fixes.

Skip on small edits (fixing a color, adjusting one duration). Run on new compositions and significant animation changes.
```

**Inputs:** the composition directory.

**Outputs / artifacts:** `<composition-dir>/.hyperframes/anim-map/animation-map.json` with per-tween summaries, ASCII timeline, stagger detection, dead zones, element lifecycles, scene snapshots, and flags (`SKILL.md:451-459`).

**Conventions / hard rules at this step:**

- Canonical interpretation: "Read the JSON. Scan summaries for anything unexpected. Check every flag — fix or justify. Verify the timeline shows the intended choreography rhythm. Re-run after fixes." (`SKILL.md:461`)
- Flag set: `offscreen`, `collision`, `invisible`, `paced-fast` (under 0.2s), `paced-slow` (over 2s) (`SKILL.md:459`).
- Skip on small edits (`SKILL.md:463`).

**Quality checks:** the animation map itself; iterate until flags are fixed or each is explicitly justified (`SKILL.md:461`).

**Sub-agent dispatches:** None.

**Transition rule to next step:** flags resolved; the composition is ready to serve.

---

## Step 22: Editing existing compositions (on a follow-up request)

**Canon source:** `SKILL.md:369-374`

**Verbatim canon text:**

```
## Editing Existing Compositions

- **Read actual files, don't guess.** When editing, extending, or creating companion compositions, read the existing source. Don't reconstruct hex codes from memory. Don't guess GSAP easing patterns. The composition IS the spec — extract exact values from it.
- Match existing fonts, colors, animation patterns from what you read
- Only change what was requested
- Preserve timing of unrelated clips
```

**Inputs:** the existing on-disk composition source.

**Outputs / artifacts:** edits limited to what was requested, preserving unrelated timing (`SKILL.md:373-374`).

**Conventions / hard rules at this step:**

- "Read actual files, don't guess." (`SKILL.md:371`)
- "Only change what was requested." (`SKILL.md:373`)
- "Preserve timing of unrelated clips." (`SKILL.md:374`)

**Quality checks:** re-run the Output Checklist (Step 16) afterward.

**Sub-agent dispatches:** None.

**Transition rule to next step:** N/A — this is the terminal follow-up step. A new request begins again at Step 0 or Step 3 (small edits skip Plan: "For small edits (fix a color, adjust timing, add one element), skip straight to the rules." — `SKILL.md:58`).

---

## Appendix — Conventions index

Cross-reference of every Hard Rule and named convention to the step that introduces or applies it.

### HARD-GATE (`SKILL.md:60-62`)

- **Visual-identity HARD-GATE** — "Before writing ANY composition HTML — verify you have a visual identity from Step 1. If you're reaching for `#333`, `#3b82f6`, or `Roboto`, you skipped it." (`SKILL.md:61`). Discrete Step 10b — fires after planning is complete (Steps 3-10) and before Step 11 (Write composition HTML).

### Scene Transitions (Non-Negotiable) (`SKILL.md:321-348`)

- **Rule 1** — Always use transitions between scenes. No jump cuts. No exceptions. (`SKILL.md:325`). Step 10.
- **Rule 2** — Always use entrance animations on every scene; every element animates IN via `gsap.from()`. (`SKILL.md:326`). Step 8.
- **Rule 3** — Never use exit animations except on the final scene. The transition IS the exit. (`SKILL.md:327`). Step 9.
- **Rule 4** — Final scene only may fade elements out. (`SKILL.md:328`). Step 9.

### Rules (Non-Negotiable) (`SKILL.md:295-319`)

- **Deterministic** — No `Math.random()`/`Date.now()`/time-based logic; seeded PRNG (mulberry32) if needed. (`SKILL.md:297`). Step 8.
- **GSAP visual-properties-only** — only `opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms; do NOT animate `visibility`/`display`; do NOT call `video.play()`/`audio.play()`. (`SKILL.md:299`). Steps 8, 13, 15.
- **Animation conflicts** — never animate the same property on the same element from multiple timelines simultaneously. (`SKILL.md:301`). Step 8.
- **No `repeat: -1`** — calculate exact repeat count from composition duration. (`SKILL.md:303`). Steps 8, 15.
- **Synchronous timeline construction** — never inside `async`/`await`, `setTimeout`, or Promises. (`SKILL.md:305`). Step 8.
- **Never-do 1** — Forget `window.__timelines` registration. (`SKILL.md:309`). Step 8.
- **Never-do 2** — Use video for audio. (`SKILL.md:309`). Step 13.
- **Never-do 3** — Nest video inside a timed div. (`SKILL.md:310`). Step 13.
- **Never-do 4** — Use `data-layer` or `data-end` instead of `data-track-index`/`data-duration`. (`SKILL.md:311`). Step 11.
- **Never-do 5** — Animate video element dimensions. (`SKILL.md:312`). Step 13.
- **Never-do 6** — Call play/pause/seek on media. (`SKILL.md:313`). Step 13.
- **Never-do 7** — Top-level container without `data-composition-id`. (`SKILL.md:314`). Step 11.
- **Never-do 8** — `repeat: -1` on any timeline or tween. (`SKILL.md:315`). Step 15.
- **Never-do 9** — Build timelines asynchronously. (`SKILL.md:316`). Step 8.
- **Never-do 10** — `gsap.set()` on clip elements from later scenes; use `tl.set(selector, vars, timePosition)` instead. (`SKILL.md:317-318`). Step 8.
- **Never-do 11** — `<br>` in content text (except permitted short display-title exception). (`SKILL.md:319`). Step 14.

### Timeline Contract (`SKILL.md:287-293`)

- All timelines start `{ paused: true }` (`SKILL.md:289`). Step 8.
- Register every timeline: `window.__timelines["<composition-id>"] = tl` (`SKILL.md:290`). Step 8.
- Framework auto-nests sub-timelines — do NOT manually add them (`SKILL.md:291`). Step 8.
- Duration comes from `data-duration`, not GSAP timeline length (`SKILL.md:292`). Steps 6, 11.
- Never create empty tweens to set duration (`SKILL.md:293`). Step 8.

### Layout Before Animation (`SKILL.md:64-132`)

- Position elements at their most visible moment as static HTML+CSS first (`SKILL.md:66`). Step 7.
- Identify the hero frame per scene (`SKILL.md:72`). Step 7.
- `.scene-content` MUST fill the scene via `width/height/padding` + flex; reserve `position: absolute` for decoratives only (`SKILL.md:73`). Step 7.
- CSS position is the ground truth; tweens describe the journey (`SKILL.md:74`). Step 7.
- In sub-compositions loaded via `data-composition-src`, prefer `gsap.fromTo()` (`SKILL.md:74`). Steps 7, 8.

### Animation Guardrails (`SKILL.md:350-357`)

- Offset first animation 0.1-0.3s, not t=0 (`SKILL.md:352`). Step 8.
- Vary eases across entrance tweens — at least 3 different eases per scene (`SKILL.md:353`). Step 8.
- Don't repeat an entrance pattern within a scene (`SKILL.md:354`). Step 8.
- Avoid full-screen linear gradients on dark backgrounds (H.264 banding) (`SKILL.md:355`). Steps 7, 11.
- 60px+ headlines, 20px+ body, 16px+ data labels for rendered video (`SKILL.md:356`). Step 14.
- `font-variant-numeric: tabular-nums` on number columns (`SKILL.md:357`). Step 14.

### Composition Structure (`SKILL.md:166-192`)

- Sub-compositions loaded via `data-composition-src` use a `<template>` wrapper; standalone (root) compositions do NOT (`SKILL.md:168`). Steps 4, 11.

### Data Attributes (`SKILL.md:136-165`)

- All Clips required: `id`, `data-start`, `data-duration` (for img/div/compositions), `data-track-index` (`SKILL.md:140-145`). Step 11.
- `data-track-index` does NOT affect visual layering — use CSS `z-index` (`SKILL.md:147`). Steps 4, 11.
- Composition Clips required: `data-composition-id`, `data-start`, `data-duration`, `data-width`/`data-height` (`SKILL.md:152-156`). Step 11.
- Root `<html>` `data-composition-variables` drives Studio editing UI and provides `getVariables()` defaults (`SKILL.md:163`). Step 12.

### Variables (`SKILL.md:194-262`)

- Declare on root `<html>` with `data-composition-variables` (id/type/label/default; enum needs options) (`SKILL.md:200`). Step 12.
- Read with `window.__hyperframes.getVariables()` (`SKILL.md:201`). Step 12.
- Override at render time via CLI `--variables` / `--variables-file` or per-instance `data-variable-values` (`SKILL.md:202`). Step 12.
- Always provide a sensible default (`SKILL.md:258`). Step 12.
- Read once at top of script (`SKILL.md:259`). Step 12.
- Use `--strict-variables` in CI (`SKILL.md:260`). Step 12.

### Video and Audio (`SKILL.md:263-285`)

- Video must be `muted playsinline` (`SKILL.md:265`). Step 13.
- Audio is always a separate `<audio>` element (`SKILL.md:265`). Step 13.

### Typography and Assets (`SKILL.md:362-367`)

- Built-in fonts: write `font-family`; compiler embeds (`SKILL.md:364`). Step 14.
- Custom fonts: `.woff2` in `fonts/` + `@font-face`; pre-HTML warning if missing (`SKILL.md:364`). Steps 1, 14.
- `crossorigin="anonymous"` on external media (`SKILL.md:365`). Steps 13, 14.
- Dynamic text overflow: `window.__hyperframes.fitTextFontSize(...)` (`SKILL.md:366`). Steps 14, 18.
- All files at project root alongside `index.html`; sub-compositions use `../` (`SKILL.md:367`). Steps 11, 14.

### Output Checklist + Quality Checks (`SKILL.md:376-463`)

- Fast: `lint` + `validate` + design adherence (`SKILL.md:380-381`). Steps 17, 20.
- Slow: `inspect` + contrast + animation choreography (`SKILL.md:385-387`). Steps 18, 19, 21.
- Inspect intentional overflow → `data-layout-allow-overflow`; decorative skip → `data-layout-ignore` (`SKILL.md:402`). Step 18.
- WCAG AA contrast: 4.5:1 normal text, 3:1 large text (24px+ or 19px+ bold) (`SKILL.md:417`). Step 19.
- Stay within palette family when adjusting contrast (`SKILL.md:419`). Step 19.
- `--no-contrast` opt-out for rapid iteration (`SKILL.md:422`). Step 17.
- Design Adherence 6 checks: Colors, Typography, Corners, Spacing, Depth, Avoidance rules (`SKILL.md:428-433`). Step 20.
- House-style-only path: Palette consistency + No lazy defaults (`SKILL.md:439-441`). Step 20.
- Animation Map flags: `offscreen`, `collision`, `invisible`, `paced-fast`, `paced-slow` (`SKILL.md:459`). Step 21.
- Animation Map skip rule for small edits (`SKILL.md:463`). Step 21.

### Prompt Expansion (`references/prompt-expansion.md`)

- Pre-action 1 — read `DESIGN.md` (`prompt-expansion.md:11`). Step 2.
- Pre-action 2 — read `beat-direction.md` (`prompt-expansion.md:12`). Step 2.
- Pre-action 3 — read `video-composition.md` (`prompt-expansion.md:13`). Step 2.
- Pre-action 4 — read `house-style.md` (`prompt-expansion.md:14`). Step 2.
- Output section 1 — Title + style block (`prompt-expansion.md:41`). Step 2.
- Output section 2 — Rhythm declaration (`prompt-expansion.md:43`). Step 2.
- Output section 3 — Global rules (`prompt-expansion.md:45`). Step 2.
- Output section 4 — Per-scene beats in beat-direction format: Concept / Mood / Depth layers / Animation choreography / Transition out (`prompt-expansion.md:48-52`). Step 2.
- Output section 5 — Recurring motifs (`prompt-expansion.md:54`). Step 2.
- Output section 6 — Negative prompt (`prompt-expansion.md:56`). Step 2.
- Canonical output path `.hyperframes/expanded-prompt.md` (`prompt-expansion.md:58-60`). Step 2.
- Mandatory user-approval gate (`prompt-expansion.md:62-68`). Step 2b.

### Transitions calibration (`references/transitions.md`)

- Energy → Transition character — soft/organic, directional/purposeful, percussive/instant (`transitions.md:18-22`). Step 10.
- Mood → Motion quality — nine moods (`transitions.md:30-40`). Step 10.
- Narrative Position — six named positions (`transitions.md:48-53`). Step 10.
- Blur and motion intensity — three calibration ranges (`transitions.md:64-66`). Step 10.
- Shader-Compatible CSS Rule 1 — no `transparent` keyword in gradients (`transitions.md:127`). Step 10.
- Shader-Compatible CSS Rule 2 — no gradient backgrounds on elements thinner than 4px (`transitions.md:128`). Step 10.
- Shader-Compatible CSS Rule 3 — no `var()` on elements visible during capture (`transitions.md:129`). Step 10.
- Shader-Compatible CSS Rule 4 — mark uncapturable decoratives with `data-no-capture` (`transitions.md:130`). Step 10.
- Shader-Compatible CSS Rule 5 — no gradient opacity below 0.15 (`transitions.md:131`). Step 10.
- Shader-Compatible CSS Rule 6 — every `.scene` div needs explicit `background-color` matching `bgColor` config (`transitions.md:132`). Step 10.
- Velocity-Matched Transitions (`beat-direction.md:169-171`). Step 10.

### Transitions Catalog Hard Rules (CSS) (`references/transitions/catalog.md`)

- Scene visibility — Scene 1 visible by default; Scenes 2+ have `opacity: 0` on container div (`catalog.md:9`). Step 10.
- Fonts — write `font-family`, compiler embeds via `@font-face` (`catalog.md:11`). Step 10.
- Element structure — no `class="clip"` on scene divs in standalone (`catalog.md:13`). Step 10.
- Overlay elements — staggered-blocks/glitch/light-leak/overexposure specifics (`catalog.md:15`). Step 10.
- VHS tape specifics (`catalog.md:17`). Step 10.
- Z-index — gravity drop / zoom out / diagonal split outgoing on top (`catalog.md:19`). Step 10.
- Page burn — `tl.set` at burn end (not `onComplete`); restore `clipPath: "none"` on rewind (`catalog.md:21`). Step 10.
- Clock wipe — 9-point polygon, 4 quadrant tweens (`catalog.md:23`). Step 10.
- Grid dissolve — cycle 5 palette colors per cell (`catalog.md:25`). Step 10.
- Blinds count by energy — calm 4h/6v, medium 6-8h/8v, high 12-16h/16v (`catalog.md:27`). Step 10.
- Don't use — star iris, tilt-shift, lens flare, hinge/door (`catalog.md:29`). Step 10.

### Load-Bearing GSAP Rules (`references/motion-principles.md`)

- Scene structure: build, breathe, resolve (`motion-principles.md:39-46`). Step 7.
- Load-Bearing Rule 1 — No iframes for captured content (`motion-principles.md:93`). Step 8.
- Load-Bearing Rule 2 — Never stack two transform tweens on the same element (`motion-principles.md:95`). Step 8.
- Load-Bearing Rule 3 — Prefer `tl.fromTo()` over `tl.from()` inside `.clip` scenes (`motion-principles.md:123`). Step 8.
- Load-Bearing Rule 4 — Ambient pulses must attach to seekable `tl`, never bare `gsap.to()` (`motion-principles.md:133`). Step 8.
- Hard-kill at every scene boundary (`motion-principles.md:143`). Step 8.

### Editing Existing Compositions (`SKILL.md:369-374`)

- Read actual files, don't guess (`SKILL.md:371`). Step 22.
- Only change what was requested (`SKILL.md:373`). Step 22.
- Preserve timing of unrelated clips (`SKILL.md:374`). Step 22.

### Small-edit shortcut (`SKILL.md:58`)

- "For small edits (fix a color, adjust timing, add one element), skip straight to the rules." (`SKILL.md:58`). Steps 3-10 may be skipped.

### Always-read references (per `SKILL.md:467-489`)

- `references/video-composition.md` — **Always read** (`SKILL.md:472`). Step 3 onward.
- `references/beat-direction.md` — **Always read for multi-scene compositions** (`SKILL.md:473`). Step 5.
- `references/typography.md` — **Always read** (`SKILL.md:474`). Step 14.
- `references/motion-principles.md` — **Always read** (`SKILL.md:475`). Steps 7, 8.
- `references/transitions.md` — **Always read for multi-scene compositions** (`SKILL.md:487`). Step 10.
