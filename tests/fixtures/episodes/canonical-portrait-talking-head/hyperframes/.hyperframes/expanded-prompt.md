# Expanded Prompt — Canonical Portrait Talking-Head

## 1. Title + Style Block

**Title:** Velvet Standard — Enduring Craft (canonical-portrait-talking-head)

**Format:** 1080×1920 portrait, ~26.5s, four-beat monologue (HOOK → PROBLEM → PIVOT → PAYOFF). The talking-head video plate is the hero on every beat; overlays sit in the upper or lower third of the frame and never crash the speaker's face on the middle third.

**Mood:** Enduring craft, not AI launch. A quiet, reflective argument for pay-once software, made in the patina-warm tones of a tool that ages well rather than the chrome of a product page. Vignelli/Unimark architecture (generous gutters, hairline rules, slow glides) warmed away from corporate indigo toward an aged-brass accent.

**Palette (cite from `DESIGN.md` — do not invent):**

- background `#0d0b08` (warm ink — never `#000`)
- background-stop-1 `#0a0907` · background-stop-2 `#060504` (vignette stops)
- background-highlight-1 `#1a1611` · background-highlight-2 `#272118` (rim under hairlines)
- foreground `#f4ede0` (ivory — never `#fff`)
- foreground-stop-1 `#dcd5c9` (secondary text, captions)
- foreground-highlight-1 `#ffffff` (reserved for ONE PAYOFF emphasis word — used nowhere else)
- accent `#c8a04b` (aged brass — the single accent across all four beats)
- accent-stop-1 `#b48f43` · accent-stop-2 `#a07e3b` · accent-highlight-1 `#d6b466`
- midtone `#6b5e48` · midtone-stop-1 `#5f5440` (timecode, role chips, hairline dividers)

**Typography (from DESIGN.md — exact):**

- Headline — **Inter 300**, 4rem, uppercase, `letter-spacing: 0.12em`. Used only on HOOK ("AGE OF / ARTIFICIAL / INTELLIGENCE", three deliberate lines).
- Body / caption — **Inter 300**, 1.5–2rem in portrait, `line-height: 1.6`, sentence case.
- Pull / pivot serif — **Playfair Display italic**, 3rem, mixed case. Appears EXACTLY ONCE per composition: on PIVOT, for "I thought…".
- Label / timecode — **Inter 400**, 0.875rem, uppercase, `letter-spacing: 0.18em`, midtone.
- Numbers — `font-variant-numeric: tabular-nums`. Banned: Roboto, default Helvetica fallback, gradient text, faux italic.

**Grade reference (from Phase 3 strategy):** Neutral natural-light talking-head; gentle lift in shadows, mild contrast, slightly warm midtones to keep skin tones inviting; no stylized LUT. The brass accent on overlays does the warming work — the plate stays naturalistic.

---

## 2. Rhythm Declaration

**Rhythm:** `quiet-hook · breathe-PROBLEM · turn-PIVOT · resolve-PAYOFF`

This is a calm-energy four-beat (motion energy: `calm` per DESIGN.md). No PUNCH, no SLAM. The episode argues against AI-launch hype, so the rhythm itself is editorial — a slow glide between holds, with the only rhetorical accent landing on PIVOT (the italic serif "I thought…") and the only chromatic accent landing on PAYOFF (the single `#ffffff` emphasis word). Cuts ride the conversational phrase boundaries from Phase 3 pacing — tight on inter-phrase silences, breath preserved between the two "I thought" clauses for rhetorical weight.

**Beat duration budget (~26.5s total, mapped from Phase 3 takes):**

- HOOK ≈ 2.0s — "Age of artificial intelligence." (transcript range 000.12–001.34, plus tail breath)
- PROBLEM ≈ 11.5s — "when I'm increasingly using free open-source tools…" (003.10–013.60, plus joiner breath)
- PIVOT ≈ 2.5s — "I thought, 'Why don't we turn…'" (015.72–017.36, held to give the italic serif a breath)
- PAYOFF ≈ 10.5s — "I thought, 'Why don't we return to the roots…'" (018.82–030.80, ending on the unfinished aspirational thought)

---

## 3. Global Rules

**Container & layout (every beat):**

- `width: 100%; height: 100%; padding: 96px 64px; box-sizing: border-box;` per Layout-Before-Animation. No absolute-positioned content containers.
- Talking-head video plate fills the frame; overlay typography pinned to the upper or lower third only.
- One **vertical hairline rule** (`1px solid #b48f43` / `accent-stop-1`, x = 64px, full height) anchors the left rail across all four beats — visual continuity through transitions.
- 12-column logical grid; copy stays in columns 1–8, leaving 9–12 for accent marks and timecode.
- ≥35% of any hero frame remains empty ground. No edge-to-edge content. No cards. No borders. Surfaces are implied by hairlines and tonal shifts.

**Atmosphere layers (3 per beat sharing one breath cycle, per DESIGN.md "atmosphere: hairline-rules / subtle-grain / ambient-glow"):**

1. **Hairline rule** — left rail vertical, `accent-stop-1` 1px, opacity breathing 0.6 → 0.9 → 0.6 over 6s (`sine.inOut`, finite repeat count derived from beat duration).
2. **Subtle procedural grain** — full-frame, 4–6% opacity, static (no animation; the breath belongs to the glow). Tinted toward foreground ivory so it reads as paper-stained, not OLED noise.
3. **Ambient brass glow** — `radial-gradient(circle at 50% 60%, #c8a04b 8%, transparent 65%)` behind speaker. 6s breath, opacity 0.05 → 0.10 → 0.05 (`sine.inOut`, finite repeat).
4. (HOOK + PIVOT only) **Ghost word** at 4% opacity foreground — `INTELLIGENCE` on HOOK, `THOUGHT` on PIVOT — oversized (12rem+), top-left, slow drift `y: -8 → 0 → -8` over 8s.

**Motion (calm energy from DESIGN.md):**

- Easings: entry `sine.inOut`, exit `power1.in`, ambient `sine.inOut`. Vary entrance ease per beat — `sine.inOut` (HOOK), `power2.out` (PROBLEM), `expo.out` (PIVOT), `power3.out` (PAYOFF) — so beats don't feel mechanically identical (DESIGN.md "Do" rule).
- Entrance duration 1.0s, hold 2.5s, transition 1.2s.
- Every decorative has ambient motion — breath, drift, or pulse. Static decoratives are forbidden by house-style.
- No `repeat: -1`. All ambient cycles use finite repeat counts calculated from beat duration.
- No exit animations on HOOK / PROBLEM / PIVOT — the transitions handle the exits. PAYOFF (final beat) may fade out on the last 0.6s.

**Transitions (global):**

- Primary: **cross-warp-morph** shader (per DESIGN.md `motion.transition: cross-warp-morph`). 0.8s, `power2.inOut`. Used on HOOK→PROBLEM and PIVOT→PAYOFF — the two "lean-in" moments.
- Connective: **CSS blur-through** (`blur:20px, 0.3s` exit → `blur:20px → 0, 0.25s power3.out` entry). Used on PROBLEM→PIVOT — the editorial mid-step where the italic serif arrives.
- Velocity-matched: exit acceleration meets entry deceleration within ~5% tolerance at the cut.
- Burned-in captions cross the transition seam owned by HyperFrames root timeline (no per-scene caption fan-out).

**Captions strip (all four beats):**

- Word-grouped, burned-in, lower rail, `foreground-stop-1` Inter 300, sentence case. No background plate; relies on grain + hairline for legibility.
- Marker sweep on the key term per beat: HOOK `intelligence`, PROBLEM `AI agents`, PIVOT `I thought`, PAYOFF `for life`. Sweep is a 0.4s `accent-highlight-1` underline that draws left → right under the word at its onset timestamp from `transcripts/final.json`.

---

## 4. Per-Scene Beats

### Scene 1 — HOOK (≈ 0.0s – 2.0s)

**Concept.** Camera is already inside a quiet room. The speaker is mid-frame, naturally lit. Three uppercase words — AGE OF / ARTIFICIAL / INTELLIGENCE — settle into the upper third like serial numbers stamped on a brass plate. This is the only beat where the headline shouts; the brand argues the rest of the way in mixed case. The viewer should feel the "Age of AI" claim being received with skepticism, not wonder.

**Mood direction.** Vignelli editorial title card meets the opening of a documentary about analog instruments. NOT a tech-launch hero. Think of the way a Criterion Collection title sits — confident, reserved, slightly off-axis from corporate.

**Depth layers (8 elements):**

- BG (3 atmosphere): warm-ink gradient base `#0d0b08 → #060504` (vignette); ambient brass radial glow (`#c8a04b` at 8%, breathing 6s); subtle procedural grain (4% opacity).
- BG (1 thematic): ghost word `INTELLIGENCE` at 4% foreground opacity, 12rem Inter 300 uppercase, top-left, slow vertical drift.
- MG (2 content): three-line headline `AGE OF / ARTIFICIAL / INTELLIGENCE` (Inter 300, 4rem, uppercase, `letter-spacing: 0.12em`, foreground `#f4ede0`), upper third columns 1–8; talking-head video plate behind, full-frame.
- FG (2 structural): vertical hairline rule `accent-stop-1` 1px at x=64px, breathing opacity 0.6–0.9; timecode chip `EP·01 / 00:00` top-right, midtone Inter 400 0.875rem uppercase `letter-spacing: 0.18em`, static.

**Animation choreography.**

- Headline lines CASCADE in stagger 0.18s — `AGE OF` arrives at 0.10s, `ARTIFICIAL` at 0.28s, `INTELLIGENCE` at 0.46s. Each line: opacity 0 → 1, `y: +24 → 0`, 1.0s `sine.inOut`. No blur, no scale.
- Hairline rule DRAWS down — `scaleY: 0 → 1`, `transformOrigin: top`, 0.9s `sine.inOut`, starting at 0s.
- Timecode chip fades in — opacity 0 → 1, 0.6s `sine.inOut`, starting at 0.40s.
- Ambient glow breathes — opacity 0.05 → 0.10 → 0.05, 6s `sine.inOut` (finite repeat × 0 within HOOK's 2s; carries through transition).
- Ghost `INTELLIGENCE` drifts — `y: -8 → 0 → -8`, 8s `sine.inOut` (partial cycle within HOOK).
- Caption strip word-group `AGE OF ARTIFICIAL INTELLIGENCE` arrives lower rail, with marker sweep under `intelligence` at the word's onset timestamp.
- Talking-head plate plays naturally; no overlay competes with face mid-frame.

**Transition out.** **Cross-warp-morph shader**, 0.8s, `power2.inOut`. The headline glyphs warp outward toward edges as PROBLEM's body copy warps inward. The hairline rule and timecode persist across the seam (continuity anchors).

---

### Scene 2 — PROBLEM (≈ 2.0s – 13.5s)

**Concept.** A long, conversational settle. The viewer hears the actual argument being assembled: "open-source tools, deployed by AI agents, software I write for myself for work." The visual frame quiets — no headline, just the speaker, the rail, and the burned-in captions doing the load-bearing work. The atmosphere here is `editorial calm` — the longest beat of the four, and it must breathe.

**Mood direction.** The middle pages of a print essay. Documentary mid-act, between the title card and the turning point. Editorial restraint. Think the quiet stretch in a Wes Anderson interview — composed, flat-lit, patient.

**Depth layers (9 elements):**

- BG (3 atmosphere): warm-ink gradient base; ambient brass glow continues breathing from HOOK (no re-entrance — continuity); subtle grain.
- BG (1 thematic): faint vertical column ruling at x = 33%, `midtone-stop-1` 1px, opacity 0.25, slow horizontal drift ±2px over 10s — implies the 12-column grid without showing it.
- MG (2 content): talking-head video plate (hero); role chip `OPEN-SOURCE / SELF-BUILT TOOLS` upper third, columns 1–6, midtone Inter 400 0.875rem uppercase `letter-spacing: 0.18em`.
- FG (3 structural / accent): vertical hairline rule (carried from HOOK, breathing); timecode chip top-right ticks `EP·01 / 00:02 → 00:13` (tabular-nums, slow count-up); caption strip lower rail with marker sweep under `AI agents`.

**Animation choreography.**

- Role chip `OPEN-SOURCE / SELF-BUILT TOOLS` types on (character-by-character, 0.018s per glyph, total ≈ 0.5s) at 2.2s. `power2.out`.
- Faint column ruling DRIFTS horizontally `x: -2 → +2 → -2` over 10s `sine.inOut` (finite cycle within beat).
- Timecode chip COUNTS UP — `00:02` → `00:13` driven by `data-start` / `data-duration` and a `gsap.to({ duration: 11 })` on a number-stepper, tabular-nums.
- Ambient glow continues breathing (no re-entrance).
- Hairline rule continues breathing.
- Caption strip word groups arrive on phrase boundaries from `transcripts/final.json` — natural pacing; marker sweep fires under `AI agents` at the word's onset timestamp, 0.4s `accent-highlight-1` left-to-right.
- No exit animation. Transitions handle the handoff.
- Talking-head plate plays naturally; speaker's face stays uncluttered.

**Transition out.** **CSS blur-through**, exit `blur: 0 → 20px, 0.3s power3.in` → entry `blur: 20px → 0, 0.25s power3.out`. Connective tissue — the speaker's face stays present across the seam, suggesting one continuous monologue rather than a cut.

---

### Scene 3 — PIVOT (≈ 13.5s – 16.0s)

**Concept.** The rhetorical hinge. After eleven seconds of quiet diagnosis, a single italic line — Playfair Display, 3rem — slides in from the lower-left, indented from the rail, beneath a fresh accent hairline. "I thought…" The italic serif appears EXACTLY here in the entire composition (per DESIGN.md). It marks the turn from problem to proposition — a literary aside, not a title.

**Mood direction.** The page-turn in an essay. The moment a documentary subject pauses, looks slightly off-camera, and the editor cuts to silence. Cinematic title-sequence punctuation, but quietly — no Klieg lights.

**Depth layers (8 elements):**

- BG (3 atmosphere): warm-ink gradient base; ambient brass glow (continuing breath); subtle grain.
- BG (1 thematic): ghost word `THOUGHT` at 4% foreground opacity, 12rem Inter 300 uppercase, top-right (mirrored from HOOK's top-left), slow drift `y: +8 → 0 → +8` over 8s.
- MG (2 content): talking-head video plate; pull quote `I thought…` (Playfair Display italic, 3rem, foreground `#f4ede0`, mixed case) lower-third, columns 2–8, indented one column from the rail.
- FG (2 structural / accent): a SECOND short horizontal hairline rule `accent-stop-1` 1px directly beneath the pull quote, `width: 0 → 240px`, `transformOrigin: left`, 0.6s `expo.out`; vertical hairline rule (continuing breath); timecode chip persists.

**Animation choreography.**

- Pull quote `I thought…` enters with `expo.out` — opacity 0 → 1, `y: +24 → 0`, 1.0s. Glyphs settle in one piece (no per-letter stagger — that would feel mechanical against the literary tone).
- Short horizontal hairline DRAWS beneath the quote — `scaleX: 0 → 1`, `transformOrigin: left`, 0.6s `expo.out`, starting 0.18s after the quote arrives.
- Ghost word `THOUGHT` drifts vertically (8s sine).
- Vertical hairline continues breathing.
- Ambient glow continues breathing.
- Caption strip marker sweep fires under `I thought` at the word's onset timestamp (0.4s `accent-highlight-1` underline).
- No exit animation on pull quote. The shader transition lifts it out.

**Transition out.** **Cross-warp-morph shader**, 0.8s, `power2.inOut`. The italic glyphs and the short rule warp outward; PAYOFF's body copy warps in. The vertical hairline rail persists.

---

### Scene 4 — PAYOFF (≈ 16.0s – 26.5s)

**Concept.** The aspirational unfinished thought. The speaker lands the proposition — return to good old software you pay for once and use for life — and the composition ends mid-aspiration. The single `#ffffff` emphasis word arrives on `for life`: same Inter 300, same body size as the surrounding caption, but in pure foreground-highlight. No underline, no box. The color shift IS the emphasis. The viewer is left with an unfinished sentence and a brass rail still breathing.

**Mood direction.** The closing paragraph of an editorial. The last quiet line of a documentary, before the credits. Resolution without bombast — the argument has been made; the music doesn't swell.

**Depth layers (10 elements):**

- BG (3 atmosphere): warm-ink gradient base; ambient brass glow (continuing breath, brightening 0.05 → 0.10 → 0.07 to mark resolution); subtle grain.
- BG (1 thematic): faint horizontal hairline at 80% frame height, `accent-stop-2` 1px, opacity 0.2 — a quiet "ground line" suggesting the thought is settling.
- MG (3 content): talking-head video plate; role chip `PAY ONCE / USE FOR LIFE` upper third columns 1–6, midtone Inter 400 0.875rem uppercase `letter-spacing: 0.18em`; emphasis fragment `for life` rendered in caption strip in `foreground-highlight-1` `#ffffff` (the only `#ffffff` in the entire composition).
- FG (3 structural / accent): vertical hairline rule (continuing breath, lifting to opacity 1.0 in last 0.6s); timecode chip ticks `EP·01 / 00:16 → 00:26`; caption strip lower rail with marker sweep under `for life`.

**Animation choreography.**

- Role chip `PAY ONCE / USE FOR LIFE` types on (character-by-character, 0.018s per glyph, ≈ 0.4s) at 16.3s. `power3.out`.
- Faint horizontal "ground line" DRAWS — `scaleX: 0 → 1`, `transformOrigin: left`, 1.2s `power3.out`, starting 16.2s.
- Caption strip word groups arrive on phrase boundaries; the word `life` (within `for life`) renders in `#ffffff` while neighboring caption words stay `foreground-stop-1`. Marker sweep fires under `for life` at the phrase onset timestamp.
- Timecode chip COUNTS UP `00:16` → `00:26` (tabular-nums).
- Ambient glow brightens slightly across the beat (0.05 → 0.10 → 0.07).
- Vertical hairline rail lifts to full opacity 1.0 in the final 0.6s — the only beat where the rail goes to full strength. Subtle resolution.
- PAYOFF (final beat) fade-out — `opacity: 1 → 0`, 0.6s `power1.in`, applied to caption strip and role chip in the last 0.6s. The talking-head plate fades with the master timeline.

**Transition out.** None — final beat. Composition resolves on the unfinished aspirational thought; the master fade carries the close.

---

## 5. Recurring Motifs

These threads run across all four beats and bind them into a single composition rather than four cuts:

- **Vertical brass hairline rail at x = 64px** — present on every beat, breathing on the same 6s `sine.inOut` cycle. Acts as the spine; the eye returns to it through every transition. Lifts to full opacity only in the final 0.6s of PAYOFF.
- **Ambient brass radial glow** — `radial-gradient(circle at 50% 60%, #c8a04b 8%, transparent 65%)` behind the speaker, continuous breath across all four beats (no re-entrance per scene). Brightens subtly on PAYOFF.
- **Subtle procedural grain** — 4–6% opacity, static, full-frame, all four beats. Reads as paper-stain, not noise. The "patina" of the brand.
- **Timecode chip `EP·01 / MM:SS`** — top-right, midtone Inter 400 0.875rem uppercase `letter-spacing: 0.18em`, ticks across PROBLEM and PAYOFF (the two "letting time pass" beats). Holds on HOOK and PIVOT.
- **Ghost word at 4% opacity** — `INTELLIGENCE` (HOOK, top-left) and `THOUGHT` (PIVOT, top-right). Bookends the rhetorical structure. Slow drift, finite cycle.
- **Brass marker sweep under one key term per beat** — HOOK `intelligence`, PROBLEM `AI agents`, PIVOT `I thought`, PAYOFF `for life`. Same mechanic, four occurrences. The argument's load-bearing words.
- **Inter 300 everywhere; Playfair Display italic exactly once** — the typographic discipline IS the brand. The single italic appearance on PIVOT earns its place precisely because it's unique.
- **Single `#ffffff` highlight reserved for `life` in PAYOFF** — every other "white" in the composition is `#f4ede0` (foreground) or `#dcd5c9` (foreground-stop-1). The lone `#ffffff` glyph carries the emphasis without underline, box, or weight change.

---

## 6. Negative Prompt

Informed by `DESIGN.md` "Don't" rules and `house-style.md` lazy-default warnings:

- **No AI-launch palette.** No cyan-on-dark, no purple-to-blue gradients, no neon, no electric anything. The episode argues against that aesthetic; using it would betray the content.
- **No gradient text.** `background-clip: text` is forbidden. The brass appears as fills, hairlines, and glows only.
- **No card grids, no boxes, no panels.** Surfaces are hairlines and tonal shifts. There are no borders.
- **No drop shadows or colored glows behind text.** Depth comes from grain and hairlines, not blur.
- **No pure `#000` or `#fff`** — except the single reserved `#ffffff` on PAYOFF's `life`. Every black is `#0d0b08` or its stops; every other white is `#f4ede0` or its stops.
- **No serif on body copy.** Playfair Display appears EXACTLY ONCE — PIVOT pull quote. Anywhere else, Inter.
- **No ALL-CAPS shouting beyond HOOK.** PROBLEM, PIVOT, PAYOFF stay in mixed/sentence case. This is a quiet argument, not a hype reel.
- **No exit animations on HOOK / PROBLEM / PIVOT.** Transitions handle the exits. Only PAYOFF (final) may fade out.
- **No `repeat: -1`.** All ambient cycles use finite repeat counts derived from beat duration. (HF lint regex flags `repeat: -1` even in comments — avoid the literal substring entirely.)
- **No left-edge accent stripes on cards/callouts.** The vertical hairline at x=64px IS the rail; do not add competing left-edge stripes on individual elements.
- **No identical entrance pattern across beats.** Vary entrance ease per beat (`sine.inOut` / `power2.out` / `expo.out` / `power3.out`). If every element enters the same way, the composition has no choreography.
- **No overlay content on the middle third of the frame.** The speaker's face occupies the middle third; overlays live in the upper or lower third only.
- **No multi-beat sub-composition split.** HF 0.4.41/0.4.44 sub-comp loader produces black renders (orchestrator memo `feedback_multi_beat_sub_compositions`). All four beats live inline in `index.html` until upstream #589 lands.
- **No `data-has-audio="true"` on the talking-head video plate's StaticGuard probe** — set `data-has-audio="false"` on the inline video element and route the audio through a separate `<audio>` track per HF canon (`feedback_hf_video_audio_canon_bug`).
- **No banned fonts.** Roboto, default Helvetica fallback, faux italic — none of these. Inter and Playfair Display only, both loaded explicitly.
- **No invented hex values.** Every color cited above appears in `DESIGN.md`. Beat sub-agents do not introduce off-palette hexes.
