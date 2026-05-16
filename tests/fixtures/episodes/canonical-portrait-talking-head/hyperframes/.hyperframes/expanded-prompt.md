# Expanded Prompt — canonical-portrait-talking-head

Four-beat editorial talking-head monologue, 26.5s portrait (1080×1920), shape: single continuous take with phrase-boundary cuts. Visual register: Stripe Press / Kinfolk — italic serif on warm-tinted near-black, generous negative space, one muted-indigo accent reserved for the loaded word per scene. Cadence is breath-paced, not kinetic. The viewer should feel they are reading a memo.

Canon read for this expansion: `house-style.md`, `references/video-composition.md`, `references/beat-direction.md`, `references/prompt-expansion.md`, plus `hyperframes/DESIGN.md` (Long-Form Memo system).

---

## 1. Title + Style Block

**Title:** _Age of Artificial Intelligence — A Memo to the Pay-Once Era_

**Palette (verbatim from DESIGN.md):**

- Background: `#0c0b0a` (warm-tinted near-black; never #000)
- Background stops: `#080706`, `#050403`
- Background highlights (vignette upper-left): `#16140f`, `#1d1a13`
- Foreground: `#f3ece0` (parchment)
- Foreground stops: `#d9d2c5`, `#bfb8ab`
- Foreground highlight: `#fbf6ec`
- Midtone (rules, overlines, decorative underscores): `#b8a982`
- Midtone stops: `#988a66`, highlight `#cdbf99`
- Accent (editorial indigo — ONE word/glyph per scene): `#3a4cb8`
- Accent stops: `#2b3a93`, `#1d296e`
- Accent highlight (used when accent lands on text, for AA): `#5a6dd1`, `#8294e3`

**Typography (verbatim):**

- Headline — Playfair Display, italic, 400, 4.5rem, letter-spacing -0.02em, line-height 1.05
- Pullquote — Playfair Display, italic, 400, 6rem, letter-spacing -0.025em, line-height 1.0
- Overline — Inter, 500, 0.8125rem, uppercase, letter-spacing 0.18em
- Body — Inter, 300, 1.15rem, line-height 1.6, measure capped at 56ch

**Mood:** Editorial calm. Stripe Press book cover meets a quiet Kinfolk spread. Italic serif IS the voice — reflective, not announcing. The composition argues against the visual idiom of AI hype (neon, gradients, particles); using that idiom would undermine the message.

**Energy:** Calm. Easings — entry `sine.inOut`, exit `power1.in`, ambient `sine.inOut`. Entrance 1.0s, hold 2.0s, transition 1.2s.

**Atmosphere bank (from DESIGN.md):** hairline-rules, warm-grain, parchment-vignette.

---

## 2. Rhythm Declaration

`hold-BUILD-pivot-hold` — four beats over 26.5s:

- **HOOK** (00.00 → 03.10, ~3.1s) — single phrase + a long held breath. The frame announces the register, then waits.
- **PROBLEM** (03.10 → 14.40, ~11.3s) — the longest scene; the spoken thought unspools. Type cascades phrase by phrase as the speaker accrues the argument.
- **PIVOT** (14.40 → 18.20, ~3.8s) — false-start hesitation "I thought, 'Why don't we turn...'". A typographic stutter; one glyph swap on accent.
- **PAYOFF** (18.20 → 26.50, ~8.3s) — the resolved thought; pullquote scale; the only fully-set headline in the piece; trails off mid-sentence with no exit tween.

Shaders land on HOOK→PROBLEM (cross-warp-morph, 1.2s) and on PAYOFF (no transition out — the piece ends mid-thought; the cross-warp shader handles HOOK→PROBLEM and PROBLEM→PIVOT; PIVOT→PAYOFF is a CSS blur-through to model the rhetorical self-correction). Per beat-direction.md: 1–2 shader moments + the rest CSS keeps shader impact intact.

---

## 3. Global Rules

- **Parallax layers:** three depths per scene — BG (vignette + grain + ghost type), MG (headline / pullquote / body), FG (overline + hairline rule + one accent glyph). MG drifts ±4px on a 10s sine; FG holds still. BG vignette breathes scale 1.00 ↔ 1.04 on a 6s sine.
- **Micro-motion:** every decorative animates. Vignette breathes. Hairline rules pulse opacity 0.25 ↔ 0.35 on an 8s sine. Ghost type drifts 8–12px over 12s sine. Grain is static (per DESIGN.md — does not animate).
- **Primary transition:** cross-warp-morph (DESIGN.md `motion.transition`), 1.2s, power2.inOut — used between HOOK↔PROBLEM and PROBLEM↔PIVOT.
- **Accent transition:** blur-through (`blur:20px→0, 0.8s power3.out`) for PIVOT↔PAYOFF — slower than the catalog default (0.25s) because cadence is calm; the blur stands in for the speaker's reconsidered phrasing.
- **No exit on final beat** — PAYOFF ends with the speaker trailing off; the frame must also trail off (visible at hold) rather than tween out.
- **Accent discipline:** ONE word or ONE glyph per scene in `#3a4cb8` (or `#5a6dd1` if on text, for AA). Never as a gradient stop. Never as a fill.
- **No #000 / #fff anywhere.** Tint every neutral warm. Dead grey forbidden.
- **Asymmetric columns only.** Headlines live in cols 1–8 of an implicit 12-col grid; overlines and decorative rules float cols 9–12 OR vice versa, never both.
- **No cards, no rounded containers, no shadows.** Editorial register; not product UI.

---

## 4. Per-Scene Beats

### Scene 1 — HOOK (00.00 → 03.10, ~3.1s)

**Spoken:** "Age of artificial intelligence."

**Concept.** A title page in a serious book. The camera is already settled, not arriving — we open mid-thought, into a warm-tinted near-black canvas where a single overline and a single italic phrase carry the entire frame. The phrase "artificial intelligence" is the register-setter: this is a reflective monologue, not a launch reel. The viewer should feel they have opened a memo.

**Mood direction.** Stripe Press cover. The quiet first page of a Kinfolk essay. The opening title of a 1970s public-broadcasting essay film — calm, certain of itself, unhurried.

**Depth layers (8 elements):**

- BG-1 — Vignette: `radial-gradient(ellipse at top left, #16140f 0%, #0c0b0a 55%, #050403 100%)`, full-frame. Ambient: scale 1.00 ↔ 1.04 on 6s sine loop. _breath_
- BG-2 — Ghost type: the word `MEMO` set in Playfair Display italic 18rem, color `#1d1a13` (background-highlight-2), positioned cols 7–12 rows 2–5, opacity 0.55 in its own color (still very low against bg). Drift 10px on 12s sine. _drift_
- BG-3 — Grain overlay: 7px noise PNG at opacity 0.04, full-frame. Static.
- FG-1 — Overline: `EPISODE 01 · A MEMO`, Inter 500 uppercase 0.8125rem letter-spacing 0.18em, color `#b8a982`, anchored top-left at col 2 row 3. Types on character by character, 0.05s stagger, sine.inOut. _types on_
- FG-2 — Hairline rule: 1px solid `#b8a982` at opacity 0.30, horizontal, cols 2–6, sitting 32px below the overline. Draws left→right `scaleX: 0 → 1`, 0.8s expo.out, transform-origin left. _DRAWS_
- MG-1 — Headline: _Age of_ in Playfair Display italic 4.5rem, color `#f3ece0`, cols 2–8 row 7. Fades and rises `y:24, opacity:0 → y:0, opacity:1`, 1.0s sine.inOut, delayed 0.4s after the hairline. _floats up_
- MG-2 — Pullquote: _artificial intelligence_ in Playfair Display italic 6rem, color `#fbf6ec`, cols 2–10 rows 9–11. The opening glyph `a` is set in `#5a6dd1` (the scene's accent moment — italic lowercase a in indigo). Fades in 1.2s after the headline, 1.2s sine.inOut. _settles in_
- FG-3 — Decorative underscore: 2px solid `#988a66`, beneath the pullquote, cols 2–7. Animates left→right `scaleX: 0 → 1`, 0.6s expo.out, beginning the moment the pullquote settles. _DRAWS_

**Animation choreography summary.** Overline _types on_ → hairline _DRAWS_ left→right → headline _floats up_ from y:24 → pullquote _settles in_ with its accent glyph → underscore _DRAWS_ beneath. Hold for ~1.0s of dead air (the speaker's pause after "intelligence"). Five staggered entrances inside the first 1.6s, then breath.

**Transition out.** cross-warp-morph (`packages/shader-transitions/README.md`), 1.2s, power2.inOut, into PROBLEM. The shader carries the typographic shift from large pullquote to body-set paragraph — the morph reads as the speaker's thought continuing on the next page.

**SFX cue.** A single soft cloth-paper turn at t=0.0 (very low; just enough to ground the register). Silence underneath.

---

### Scene 2 — PROBLEM (03.10 → 14.40, ~11.3s)

**Spoken:** "when I'm increasingly using free open-source tools because I can simply deploy them for myself easily with the help of AI agents or just write the software I need for work myself,"

**Concept.** The thought unspools. We are now reading the paragraph that follows the title. The text builds line by line as the speaker accrues the argument — open-source, deploy-for-myself, AI-agents, write-it-myself. The frame holds an asymmetric editorial reading column; the eye travels top-to-bottom as new phrases settle in. ONE word — `myself` — carries the scene's accent indigo: it is the rhetorical fulcrum (the speaker is no longer a consumer of software; he is the maker).

**Mood direction.** A long paragraph in a New Yorker profile. Editorial calm. The quiet middle section of a documentary chapter, where the narration is the work and the visual stays out of its way.

**Depth layers (9 elements):**

- BG-1 — Vignette: same upper-left radial as Scene 1, ambient breath continued (the breath does NOT reset on cuts — it's a continuous loop across the whole composition).
- BG-2 — Ghost type: `OPEN SOURCE` set in Playfair Display italic 14rem, color `#16140f`, cols 1–7 rows 12–17 (lower-left this time, balancing Scene 1's upper-right ghost). Drift 12px on 12s sine.
- BG-3 — Grain overlay: continued (static).
- FG-1 — Overline: `§ 02 — THE DRIFT`, Inter 500 uppercase color `#b8a982`, anchored top-right cols 9–11 row 3. Fades in opacity:0 → 1, 0.6s sine.inOut. _fades in_
- FG-2 — Hairline rule: vertical 1px solid `#b8a982` at opacity 0.28, cols 8 rows 3–18 — a thin reading-margin rule down the right side. Draws top→bottom `scaleY: 0 → 1`, 1.0s sine.inOut, transform-origin top. _DRAWS down_
- MG-1 — Body paragraph (line 1): _"when I'm increasingly using free open-source tools"_, Inter 300 1.15rem line-height 1.6 color `#f3ece0`, cols 2–7 row 6. _CASCADE in_ word-by-word, 0.08s per word stagger, each word `y:8, opacity:0 → y:0, opacity:1` 0.5s sine.inOut. Timed to roughly track the spoken phrase.
- MG-2 — Body paragraph (line 2): _"because I can simply deploy them for myself easily"_, same style, cols 2–7 row 9. _CASCADE_ on the spoken cue. The word `myself` is set in `#5a6dd1` italic (Playfair Display italic 1.15rem inline, NOT Inter — a single-word typographic shift to mark the accent). This is the scene's one accent moment.
- MG-3 — Body paragraph (line 3): _"with the help of AI agents"_, cols 2–7 row 12. _CASCADE_ on cue.
- MG-4 — Body paragraph (line 4): _"or just write the software I need for work myself,"_ cols 2–7 row 15. _CASCADE_ on cue. The trailing comma sits in `#b8a982` to mark the unresolved clause.
- FG-3 — Tick indicator: a tiny `+` mark in `#b8a982` opacity 0.45 at the bottom of the right-side hairline rule (cols 8 row 18), Inter 300 1rem. Pulses opacity 0.45 ↔ 0.65 on a 4s sine — a reading-progress marker. _pulse_

**Animation choreography summary.** Vertical hairline _DRAWS down_ first, framing the reading column. Overline _fades in_. Then four body lines _CASCADE_ in sequence, word-by-word, timed to the spoken phrases. The accent on `myself` (line 2) is a typographic substitution that lands the moment the speaker says it — italic Playfair Display in indigo, against three lines of Inter 300 parchment. Tick `+` pulses throughout. The frame holds heavy on the trailing comma — the sentence is unfinished; the visual must wait.

**Transition out.** cross-warp-morph, 1.2s, power2.inOut, into PIVOT. The shader carries the four-line paragraph into the next beat's hesitation. The morph models the speaker drawing breath before a corrected thought.

**SFX cue.** Very faint typewriter-key tap on the entrance of each body line (mixed −18 dB; almost subliminal — texture, not Foley).

---

### Scene 3 — PIVOT (14.40 → 18.20, ~3.8s)

**Spoken:** "I thought, 'Why don't we turn...'" (false start — the speaker corrects himself)

**Concept.** A typographic stutter. The speaker says "turn" and stops; on the next breath he will correct it to "return." The frame must SHOW the false start. The headline appears, then the final glyph dissolves — leaving the phrase visibly unfinished. The frame is asking the same question the speaker is.

**Mood direction.** The moment in a documentary where the subject's first take is left in. A typesetter's correction mark in the margin. A poem with a word crossed out and rewritten — the original still visible underneath.

**Depth layers (8 elements):**

- BG-1 — Vignette: continued breath.
- BG-2 — Ghost type: the word `THOUGHT` in Playfair Display italic 16rem, color `#16140f`, cols 6–12 rows 4–8 (mid-right). Drift 10px on 12s sine.
- BG-3 — Grain overlay: continued.
- FG-1 — Overline: `§ 03 — A FALSE START`, Inter 500 uppercase color `#b8a982`, anchored top-left cols 2–5 row 3. Fades in. _fades in_
- FG-2 — Hairline rule: horizontal 1px solid `#b8a982` at opacity 0.30, cols 2–6 row 4. _DRAWS_ left→right 0.6s expo.out.
- MG-1 — Headline: _"I thought,"_, Playfair Display italic 4.5rem color `#f3ece0`, cols 2–8 row 7. _floats up_ from y:20, 0.8s sine.inOut.
- MG-2 — Pullquote: _"Why don't we turn..."_, Playfair Display italic 6rem color `#fbf6ec`, cols 2–10 rows 9–12. _settles in_ word-by-word, 0.18s stagger. The final word `turn` and the ellipsis `...` are tracked separately so they can be unset.
- FG-3 — Strikethrough rule: 2px solid `#988a66`, drawn horizontally THROUGH the word `turn` only — appearing in the last 0.6s of the beat, _DRAWS_ left→right 0.5s power2.in, transform-origin left. The accent moment of this scene: the strikethrough itself is in midtone, but the ellipsis glyph `...` is set in `#5a6dd1` (the indigo accent) the instant the strikethrough completes — marking the correction. _DRAWS_ + _glyph swap_

**Animation choreography summary.** Overline _fades in_ → hairline _DRAWS_ → headline `"I thought,"` _floats up_ → pullquote `"Why don't we turn..."` _settles in_ → strikethrough _DRAWS_ through `turn` → ellipsis glyph _swaps_ to indigo. The whole beat is 3.8s; the last 1.0s is the visible correction. The hold is short by design — we cut on the speaker's intake of breath.

**Transition out.** CSS blur-through, exit `blur:20px, opacity:0, 0.8s power3.in` on the pullquote only (overline + hairline cross-fade with the next beat under the shader), into PAYOFF. The blur stands in for the speaker reconsidering his phrasing — visually we are unfocusing the wrong word and refocusing on the right one. Slower than the catalog default (0.25s) because cadence is calm.

**SFX cue.** A single soft pencil-line scratch (the strikethrough), then silence. No music shift.

---

### Scene 4 — PAYOFF (18.20 → 26.50, ~8.3s)

**Spoken:** "I thought, 'Why don't we return to the roots, to good old software that you pay for once and use for life?' Yes, maybe it's not as interesting from a business point-of-view, but how cool is it to..."

**Concept.** The resolved thought. The largest typographic moment of the piece — the only fully-set pullquote, framed in the center of the reading column, holding the rhetorical question that is the monologue's thesis. The word `roots` carries the accent indigo. The final phrase trails off mid-sentence ("...how cool is it to...") — the visual must trail off with it. No exit tween. The piece ends visibly unfinished, as a memo with the pen still moving.

**Mood direction.** The last page of a Stripe Press essay. The pullquote on a New Yorker spread. The single image that closes a documentary chapter — held, unhurried, not punctuated.

**Depth layers (10 elements):**

- BG-1 — Vignette: continued breath.
- BG-2 — Ghost type: the word `ROOTS` in Playfair Display italic 22rem, color `#1d1a13` (slightly brighter than prior scenes — this is the climax; the ghost is allowed to assert), cols 1–9 rows 14–18. Drift 8px on 12s sine. Ambient opacity pulse 0.55 ↔ 0.70 on 8s sine (very subtle).
- BG-3 — Grain overlay: continued.
- FG-1 — Overline: `§ 04 — A MEMO TO MYSELF`, Inter 500 uppercase color `#b8a982`, anchored top-left cols 2–6 row 3. Fades in. _fades in_
- FG-2 — Hairline rule (upper): 1px solid `#b8a982` at opacity 0.30, horizontal cols 2–6 row 4. _DRAWS_ 0.8s expo.out.
- FG-3 — Hairline rule (lower): 1px solid `#b8a982` at opacity 0.30, horizontal cols 2–10 row 13 — a closing rule beneath the pullquote. _DRAWS_ 1.0s expo.out, beginning after the pullquote settles.
- MG-1 — Headline: _"I thought,"_, Playfair Display italic 4.5rem color `#d9d2c5` (foreground-stop-1, slightly demoted — we want the pullquote to dominate), cols 2–8 row 6. _floats up_ from y:18, 0.8s sine.inOut.
- MG-2 — Pullquote: _"Why don't we return to the roots"_, Playfair Display italic 6rem color `#fbf6ec`, cols 2–11 rows 8–12. _settles in_ word-by-word, 0.22s stagger. The word `roots` is set in `#5a6dd1` italic — the scene's accent moment, and the keystone word of the entire monologue. A 2px solid `#988a66` decorative underscore _DRAWS_ left→right beneath `roots` only (0.6s expo.out), arriving the instant the word lands.
- MG-3 — Body paragraph (line 1): _"good old software that you pay for once and use for life."_, Inter 300 1.15rem line-height 1.6 color `#f3ece0`, cols 2–7 row 14 (below the lower hairline). _CASCADE_ word-by-word, 0.06s stagger.
- MG-4 — Body paragraph (line 2, trailing): _"Yes, maybe it's not as interesting from a business point-of-view, but how cool is it to"_, Inter 300 1.15rem color `#bfb8ab` (foreground-stop-2 — visibly demoted, marking it as continuing-thought), cols 2–7 rows 16–18. _CASCADE_ word-by-word, 0.06s stagger. The trailing `to` is followed by NO ellipsis — the sentence simply ends; the absence of punctuation IS the unfinished gesture. Final word `to` is held at its entrance state, then nothing.

**Animation choreography summary.** Overline _fades in_ → upper hairline _DRAWS_ → headline `"I thought,"` _floats up_ → pullquote `"Why don't we return to the roots"` _settles in_ with the keystone `roots` in indigo + decorative underscore _DRAWS_ beneath it → lower hairline _DRAWS_ → body line 1 _CASCADES_ → body line 2 _CASCADES_, slower and demoted in tone → the final word `to` lands and the composition holds, motion-still except for the continuous vignette breath, hairline opacity pulse, and ghost-type drift. No exit. The shader does NOT run on the final cut. The frame trails off the way the voice does.

**Transition out.** NONE. Per DESIGN.md: "Don't animate exits on the final beat — the speaker's last line trails off mid-thought; the visual must trail off too." The composition holds at its final pose. The cross-warp-morph shader does NOT fire. The audio fades; the frame does not.

**SFX cue.** None. Silence at the close. The continuous ambient (vignette breath, grain texture) is the only audio underneath the dialogue.

---

## 5. Recurring Motifs

A small set of visual threads runs across all four scenes — these are how the composition reads as a single memo, not four slides:

- **The upper-left vignette breath** — `radial-gradient(ellipse at top left, #16140f 0%, #0c0b0a 55%, #050403 100%)` on a 6s sine scale 1.00 ↔ 1.04. Continuous across the entire 26.5s; does NOT reset on cuts. This is the "reading lamp" that grounds every scene in the same warm-tinted room.
- **Hairline rules in `#b8a982` at opacity 0.25–0.35** — every scene anchors at least one hairline (horizontal in HOOK / PIVOT / PAYOFF; vertical reading-margin in PROBLEM). The rules pulse opacity 0.25 ↔ 0.35 on an 8s sine — the heartbeat of the memo.
- **Ghost type in `#16140f` to `#1d1a13`** — a single oversize italic word per scene drifting in a lower opacity background register: `MEMO` (HOOK upper-right) → `OPEN SOURCE` (PROBLEM lower-left) → `THOUGHT` (PIVOT mid-right) → `ROOTS` (PAYOFF lower-left, larger and slightly brighter as climax). The position rotates around the frame as the eye does.
- **Overline numbering** — `EPISODE 01 · A MEMO` → `§ 02 — THE DRIFT` → `§ 03 — A FALSE START` → `§ 04 — A MEMO TO MYSELF`. The numbering treats the piece as the chapters of a printed essay.
- **One accent indigo moment per scene** — lowercase italic `a` in HOOK (`#5a6dd1`); the word `myself` in PROBLEM (`#5a6dd1`); the ellipsis glyph `...` in PIVOT (`#5a6dd1`); the word `roots` in PAYOFF (`#5a6dd1`). The accent never appears on more than one element per scene, and never as a fill or gradient stop.
- **Decorative underscore in `#988a66`** — drawn left→right under the loaded word/phrase in HOOK and PAYOFF (0.6s expo.out). Acts as a typesetter's emphasis mark.
- **Static 7px grain at opacity 0.04** — full-frame, every scene, never animated. Keeps the printed-page feel; prevents the dark canvas from reading as digital flat fill.
- **Asymmetric reading column** — every scene reserves 25–40% of the frame as deliberate negative space. The column lives in cols 1–8 OR cols 5–12, never centered. The unfilled cols always carry exactly one decorative anchor (overline, hairline, or ghost type), never two.

---

## 6. Negative Prompt

Do NOT:

- Use neon, cyan-on-dark, purple-to-blue gradients, or any "AI-product" visual idiom. The monologue rejects that aesthetic; rendering in it would undermine the argument. (DESIGN.md hard constraint.)
- Use particle fields, scan-lines, radial neon glows, Data-Drift / Deconstructed atmospheres. (DESIGN.md hard constraint.)
- Use pure `#000` or pure `#fff` anywhere. Every neutral pulls toward `#b8a982` warm midtone.
- Use gradient text (`background-clip: text` + gradient). Lazy-default per house-style.md.
- Use left-edge accent stripes on callouts. Lazy-default per house-style.md.
- Use cards, rounded buttons, drop shadows, or any shadow-elevated container. Editorial register; not product UI.
- Introduce a third typeface. Playfair Display + Inter only. No Space Grotesk, Roboto, Open Sans, Lato, Montserrat, or any geometric display sans that would echo Silicon Valley deck aesthetics.
- Swap fonts mid-scene.
- Center text blocks with equal weight. Every scene leads with overline OR ghost-type anchor, never balanced bilaterally.
- Render numeric stats large. The script has no data; faking stat-card scaffolding would be dishonest. (DESIGN.md hard constraint.)
- Apply the accent indigo to more than ONE word/glyph per scene, or as a fill/gradient stop on text. The accent is a typographic mark, not a decoration.
- Animate an exit on the final beat. PAYOFF holds; the cross-warp-morph shader does NOT fire on the closing cut.
- Reset the vignette breath, hairline pulse, or ghost-type drift on scene cuts. These are continuous ambient loops; cutting them re-attacks each beat and breaks the single-memo reading.
- Use animation verbs from the high-energy register (SLAMS, CRASHES, PUNCHES, SHATTERS). Cadence is calm — `floats up`, `settles in`, `CASCADE`, `types on`, `DRAWS`, `fades in`, `pulse`, `breath`, `drift` only.
- Add box-shadows on text or content. The ONLY elevation cue is the upper-left vignette. (DESIGN.md hard constraint.)
