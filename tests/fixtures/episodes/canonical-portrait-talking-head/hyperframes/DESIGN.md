---
name: Long-Form Memo
colors:
  background: "#0c0b0a"
  background-stop-1: "#080706"
  background-stop-2: "#050403"
  background-highlight-1: "#16140f"
  background-highlight-2: "#1d1a13"
  foreground: "#f3ece0"
  foreground-stop-1: "#d9d2c5"
  foreground-stop-2: "#bfb8ab"
  foreground-highlight-1: "#fbf6ec"
  midtone: "#b8a982"
  midtone-stop-1: "#988a66"
  midtone-highlight-1: "#cdbf99"
  accent: "#3a4cb8"
  accent-stop-1: "#2b3a93"
  accent-stop-2: "#1d296e"
  accent-highlight-1: "#5a6dd1"
  accent-highlight-2: "#8294e3"
typography:
  headline:
    fontFamily: Playfair Display
    fontSize: 4.5rem
    fontWeight: 400
    fontStyle: italic
    letterSpacing: -0.02em
    lineHeight: 1.05
  pullquote:
    fontFamily: Playfair Display
    fontSize: 6rem
    fontWeight: 400
    fontStyle: italic
    letterSpacing: -0.025em
    lineHeight: 1.0
  overline:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: 500
    textTransform: uppercase
    letterSpacing: 0.18em
  body:
    fontFamily: Inter
    fontSize: 1.15rem
    fontWeight: 300
    lineHeight: 1.6
rounded:
  none: 0px
  sm: 2px
spacing:
  xs: 4px
  sm: 12px
  md: 28px
  lg: 56px
  xl: 96px
motion:
  energy: calm
  easing:
    entry: "sine.inOut"
    exit: "power1.in"
    ambient: "sine.inOut"
  duration:
    entrance: 1.0
    hold: 2.0
    transition: 1.2
  atmosphere:
    - hairline-rules
    - warm-grain
    - parchment-vignette
  transition: cross-warp-morph
---

## Overview

A reflective talking-head monologue contrasting AI-era self-built tooling with the nostalgia of pay-once software. The visual language must NOT borrow the chrome of the thing the speaker is critiquing — no neon, no particle fields, no cyan/purple gradients. Instead, the design reads like a Stripe Press book cover or a Kinfolk spread: italic serif headlines on warm-tinted near-black, generous negative space, a single muted-indigo accent reserved for the single most-loaded word per scene. Cadence is slow (26.5s for four beats), so motion is breath-paced, not kinetic. The viewer should feel they are reading a memo, not watching a launch reel.

## Colors

Background is a warm-tinted near-black (#0c0b0a) — never pure #000. Foreground is parchment (#f3ece0), tinted warm to evoke printed page rather than screen. The accent is a deep editorial indigo (#3a4cb8) — used sparingly, ONE word or ONE glyph per scene, never as a fill or gradient stop on text. The midtone parchment gold (#b8a982) carries hairline rules, overlines, and decorative underscores; it is the nostalgia thread.

Every base role pre-bakes 1–2 darker stops (for radial vignettes and background gradient bottoms) and 1 lighter highlight (for the upper-left reading-lamp glow each scene carries). Beat sub-agents MUST select hexes from `palette[*].hex` literally — no improvised mid-shades.

Contrast: foreground #f3ece0 on background #0c0b0a yields ~16.4:1 — well over WCAG AA. Accent #3a4cb8 on background passes for non-text decorative use; if accent is used on text, use #5a6dd1 (accent-highlight-1) for AA compliance.

## Typography

Two families, cross-category per the typography rule:

- **Playfair Display** — italic, weight 400 — carries headlines (4.5rem) and pullquotes (6rem). The italic is non-negotiable; it sets the reflective register. Letter-spacing is tight (-0.02em to -0.025em) so the type reads as set, not stretched.
- **Inter** — weight 300 for body copy (1.15rem, line-height 1.6) and weight 500 for overlines (0.8125rem uppercase, letter-spaced 0.18em).

No third family. No font swaps mid-composition. Body measure caps at ~56ch — anything wider breaks the editorial feel.

Banned: Roboto, Open Sans, Lato, Montserrat (per house-style typography rules), and any geometric display sans that would echo Silicon Valley deck aesthetics (no Space Grotesk here — the script is rejecting that world).

## Layout

Asymmetric reading column is the dominant pattern. Every beat reserves 25–40% of the frame as deliberate negative space — the eye is led by emptiness, not by centered alignment. Vertical rhythm uses the spacing scale (xs 4 / sm 12 / md 28 / lg 56 / xl 96). Hairline rules (1px, midtone at 25–35% opacity) act as section anchors.

Grid: implicit 12-column at 1080×1920 portrait. The headline column lives in cols 1–8; overlines and decorative rules float in cols 9–12 OR vice versa, never both filled.

## Elevation

No box-shadows on text or content. The ONLY elevation cue is a subtle radial vignette: `radial-gradient(ellipse at top left, background-highlight-1 0%, background 55%, background-stop-2 100%)` — this creates the reading-lamp feel in the upper-left and pulls focus to the headline. No drop-shadows, no card glows, no neon bloom. The vignette breathes on a 6s sine loop (scale 1.00 ↔ 1.04) at very low amplitude.

## Components

- **Overline**: Inter 500 uppercase 0.8125rem letter-spaced 0.18em, color = midtone (#b8a982). Always sits 28–40px above its headline. NEVER centered.
- **Headline**: Playfair Display italic 4.5rem, color = foreground or foreground-stop-1. Tracking -0.02em. Left-aligned in cols 1–8.
- **Pullquote**: Playfair Display italic 6rem, color = foreground-highlight-1. One glyph (opening cap or terminal ellipsis) may be swapped to accent-stop-1 (#2b3a93) or accent-highlight-1 (#5a6dd1) — choose based on AA contrast at the glyph's local background.
- **Body**: Inter 300 1.15rem, line-height 1.6, color = foreground. Measure capped at 56ch. ONE word per body block may take color = accent-highlight-1 for emphasis (`myself`, `roots`, etc.).
- **Hairline rule**: 1px solid midtone at opacity 0.25–0.35. Used as scene anchor, never as a divider between text blocks.
- **Decorative underscore**: 2px solid midtone-stop-1 (#988a66), animated left→right beneath a pullquote on entrance (0.6s expo.out), then held.
- **Vignette**: radial gradient anchored upper-left, mixing background-highlight-1 → background → background-stop-2. Ambient breath: scale 1.00 ↔ 1.04 on 6s sine loop.
- **Grain overlay**: 7px noise PNG (or SVG turbulence) at opacity 0.04 over the entire frame. Static — does not animate.

## Do's and Don'ts

**Do:**

- Reserve accent (#3a4cb8 / #5a6dd1) for ONE loaded word or ONE glyph per beat — the speaker's rhetorical emphasis maps to one accent moment per scene.
- Tint every neutral warm toward the midtone parchment. Dead grey is forbidden.
- Lead the eye with negative space, not with centering. Asymmetric columns only.
- Hold long. The script's rhetorical pauses between 'I thought' clauses are load-bearing; let the frame rest with them.
- Use italic Playfair for ALL display type. The italic IS the voice.
- Let transitions carry exits. Scenes end without exit-tweens; the cross-warp-morph shader handles the handoff so the final words can trail off as the speaker does.

**Don't:**

- Don't reach for gradient text, neon, cyan-on-dark, or purple-to-blue gradients. Those are the visual idiom of the AI hype the monologue argues against; using them visually undermines the message.
- Don't use particle fields, scan-lines, radial neon glows, or any Data-Drift / Deconstructed atmosphere.
- Don't use pure #000 or pure #fff anywhere. Pull every neutral toward the warm midtone.
- Don't center text blocks with equal weight. Every scene leads with an overline OR a vertical-rotated label, never balanced bilaterally.
- Don't introduce cards, rounded buttons, or shadow-elevated containers. This is editorial; cards are product UI.
- Don't add a third typeface or swap fonts mid-scene. Playfair + Inter, nothing else.
- Don't animate exits on the final beat — the speaker's last line trails off mid-thought; the visual must trail off too.
- Don't render numeric stats large. The script has no data; faking stat-card scaffolding to fill the frame would be dishonest.
