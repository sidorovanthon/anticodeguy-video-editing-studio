---
name: Soft Signal — Portrait Reflection
colors:
  background: "#FFF8EC"
  background-stop-1: "#E6DFD4"
  background-stop-2: "#CCC6BD"
  background-highlight-1: "#FFFDF8"
  foreground: "#2a2a2a"
  foreground-stop-1: "#1f1f1f"
  foreground-highlight-1: "#404040"
  accent: "#F5A623"
  accent-stop-1: "#DC951F"
  accent-stop-2: "#C4841C"
  accent-highlight-1: "#F6AF39"
  midtone: "#C4A3A3"
  midtone-stop-1: "#B09292"
typography:
  headline:
    fontFamily: Playfair Display
    fontSize: 4.5rem
    fontWeight: 400
    fontStyle: italic
    letterSpacing: -0.01em
    lineHeight: 1.05
  body:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: 300
    lineHeight: 1.7
  overline:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: 500
    letterSpacing: 0.18em
    textTransform: uppercase
rounded:
  sm: 8px
  md: 16px
  lg: 24px
spacing:
  sm: 12px
  md: 24px
  lg: 48px
  xl: 96px
motion:
  energy: calm
  easing:
    entry: "sine.inOut"
    exit: "power1.inOut"
    ambient: "sine.inOut"
  duration:
    entrance: 0.9
    hold: 2.4
    transition: 1.2
  atmosphere:
    - warm-grain
    - soft-radial-glow
    - hairline-margin-rule
  transition: thermal-distortion
---

## Overview

A reflective portrait talking-head — a single human, mid-frame, speaking from a settled place. The visual identity yields to the speaker rather than competing with them. Warm cream canvas (a soft photographic seamless, not a "page"), italic editorial serif used sparingly for pull-out moments, thin humanist sans for everything else. Motion is breath-paced: nothing snaps, nothing slams. Where Sagmeister's intimate work earns its warmth through texture and craft, this composition earns it through restraint plus a single warm amber accent that holds the eye where the speaker pauses.

The 1080×1920 portrait frame puts the talking head in the upper-middle third; supporting type lives below the speaker's chin line, never crossing it. The grade is warm-neutral with a gentle midtone lift and slight shadow desaturation — design choices echo that: cream-not-white background, charcoal-not-black foreground, amber-not-orange accent.

## Colors

```
background             #FFF8EC   warm cream — the photographic seamless
background-stop-1      #E6DFD4   gradient bottom for radial atmosphere glows
background-stop-2      #CCC6BD   shadow-side gradient stop, used sparingly
background-highlight-1 #FFFDF8   rim-light highlight for soft vignette top

foreground             #2a2a2a   charcoal — body & headline color
foreground-stop-1      #1f1f1f   pull-quote / italic emphasis
foreground-highlight-1 #404040   secondary copy, attribution, timestamps

accent                 #F5A623   warm amber — the eye-rest color
accent-stop-1          #DC951F   accent gradient body
accent-stop-2          #C4841C   accent gradient deep stop, hairline rules
accent-highlight-1     #F6AF39   accent rim / pulse peak

midtone                #C4A3A3   muted rose — connective tissue, dividers
midtone-stop-1         #B09292   midtone deep stop, tag chips on light fg
```

One accent hue only. Amber is the rest-point. The rose midtone is connective — never the headline color, never an action color. Cream backgrounds across all three beats; beat-level distinction comes from amber **opacity and placement**, not from changing the canvas.

WCAG: charcoal `#2a2a2a` on cream `#FFF8EC` clears AAA at body sizes. Amber `#F5A623` on cream is decorative-only at small sizes — it fails AA. For amber text, keep ≥40px or set on `foreground-stop-1` `#1f1f1f` panels.

## Typography

**Headline** — Playfair Display, italic, regular weight (400), 4.5rem (72px) at 1080-wide reference. Used only on THESIS and PAYOFF beats, one phrase per frame, pulled directly from the speaker's words. Italic earns the typographic intimacy that an upright cut would not — and avoids the Maximalist Type trap of shouting.

**Body / overline** — Inter Light (300) for any subtitling/attribution, Inter Medium (500) tracked +0.18em uppercase for overlines. Inter is the only secondary face. No third typeface. Two-family discipline (humanist serif + neutral sans) is non-negotiable.

**Numerics:** `font-variant-numeric: oldstyle-nums` on the serif headline, `tabular-nums` only if a counter appears (none currently planned).

Caption styling: caption font-family inherits from `--body-family`; fill is `foreground-highlight-1` over a `background-highlight-1` translucent strip. No caps, no per-word color flips.

## Layout

Portrait 1080×1920. Three horizontal bands:

- **Top 12%** — quiet zone. Hairline rule at 96px from frame top, midtone color, 1px. Optional overline ("REFLECTION", "01 / HOOK") right-aligned to the rule's right edge.
- **Middle 56%** — the speaker. Talking-head video clip occupies this band edge-to-edge, grade applied. No overlay copy crosses this band's midpoint.
- **Bottom 32%** — typographic stage. Padding `xl` (96px) sides, `lg` (48px) bottom. Headline phrase sits flush-left with a slight optical hang into the side padding (negative `margin-left: -0.05em`). Attribution/cadence note sits `md` (24px) below the headline at `foreground-highlight-1`.

Containers fill the scene via `width: 100%; height: 100%; padding: …; box-sizing: border-box` — never absolute-positioned. Decoratives (radial glow, hairline rule, grain layer) use `position: absolute` inside an `overflow: hidden` parent.

## Elevation

Flat. No drop shadows on type. The depth budget spends entirely on:

1. A single radial glow per beat at `accent` 12% opacity, 720px diameter, breathing 0.96→1.04 over `transition` duration.
2. A whisper-thin hairline rule (1px, `midtone` 60% opacity) at the band boundary.
3. A baked-in warm grain overlay (noise PNG at 4% opacity, mix-blend-mode multiply).

Shadows on cards/buttons are explicitly not used — there are no cards, no buttons. This is a portrait, not a UI surface.

## Components

- **Overline label** — Inter Medium 12px, `foreground-highlight-1`, tracked +0.18em uppercase, with a 24px-wide `accent` underline rule beneath at 2px height. Used once per beat, top-right.
- **Headline phrase** — Playfair Display Italic 72px, `foreground`, max-width 80% of the bottom band. Wraps naturally; no `<br>`. THESIS/PAYOFF only.
- **Caption strip** — handled by the captions composition; constraints documented in Typography.
- **Hairline rule** — 1px solid `midtone` at 60% opacity, full bleed minus `xl` padding on each side.
- **Radial glow** — `radial-gradient(circle at 50% 60%, accent 0%, transparent 60%)` at 12% layer opacity, breathing scale 0.96→1.04, ambient `sine.inOut` over 4s.
- **No buttons, chips, or cards.** If a future revision needs them, derive primary from `accent-stop-1`, secondary from `midtone`.

## Motion

Calm. Entrances: `sine.inOut` over 0.9s; vary stagger between elements (0ms / 180ms / 320ms — three different offsets, never identical). Overlay copy fades up from `y: +24` and `opacity: 0` to its CSS rest position. No exits except on PAYOFF's final fade. Scene-to-scene change is the canonical `thermal-distortion` shader transition (matches Soft Signal canon) — duration 1.2s, eased `sine.inOut`.

The radial glow and grain layer animate independently as ambient motion (breathing scale, slow drift) so the frame is never visually static even during 2.4s holds. Per house-style §"Background Layer", scenes need 2–5 decoratives sharing the ambient breath — here: glow + hairline + grain = three. That is the floor; do not strip it.

Pacing yields to performance: if the speaker's pause runs to 3.7s, the headline holds for 3.7s — the `2.4` token is a default, not a rule.

## Do's and Don'ts

**Do**

- Let the speaker's pauses dictate hold length.
- Use amber `#F5A623` exactly once per beat as a single eye-rest mark — the underline beneath the overline, OR the radial glow tint, OR a single underlined word in the headline. Never two amber marks in the same frame.
- Tint shadows toward warm (the `background-stop-2` cream-shadow), not toward cool gray. The grade is warm; the design follows.
- Italic headline on THESIS and PAYOFF; HOOK is type-free except for the small overline. The opening belongs to the face.

**Don't**

- No gradient text. `background-clip: text` on the headline would convert this from editorial intimacy to wellness-app advert in one keystroke.
- No center-stacked equal-weight composition. Headline is flush-left; speaker is mid-frame. The eye must travel from face to phrase, not bounce on a center axis.
- No drop shadows under the headline (or any type). Flat layering is the entire point of the warm-neutral grade.
- No ALL-CAPS display headlines. Caps shout; this monologue invites. Overlines are the only place caps appear.
- No sage-green accent, even though Soft Signal canon offers it. Sage pushes the piece into the wellness-category cliché and dilutes the single-accent discipline.
- No second sans-serif. Inter is the sans. Do not pair Inter with DM Sans, Space Grotesk, or any other neutral grotesque.
- No hard cuts between beats. The thermal-distortion transition is mandatory — jump cuts would break the reflective register.
- No element appears fully formed. Every overline, headline, hairline rule animates IN via `gsap.from()` at its beat's start.

## Beat Visual Mapping

- **HOOK** — speaker only, no headline. Overline "01 / REFLECTION" top-right with 24px amber underline. Radial glow at frame's lower-third tinted `accent` 8% (slightly under canon — the eye should commit to the face, not the design). Hairline rule fades in at 0.4s. Hold the speaker; the frame teaches the visual language without showing it off.
- **THESIS** — overline "02 / THESIS"; italic Playfair headline pulls a single phrase from the speaker's words, flush-left in the bottom band. Amber accent moves to a single underlined word in the headline (the phrase's emotional weight-point) at `accent` 100%. Radial glow opacity steps up to 12%, repositioned to bottom-left to lead the eye into the headline. Headline staggers in 320ms after overline.
- **PAYOFF** — overline "03 / PAYOFF"; second italic Playfair headline, same flush-left position, but at `foreground-stop-1` (slightly deeper charcoal — the resolution feels grounded). Amber accent retreats to the radial glow only (no underlined word). Final 0.4s of the beat is the only allowed exit: headline fades to `opacity: 0` over 0.4s, ease `power1.inOut`, leaving the speaker on cream before the cut to black.
