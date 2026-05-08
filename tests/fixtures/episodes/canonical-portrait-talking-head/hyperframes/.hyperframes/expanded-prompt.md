# Expanded Prompt — canonical-portrait-talking-head

> Reflective monologue, portrait 1080×1920, ~22.6s. Three beats: HOOK → THESIS → PAYOFF.
> The speaker IS the visual. Overlays are deferential, warm, and slow — they frame the
> face, never compete with it. Visual identity: **Soft Signal — Reflective Portrait**
> (see `hyperframes/DESIGN.md`).

---

## 1 · Title + Style Block

**Title:** *Soft Signal — Return to Roots*

**Frame:** 1080 × 1920 portrait. Speaker occupies the upper ~70% (y < 1280px). Lower
third (y ≥ 1280px) hosts the caption plate; the top-edge band (y ≤ 120px) hosts the
beat marker. The middle band is the speaker's face — never covered.

**Palette (from DESIGN.md — exact values, do NOT invent):**

- `primary` — `#1a1614` (background, from speaker's desaturated shadow tone)
- `on-primary` — `#f4ebdc` (foreground / caption fill — warm cream, never `#ffffff`)
- `surface` — `#241f1b` (caption plate fill, used at 0.78 opacity over the video)
- `accent-amber` — `#e8a14a` (lead emphasis: dot, hairline, quote mark, key-word swap)
- `accent-rose` — `#c08c87` (support tint ≤ 35% opacity — soft underlines, gradient stops)
- `muted` — `#8a7e72` (timestamps, attribution, beat labels)

Pure `#000` and pure `#fff` are banned. One accent per beat (`accent-amber` is lead;
`accent-rose` only as support tint, never primary).

**Typography (from DESIGN.md):**

- Headline — Playfair Display 400 italic, 3.25rem, lowercase. Reserved for HOOK pull-line
  and PAYOFF sign-off.
- Caption — Inter 400, 1.5rem, line-height 1.45, `max-width: 78%`. Tabular figures off.
- Label — Inter 500, 0.75rem, uppercase, letter-spacing 0.18em. Beat marker, timestamp.
- Two families maximum. No fallback to Roboto / Arial.

**Mood:** intimate, reflective, candle-warm. Editorial-portrait energy — closer to
*The New Yorker* photo essay than tech-explainer. The grade does the heavy lifting;
the UI breathes around it.

---

## 2 · Rhythm Declaration

**Pattern:** `hook-breathe-THESIS-hold-PAYOFF-resolve`

- HOOK (0.0–1.34s, ~1.2s) — quick utterance, "Age of artificial intelligence." Plate
  enters; pull-line lands on the noun. No transition fanfare — the speaker is mid-thought.
- THESIS (1.34–13.60s, ~10.5s extracted from take [003.10-013.60]) — the sustained
  argument. Plate stays anchored; captions cycle inside it on word groups; ambient
  motion is breath, not movement.
- PAYOFF (13.60–22.6s, ~10.7s from take [018.82-029.50]) — the question + the soft
  qualifier. Pull-line returns in italic Playfair for the distilled phrase ("return
  to the roots"); plate lingers; final hold of +0.4s after audio resolves.

This is a *deliberate* rhythm. Nothing snaps; nothing slams. Energy peaks at the
THESIS-to-PAYOFF transition (the rhetorical pivot — "I thought, why don't we…") and
resolves into a held final frame. Pauses in the audio are visible: the plate doesn't
fill them with motion.

---

## 3 · Global Rules

- **Parallax layers:** three. (1) Background — `primary` fill + warm-grain overlay +
  soft-vignette. (2) Midground — the speaker (the underlying video clip). (3) Foreground —
  caption plate, beat marker, hairline rule, optional pull-line / timestamp. The middle
  layer is sacred — no overlay crosses the speaker's face band.
- **Atmosphere (DESIGN.md `motion.atmosphere`):** `warm-grain`, `soft-vignette`,
  `hairline-rule` — these are the three persistent decoratives that ride underneath
  every beat. They never enter; they're already there. They breathe.
- **Micro-motion baseline:** every decorative has slow ambient motion (`sine.inOut`,
  4–8s cycles, ≤ 4% opacity oscillation). Static decoratives are forbidden. The grain
  drifts; the vignette breathes; the hairline pulses 0.6 → 0.8 opacity.
- **Entrance language:** `gsap.from()` opacity 0 → 1, y +24 → 0 for caption plate; y +18
  → 0 for pull-line; opacity-only for beat marker. Vary at least three eases per beat
  (`sine.inOut` lead, plus `power1.out` and `power2.out` accents). Stagger plate before
  text by 0.15s.
- **Exit language:** **NONE.** Soft Signal forbids `gsap.to(opacity: 0)` on captions,
  plates, or pull-lines (DESIGN.md "Don't"). The transition between beats IS the exit.
- **Primary transition:** *thermal-distortion* (DESIGN.md `motion.transition`) — a
  slow CSS blur+warm-tint crossfade, 1.1s, `power1.inOut`. Used between HOOK→THESIS and
  THESIS→PAYOFF. No shader transitions in this episode (the medium is a face, not a
  brand reveal — shaders would feel imposed).
- **Accent transition:** at the THESIS→PAYOFF pivot, the hairline rule pulses up from
  0.6 → 1.0 opacity for 0.3s, `sine.out`, then settles back. This is the only "punch"
  in the episode — a quiet amber heartbeat under the rhetorical turn.
- **Pacing:** preserve audio pauses verbatim — the gap between "work myself" (11.9s)
  and "I thought" (12.05s) is held; the gap between "life?" (18.39s) and "Yes" (18.81s)
  is held. No motion fills these gaps. They are the breath.
- **Final hold:** the PAYOFF caption holds an extra 0.4s after the last audible word
  ("point-of-view") at 22.15s — final frame ends at 22.55s.

---

## 4 · Per-Scene Beats

### Scene 1 · HOOK (0.0 → 1.34s)

**Concept.** The viewer drops into the middle of a thought. A warm, low-lit portrait
in a soft room. The speaker's mouth is already moving — "Age of artificial
intelligence." — and the words materialize beneath them as if the camera is
*overhearing* rather than presenting. This is not a title card. It's the
post-it-note version of a thesis: small, off-center, anchored low.

**Mood direction.** Editorial portraiture. Think Joan Didion essay opener — a single
line, italic, lowercase, surrounded by air. Not a TED talk lower-third; not a
broadcast chyron. The screen is *almost* empty.

**Depth layers (BG → MG → FG).**

- BG — `primary` (`#1a1614`) fill; **warm-grain** layer at 8% opacity, slow drift
  (transform: translate(0, 0) → translate(-2px, -1px) over 6s, `sine.inOut`);
  **soft-vignette** radial at 12% opacity, breathing scale 1.0 → 1.04 over 7s.
- MG — the speaker video (underlying clip, take `[000.12-001.34]`). No overlay
  crosses y = 120–1280px.
- FG — (1) **beat marker** top-left at (64, 96): 6px `accent-amber` dot + 12px gap +
  Inter label `muted` "HOOK · 1 / 3". Anchored, no motion beyond opacity 0 → 1.
  (2) **caption plate** lower third, full-width, `surface` at 0.78 opacity, 28px
  vertical / 64px horizontal padding, `border-radius: 14px`. Caption text "age of
  artificial intelligence." in Inter caption role, `on-primary`, `max-width: 78%`,
  left-aligned. (3) **pull-line** above the caption plate (28px gap): Playfair
  Display italic 3.25rem, `on-primary`, lowercase — the single distilled phrase
  "the age of artificial intelligence." (4) **hairline rule** between pull-line and
  plate: 1px `accent-amber` at 0.6 opacity, 240px wide, left-aligned to the plate
  edge. Eight elements total counting BG decoratives — within the 8–10 budget.

**Animation choreography.**

- Beat marker: opacity 0 → 1, 0.4s `sine.inOut`, t = 0.05 (sync with the first
  audible "Age").
- Caption plate: opacity 0 → 1, y +24 → 0, 0.9s `sine.inOut`, t = 0.10. The plate
  *settles* — no overshoot, no bounce.
- Caption text: opacity 0 → 1, y +12 → 0, 0.7s `power1.out`, t = 0.25 (staggered
  0.15s after plate).
- Hairline rule: `scaleX: 0 → 1` from `transformOrigin: left center`, 0.7s
  `sine.inOut`, t = 0.35.
- Pull-line: opacity 0 → 1, y +18 → 0, 0.9s `sine.inOut`, t = 0.45 (DESIGN.md
  prescribes a 0.4s offset from the caption plate; 0.45s lands the entrance just
  after the speaker says "intelligence").
- BG ambient: warm-grain drift + vignette breath are already running at scene
  start (no entrance — they ride underneath all beats).

**Transition out.** `thermal-distortion` (CSS) — caption plate and pull-line
remain fully visible at the cut; the next scene's plate enters under the same
coordinates. 1.1s blur+warm-tint crossfade, `power1.inOut`. Plate y-position
maintained across the cut for continuity (the eye doesn't relocate).

**SFX cues.** None. The room tone of the original take carries the audio — no
added foley.

---

### Scene 2 · THESIS (1.34 → 13.60s)

**Concept.** The viewer settles in. The argument unfolds — *I'm using free
open-source tools, AI agents, writing the software I need myself, for work*. The
plate stays put; only the words inside it cycle. The speaker is the source of
motion now; the UI is a transcript-frame, not a co-presenter. Low energy,
sustained attention.

**Mood direction.** Workshop interview, late afternoon. Light through a single
window. Not a podcast lower-third — a documentary subtitle. The viewer should
feel they are listening, not being addressed.

**Depth layers.**

- BG — same `primary` fill; warm-grain continues its drift; soft-vignette
  continues its breath. No new BG decoratives — continuity is the design.
- MG — speaker video, take `[003.10-013.60]`.
- FG — (1) **beat marker** updates label in place (no re-entrance) to "THESIS ·
  2 / 3"; the dot remains `accent-amber`. (2) **caption plate** persists from
  HOOK (same coordinates, same opacity); its inner caption text cycles in
  word-groups synced to transcript timing. (3) **caption text** — three or four
  word-groups across 10.5s, each fading the previous out via opacity 1 → 0 (250ms
  `power1.in`) before the next fades in (opacity 0 → 1, y +8 → 0, 350ms
  `power1.out`). Group boundaries (rough, refine to transcript): "i'm increasingly
  using" → "free open-source tools" → "because i can deploy them for myself
  easily" → "with the help of AI agents — or just write the software I need".
  Note: caption *content* exits via fade because each is a sub-element inside the
  persistent plate, not a beat overlay. The plate itself never exits.
  (4) **hairline rule** persists; its opacity pulses 0.6 → 0.8 over 5s
  (`sine.inOut`, slow heartbeat). (5) **key-word accent** — at the moment the
  speaker says "AI agents" (~7.7–8.4s), the words "AI agents" are emphasized in
  `accent-amber` for that group's lifetime. This is the one foreground accent
  hit in this beat.

**Animation choreography.**

- Beat marker label crossfade: outgoing label opacity 1 → 0 (200ms), incoming
  label opacity 0 → 1 (300ms), staggered 100ms. Single moment at t = 1.40s.
- Caption text groups: each enters with opacity 0 → 1 + y +8 → 0 (`power1.out`,
  350ms); previous group exits with opacity 1 → 0 (`power1.in`, 250ms). Group
  starts: ~1.86s, ~3.10s, ~5.08s, ~7.20s. Verbs: types-on-the-tail-of-the-pause,
  fades, lifts, settles.
- Key-word accent: `accent-amber` color swap on "AI agents" — `gsap.to(color:
  '#e8a14a', duration: 0.4, ease: sine.inOut)` at the start of that group;
  reverts to `on-primary` when the group fades out.
- BG ambient continues uninterrupted.
- **NO exit tweens** on plate, hairline, beat marker, or pull-line. (There is no
  pull-line in THESIS — Soft Signal reserves Playfair italic for HOOK and PAYOFF
  only. The plate alone carries the body.)

**Transition out.** `thermal-distortion` again, 1.1s `power1.inOut`. **Accent
transition** layered on top: starting 0.3s before the cut, the hairline rule
pulses opacity 0.6 → 1.0 (`sine.out`, 300ms) and back (`sine.in`, 300ms) — the
amber heartbeat marking the rhetorical pivot. Plate, marker, and final caption
group are fully visible at the cut.

**SFX cues.** None. Honor the natural pause around 8.4–8.78s (between "agents"
and "or just"). Visually, the plate sits still — no motion fills the gap.

---

### Scene 3 · PAYOFF (13.60 → 22.55s)

**Concept.** The pivot lands. *I thought — why don't we return to the roots, to
good old software you pay for once and use for life?* The pull-line returns in
italic Playfair, surfacing the distilled phrase — "return to the roots" — over
the caption plate. A single timestamp / attribution drifts in lower-right of the
plate, quiet authorship. The final qualifier ("yes, maybe it's not as
interesting from a business point-of-view") rides out under a 0.4s held final
frame.

**Mood direction.** Closing paragraph of an essay. The kind of last line where
the author exhales. Not a CTA, not a sign-off card — a thought completing
itself. Editorial-warm, not promotional.

**Depth layers.**

- BG — same `primary`; grain continues; vignette continues; an additional
  **soft amber ambient gradient stop** appears at lower-left, `accent-rose` at
  18% opacity (well within the ≤ 35% support-tint rule), radius 600px, breathing
  scale 1.0 → 1.06 over 8s (`sine.inOut`). This is the only new BG decorative —
  it warms the closing frame without competing with the speaker.
- MG — speaker video, take `[018.82-029.50]` (the strategy uses up to 029.50 but
  audible content resolves at 22.15s; final frame holds the pose).
- FG — (1) **beat marker** updates to "PAYOFF · 3 / 3" via the same in-place
  crossfade. (2) **pull-line** returns: Playfair Display italic 3.25rem,
  `on-primary`, lowercase, "return to the roots." 28px above the plate. Quote
  glyph (`"`) in `accent-amber` precedes it as a single 0.6em-tall mark. (3)
  **caption plate** persists. (4) **caption text** cycles in two word-groups:
  "i thought, why don't we return to the roots, to good old software you pay
  for once and use for life?" → "yes, maybe it's not as interesting from a
  business point-of-view." (5) **hairline rule** persists, opacity 0.6
  steady — no pulse here; the pulse already fired at the pivot. (6)
  **timestamp / attribution** — Inter label `muted`, lower-right of the caption
  plate, 96px right-padding inside the plate. Format `font-variant-numeric:
  tabular-nums`. Single optional element, fades in at t = +0.6s into the scene.
  (7) Optional sign-off glow under the pull-line — `0 0 24px rgba(232, 161, 74,
  0.12)` — DESIGN.md allows this on PAYOFF only, never on captions.

**Animation choreography.**

- Beat marker label crossfade at t = 13.60s (same pattern as Scene 2).
- Caption plate persists across the transition — no re-entrance.
- Pull-line entrance: opacity 0 → 1, y +18 → 0, 0.9s `sine.inOut`, t =
  13.95s (0.35s after the cut, lands as the speaker says "I thought").
- Quote glyph: opacity 0 → 1, scale 0.92 → 1, 0.6s `power1.out`, t = 13.95s
  (synchronized with pull-line).
- Caption text group 1 enters at t = 14.00s, fades out at ~18.55s. Group 2
  enters at t = 18.85s (sync with "Yes"), holds through 22.15s.
- Timestamp: opacity 0 → 1, y +6 → 0, 0.6s `power1.out`, t = 14.20s.
- Ambient gradient stop is already breathing from scene start.
- **Final hold** — at 22.15s, the audio resolves. From 22.15s → 22.55s the
  frame is held: caption group 2 visible, pull-line visible, plate visible,
  speaker on the held final frame of the take. At 22.55s, **only the final
  scene** may fade — a slow opacity 1 → 0 over 0.7s `power1.inOut` on a black
  warm wash (`primary`). This is the single permitted exit in the episode.

**Transition out.** Final scene — fade to `primary` (`#1a1614`) over 0.7s
`power1.inOut`, starting at 22.55s, completing at 23.25s. Pull-line, plate, and
caption fade together as a single visual unit.

**SFX cues.** None added. Honor the natural pause between "life?" (18.39s) and
"Yes" (18.81s) — the plate holds the question mark; no motion fills the gap.

---

## 5 · Recurring Motifs

- **The amber dot.** A 6px `accent-amber` circle sits at the head of the beat
  marker in every scene. It does not move. It is the one constant — three quiet
  punctuation marks across 22.6 seconds. The viewer sees three of them; they
  count the beats unconsciously.
- **The hairline rule.** A 1px `accent-amber` 240px line sits between pull-line
  and plate in HOOK, persists through THESIS (where it carries the heartbeat
  pulse at the pivot), and persists through PAYOFF. It is the only structural
  element that crosses every beat.
- **Italic lowercase Playfair.** The pull-line appears in HOOK and returns in
  PAYOFF. THESIS deliberately omits it — the absence is part of the rhythm
  (statement → argument-without-ornament → return-of-the-distilled-phrase).
- **Warm grain + soft vignette.** Run continuously across all three beats. They
  never enter, never exit — they ARE the room.
- **Caption plate continuity.** The same plate, same coordinates, same opacity,
  carries every word the speaker says. It does not relocate, resize, or
  reshape. The viewer's eye lands in the same place every time.

---

## 6 · Negative Prompt — Avoid

Informed by DESIGN.md "Don't" plus house-style "Lazy Defaults to Question":

- **No exit animations** on the caption plate, pull-line, hairline rule, or
  beat marker. The transition IS the exit. Only the very final fade-to-`primary`
  at 22.55s is allowed (DESIGN.md explicit rule).
- **No gradient text** (`background-clip: text`). Reads as 2024 AI landing page
  and breaks the intimate, unstyled tone.
- **No cyan-on-dark, no purple→blue gradients, no neon accents.** They fight the
  warm grade.
- **No `#000000` or `#ffffff`.** Use `#1a1614` (warm shadow) and `#f4ebdc`
  (warm cream). Pure black/white reads cold.
- **No `#333` placeholder grey, no `#3b82f6` placeholder blue, no Roboto/Arial
  fallback.** This is a hard-gate — these are the AI-default markers DESIGN.md
  flags.
- **No more than two text elements visible simultaneously.** Allowed pairs:
  caption plate + beat marker; caption plate + pull-line; caption plate +
  timestamp. Never plate + pull-line + timestamp + marker all at once.
- **No drop shadows, no glassmorphism, no neumorphic UI.** Depth comes from
  the camera grade, not from CSS.
- **No left-edge accent stripes on the caption plate.** No card grids, no
  centered-and-floating layout. Anchor lower-third and top-left only;
  diagonals stay empty.
- **No accent-color fills behind body text.** `accent-amber` is for hairlines,
  dots, glyphs, single-word swaps — never as a background tint behind a
  caption.
- **No `<br>` in caption text.** Use `max-width: 78%` and let the line wrap.
- **No animation of `visibility` / `display`.** Only `opacity`, transforms,
  and color (per HF non-negotiables).
- **No `repeat: -1`.** Compute exact repeat counts from the 22.6s duration:
  `Math.ceil(22.6 / cycleSeconds) - 1`.
- **No shader transitions.** This is a face, not a brand reveal — shaders feel
  imposed. The single CSS `thermal-distortion` is the right register.
- **No music bed, no SFX, no foley.** The room tone of the original take is
  the audio. Adding anything else competes with the voice.
- **No covering the speaker's face band (y = 120–1280px).** No overlay crosses
  this zone, ever.
- **No three-beat-marker-on-three-things-at-once rule violation.** If
  `accent-amber` appears in more than one foreground element in the same frame
  (besides the persistent dot), remove one.
