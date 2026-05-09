# Expanded Prompt — canonical-portrait-talking-head

## 1. Title + Style Block

**Title:** Soft Signal — Reflective Portrait (talking-head monologue, three beats: HOOK → THESIS → PAYOFF)

**Frame:** 1080×1920 portrait. Total duration ≈ 22.6 s. Speaker occupies the upper ~70% of frame; all overlay content sits in the lower third (y ≥ 1280px) or as a thin upper-edge label bar (y ≤ 120px). The middle band (120–1280px) is reserved for the speaker's face and is NEVER covered by an opaque overlay.

**Palette (cite DESIGN.md exactly — do NOT invent):**

| Role | Hex | Application |
| --- | --- | --- |
| primary | `#1a1614` | Background fill, scene backstop. Warm desaturated shadow tone. |
| on-primary | `#f4ebdc` | All body text, captions, pull-line. Warm cream — never pure white. |
| surface | `#241f1b` | Caption plate fill at 0.78 opacity, subtitle bar. |
| accent-amber | `#e8a14a` | One-per-beat emphasis: hairline rule, beat-marker dot, quote glyph, PAYOFF glow. |
| accent-rose | `#c08c87` | Secondary tint at ≤ 0.35 opacity. Soft underlines and ambient gradient stops only. |
| muted | `#8a7e72` | Beat label, timestamps, attribution, atmosphere lines. |

Pure `#000000` and pure `#ffffff` are banned (DESIGN.md "Don't"). Tint everything toward the warm grade.

**Typography (cite DESIGN.md exactly):**

- **headline** — `Playfair Display`, weight 400, italic, 3.25rem. Reserved for HOOK pull-line and PAYOFF sign-off only. Lowercase except proper nouns.
- **caption** — `Inter`, weight 400, 1.5rem, line-height 1.45. Burned-in subtitles. `max-width: 78%`. No `<br>`.
- **label** — `Inter`, weight 500, 0.75rem, letter-spacing 0.18em, uppercase. Beat marker, timestamps, "1 / 3" indicators.

Two families maximum. Banned: Roboto, Arial, system-ui fallbacks; gradient text; neon accents; cyan-on-dark; purple→blue gradients.

**Mood / grade:** Warm neutral; gentle midtone lift; slight shadow desaturation. Candle-warm amber lives INSIDE the speaker's lighting, not on top of it. The atmosphere descriptors are `warm-grain`, `soft-vignette`, `hairline-rule` (from DESIGN.md `motion.atmosphere`).

**Motion energy:** calm. Entry ease `sine.inOut`, exit ease `power1.inOut`, ambient ease `sine.inOut`. Entrance duration 0.9s, hold 2.6s, transition 1.1s. Nothing snaps; nothing overshoots; nothing punches. The only honest verbs in this composition are: SETTLES, BLEEDS IN, BREATHES, DRIFTS, FADES UP, EASES.

---

## 2. Rhythm Declaration

**Pattern:** `breath–HOLD–breath` (reflective monologue, three beats).

This is NOT a hook-PUNCH-CTA shape. The strategy explicitly forbids tight cuts: "deliberate; preserve natural pauses between phrases, no aggressive tightening." Each beat is allowed to breathe at its own length:

- **HOOK** — `breath` — short opener (~1.2 s of speech, [000.12 → 001.34]). Sets the warm room. One pull-line surfaces a single distilled phrase. Caption plate enters under it.
- **THESIS** — `HOLD` — the longest beat (~10.5 s, [003.10 → 013.60]). The viewer is meant to settle. Caption plate updates with rolling subtitle; beat marker holds; nothing competes with the voice. This is where the camera stops moving.
- **PAYOFF** — `breath` — closing reflection (~10.7 s of source, trimmed to land the sign-off, [018.82 → 029.50]). Pull-line returns as a sign-off (italic Playfair, lowercase). Single accent-amber glow under the headline. Frame holds an extra 0.4s after the audio resolves (DESIGN.md "Let pauses be visible").

Energy curve: low → low-with-gravity → low-with-warmth. The composition never lifts above `calm`. Any attempt to inject "PUNCH" or "SLAM" violates DESIGN.md `motion.energy: calm`.

---

## 3. Global Rules

**Background layer (every beat — house-style §"Background Layer", 2–5 atmospheric decoratives):**

1. **Warm grain overlay** (`#241f1b` noise PNG or seeded canvas) — full-frame, 0.10 opacity, NEVER pure black. Ambient: opacity breathes 0.08 ↔ 0.12 over 6 s, `sine.inOut`. Constant across all three scenes (continuity).
2. **Soft vignette** — radial gradient from transparent center to `#1a1614` at the edges, 0.45 opacity at corners. Ambient: scale 1.00 ↔ 1.04 over 8 s, `sine.inOut`. Anchors the speaker's face.
3. **Candle-warm halo** — radial glow `#e8a14a` at 0.10 opacity, 720px wide, positioned ~30% from top-left. Sits BEHIND the speaker as if leaking from off-frame practical light. Ambient: opacity 0.08 ↔ 0.12, x ±20px drift over 9 s, `sine.inOut`.
4. **Hairline tick** (decorative, distinct from the structural hairline rule) — 1px `accent-amber` at 0.30 opacity, 96px wide, anchored top-right (y ≈ 80px, x = right - 64px). Ambient: scaleX 0.92 ↔ 1.00 over 5 s, `sine.inOut`. Reads as a thermal-instrument indicator.
5. **Ghost type (THESIS only)** — the word `signal` set in Playfair Display italic at 480px, `#f4ebdc` at 0.04 opacity, anchored bottom-right and clipped by the frame edge so only the descender curve is visible. Ambient: y +12 ↔ -12 over 12 s, `sine.inOut`.

All five decoratives obey ambient-motion-only rules. None of them carry their own entrance — they fade in once at scene 1 with the grain and persist through transitions (the ghost type is the exception — it bleeds in at THESIS open and dismisses with the THESIS→PAYOFF shader).

**Micro-motion requirements:**

- Every decorative has a slow ambient GSAP tween (breath / drift / pulse). Static decoratives are forbidden by house-style §"Motion".
- Cycle counts MUST be finite per HF Hard Rule #8: `repeat: Math.ceil(duration / cycleDuration) - 1`. For a 22.6 s composition, a 6 s breath cycle uses `repeat: 3` (4 plays total ≈ 24 s, comfortably covering the duration).
- Caption plate and pull-line entrances use `gsap.from()`. Decoratives use `gsap.fromTo()` so their seek state is deterministic.

**Transition style:**

- **Primary transition:** `thermal-distortion` shader (DESIGN.md `motion.transition`). Used between HOOK→THESIS and THESIS→PAYOFF. 1.1 s duration, `power1.inOut`. The shader warps the warm grade into the next frame as if heat-haze drifts across — emotionally consistent with `warm-grain` + `soft-vignette` atmosphere, never aggressive (no glitch, no whip-pan, no smash cut).
- **Accent transition:** none. Three beats, two transitions, both thermal-distortion. Repeating one transition twice is a feature here — the composition is meant to feel continuous, like a single take with breath between thoughts.
- **Exit rule (NON-NEGOTIABLE — HF canon §"Scene Transitions" + DESIGN.md "No exit animations"):** No element animates `opacity: 0` or `y` offscreen before its scene's transition. Every element on a beat is fully visible the moment the thermal-distortion shader fires. The shader IS the exit. PAYOFF is the only beat where a final `gsap.to(opacity: 0)` is permitted, and only on the PAYOFF pull-line + glow during the 0.4 s post-audio hold.

**Density (per HF video-composition.md §"Density" — 8–10 elements per scene):**

| Layer | Count target |
| --- | --- |
| BG decoratives (atmosphere) | 4–5 (HOOK and PAYOFF use 4; THESIS adds the ghost type for 5) |
| MG content | 2–3 (caption plate + caption text + optional pull-line) |
| FG accents | 2–4 (beat marker dot + label, structural hairline, pull-line, PAYOFF timestamp) |
| **Total** | **8–10** |

**Color presence:** `accent-amber` appears exactly ONCE per beat as the eye-pull (a dot, a hairline, or a glow). Never on more than one element per beat (DESIGN.md "Once it's on three things in the same frame, remove two"). `accent-rose` is purely atmospheric — it tints the candle halo's outer falloff at ≤ 0.35 opacity and never carries text or structure.

**Pacing micro-beats:**

- Every entrance offsets at least 0.1–0.3 s from t=0 of its scene (HF §"Animation Guardrails"). No element fires at the exact frame of scene start.
- Within a beat, vary at least three eases on entrances. House style here is `sine.inOut` for the dominant motion, `power1.out` for the hairline scaleX, and `expo.out` for the beat-marker dot fade-in. Three eases. No more — calm energy forbids elastic / back / bounce.
- Hold the final frame 0.4 s after audio resolves (DESIGN.md "Do" — "Let pauses be visible").

---

## 4. Per-Scene Beats

### Scene 1 — HOOK  (source `[000.12 → 001.34]`, ≈ 1.22 s of speech, scene total ≈ 4.0 s)

**Concept.** Camera is already in the warm room. The speaker has just begun — we catch the breath before the first word. The frame feels like a hand-held portrait at golden hour, the grade already settled, the practical amber bleeding from a fixture just out of frame. The viewer leans in because the room is quiet, not because the cut is loud. One italic phrase surfaces beneath the speaker's voice — a thought already in motion. Nothing demands attention; the room is the attention.

**Mood direction.** Editorial calm. Reference: a Wim Wenders portrait still, or a Joan Didion essay opening — the kind of opening where the camera respects the silence. NOT a tech keynote, NOT a YouTube hook. The pull-line sits like a footnote the viewer overhears.

**Depth layers.**
- **BG (4 decoratives, persistent):** warm grain (full-frame, 0.10 opacity, breath cycle); soft vignette (radial fall-off to `#1a1614`); candle-warm halo (`#e8a14a` 0.10 opacity radial, top-left); decorative hairline tick (top-right, 96px wide, 0.30 opacity). All four enter together with a 0.6 s cross-fade from black-warm at t=0.
- **MG (2 elements):** caption plate (`surface` `#241f1b` at 0.78 opacity, full-width across lower third, 64px horizontal padding, 28px internal padding, `border-radius: 14px`) carrying the burned-in subtitle from the speech [000.12-001.34]. Caption text in `Inter` 1.5rem, `#f4ebdc`, `max-width: 78%`, left-aligned.
- **FG (3 elements):** beat marker top-left ("HOOK · 1 / 3" — `accent-amber` 6px dot + 12px gap + `Inter` 0.75rem 500 letter-spaced 0.18em uppercase in `muted` `#8a7e72`); pull-line (italic Playfair Display 3.25rem in `#f4ebdc`, lowercase, `max-width: 70%`, sitting 28px above the caption plate); structural hairline (1px `accent-amber` `#e8a14a` at 0.6 opacity, 240px wide, anchored to caption plate's left edge, between pull-line and plate).

Element count: 4 BG + 2 MG + 3 FG = **9** ✓

**Animation choreography (verbs — calm energy only):**
- BG grain, vignette, halo, hairline-tick → BLEED IN together at t=0.0–0.6, opacity 0 → target. Then SETTLE into ambient breath cycles for the rest of the composition.
- Beat marker → FADES UP at t=0.3, opacity 0 → 1, duration 0.6, `expo.out`. No motion (markers feel anchored, never animated — DESIGN.md "Beat marker" entrance rule).
- Caption plate → SETTLES UP at t=0.5, `gsap.from({opacity: 0, y: 24})`, duration 0.9, `sine.inOut`.
- Caption text → BLEEDS IN at t=0.65 (caption plate + 0.15s stagger per DESIGN.md), `gsap.from({opacity: 0, y: 12})`, duration 0.8, `sine.inOut`.
- Structural hairline → DRAWS LEFT-TO-RIGHT at t=1.1, `gsap.fromTo({scaleX: 0}, {scaleX: 1, transformOrigin: "left center"})`, duration 0.7, `power1.out`.
- Pull-line → EASES UP at t=1.4 (caption plate + 0.4s delay per DESIGN.md), `gsap.from({opacity: 0, y: 18})`, duration 0.9, `sine.inOut`.
- All decoratives continue ambient cycles. NO element exits.

Three distinct eases on entrances: `sine.inOut`, `expo.out`, `power1.out`. ✓

**Transition out.** `thermal-distortion` shader, 1.1 s, `power1.inOut`, fires at scene end (≈ t = 4.0 s of composition). The amber halo, grain, and vignette persist through the shader as "shared atmosphere"; only the caption plate, caption text, pull-line, hairline, and beat marker label are destination-different on the other side. The shader IS the exit — no `gsap.to(opacity: 0)` on any HOOK element.

---

### Scene 2 — THESIS  (source `[003.10 → 013.60]`, ≈ 10.5 s of speech, scene total ≈ 11.5 s)

**Concept.** The reflection deepens. The room has not changed but the viewer has — they're now listening at the speaker's pace. The frame holds. A fifth atmospheric decorative — the ghost word `signal` — bleeds into the lower-right edge of the frame as if the speaker's idea is becoming visible. The caption plate updates with rolling subtitle from the transcript; the pull-line is gone; nothing else moves except the breath of the decoratives and the speaker. This is the longest beat by design (`HOLD`) — the hold IS the message.

**Mood direction.** Editorial calm, settled. Reference: the second movement of a chamber piece — the place where the listener stops counting bars and starts feeling the line. The page from a printed essay where the reader's eye slows.

**Depth layers.**
- **BG (5 decoratives):** the four from HOOK continue (grain, vignette, halo, hairline-tick). NEW: ghost type — the word `signal` set in Playfair Display italic at 480px, `#f4ebdc` at 0.04 opacity, anchored bottom-right and clipped by the frame edge so only the upper descender curve is visible above the caption plate. Drifts y ±12px over 12 s.
- **MG (2 elements):** caption plate (same component, same position as HOOK) carrying rolling subtitles for [003.10–013.60]. Multi-line, two lines max, wrapped via `max-width: 78%`. Text in `Inter` 1.5rem `#f4ebdc`. Caption updates as the speech progresses (per-phrase, not per-word).
- **FG (2 elements):** beat marker updates to "THESIS · 2 / 3" (same component, same `accent-amber` dot + `muted` label). NO structural hairline this scene (hairline is reserved for HOOK and PAYOFF where it pairs with a pull-line). NO pull-line.

Element count: 5 BG + 2 MG + 2 FG = **9** ✓

**Animation choreography (verbs — calm energy only):**
- BG grain, vignette, halo, hairline-tick → continue ambient cycles (no entrance — they persisted through the thermal shader).
- Ghost type "signal" → BLEEDS IN at scene-local t=0.4, `gsap.fromTo({opacity: 0}, {opacity: 0.04})`, duration 1.4, `sine.inOut`. Ambient drift starts at t=1.8.
- Beat marker label → CROSSFADES from "HOOK · 1 / 3" to "THESIS · 2 / 3" via the shader's transitional frame (the label text is destination-different; the dot persists). On the THESIS side, opacity rises from 0 → 1 over 0.6 s, `expo.out`, t=0.3.
- Caption plate → SETTLES UP at scene-local t=0.5, `gsap.from({opacity: 0, y: 24})`, duration 0.9, `sine.inOut`. (Plate is a fresh element on this scene; the HOOK plate was ended by the shader.)
- Caption text — first phrase → BLEEDS IN at t=0.65, `gsap.from({opacity: 0, y: 12})`, duration 0.8, `sine.inOut`.
- Caption text — subsequent phrases → swap at phrase boundaries from the transcript via `tl.to(prevText, {opacity: 0}, swapTime)` followed by `tl.from(nextText, {opacity: 0, y: 8}, swapTime + 0.1)`. **Exception to the no-exit rule:** caption-text phrase swaps inside a single scene are not "scene exits" — they're caption rotation, allowed by HF caption canon. The caption PLATE never exits mid-scene; only the rotating text content does.
- All decoratives continue ambient cycles. NO scene-level element exits before the THESIS→PAYOFF thermal-distortion fires.

Three distinct eases: `sine.inOut`, `expo.out`, ambient `sine.inOut` cycles (plus the inherited `power1.out` of the persisted hairline-tick from HOOK). ✓

**Transition out.** `thermal-distortion` shader, 1.1 s, `power1.inOut`, fires at scene-local t ≈ 10.5 s (audio ends at [013.60]; allow 0.4 s pause before transition begins). Atmosphere (grain, vignette, halo, hairline-tick) persists; ghost type, caption plate, caption text, beat marker label are destination-different. No exit tweens.

---

### Scene 3 — PAYOFF  (source `[018.82 → 029.50]`, ≈ 10.7 s of source, scene total ≈ 7.1 s of composition after pacing)

**Concept.** The reflection lands. The speaker has arrived at the line they've been moving toward; the frame has been waiting for it. The italic Playfair pull-line returns as a sign-off — the same typographic voice as the HOOK pull-line, deliberately rhyming with it (recurring motif). A single candle-warm `accent-amber` glow blooms under the sign-off, one breath wide, then fades with the audio. The lower-right caption plate carries a `muted` timestamp and attribution — quiet authorship, no weight. After the audio resolves, the frame holds for 0.4 s — the breath after the last word — before the final fade.

**Mood direction.** Editorial close, intimate. Reference: the last paragraph of a New Yorker essay; a hand-set author's note on the colophon page. The kind of ending where the reader looks up at the room before turning the page.

**Depth layers.**
- **BG (4 decoratives, persistent):** grain, vignette, halo, hairline-tick (the ghost type from THESIS is dismissed by the thermal shader — it belongs to the THESIS hold). All four continue ambient cycles.
- **MG (2 elements):** caption plate carrying the final speech transcript [018.82–029.50] in `Inter` 1.5rem `#f4ebdc`, `max-width: 78%`. Plate component is identical to HOOK and THESIS for visual continuity.
- **FG (4 elements):** beat marker updates to "PAYOFF · 3 / 3"; structural hairline returns (1px `accent-amber` 0.6 opacity, 240px wide, anchored to caption plate's left edge, between pull-line and plate); pull-line in italic Playfair Display 3.25rem lowercase `#f4ebdc`, `max-width: 70%`, sign-off phrase distilled from the speech (NOT a verbatim caption duplicate — DESIGN.md `Pull-line` rule); timestamp / attribution in `Inter` 0.75rem 500 letter-spaced 0.18em uppercase `#8a7e72`, lower-right of caption plate, `font-variant-numeric: tabular-nums`.

Element count: 4 BG + 2 MG + 4 FG = **10** ✓ (DESIGN.md allows the timestamp ONLY on PAYOFF, which is why this beat carries one more FG element than HOOK.)

**Animation choreography (verbs — calm energy only, plus the only allowed exits in the composition):**
- BG decoratives → continue ambient cycles.
- Beat marker label → CROSSFADES from "THESIS · 2 / 3" to "PAYOFF · 3 / 3" through the shader; on PAYOFF side, opacity 0 → 1 over 0.6 s, `expo.out`, t=0.3.
- Caption plate → SETTLES UP at t=0.5, `gsap.from({opacity: 0, y: 24})`, duration 0.9, `sine.inOut`.
- Caption text → BLEEDS IN at t=0.65, `gsap.from({opacity: 0, y: 12})`, duration 0.8, `sine.inOut`.
- Structural hairline → DRAWS LEFT-TO-RIGHT at t=1.1, `gsap.fromTo({scaleX: 0}, {scaleX: 1, transformOrigin: "left center"})`, duration 0.7, `power1.out`.
- Pull-line (sign-off) → EASES UP at t=1.4, `gsap.from({opacity: 0, y: 18})`, duration 0.9, `sine.inOut`.
- Candle-warm glow under pull-line → BLOOMS at t=1.8, `gsap.fromTo({opacity: 0, scale: 0.92}, {opacity: 1, scale: 1.0})`, duration 1.0, `sine.inOut`. Single glow at `0 0 24px rgba(232, 161, 74, 0.12)` — the only `box-shadow` permitted in the entire composition (DESIGN.md `Elevation` rule).
- Timestamp → FADES UP at t=2.2, `gsap.from({opacity: 0})`, duration 0.7, `sine.inOut`. No motion — it's a quiet credit, not a callout.
- **Final hold + fade (the only allowed exit animations in the composition).** Audio resolves at scene-local t ≈ 6.7 s. Hold for 0.4 s. At t=7.1, fade pull-line + glow + caption plate + caption text simultaneously: `gsap.to({opacity: 0})`, duration 0.9, `power1.inOut`. Decoratives fade last with `duration: 1.1`, `power1.inOut`. Frame ends on warm-vignetted near-black.

Three distinct eases on entrances: `sine.inOut`, `expo.out`, `power1.out`. ✓

**Transition out.** None. PAYOFF is the final scene; the fade-to-warm-black IS the close. No shader transition fires after PAYOFF.

---

## 5. Recurring Motifs

These visual threads run across all three beats and create the composition's identity beyond any single scene. Every motif uses ONLY the DESIGN.md palette — no invented hexes.

1. **Persistent atmosphere.** Warm grain (`#241f1b` noise at 0.10), soft vignette to `#1a1614`, candle-warm halo (`#e8a14a` at 0.10), and the top-right hairline tick (`#e8a14a` at 0.30) persist through both thermal-distortion shader transitions. They are NOT re-entered per scene; they exist as a single shared atmosphere. This is what makes the three beats feel like one continuous take.

2. **One amber accent per beat.** HOOK: structural hairline (`#e8a14a` at 0.6 opacity, 240px). THESIS: ghost type's faint warmth via the persisted halo only — no new amber element introduced (this is a hold beat; restraint is the motif). PAYOFF: structural hairline returns, plus a single sign-off glow (`0 0 24px rgba(232, 161, 74, 0.12)`). Amber is metered — one warm note per beat, never two.

3. **Italic Playfair as bookend voice.** The HOOK pull-line and PAYOFF sign-off both use `Playfair Display italic 3.25rem 400 lowercase`. They are visually rhymed — the viewer reads PAYOFF's italic line as the close of the thought HOOK opened. THESIS deliberately omits the pull-line; the silence between bookends IS the structural rhyme.

4. **Caption plate as anchor.** Same component, same position, same `surface #241f1b at 0.78`, same `border-radius: 14px`, same 28v / 64h padding across all three beats. The plate is the only constant MG element. Text inside swaps; the plate persists in form. This creates the felt sense that the speaker has not moved.

5. **Beat marker as quiet ledger.** Top-left, single line, `accent-amber` 6px dot + `muted` `Inter` label uppercase letter-spaced. "HOOK · 1 / 3" → "THESIS · 2 / 3" → "PAYOFF · 3 / 3". The dot persists (same color, same size); only the label text changes. This is the only piece of UI that explicitly counts — and it counts in the smallest type permitted by DESIGN.md.

6. **Calm motion grammar.** `sine.inOut` is the dominant ease across every entrance. `expo.out` for fades that should feel inevitable (beat marker, ghost type). `power1.out` for the structural hairline draw. `power1.inOut` for the thermal-distortion shader and the final fade. No elastic, no back, no bounce, no overshoot anywhere in the composition — these are forbidden by DESIGN.md `motion.energy: calm`.

7. **Lower-third anchoring.** Every text element lives in y ≥ 1280px (caption plate, caption text, pull-line, structural hairline) or y ≤ 120px (beat marker, top-right hairline tick). The middle band 120–1280px is reserved for the speaker's face. This is enforced across every beat — the diagonals stay empty.

---

## 6. Negative Prompt — What to Avoid

Informed by DESIGN.md "Don't" + house-style.md "Lazy Defaults to Question" + HF canon "Rules (Non-Negotiable)" + HF canon "Scene Transitions (Non-Negotiable)".

**Palette.**
- No pure `#000000` background. No pure `#ffffff` text. The grade is warm — `#1a1614` and `#f4ebdc` only.
- No invented hex values. Every color in the composition must appear in the DESIGN.md table above (primary, on-primary, surface, accent-amber, accent-rose, muted) or be a stated opacity variant of one of those.
- No `#333` placeholder grey, no `#3b82f6` placeholder blue, no Roboto / Arial / system-ui fallbacks. The HARD-GATE in HF canon §"Plan" is real.
- No cyan-on-dark, no purple→blue gradients, no neon accents — these fight the warm grade and are explicit DESIGN.md "Don't"s.
- No gradient text (`background-clip: text` + gradient) — DESIGN.md "looks like an AI landing page from 2024".
- No left-edge accent stripes on cards, no identical card grids — house-style §"Lazy Defaults to Question".

**Typography.**
- No third typeface. Two families maximum: Playfair Display + Inter.
- No `<br>` inside caption text — let it wrap via `max-width: 78%` (HF canon §"Never do" #11).
- No font-size under 24px in MG/FG content. Only `label` (0.75rem ≈ 18px under default rem; this is justified by DESIGN.md as the timestamp/marker role and is the documented exception).
- No headlines outside the bookend roles (HOOK pull-line, PAYOFF sign-off). THESIS does NOT carry a Playfair line.

**Layout.**
- No equal-weight centered layouts. No full-frame symmetric type. The speaker is off-center; the UI must be too.
- No overlay in the middle band (y = 120–1280px). The speaker's face is sacred.
- No more than two text elements visible simultaneously per DESIGN.md `Layout` rule (caption plate counts as one text element; caption + pull-line is allowed; caption + pull-line + timestamp is allowed only on PAYOFF and only because the timestamp is a quiet `muted` label, not a focal element).
- No drop shadows, no glassmorphism, no neumorphic UI, no layered cards — DESIGN.md `Elevation`. The single permitted shadow is the PAYOFF sign-off glow.

**Motion.**
- No `repeat: -1` on any tween — finite repeats only, calculated from composition duration (HF canon §"Rules" + house-style).
- No exit animations on captions, plates, or pull-lines BEFORE the scene's transition — the thermal-distortion shader IS the exit. The only permitted `gsap.to({opacity: 0})` is on PAYOFF's final fade after the audio resolves (DESIGN.md "Don't" + HF canon §"Scene Transitions" rule 3 + 4).
- No elastic, back, or bounce eases — `motion.energy: calm` forbids them.
- No SLAM / CRASH / PUNCH / STAMP / SHATTER verbs anywhere. This composition has no high-impact moments by design.
- No `Math.random()`, `Date.now()`, or async timeline construction (HF canon §"Rules" — Deterministic + Synchronous).
- No `video.play()` / `audio.play()` calls — framework owns playback (HF canon §"Rules" — GSAP).

**Density.**
- No scenes with fewer than 8 elements. Each beat must hit 8–10 (HF video-composition.md §"Density").
- No static decoratives. Every BG element has an ambient breath / drift / pulse cycle.
- No third instance of `accent-amber` in any single beat. One amber element per beat is the rule; two is a tolerance ceiling; three is a violation (DESIGN.md "Once it's on three things, remove two").

**Pacing.**
- No aggressive tightening of the speech takes. Strategy says "preserve natural pauses" — the visual transitions must respect them. THESIS holds its full ~10.5 s; PAYOFF holds an extra 0.4 s after audio resolves.
- No element fires at exact t=0 of its scene. Minimum 0.1 s offset (HF §"Animation Guardrails").
- No transition shorter than 0.9 s or longer than 1.3 s. Both thermal-distortion fires use 1.1 s exactly (DESIGN.md `motion.duration.transition`).
