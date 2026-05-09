# Expanded Prompt — Soft Signal · Portrait Reflection (Canonical Portrait Talking-Head)

## 1. Title + Style Block

**Title:** Soft Signal — Portrait Reflection. A reflective portrait talking-head, 1080×1920, ~22.6s, three beats (HOOK → THESIS → PAYOFF) per the Phase 3 strategy shape.

**Mood (from DESIGN.md Overview):** intimate, breath-paced, restrained. The visual identity yields to the speaker; the canvas is a warm photographic seamless, not a "page". Editorial portrait register — Sagmeister intimacy earned through restraint plus a single warm amber accent that holds the eye where the speaker pauses.

**Palette (cited verbatim from `hyperframes/DESIGN.md`):**

| Role                     | Hex        | Use                                                                                  |
| ------------------------ | ---------- | ------------------------------------------------------------------------------------ |
| `background`             | `#FFF8EC`  | Warm cream — the photographic seamless. Canvas across all three beats.               |
| `background-stop-1`      | `#E6DFD4`  | Gradient bottom for radial atmosphere glows.                                         |
| `background-stop-2`      | `#CCC6BD`  | Shadow-side gradient stop, used sparingly.                                           |
| `background-highlight-1` | `#FFFDF8`  | Rim-light highlight for soft vignette top; caption strip translucent fill.           |
| `foreground`             | `#2a2a2a`  | Charcoal — body & headline color (THESIS, HOOK overline label).                      |
| `foreground-stop-1`      | `#1f1f1f`  | Pull-quote / italic emphasis (PAYOFF headline — slightly deeper charcoal).            |
| `foreground-highlight-1` | `#404040`  | Secondary copy, attribution, timestamps, caption fill.                                |
| `accent`                 | `#F5A623`  | Warm amber — the eye-rest color. Once per beat: underline rule, glow tint, OR word.   |
| `accent-stop-1`          | `#DC951F`  | Accent gradient body.                                                                 |
| `accent-stop-2`          | `#C4841C`  | Accent gradient deep stop, hairline rules.                                            |
| `accent-highlight-1`     | `#F6AF39`  | Accent rim / pulse peak.                                                              |
| `midtone`                | `#C4A3A3`  | Muted rose — connective tissue, dividers (hairline rule at 60% opacity).              |
| `midtone-stop-1`         | `#B09292`  | Midtone deep stop.                                                                    |

One accent hue only — amber. The rose midtone is connective, never headline, never an action color. Cream backgrounds across all three beats; beat-level distinction comes from amber **opacity and placement**, not from changing the canvas. Per DESIGN.md Don'ts: no sage-green, even though Soft Signal canon offers it.

**Typography (cited verbatim from `hyperframes/DESIGN.md`):**

- **headline** — Playfair Display, regular weight (400), italic, `4.5rem` (72px at 1080-wide), `letterSpacing: -0.01em`, `lineHeight: 1.05`. Used on THESIS and PAYOFF only — one phrase per frame, pulled directly from the speaker's words. `font-variant-numeric: oldstyle-nums`.
- **body** — Inter, weight 300, `1.125rem`, `lineHeight: 1.7`. Subtitling/attribution.
- **overline** — Inter, weight 500, `0.75rem`, `letterSpacing: 0.18em`, uppercase. Beat label only ("01 / REFLECTION", "02 / THESIS", "03 / PAYOFF") — top-right of frame, once per beat.

Two families maximum: Playfair Display (italic, display) + Inter (everything else). No third sans (DESIGN.md Don'ts: "no second sans-serif. Inter is the sans.").

**Tokens:**

- `rounded.sm = 8px` · `rounded.md = 16px` · `rounded.lg = 24px`
- `spacing.sm = 12px` · `spacing.md = 24px` · `spacing.lg = 48px` · `spacing.xl = 96px`
- `motion.energy = calm` · `easing.entry = sine.inOut` · `easing.exit = power1.inOut` · `easing.ambient = sine.inOut`
- `duration.entrance = 0.9s` · `duration.hold = 2.4s` (default — pacing yields to performance) · `duration.transition = 1.2s`

**Atmosphere set (from DESIGN.md `motion.atmosphere`):** `warm-grain`, `soft-radial-glow`, `hairline-margin-rule`. **Transition family:** `thermal-distortion` (canonical Soft Signal transition; mandatory between beats per DESIGN.md Don'ts: "No hard cuts between beats.").

## 2. Rhythm Declaration

**Rhythm:** `drift-build-resolve` — the calm-end shape of `drift-build-PEAK-drift-resolve` from `references/beat-direction.md`. There is no PEAK in the percussive sense; the PEAK is the THESIS headline landing, but it lands as a settle, not a slam.

| Beat   | Take              | Approx. duration | Energy            | Function                                                  |
| ------ | ----------------- | ---------------- | ----------------- | --------------------------------------------------------- |
| HOOK   | `[000.12-001.34]` | ~1.2s            | drift / arrival   | open into the room; speaker only; no headline             |
| THESIS | `[003.10-013.60]` | ~10.5s           | build / sustained | the argument lands; italic headline; longest hold         |
| PAYOFF | `[018.82-029.50]` | ~10.7s           | resolve           | grounded sign-off; final 0.4s headline fade is only exit  |

**Total runtime:** ~22.6s. **No hard cuts.** No PUNCH. No SLAM. `motion.energy: calm` → every transition rides `sine.inOut` (entry) or `power1.inOut` (exit). Strategy says "preserve natural pauses between phrases, no aggressive tightening — this is a reflective monologue, not a fast cut." The rhythm honors that: every beat ends with a 0.4s held tail before its `thermal-distortion` transition begins, so audio resolves into stillness before the visual moves.

## 3. Global Rules

**Frame:** 1080×1920 portrait. Three horizontal bands per DESIGN.md §Layout:

- **Top 12%** (y ≤ 230) — quiet zone. Hairline rule at 96px from frame top, `midtone` `#C4A3A3` at 60% opacity, 1px. Overline label right-aligned to the rule's right edge.
- **Middle 56%** (230 ≤ y ≤ 1305) — the speaker. Talking-head video clip occupies this band edge-to-edge with grade applied (warm-neutral, midtone lift, slight shadow desaturation per Phase 3 strategy). **No overlay copy crosses this band's midpoint.**
- **Bottom 32%** (y ≥ 1305) — typographic stage. Padding `xl` (96px) sides, `lg` (48px) bottom. Headline phrase sits flush-left with a slight optical hang (`margin-left: -0.05em`).

**Container:** Containers fill the scene via `width: 100%; height: 100%; padding: …; box-sizing: border-box` — never absolute-positioned (DESIGN.md §Layout). Decoratives use `position: absolute` inside an `overflow: hidden` parent.

**Parallax / depth layers (every beat — house-style §Background Layer minimum 2–5 decoratives, here three sharing one ambient breath):**

- **BG-1 (atmosphere)** Warm grain — baked-in noise PNG at **4% opacity, `mix-blend-mode: multiply`** (DESIGN.md §Elevation #3). Drift translateX `0 → 4 → -3 → 0` px over 7.4s `sine.inOut`, infinite yoyo. The film stock.
- **BG-2 (atmosphere)** Soft radial glow — `radial-gradient(circle at 50% 60%, accent 0%, transparent 60%)` at **12% layer opacity** (DESIGN.md §Elevation #1, §Components → Radial glow). Breathing scale `0.96 ↔ 1.04` over `transition` duration (1.2s), ease `sine.inOut`, infinite yoyo. Repositioned per beat — see §4.
- **BG-3 (structural)** Hairline margin rule — 1px solid `midtone` `#C4A3A3` at **60% opacity**, full bleed minus `xl` (96px) padding on each side, anchored at the band boundary (96px from top). Slow opacity pulse `0.55 ↔ 0.65` over 4.0s `sine.inOut`, infinite yoyo.

**Midground:** the speaker plate (BG-1-video equivalent — the talking-head footage itself, full-bleed in the middle band) plus, on THESIS/PAYOFF only, a flush-left italic Playfair headline anchored in the bottom band.

**Foreground:** the overline label (top-right) with its 24px-wide accent underline rule (HOOK only — see §4 amber discipline). On PAYOFF, a single attribution/cadence note `md` (24px) below the headline at `foreground-highlight-1`.

**Caption plate (handled by the captions composition, constraints set here):**

- Font family inherits from `--body-family` (Inter 300).
- Fill: `foreground-highlight-1` `#404040` over a `background-highlight-1` `#FFFDF8` translucent strip.
- No caps. No per-word color flips. `max-width` consistent with the bottom band's `xl` padding.

**Density target:** 8–10 visible elements per scene per `references/video-composition.md`. Two of those are decoratives the user did not request — added because empty frames look broken. Per-beat element list is enumerated in §4. The DESIGN.md also adds a hard ceiling: within a single instant, **two text elements maximum** (overline + headline, OR overline + caption — not three). Atmosphere decoratives don't count toward that text-element budget.

**Ambient motion (every decorative — house-style §Motion: "static decoratives feel dead"):**

- Warm-grain — drift 7.4s `sine.inOut`, infinite yoyo (see BG-1).
- Soft radial glow — breathe 1.2s scale + opacity yoyo, `sine.inOut` (see BG-2). Per DESIGN.md §Components: 720px diameter, `accent` 12%, scale 0.96→1.04.
- Hairline margin rule — opacity pulse 4.0s `sine.inOut`, yoyo (see BG-3).
- Overline accent underline (HOOK) — single 24px-wide `accent` underline at 2px height, *static* once drawn (anchor weight; the eye-rest amber must not pulse, or it stops being a rest-point).

**Transition style — primary:** `thermal-distortion` (DESIGN.md §Motion: "Scene-to-scene change is the canonical `thermal-distortion` shader transition (matches Soft Signal canon) — duration 1.2s, eased `sine.inOut`."). The warm-grain heat-shimmer aesthetic is the connective tissue.

**Accent transition (HOOK→THESIS, THESIS→PAYOFF):** the overline label content cross-fades inside the `thermal-distortion` warp (opacity 1 → 0 → 1 over 0.4s `power1.inOut`, mid-warp), so the label text mutates ("01 / REFLECTION" → "02 / THESIS" → "03 / PAYOFF") without leaving the frame.

**Velocity match (`references/beat-direction.md` §Velocity-Matched Transitions):** every beat ends with a 0.4s decelerating tail (motion settling to zero), then `thermal-distortion` enters at low velocity matching that tail. **No accelerating exits** — the calm energy forbids `power3.in` snap-outs.

**Hold pacing yields to performance** (DESIGN.md §Motion): "if the speaker's pause runs to 3.7s, the headline holds for 3.7s — the `2.4` token is a default, not a rule." The transcript at `edit/transcripts/final.json` is the source of truth for caption swap timings; the scene sub-agent reads it for natural-pause boundaries.

**Color presence:** `accent` `#F5A623` is visible in every beat through **exactly one element**, per DESIGN.md Do's: "Use amber `#F5A623` exactly once per beat as a single eye-rest mark — the underline beneath the overline, OR the radial glow tint, OR a single underlined word in the headline. Never two amber marks in the same frame." HOOK = underline beneath overline. THESIS = single underlined word in headline. PAYOFF = radial glow tint only (no headline word). `accent` is decorative-only at small sizes (fails AA on cream); for amber text, ≥40px or set on `foreground-stop-1` panels (DESIGN.md WCAG note).

**No banned defaults** (house-style §Lazy Defaults to Question + DESIGN.md Don'ts):

- No gradient text (`background-clip: text` + gradient).
- No center-stacked equal-weight composition. Headline is flush-left; speaker is mid-frame. Eye must travel face → phrase, never bounce on a center axis.
- No drop shadows under any type. Flat layering is the entire point of the warm-neutral grade.
- No ALL-CAPS display headlines. Caps shout; this monologue invites. Overlines are the only place caps appear.
- No sage-green accent.
- No second sans-serif.
- No hard cuts.
- No element appears fully formed — every overline, headline, hairline rule animates IN via `gsap.from()` at its beat's start (DESIGN.md Don'ts).
- No banned fonts (Roboto, Arial, Helvetica, Open Sans, DM Sans, Space Grotesk).

## 4. Per-Scene Beats

### Beat 1 — HOOK · `[000.12-001.34]` · ~1.2s

**Concept.** The speaker is already mid-thought; we slip into a conversation that has been happening before the camera arrived. The room is warm, the cream canvas is the photographic seamless, the air carries one breath of grain. Nothing competes with the face — no headline, no display type, just the speaker, an overline label that confirms we are in the right register, and a single amber underline that the eye eventually finds. This beat is the doorway. Per DESIGN.md §Beat Visual Mapping: "Hold the speaker; the frame teaches the visual language without showing it off."

**Mood direction.** Editorial portrait photography. Late-evening, candle-warm, the first page of a Sebald novel. The opening title of a Wong Kar-wai film — warm, slow, slightly melancholic, deeply considered. Sagmeister's intimate work, not a tech reveal. Not a wellness ad — DESIGN.md explicitly bans the wellness-category cliché (no sage-green, no gradient text).

**Depth layers (8 elements).**

- **BG-1** Speaker plate — talking-head footage in the middle band (230 ≤ y ≤ 1305), warm-neutral grade with midtone lift and slight shadow desaturation per strategy. Edge-to-edge in the band.
- **BG-2** Warm-grain overlay — full-frame, noise PNG at 4% opacity, `mix-blend-mode: multiply`, drift ambient (7.4s yoyo).
- **BG-3** Soft radial glow — `radial-gradient(circle at 50% 60%, #F5A623 0%, transparent 60%)` at **8% layer opacity** (DESIGN.md §Beat Visual Mapping: HOOK glow is "slightly under canon — the eye should commit to the face, not the design"). Breathing 1.2s scale + opacity ambient.
- **BG-4** Hairline margin rule (top band) — 1px `midtone` 60%, anchored 96px from top, full-bleed minus `xl` padding. Slow opacity pulse ambient.
- **MG-1** Overline label — top-right, anchored to the right end of the hairline rule. Inter 500, `0.75rem`, uppercase, `letterSpacing: 0.18em`, `foreground-highlight-1` `#404040`. Text: **"01 / REFLECTION"** (per DESIGN.md §Beat Visual Mapping HOOK label text).
- **MG-2** Overline accent underline — 24px wide, 2px height, solid `accent` `#F5A623`, sitting beneath the overline label. **(This is HOOK's amber lead — the single eye-rest mark per DESIGN.md Do's.)**
- **FG-1** Caption strip — Inter 300, `1.125rem`, `lineHeight: 1.7`, fill `foreground-highlight-1` `#404040` on a `background-highlight-1` `#FFFDF8` translucent strip, anchored in the bottom band, `xl` padding sides, `lg` bottom. Burned-in transcript content for the HOOK take.
- **FG-2** Soft vignette top — `radial-gradient` rim-light highlight using `background-highlight-1` `#FFFDF8` at the very top of the frame (subtle "rim-light highlight for soft vignette top" per DESIGN.md `background-highlight-1` description). 8% opacity, static.

*HOOK has no headline (DESIGN.md §Beat Visual Mapping: "speaker only, no headline" + "HOOK is type-free except for the small overline. The opening belongs to the face.").*

**Animation choreography.** Every element gets a verb.

- **BG-1 speaker plate** — *holds* (footage already plays from t=0; we don't fade in the face on a portrait monologue, we open into it).
- **BG-2 warm-grain** — *drifts* (ambient, see Global Rules).
- **BG-3 radial glow** — *breathes* (ambient).
- **BG-4 hairline rule (top band)** — *draws in* via `gsap.from(scaleX: 0, transformOrigin: 'right center', duration: 0.6, ease: 'sine.inOut', delay: 0.1)` so the rule unfurls leftward from the overline anchor — DESIGN.md §Beat Visual Mapping: "Hairline rule fades in at 0.4s." We use `0.4s` for hairline in/visible, leading edge enters at `t=0.1` so it completes by `t=0.4–0.7`.
- **MG-1 overline label** — *settles in* via `gsap.from({y: +24, opacity: 0}, duration: 0.9, ease: 'sine.inOut', delay: 0.0)` per DESIGN.md §Motion: "Overlay copy fades up from `y: +24` and `opacity: 0` to its CSS rest position."
- **MG-2 overline accent underline** — *draws* via `gsap.from({scaleX: 0}, transformOrigin: 'left center', duration: 0.6, ease: 'sine.inOut', delay: 0.18)` — staggered 180ms after the overline per DESIGN.md §Motion: "vary stagger between elements (0ms / 180ms / 320ms — three different offsets, never identical)." Once drawn, *holds static* — amber is the rest-point; it does not pulse.
- **FG-1 caption strip** — *fades up* via `gsap.from({y: +24, opacity: 0}, duration: 0.9, ease: 'sine.inOut', delay: 0.32)` — third stagger offset per DESIGN.md.
- **FG-2 soft vignette top** — *settles* (opacity 0 → 0.08, 0.6s `sine.inOut` from t=0.0; then static).

**Pacing within the beat.** t=0.0 the room is there (plate holds, grain drifts, glow breathes). t=0.10 the hairline begins drawing leftward. t=0.18 overline accent underline draws. t=0.0–0.9 overline label settles in (peaks at t=0.45, eases to rest by t=0.9). t=0.32–1.22 caption strip fades up (settled by t=1.22). The remaining ~0.05s is the held tail; the next phrase from the take's tail bleeds toward the transition. **No exits except the transition itself** — DESIGN.md Don'ts forbid premature opacity-0 fades.

**SFX cues.** None overlaid; the speaker's voice carries. Ambient room-tone is the soundscape.

**Transition out → THESIS.** `thermal-distortion` shader, 1.2s `sine.inOut`. Per DESIGN.md §Components / §Motion. Inside the warp:

- The radial glow opacity steps up from 8% → 12% over the 1.2s warp (DESIGN.md §Beat Visual Mapping THESIS: glow opacity steps up; here the step happens *during* the transition, not after, so THESIS opens with the new opacity already settled).
- The radial glow's *position* eases from `(50%, 60%)` to bottom-left (DESIGN.md THESIS: "repositioned to bottom-left to lead the eye into the headline") — 1.2s `sine.inOut` co-running with the warp.
- Overline label content mutates "01 / REFLECTION" → "02 / THESIS" via mid-warp opacity bridge (0.4s `power1.inOut`, peak at t=0.6 of the warp).
- Overline accent underline cross-fades to opacity 0 (0.4s `power1.inOut`, mid-warp) — THESIS does not use the underline (THESIS's amber lead moves to the headline word).
- Caption strip cross-fades content (0.3s `sine.inOut` opacity bridge inside warp) to THESIS's first caption phrase. The strip itself does not exit.
- Hairline margin rule (top band) carries across — does not retract.

---

### Beat 2 — THESIS · `[003.10-013.60]` · ~10.5s

**Concept.** The argument lands. Not loudly — this is the long middle of a quiet conversation, the part where the speaker's reasoning unfolds in the upper band and a single italic phrase, pulled directly from their words, surfaces in the lower band. The italic earns the typographic intimacy that an upright cut would not — and avoids the Maximalist Type trap of shouting (DESIGN.md §Typography). The frame holds longer than feels safe; the captions update on natural pauses, but the rest of the room barely moves. One amber word — the emotional weight-point of the phrase — is the only saturated color in the frame. This beat is a held breath: "let me explain."

**Mood direction.** Long-take editorial documentary. The interview shot in a Werner Herzog character close-up — the camera that doesn't blink. Editorial calm, late-night radio, a fireside reading. Bauhaus restraint applied to portraiture. No competing visual events.

**Depth layers (9 elements).**

- **BG-1** Speaker plate — continuing from HOOK, no re-fade.
- **BG-2** Warm-grain overlay — same 4% opacity / `multiply` blend, drifting (ambient).
- **BG-3** Soft radial glow — repositioned to bottom-left (per DESIGN.md THESIS: "repositioned to bottom-left to lead the eye into the headline"). `accent` `#F5A623` at **12% opacity** (per DESIGN.md §Components → Radial glow canonical 12% — THESIS is at-canon). Breathing 1.2s ambient.
- **BG-4** Hairline margin rule (top band) — held from HOOK, ambient pulse.
- **MG-1** Overline label — top-right, content **"02 / THESIS"** (mutated during the HOOK→THESIS warp). Inter 500, 0.75rem, uppercase, `letterSpacing: 0.18em`, `foreground-highlight-1`. Held in place.
- **MG-2** Headline phrase — Playfair Display, italic, 400 weight, **4.5rem (72px)**, `letterSpacing: -0.01em`, `lineHeight: 1.05`, color `foreground` `#2a2a2a`, `font-variant-numeric: oldstyle-nums`. Anchored flush-left in the bottom band with optical hang `margin-left: -0.05em`. `max-width: 80%` of the bottom band (DESIGN.md §Components → Headline phrase). One phrase — pulled from the speaker's actual words in the THESIS take, derived by the scene sub-agent from the transcript at `edit/transcripts/final.json`. **No `<br>`** — wraps naturally. Lowercase except proper nouns (DESIGN.md Don'ts: no ALL-CAPS).
- **MG-3** Headline accent underline — beneath a **single underlined word** in the headline (the phrase's emotional weight-point — chosen by the scene sub-agent). 2px solid `accent` `#F5A623` at **100% opacity** (DESIGN.md §Beat Visual Mapping THESIS: "Amber accent moves to a single underlined word in the headline … at `accent` 100%"). **(This is THESIS's amber lead — the single eye-rest mark.)**
- **FG-1** Caption strip — Inter 300, content swaps on natural pause boundaries from the transcript (each swap: 0.3s `sine.inOut` opacity cross-fade only — no y-translate; too much motion competes with the speaker). 3–5 swaps over 10.5s, gated to `edit/transcripts/final.json` word timings.
- **FG-2** Soft vignette top — held from HOOK, static.

*No timestamp / attribution on THESIS — that is PAYOFF-only territory per DESIGN.md §Components.*

**Animation choreography.**

- **BG-1 speaker plate** — *holds*.
- **BG-2 warm-grain** — *drifts* (ambient).
- **BG-3 radial glow** — *settled into new position from warp; breathes* (ambient).
- **BG-4 hairline rule (top band)** — *holds; pulses* (ambient).
- **MG-1 overline label** — *holds* (text already mutated mid-warp).
- **MG-2 headline phrase** — *surfaces* via `gsap.from({y: +24, opacity: 0}, duration: 0.9, ease: 'sine.inOut', delay: 0.32)` (DESIGN.md §Beat Visual Mapping THESIS: "Headline staggers in 320ms after overline" — overline settled during transition; we treat the warp's end as t=0 of THESIS, so headline enters at t=0.32 of the beat).
- **MG-3 headline accent underline** — *draws* via `gsap.from({scaleX: 0}, transformOrigin: 'left center', duration: 0.6, ease: 'sine.inOut', delay: 0.95)` — sequenced AFTER the headline settles (entrance peak at t≈0.95), like a hand underlining the chosen word in real time. Once drawn, *holds static* (amber rest-point).
- **FG-1 caption strip** — *holds*; *swaps content* per phrase (opacity 1 → 0 → 1 over 0.3s `sine.inOut`, gated to natural pause boundaries).
- **FG-2 soft vignette top** — *holds*.

**Pacing within the beat.**

- t=0.0–0.32: arrival from transition. Plate holds; glow now at 12% in bottom-left; overline already says "02 / THESIS"; first caption phrase visible.
- t=0.32–1.22: headline phrase surfaces. (`y: +24 → 0`, 0.9s, `sine.inOut`.)
- t=0.95–1.55: amber underline draws beneath the chosen word. Underline holds.
- t=1.55–8.5: the held middle. 3–4 caption swaps on natural pauses. Ambient motion only — breathe, drift, pulse. No discrete events. The speaker's voice carries the beat.
- t=8.5–10.1s: closing phrase of the thesis lands and holds.
- t=10.1–10.5s: 0.4s held tail — speaker's voice has resolved; visual is dead-still except for ambient breathing — before the transition into PAYOFF.

**SFX cues.** None overlaid. Speaker carries. The amber underline draw should land in silence — no chime, no swoosh; the sine.inOut ease is the gesture.

**Transition out → PAYOFF.** `thermal-distortion`, 1.2s `sine.inOut`. Inside the warp:

- The headline phrase exits — but **NOT via opacity-to-zero** on the element itself. The thermal-distortion shader visually dissolves it; we do not animate `opacity: 0` on `MG-2` or `MG-3`. (DESIGN.md Don'ts: "the transition IS the exit" implication; explicit "No element appears fully formed" + "No exits except on PAYOFF's final fade" means inter-beat exits ride the shader, not element opacity.)
- Headline accent underline retracts inside the warp (`scaleX: 1 → 0`, `transformOrigin: left center`, 0.5s `sine.inOut`, kicked off at warp midpoint t=0.6) — PAYOFF does not use the underline (PAYOFF's amber lead is the radial glow only). Retracting cleanly avoids carry-over.
- Radial glow eases from bottom-left back to centered-and-slightly-low (per DESIGN.md PAYOFF: "Amber accent retreats to the radial glow only"; positioning held at the canonical center-60% with a slight lift on PAYOFF — 1.2s `sine.inOut` co-running with warp).
- Overline label content mutates "02 / THESIS" → "03 / PAYOFF" via mid-warp opacity bridge (0.4s `power1.inOut`).
- Caption strip cross-fades content (0.3s `sine.inOut` opacity bridge inside warp) to PAYOFF's first caption phrase.

---

### Beat 3 — PAYOFF · `[018.82-029.50]` · ~10.7s

**Concept.** The thought resolves. The speaker has said the thing; now there is room for the viewer to feel it. PAYOFF is the slow exhale — a second italic Playfair headline, slightly deeper charcoal than THESIS, surfaces flush-left in the bottom band as a grounded sign-off. The amber accent retreats from the headline word back into the radial glow itself — a return to atmosphere. The room breathes one last cycle, and then the headline alone fades to opacity 0 over 0.4s `power1.inOut` (DESIGN.md §Beat Visual Mapping PAYOFF: "Final 0.4s of the beat is the only allowed exit"). The composition resolves on speaker + cream + grain — the visual identity has done its work and gets out of the way.

**Mood direction.** End-credit calm. The closing image of a Sofia Coppola film. A handwritten signature at the bottom of a journal page. The kind of resolution that doesn't punctuate with a cut — it dissolves into stillness.

**Depth layers (9 elements).**

- **BG-1** Speaker plate — continuing.
- **BG-2** Warm-grain overlay — same 4% / multiply, drifting.
- **BG-3** Soft radial glow — repositioned back to canonical `circle at 50% 60%` per DESIGN.md §Components default position. `accent` `#F5A623` at **12% layer opacity** (canonical). Breathing ambient. **(This is PAYOFF's amber lead — the single eye-rest mark, per DESIGN.md PAYOFF: "Amber accent retreats to the radial glow only — no underlined word.")**
- **BG-4** Hairline margin rule (top band) — held, pulsing ambient.
- **MG-1** Overline label — top-right, content **"03 / PAYOFF"** (mutated during the THESIS→PAYOFF warp). Inter 500, 0.75rem, uppercase, `letterSpacing: 0.18em`, `foreground-highlight-1`. Held.
- **MG-2** Headline phrase (sign-off) — Playfair Display, italic, 400, 4.5rem, `letterSpacing: -0.01em`, `lineHeight: 1.05`, color `foreground-stop-1` **`#1f1f1f`** (DESIGN.md §Beat Visual Mapping PAYOFF: "at `foreground-stop-1` (slightly deeper charcoal — the resolution feels grounded)"). Anchored flush-left, `margin-left: -0.05em`, `max-width: 80%`. One phrase — distilled from the speaker's final sentence in the take, lowercase except proper nouns. Wraps naturally.
- **MG-3** Attribution / cadence note — Inter 300, `1.125rem`, color `foreground-highlight-1` `#404040`, anchored `md` (24px) below the headline (DESIGN.md §Layout: "Attribution/cadence note sits `md` (24px) below the headline at `foreground-highlight-1`"). Optional — present only if the take's final sentence has a clear secondary clause; if the sub-agent decides to omit, the count drops to 8 elements and that is also valid. Default: include, with content drawn from a quiet thematic register (e.g. cadence label or take-marker).
- **FG-1** Caption strip — Inter 300; PAYOFF caption (final phrase verbatim from transcript). Single phrase or short two-clause sentence depending on `[018.82-029.50]`. Plate carries through; only inner text settled in via warp.
- **FG-2** Soft vignette top — held, static.

**Animation choreography.**

- **BG-1 speaker plate** — *holds*.
- **BG-2 warm-grain** — *drifts* (ambient).
- **BG-3 radial glow** — *holds new position from warp; breathes* (ambient). Glow is the amber lead — it must not pulse outside its breathing rhythm; no separate emphasis cue.
- **BG-4 hairline rule (top band)** — *holds; pulses* (ambient).
- **MG-1 overline label** — *holds*.
- **MG-2 headline phrase** — *surfaces* via `gsap.from({y: +24, opacity: 0}, duration: 0.9, ease: 'sine.inOut', delay: 0.32)` (same stagger as THESIS — overline → headline 320ms offset).
- **MG-3 attribution** — *fades up* via `gsap.from({y: +24, opacity: 0}, duration: 0.9, ease: 'sine.inOut', delay: 1.10)` — arrives like a postscript, well after the headline settles.
- **FG-1 caption strip** — *holds*; the warp's caption opacity bridge already settled the PAYOFF first phrase. Subsequent caption swaps (if any — possibly 1–2 over 10.7s) ride 0.3s `sine.inOut` opacity cross-fades on natural pauses.
- **FG-2 soft vignette top** — *holds*.

**Pacing within the beat.**

- t=0.0–0.32: arrival from transition. PAYOFF caption settled; overline already says "03 / PAYOFF"; glow at center-60% breathing.
- t=0.32–1.22: headline (sign-off) surfaces.
- t=1.10–2.00: attribution fades up below the headline.
- t=2.00–10.30: the long held resolution. ~8.3s of held, breathing stillness — only ambient motion (grain drift, glow breath, hairline pulse). The viewer sits with the sign-off. Audio carries.
- t=10.30–10.70: **the ONLY allowed exit in the entire composition**. Headline fades to opacity 0 over 0.4s `power1.inOut` (DESIGN.md §Beat Visual Mapping PAYOFF: "Final 0.4s of the beat is the only allowed exit: headline fades to `opacity: 0` over 0.4s, ease `power1.inOut`, leaving the speaker on cream before the cut to black."). Attribution fades simultaneously (same easing, same duration). Caption, overline, glow, grain, hairline, vignette: all hold. The beat resolves on speaker + cream + ambient atmosphere.

**SFX cues.** None overlaid. Speaker's voice carries to its natural resolution; the 0.4s headline fade rides silence.

**Transition out → end.** No outgoing transition — PAYOFF is the terminal beat. The composition resolves on its held final state (speaker + cream + atmosphere). If the orchestrator (`graph` p4_render or downstream) requires a final fade-to-black or fade-to-cream, that lives outside this composition's authored timeline. Per DESIGN.md, the authored content ends with the headline opacity:0 — the speaker remains on cream.

## 5. Recurring Motifs

Visual threads that repeat across all three beats — they are how the viewer knows it is the same world.

- **Cream canvas (`#FFF8EC`) — invariant.** Same background hex across all three beats. Beat distinction comes from amber placement and opacity, never from canvas swaps. (DESIGN.md §Colors: "Cream backgrounds across all three beats; beat-level distinction comes from amber **opacity and placement**, not from changing the canvas.")
- **Warm-grain overlay — invariant.** 4% opacity, `mix-blend-mode: multiply`, identical 7.4s drift in all beats. The film stock never changes; the room never changes its texture.
- **Soft radial glow — repositioned, never absent.** Present in every beat, repositioned per beat to track compositional weight (HOOK center-60% at 8%, THESIS bottom-left at 12%, PAYOFF center-60% at 12%). Always `accent` `#F5A623` led, always breathing 1.2s `sine.inOut`. The glow is the room's candle; it never leaves.
- **Hairline margin rule (top band) — held.** 1px `midtone` 60%, anchored 96px from frame top, full-bleed minus `xl` padding. Pulses ambient (0.55 ↔ 0.65) in all three beats. The structural through-line.
- **Overline label (top-right)** — same architecture, text mutates "01 / REFLECTION" → "02 / THESIS" → "03 / PAYOFF". Inter 500, 0.75rem, uppercase, +0.18em tracking, `foreground-highlight-1`. Mutations happen mid-warp via opacity bridge — the label never leaves the frame.
- **Amber discipline (DESIGN.md Do's: "exactly once per beat as a single eye-rest mark").** Exactly one amber lead per beat: HOOK = 24px overline accent underline. THESIS = single underlined word in headline at 100%. PAYOFF = radial glow tint only. Never two amber marks in the same frame.
- **Italic Playfair headline as resolution language.** THESIS and PAYOFF both carry an italic Playfair phrase, flush-left in the bottom band, `margin-left: -0.05em` optical hang, lowercase except proper nouns. The form repeats; only the color shifts (`#2a2a2a` → `#1f1f1f`) to mark thesis vs resolve.
- **`thermal-distortion` transition family** — 1.2s `sine.inOut`. Both inter-beat transitions use the same warp; consistency reads as one unbroken room being seen from different distances.
- **Calm easing.** Every entrance is `sine.inOut` 0.9s; transitions are `sine.inOut` 1.2s; the only `power1.inOut` is the PAYOFF terminal exit. No `power3.in`, no `back.out`, no overshoot, no spring. Per DESIGN.md §Motion: "nothing snaps; nothing overshoots."
- **Three staggers, never identical** (DESIGN.md §Motion: "vary stagger between elements (0ms / 180ms / 320ms — three different offsets, never identical)"). HOOK demonstrates: hairline at 100ms, overline at 0ms, accent underline at 180ms, caption at 320ms.
- **Two-text-element ceiling.** No frame ever shows three or more text elements simultaneously: HOOK has overline + caption (2). THESIS has overline + headline + caption — but the caption is a continuous strip, not a discrete element competing with the headline; the discrete-text reading is overline (top) + headline (bottom) = 2. PAYOFF same logic, plus brief overlap with attribution = 3 only during a 0.9s entrance window, otherwise 2.

## 6. Negative Prompt — Do Not Include

Informed by `DESIGN.md` Don'ts and `house-style.md` "Lazy Defaults to Question":

- **No exit animations on overlines, captions, or headlines except the PAYOFF terminal headline fade.** DESIGN.md is explicit: "Final 0.4s of the beat is the only allowed exit." Inter-beat handoffs ride `thermal-distortion`; element opacity-to-0 between beats breaks Soft Signal's continuity.
- **No gradient text** (`background-clip: text` + gradient). DESIGN.md Don'ts: "would convert this from editorial intimacy to wellness-app advert in one keystroke."
- **No center-stacked equal-weight composition.** DESIGN.md Don'ts: "Headline is flush-left; speaker is mid-frame. The eye must travel from face to phrase, not bounce on a center axis."
- **No drop shadows under the headline (or any type).** DESIGN.md §Elevation: "Flat. No drop shadows on type." Depth budget spends on glow, hairline, and grain — nothing else.
- **No ALL-CAPS display headlines.** DESIGN.md Don'ts: "Caps shout; this monologue invites." Overlines are the only caps in the composition.
- **No sage-green accent**, even though Soft Signal canon offers it. DESIGN.md Don'ts: "pushes the piece into the wellness-category cliché and dilutes the single-accent discipline."
- **No second sans-serif.** DESIGN.md Don'ts: "Inter is the sans. Do not pair Inter with DM Sans, Space Grotesk, or any other neutral grotesque."
- **No hard cuts between beats.** DESIGN.md Don'ts: "The thermal-distortion transition is mandatory — jump cuts would break the reflective register."
- **No element appears fully formed.** DESIGN.md Don'ts: "Every overline, headline, hairline rule animates IN via `gsap.from()` at its beat's start."
- **No pure `#000000`, no pure `#ffffff`.** Background is `#FFF8EC`; foreground is `#2a2a2a`. The grade is warm-neutral; the UI follows. (House-style §Lazy Defaults.)
- **No banned fonts** — no Roboto, Arial, Helvetica, Open Sans, DM Sans, Space Grotesk. (Two families: Playfair Display + Inter.)
- **No third accent color.** Amber `#F5A623` leads (once per beat). Rose `#C4A3A3` is connective tissue at midtone usage, never headline, never action color. That's it. No green, no blue, no white-flash. (DESIGN.md §Colors.)
- **No accent fill behind body text.** Amber on cream fails AA at body sizes (DESIGN.md WCAG note); use amber for ≥40px or on `foreground-stop-1` panels only — currently used only as an underline rule and a glow tint, never as text color or full panel fill.
- **No two amber marks in the same frame.** DESIGN.md Do's: "Never two amber marks in the same frame."
- **No competing focal events during the speaker's pauses.** This is a talking-head; the speaker's face is the primary focal point. UI does not pull attention away from the speaker except in the held moments after each phrase resolves.
- **No PUNCH / SLAM / CRASH / SHATTER choreography.** `motion.energy: calm`. Verbs in this composition are: *holds, drifts, breathes, pulses, surfaces, settles, draws, fades, narrows, retracts, mutates*. Anything ballistic is wrong.
- **No `<br>` in headlines.** Headlines wrap naturally via `max-width: 80%`.
- **No timestamps on HOOK or THESIS.** Attribution / cadence note is PAYOFF only (DESIGN.md §Layout).
- **No card / button / chip components.** "There are no cards, no buttons. This is a portrait, not a UI surface." (DESIGN.md §Elevation.)
- **No aggressive caption tightening.** Strategy says "preserve natural pauses between phrases, no aggressive tightening — this is a reflective monologue, not a fast cut." Caption swaps gate to transcript natural-pause boundaries; do not collapse pauses to compress runtime.
- **No animated headline color shift.** THESIS `#2a2a2a` and PAYOFF `#1f1f1f` are static; the difference is per-beat, not within a beat.
- **No ambient pulse on amber rest-points.** The amber lead is the eye-rest color (DESIGN.md). Underlines and glow tint are the rest; pulsing the rest-point defeats it. Glow breathes (scale + opacity) because that is the canonical glow ambient — the breath is part of "rest", not an emphasis cue.
- **No visual SFX overlays** (whoosh swooshes, particle bursts, sparkle effects). The grain is the texture; nothing else overlays.
- **No asymmetric per-beat transition family.** Both transitions are `thermal-distortion`. Mixing in a `glitch` or `cinematic-zoom` would fracture the unbroken-room reading.
