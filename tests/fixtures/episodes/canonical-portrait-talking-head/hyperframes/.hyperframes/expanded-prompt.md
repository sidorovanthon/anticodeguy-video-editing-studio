# Expanded Production Prompt — canonical-portrait-talking-head

## 1. Title + Style Block

**Title:** Velvet Standard — Quiet Editorial (AI-Era / Pay-Once Monologue)

**Palette (cited from DESIGN.md, do not invent intermediates):**

- background: `#0a0a0a` (stops `#080808`, `#050505`; highlight `#141414`)
- surface: `#1a1a1a` (stop `#121212`, highlight `#262626`)
- foreground: `#f0f0f0` (stop `#d8d8d8`, highlight `#ffffff`)
- accent: `#1a237e` (stops `#131a5e`, `#0d1240`; highlight `#2e3aa3`)

**Typography (cited from DESIGN.md):**

- Headline — Inter 300, `3rem`, letter-spacing `0.15em`, ALL CAPS.
- Overline — Inter 500, `0.75rem`, letter-spacing `0.32em`, ALL CAPS.
- Body — Inter 300, `1.125rem`, line-height `1.6`.
- Pull-quote — Inter 300 italic, `2rem`, line-height `1.35`.
- Single display family. No serif companion.

**Mood:** Architectural restraint over spectacle. Hardcover-book endpaper navy
on tinted near-black canvas. Massimo Vignelli lineage tuned to long-form
editorial. The frame breathes; hairline rules organize attention; one deep
indigo accent carries the through-line. Never neon, never hype.

**Format:** 1080×1920 portrait, ~26.5s, locked talking-head video plate
muted as MG; HF beat layer composites overlays + accent rule + typographic
chrome. Grade per strategy: neutral natural-light, gentle shadow lift, mild
contrast, slightly warm midtones — no LUT.

## 2. Rhythm Declaration

**Pattern:** `hook-HOLD-breathe-PIVOT-hold-resolve`

Mapped to EDL beats:

- HOOK (`Age of artificial intelligence.`) — long hold, anchor rule fades in.
- PROBLEM — body-paragraph dominance, sustained anchor, calm.
- PIVOT — italic pull-quote, single ambient brightness lift on the rule
  (the only moment the accent gets brighter than its sustained 30%).
- PAYOFF — two-line headline, longest hold, no exit tween — cross-warp-morph
  carries to black on the unfinished thought.

Energy stays calm throughout. No PUNCH, no SLAM. The rhythm is in *holds*,
not *hits*. Pacing per strategy: tight phrase-boundary cuts, breath beats
preserved between the two "I thought" clauses for rhetorical weight.

## 3. Global Rules

**Parallax / depth layers (every beat):** BG (vignette + grain + slow
breath) — MG (talking-head video plate, dimmed to ~92% luminance, plus
content typography column) — FG (overline label, anchor rule, accent
underline / dot, hairline divider).

**Element count per beat:** 8–10 (per video-composition.md). Counted as:
1 video plate · 1 vignette · 1 grain · 1 anchor rule · 1 overline · 1
hairline divider · 1 headline / body / pull-quote · 1 accent mark
(underline or dot) · 1 ghost numeral (background atmosphere) · 1
slow-vignette-breath layer.

**Micro-motion (mandatory on every decorative):**

- Anchor rule — opacity breath 0.25 ↔ 0.45, 6s sine.inOut, infinite.
- Vignette — radial-gradient luminance breath 0.92 ↔ 1.0, 8s sine.inOut.
- Grain — frame-locked 0.04 opacity static (no animation; deterministic
  pre-rendered tile to avoid `Math.random()`).
- Hairline divider — width 0 → 100% on beat entry, 1.0s sine.inOut.
- Ghost numeral (the "01" / "02" / "03" / "04") — y drift ±2px,
  10s sine.inOut, opacity sustained at 0.04.

**Transitions:**

- Primary: `cross-warp-morph` (per DESIGN.md) — 0.8s, power2.inOut.
- Used between every beat, including PAYOFF → black.
- No CSS exit tweens on text — DESIGN.md "Don't" #7 explicitly forbids
  exit tweens; the shader morph carries the hand-off.
- Entry tweens on text are allowed: `opacity 0 → 1, y 8 → 0`, 1.0s
  sine.inOut (matches DESIGN.md `motion.easing.entry`).

**Easing (cited from DESIGN.md):**

- Entry: `sine.inOut`
- Exit: `power1.in` (used only on the cross-warp-morph wrapper, not on text)
- Ambient: `sine.inOut`

**Durations (cited from DESIGN.md):**

- Entrance: 1.0s · Hold: 2.6s · Transition: 1.2s

## 4. Per-Scene Beats

---

### Beat 1 — HOOK · `[00:00.12 – 00:01.34]` · 1.22s
> "Age of artificial intelligence."

**Concept.** A library at midnight, lit by a single reading lamp. The
viewer is asked to *settle in*. Not "the future is here" excitement —
"a thought is forming". The phrase lands like the first sentence of a
hardcover essay; the page is dark, the indigo rule on the spine just
visible. The viewer should feel they have been invited to *think*, not
to *react*.

**Mood direction.** IBM-era trade paperback opening. Hardcover endpaper
indigo. Vignelli editorial poster typography. Adjacent references: a
Penguin Modern Classics title page; the first frame of a Criterion
Collection title sequence held longer than expected.

**Depth layers (≈9 elements).**

- BG: `#0a0a0a` canvas; radial vignette `background → background-stop-2`
  centered at 38% / 42% (off-axis, asymmetric); subtle-grain tile at 4%
  opacity; ghost numeral "01" at 8% / 12% from top-right, `4rem` Inter 300,
  color `foreground` × 4% opacity.
- MG: talking-head video plate at 92% luminance, anchored full-frame;
  content column at 12% from left through 77% width.
- FG: overline `01 / PREMISE` at top-of-column; 1px hairline divider;
  headline `AGE OF ARTIFICIAL INTELLIGENCE` with emphasized word
  `INTELLIGENCE` in `foreground-highlight-1` (`#ffffff`) plus 1px
  `accent` (`#1a237e`) underline at 70% character width; vertical
  anchor rule at 12% from left, full beat height,
  `accent` × 30% opacity.

**Animation choreography.**

- Video plate — fades in to 92% luminance over 0.6s sine.inOut, holds.
- Anchor rule — *draws down* from top, 1.0s sine.inOut, then enters
  ambient breath (0.25 ↔ 0.45, 6s sine).
- Overline — types on character-by-character at 35ms/char, 0.42s total,
  sine.inOut.
- Hairline divider — width 0 → 100%, 1.0s sine.inOut, lagged 0.2s
  after overline finishes.
- Headline — `opacity 0 → 1, y 8 → 0`, 1.0s sine.inOut, lagged 0.4s
  after divider.
- Emphasized word `INTELLIGENCE` — color crossfades from `foreground`
  to `foreground-highlight-1` over 0.6s sine.inOut, 0.3s after the
  headline lands.
- Accent underline — width 0 → 70%-of-word, 0.7s sine.inOut,
  immediately following the color shift.
- Vignette — slow-vignette-breath ambient (0.92 ↔ 1.0, 8s sine).
- Ghost numeral "01" — y drift ±2px ambient.

**Transition out.** `cross-warp-morph`, 0.8s, `power2.inOut`. The rule
and overline persist *through* the morph to read as continuous spine.

---

### Beat 2 — PROBLEM · `[00:03.10 – 00:13.60]` · 10.5s
> "when I'm increasingly using free open-source tools because I can simply
> deploy them for myself easily with the help of AI agents or just write
> the software I need for work myself,"

**Concept.** The page turns. We are inside the body of the essay. The
reader's eye moves across long lines of measured prose; nothing flashes,
nothing demands, the design is *getting out of the way* of the speaker's
sentence. This is the longest hold — calm, sustained, the visual
equivalent of someone explaining their workflow over a second coffee.

**Mood direction.** Editorial calm. Magazine long-read. The kind of
column where the only ornament is the drop-cap and the rule. Reference:
*The New Yorker* main feature interior page; *Wired* long-form column
when it still ran 1.6 line-height body.

**Depth layers (≈9 elements).**

- BG: `#0a0a0a`; radial vignette unchanged; subtle-grain at 4%; ghost
  numeral "02" replaces "01" with cross-warp-morph carry.
- MG: video plate sustained; content column hosts a body paragraph
  set at `1.125rem / 1.6`, color `foreground`, max 60ch.
- FG: overline `02 / NOW`; hairline divider; anchor rule sustained;
  no headline (per DESIGN.md beat mapping); a single 1px `accent` ×
  20% opacity tick at the line start of the body's third line —
  reads as a margin-mark, the editorial cue that this is the *idea*.

**Animation choreography.**

- Overline `02 / NOW` — types on 0.42s sine.inOut at beat start.
- Hairline divider — width 0 → 100%, 1.0s sine.inOut, lagged 0.2s.
- Body paragraph — paragraph-level `opacity 0 → 1`, 1.2s sine.inOut,
  lagged 0.4s after the divider. Word-level highlight: as the speaker
  hits "AI agents" and "myself," those tokens crossfade their color
  from `foreground` to `foreground-highlight-1` for 0.4s sine.inOut
  then back, synced to per-word transcript timing.
- Margin tick — fades in `opacity 0 → 0.2` over 0.6s as the third
  line lands.
- Anchor rule — sustained ambient breath (no re-trigger).
- Ghost numeral "02" — y drift ±2px ambient.
- Vignette — sustained breath.

**Transition out.** `cross-warp-morph`, 0.8s, `power2.inOut`.
A breath beat (per strategy: "preserve natural breath beats between
the two 'I thought' clauses") sits *across* the morph — the morph's
mid-point coincides with the silence.

---

### Beat 3 — PIVOT · `[00:15.72 – 00:17.36]` · 1.64s
> "I thought, 'Why don't we turn...'"

**Concept.** A held breath. The sentence breaks off mid-thought — and
we honor that. The frame becomes more *quiet*, not more loud. The
italic pull-quote is the visual equivalent of a writer sliding their
glasses up and starting again. This is the only beat where the accent
brightens — a single 0.6s lift on the rule, like a thought flickering.

**Mood direction.** A page margin where someone has written in pencil.
Cinematic title-sequence pause. Reference: a Saul Bass title card held
two beats longer than expected; the silence in a Nicolas Jaar bridge.

**Depth layers (≈9 elements).**

- BG: `#0a0a0a`; vignette + grain unchanged; ghost numeral "03".
- MG: video plate sustained at 92%; content column hosts the
  pull-quote — italic `pull-quote` cut, with a 1px `accent-stop-1`
  (`#131a5e`) left border, padding-left `md` (32px), no fill.
- FG: overline `03 / QUESTION`; hairline divider; anchor rule, but
  this beat the rule briefly lifts opacity 0.30 → 0.55 → 0.30 over
  0.6s sine.inOut on quote entry; ellipsis `...` is a separate
  inline span animated independently.

**Animation choreography.**

- Overline `03 / QUESTION` — types on 0.42s sine.inOut.
- Hairline divider — width 0 → 100%, 1.0s sine.inOut.
- Pull-quote body — `opacity 0 → 1, y 6 → 0`, 1.0s sine.inOut,
  lagged 0.3s after the divider.
- Left border (1px `accent-stop-1`) — height 0 → 100%, 0.8s sine.inOut,
  drawing downward in sync with the quote text appearing.
- Anchor rule — opacity lift 0.30 → 0.55 → 0.30 over 0.6s sine.inOut,
  triggered on quote entry. This is the only intentional non-ambient
  motion the accent rule performs across the whole video.
- Ellipsis `...` — three dots fade in sequentially, 120ms stagger,
  sine.inOut, after the quote completes — the visual breath-hold.
- Ghost numeral "03" — y drift ±2px ambient.
- Vignette + grain — sustained.

**Transition out.** `cross-warp-morph`, 0.8s, `power2.inOut`. The
ellipsis carries through the morph and dissolves into the PAYOFF
overline's first character — a typographic hand-off.

---

### Beat 4 — PAYOFF · `[00:18.82 – 00:30.80]` · 11.98s
> "I thought, 'Why don't we return to the roots, to good old software
> that you pay for once and use for life?' Yes, maybe it's not as
> interesting from a business point-of-view, but how cool is it to..."

**Concept.** A library at dawn. The thought completes, and then —
deliberately — does not. The headline carries the *offer* ("good old
software / you pay for once"); the trailing accent dot is the
*invitation* — the unfinished sentence, the next reader's turn. The
longest hold of the video. Calm, certain, never triumphant. This is
the closing page, not the curtain call.

**Mood direction.** A printed quotation on the inside back cover of a
hardcover book. Editorial restraint at its most confident. Reference:
the closing frame of a *Field Notes* almanac entry; the credit page
of a slim Penguin essay edition.

**Depth layers (≈10 elements).**

- BG: `#0a0a0a`; vignette + grain unchanged; ghost numeral "04";
  a second ghost layer — a faint horizontal hairline at 78% from
  top, `foreground` × 6% opacity, full-width — reads as the
  bottom-of-page rule of a printed book.
- MG: video plate sustained; content column hosts a two-line
  headline: line 1 `GOOD OLD SOFTWARE` / line 2 `YOU PAY FOR ONCE`,
  Inter 300, `3rem`, letter-spacing `0.15em`, ALL CAPS.
- FG: overline `04 / ASPIRATION`; hairline divider; anchor rule;
  emphasized word `ONCE` (`foreground-highlight-1` + 1px `accent`
  underline at 70% character width); a single accent dot
  (8px × 8px filled circle in `accent`) at the trailing position
  after `ONCE`, separated by 24px — the "unfinished, continuing
  thought" mark from DESIGN.md.

**Animation choreography.**

- Overline `04 / ASPIRATION` — types on 0.42s sine.inOut.
- Hairline divider — width 0 → 100%, 1.0s sine.inOut.
- Bottom-of-page hairline — width 0 → 100%, 1.4s sine.inOut, lagged
  0.6s, inward from both edges (left edge anchored, right edge meets
  it — slow, asymmetric).
- Headline line 1 (`GOOD OLD SOFTWARE`) — `opacity 0 → 1, y 8 → 0`,
  1.0s sine.inOut.
- Headline line 2 (`YOU PAY FOR ONCE`) — same tween, lagged 0.4s.
- Emphasized word `ONCE` — color crossfade `foreground` →
  `foreground-highlight-1` over 0.6s sine.inOut, 0.4s after line 2.
- Accent underline beneath `ONCE` — width 0 → 70%-of-word, 0.7s
  sine.inOut, immediately after the color shift.
- Accent dot — `opacity 0 → 1, scale 0 → 1`, 0.5s sine.inOut, lagged
  1.2s after the underline. Then enters a *very* slow ambient
  brightness breath: `accent` ↔ `accent-highlight-1`, 4s sine.inOut,
  infinite — the only element still moving at the end. This is the
  unfinished thought.
- Anchor rule — sustained ambient breath; no re-trigger.
- Ghost numeral "04" — y drift ±2px ambient.
- Vignette + grain — sustained.

**Transition out.** `cross-warp-morph` to black, 1.2s (matches
DESIGN.md `motion.duration.transition`), `power2.inOut`. No exit
tweens on text — the morph alone carries the dissolve. The accent
dot is the last visible element.

## 5. Recurring Motifs

- **The vertical anchor rule at 12% from left.** Persists through every
  beat at `accent` × 30% opacity, ambient breath. It is the spine of
  the book — the through-line from "Age of artificial intelligence"
  to the trailing dot. Never re-triggered, never reset. The rule
  *survives* every cross-warp-morph as continuous geometry.
- **Ghost numerals (`01`, `02`, `03`, `04`).** Top-right of frame at
  `foreground` × 4% opacity, Inter 300 `4rem`. They cross-warp from
  one to the next on each beat boundary — the page numbers of the
  essay.
- **Accent indigo (`#1a237e`) used at most once per beat besides the
  anchor rule.** HOOK: underline beneath `INTELLIGENCE`. PROBLEM:
  margin tick. PIVOT: pull-quote left border + the single brightness
  lift. PAYOFF: underline beneath `ONCE` + the trailing dot. The
  accent is never two foreground objects in the same beat.
- **Type-on overlines.** Every beat opens with the overline typing on
  at 35ms/char. The cadence is the audible click of editorial pacing.
- **The hairline divider.** Drawn fresh every beat, 1.0s sine.inOut.
  The unit of "this is a new section" without ever using a hard cut.
- **Subtle-grain + slow-vignette-breath + hairline-rules** — the three
  atmosphere primitives from DESIGN.md, present in every beat.

## 6. Negative Prompt — What to Avoid

Cited from DESIGN.md "Don'ts" plus video-medium constraints:

- **No gradient text.** No `background-clip: text`, no
  purple→blue display-type tells. The editorial restraint depends on
  weight + tracking, not color tricks.
- **No neon, no cyan-on-dark, no purple→blue gradients.** Those are
  the AI-product visual vocabulary this video is *critiquing*. Using
  them would be the joke landing on the wrong side.
- **No centered or symmetric compositions.** Asymmetry is the brand.
  Justify-left against the anchor rule.
- **No drop shadows beyond 1px hairlines, no glow, no rim-light, no
  soft blur shadows.** Elevation is luminance shift, not depth-of-field.
- **No second display family.** Inter is the only typeface. No serif
  companion, even for the pull-quote — italic Inter is the contrast.
- **No emoji, no decorative icons, no abstract "tech" geometry**
  (orbits, particles, mesh gradients, audio-reactive waveforms,
  rotating cubes). Those pull the frame toward the AI-landing-page
  archetype the video is rejecting.
- **No exit tweens on text.** The cross-warp-morph alone hands off.
  Do not animate text out — that's two transitions stacked on the
  same cut and reads as nervous.
- **No PUNCH / SLAM / CRASH animation verbs.** Energy is `calm` per
  DESIGN.md `motion.energy`. Verbs are *fades*, *types on*,
  *floats*, *crossfades*, *draws*, *breathes* — never percussive.
- **No `Math.random()`, no `Date.now()`, no network fetches** (HF Key
  Rule #6). Grain is a deterministic pre-rendered tile; ambient
  motion is GSAP `repeat: -1` with `yoyo: true`.
- **No more than one accent-colored foreground element per beat
  besides the anchor rule** (DESIGN.md "Do" #3).
- **No invented intermediate hexes.** Use only the named tokens from
  the DESIGN.md frontmatter — `background-stop-2`, `accent-stop-1`,
  etc. Pre-baked palette is closed.
- **No captions burned over the speaker's face.** Content typography
  lives in the right-of-rule column, not floating across the video
  plate. The talking head and the typography are *adjacent*, not
  *stacked*.
- **No audio-reactive visualization.** The voice is the content; the
  design refuses to translate it into shapes.

---

*Total beats: 4 · Approximate length: 26.5s · Energy: calm sustained ·
Transitions: 3× cross-warp-morph (between beats) + 1× cross-warp-morph
to black (after PAYOFF). Per-beat element count holds 9–10. All hex,
type, easing, and duration values are cited from
`hyperframes/DESIGN.md` and not invented at this layer.*
