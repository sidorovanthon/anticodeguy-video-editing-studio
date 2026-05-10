---
name: Velvet Standard — Quiet Editorial
colors:
  background: "#0a0a0a"
  background-stop-1: "#080808"
  background-stop-2: "#050505"
  background-highlight-1: "#141414"
  surface: "#1a1a1a"
  surface-stop-1: "#121212"
  surface-highlight-1: "#262626"
  foreground: "#f0f0f0"
  foreground-stop-1: "#d8d8d8"
  foreground-highlight-1: "#ffffff"
  accent: "#1a237e"
  accent-stop-1: "#131a5e"
  accent-stop-2: "#0d1240"
  accent-highlight-1: "#2e3aa3"
typography:
  headline:
    fontFamily: Inter
    fontSize: 3rem
    fontWeight: 300
    letterSpacing: 0.15em
    textTransform: uppercase
  overline:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: 500
    letterSpacing: 0.32em
    textTransform: uppercase
  body:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: 300
    lineHeight: 1.6
  pull-quote:
    fontFamily: Inter
    fontSize: 2rem
    fontWeight: 300
    fontStyle: italic
    lineHeight: 1.35
rounded:
  none: 0px
  sm: 2px
spacing:
  sm: 16px
  md: 32px
  lg: 64px
motion:
  energy: calm
  easing:
    entry: "sine.inOut"
    exit: "power1.in"
    ambient: "sine.inOut"
  duration:
    entrance: 1.0
    hold: 2.6
    transition: 1.2
  atmosphere:
    - subtle-grain
    - hairline-rules
    - slow-vignette-breath
  transition: cross-warp-morph
---

## Overview

A measured editorial monologue: one speaker contrasting the AI-built present
with paid-once-use-forever software of the past. The visual identity must hold
the viewer in a thinking posture — never hype, never neon. The frame breathes,
hairline rules organize attention, and a single deep-indigo accent carries the
emotional through-line from "Age of artificial intelligence" to the unfinished
aspirational close. Architectural restraint over spectacle; the words do the
heavy lifting and the design refuses to interrupt them.

The base style is **Velvet Standard** (Massimo Vignelli lineage) tuned toward
quiet long-form editorial: longer holds, wider letter-spacing on display type,
and a palette tinted away from pure black/white toward warm-cool neutrals so
nothing reads as a default white-paper template.

## Colors

Single-accent system on a near-black canvas. Backgrounds are tinted off true
`#000` (`#0a0a0a` base, with `#050808` shadow stops to feel slightly cool);
foregrounds are tinted off true `#fff` (`#f0f0f0` base, `#ffffff` only as
rim highlight). The accent is a deep navy-indigo `#1a237e` — referencing
hardcover-book endpapers and IBM-era trade paperbacks rather than tech-startup
royal blue. Gradient stops are pre-baked so beat sub-comps never invent
off-palette hexes for shadows or highlights — the palette is closed.

- `background` / `-stop-1` / `-stop-2` — vignette and gradient bottoms.
- `background-highlight-1` — surface lift behind hairline cards.
- `surface` family — secondary plates only, never as primary background.
- `foreground` is body text; `-highlight-1` is reserved for the single
  emphasized word per beat (e.g. "intelligence", "roots").
- `accent` and stops are for the rule-line, the single emphasized stat or
  word underline, and the closing aspirational marker only.

## Typography

Inter at four cuts: ultralight 300 for body and headlines, 500 overline for
labels, italic 300 for the pull-quote treatment used on the PIVOT beat. No
serif companion — the contrast comes from weight and tracking, not family
mixing. Headlines sit at `3rem` ALL-CAPS with `0.15em` tracking; the body
runs at `1.125rem / 1.6` for legibility on a calm dark canvas.

The single-display family is a deliberate departure from house "two families"
guidance: this episode is monologue, not interview, and the design must feel
like one voice. Adding a serif would suggest a second voice.

## Layout

Asymmetric columns, anchored left. A persistent thin vertical rule at ~12%
from the left edge anchors every beat; content sits in a 65%-width column to
its right. Generous top padding (`lg`/`64px`) leaves the upper third quiet.
The overline label sits above the rule's top terminus; the headline drops
below with a single line-break of breathing room. Stats and quotes never
center — they justify-left against the rule.

Grid: 12-column nominal but only 4 effective tracks used. Right edge is
intentionally ragged. Nothing is centered; nothing is symmetric.

## Elevation

Near-flat. Elevation is communicated by hairline rules and a 1px luminance
shift, never by drop shadows. Allowed:

- 1px hairline rule at `foreground` × 12% opacity for rules and dividers.
- A `background-highlight-1` plate for cards (no border, no shadow).
- A single `accent` 1px underline beneath the emphasized word per beat.

Disallowed: any `box-shadow` larger than 1px blur, any glow, any rim-light.

## Components

- **Overline label** — `overline` cut, sits 12px above the headline,
  color `foreground-stop-1`. One line, never wraps.
- **Headline** — `headline` cut, justify-left, 1–2 lines max. The single
  emphasized word switches color to `foreground-highlight-1` and gains a 1px
  `accent` underline at 70% character width.
- **Body paragraph** — `body` cut, max 60ch line length, color `foreground`.
- **Pull-quote (PIVOT only)** — `pull-quote` italic cut, 1px left border in
  `accent-stop-1`, padding-left `md`, no background fill.
- **Anchor rule** — vertical 1px line at 12% from left, full beat height,
  color `accent` × 30% opacity, slow ambient opacity breath (0.25 ↔ 0.45,
  6s sine).
- **Hairline divider** — 1px horizontal rule, used between overline and
  headline, color `foreground` × 10% opacity.

## Do's and Don'ts

**Do**

- Lead the eye to one emphasized word per beat. One word, not three.
- Let the anchor rule and overline do the structural work; trust whitespace.
- Use the accent sparingly — at most one accent-colored element per beat
  besides the anchor rule.
- Pre-bake any gradient stops from the palette family (e.g.
  `background → background-stop-2`); never invent an intermediate hex.
- Keep ambient motion at sub-perceptual amplitude — a 6s sine breath, never
  a visible pulse.

**Don't**

- No gradient text. The "background-clip: text + gradient" tell would erase
  the editorial restraint instantly.
- No neon accents, no cyan-on-dark, no purple→blue gradients — those are
  the AI-product visual default this video is critiquing.
- No centered, equal-weight compositions. Asymmetry is the brand.
- No drop shadows beyond 1px hairlines. No glow, no rim-light, no soft
  shadows — those belong to a different style entirely.
- No second display family. One voice, one typeface.
- No emoji, no decorative icons, no abstract geometric "tech" shapes
  (orbits, particles, mesh gradients) — they pull the frame toward the
  AI-landing-page archetype.
- No exit tweens on text — the cross-warp-morph transition handles the
  hand-off between beats.

## Beat Visual Mapping

- **HOOK** — "Age of artificial intelligence." Headline at full `3rem` cut,
  emphasized word: `intelligence` (`foreground-highlight-1` + accent
  underline). Anchor rule fades in over 1.0s sine.in. No body. Overline:
  "01 / Premise". Hold long.
- **PROBLEM** — Body paragraph dominates (the open-source/AI-agents
  passage). Overline: "02 / Now". Anchor rule sustains. No headline; the
  body itself is the content. Body sets at `1.125rem` and runs to ~3 lines.
- **PIVOT** — Pull-quote treatment: "Why don't we return to the roots?"
  Italic, with `accent-stop-1` left border. Overline: "03 / Question".
  Single 0.6s ambient brightness lift on the accent rule at quote entry.
- **PAYOFF** — Two-line headline ("good old software / you pay for once").
  Emphasized word: `once` (highlight + underline). A single accent dot
  marker at the trailing position to read as "unfinished, continuing
  thought." Overline: "04 / Aspiration". Longest hold; no exit tween —
  cross-warp-morph carries to black.
