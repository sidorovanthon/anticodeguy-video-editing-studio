---
name: Soft Signal — Reflective Portrait
colors:
  primary: "#1a1614"
  on-primary: "#f4ebdc"
  surface: "#241f1b"
  accent-amber: "#e8a14a"
  accent-rose: "#c08c87"
  muted: "#8a7e72"
typography:
  headline:
    fontFamily: Playfair Display
    fontSize: 3.25rem
    fontWeight: 400
    fontStyle: italic
  caption:
    fontFamily: Inter
    fontSize: 1.5rem
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: 500
    letterSpacing: 0.18em
    textTransform: uppercase
rounded:
  sm: 6px
  md: 14px
  lg: 28px
spacing:
  sm: 12px
  md: 28px
  lg: 56px
motion:
  energy: calm
  easing:
    entry: "sine.inOut"
    exit: "power1.inOut"
    ambient: "sine.inOut"
  duration:
    entrance: 0.9
    hold: 2.6
    transition: 1.1
  atmosphere:
    - warm-grain
    - soft-vignette
    - hairline-rule
  transition: thermal-distortion
---

## Overview

This is a portrait talking-head episode — a reflective monologue, ~22 seconds, three beats (HOOK → THESIS → PAYOFF). The visual identity is **Soft Signal**, adapted toward a darker portrait mood: warm-neutral palette graded into the speaker's skin tones, intimate negative space around the subject, and slow ambient motion that does not compete with the speaker's voice. The frame is portrait (1080×1920); the speaker IS the visual — overlays are minimal, deferential, and warm.

This document is the source of truth for color, type, layout, elevation, components, and motion intensity for every downstream beat sub-agent. The grading direction in the strategy ("warm neutral; gentle midtone lift; slight shadow desaturation") is reflected directly in the palette: backgrounds borrow the shadow tone, foreground borrows the lifted midtone, accent borrows a candle-warm amber that lives inside the speaker's lighting rather than on top of it.

## Colors

| Role         | Hex        | Use                                                                                  |
| ------------ | ---------- | ------------------------------------------------------------------------------------ |
| primary      | `#1a1614`  | Background. Dark warm neutral, sampled from the desaturated shadow side of the grade. |
| on-primary   | `#f4ebdc`  | Foreground / body text / caption fill. Warm cream — never pure white.                |
| surface      | `#241f1b`  | Lower-third bar, subtitle plate, optional pull-quote panel.                          |
| accent-amber | `#e8a14a`  | Single emphasis color — quote marks, hairline rules, beat-marker dots, key-word swap. |
| accent-rose  | `#c08c87`  | Secondary tint for soft underlines and ambient gradient stops only. Never primary CTA. |
| muted        | `#8a7e72`  | Timestamps, attribution, beat labels, atmosphere lines.                              |

Rules:

- One accent dominates per beat. `accent-amber` is the lead; `accent-rose` is a support tint at ≤ 35% opacity.
- Pure black (`#000000`) and pure white (`#ffffff`) are banned. The grade is warm — the UI must follow.
- Any text on `primary` must be `on-primary` or `muted`. Text on `surface` must be `on-primary`.
- Accent colors are NEVER used as fill behind body text — only as 1–2px hairlines, dots, glyphs, or quote marks.

## Typography

| Role     | Family            | Weight | Size      | Notes                                                                  |
| -------- | ----------------- | ------ | --------- | ---------------------------------------------------------------------- |
| headline | Playfair Display  | 400    | 3.25rem   | Italic. Reserved for HOOK pull-line and PAYOFF sign-off only.          |
| caption  | Inter             | 400    | 1.5rem    | Burned-in subtitles. Tabular figures off; line-height 1.45.            |
| label    | Inter             | 500    | 0.75rem   | Uppercase, letter-spaced. Beat marker, timestamps, "1 / 3" indicators. |

Rules:

- Two families maximum: Playfair Display (display italic) + Inter (everything else).
- Headline is italic and lowercase except proper nouns — preserves the intimate, hand-written tone implied by Soft Signal.
- Captions wrap via `max-width: 78%` of frame width. No `<br>`. Line-height 1.45 keeps two-line captions breathable on a portrait frame.
- Numerals in timestamps use `font-variant-numeric: tabular-nums`.

## Layout

Frame: 1080×1920 portrait. The speaker occupies the upper ~70% of frame. All overlay content lives in the lower third (y ≥ 1280px) or as a thin upper-edge label bar (y ≤ 120px). The middle band (120–1280px) is **never** covered by an opaque overlay — that is the speaker's face.

- Container: `display: flex; flex-direction: column; height: 100%; padding: 56px 64px 96px;` with content pushed to the bottom via `justify-content: flex-end`.
- Caption plate: full-width across the lower third with 64px horizontal padding, 28px internal padding, `surface` fill at 0.78 opacity over the underlying video.
- Beat marker: top-left, single line, `label` style, `accent-amber` dot + `muted` text. Never centered, never bottom.
- Hairline rules: 1px `accent-amber` at 0.6 opacity, ≤ 240px long, used as breathing dividers between caption and timestamp.

Density: low. Maximum two text elements visible simultaneously (caption plate + one marker or timestamp). The speaker's voice is the primary information channel — the screen is a frame for it, not a competitor.

## Elevation

Flat with one tier of soft separation:

- `surface` plates use a 0.78-opacity fill over the video — no `box-shadow`, no border, just translucent rest.
- Optional `0 0 24px rgba(232, 161, 74, 0.12)` glow under PAYOFF sign-off only. Never on captions, never on labels.
- No drop shadows. No layered cards. No glassy gradients. The depth comes from the grade, not from the UI.

## Components

**Caption plate** (HOOK, THESIS, PAYOFF — every speech beat):

- Container: full-width, 28px vertical / 64px horizontal padding, `surface` at 0.78 opacity, `border-radius: 14px`.
- Text: `caption` role, `on-primary` fill, `max-width: 78%`, left-aligned.
- Entrance: `gsap.from()` opacity 0 → 1, y +24 → 0, duration 0.9, `sine.inOut`. Stagger the plate before the text by 0.15s.
- Exit: handled by scene transition. NEVER `gsap.to(opacity: 0)` on a caption — the transition is the exit.

**Beat marker** (top-left, persistent through each beat):

- Layout: `accent-amber` 6px dot + 12px gap + `label` text in `muted` ("HOOK · 1 / 3").
- Entrance: opacity 0 → 1 only. No motion — markers should feel anchored, not animated.

**Pull-line** (HOOK and PAYOFF only):

- One italic `headline` line, `on-primary` fill, lowercase, `max-width: 70%`.
- Sits ABOVE the caption plate, with 28px gap. Used to surface a single distilled phrase from the beat — never a verbatim caption duplicate.
- Entrance: `gsap.from()` opacity 0 → 1, y +18 → 0, duration 0.9, `sine.inOut`, delay 0.4s after caption plate.

**Hairline rule** (between pull-line and caption plate, optional):

- 1px `accent-amber` at 0.6 opacity, 240px wide, left-aligned to the caption plate edge.
- `gsap.fromTo(scaleX: 0 → 1, transformOrigin: "left center")`, duration 0.7, `sine.inOut`.

**Timestamp / attribution** (PAYOFF only):

- `label` style, `muted` color, lower-right of caption plate. Provides quiet authorship without weight.

## Do's and Don'ts

**Do:**

- Lead with the speaker. Every overlay defers to the face in the upper 70% of frame.
- Use `accent-amber` sparingly — one element per beat carries it (a dot, a quote glyph, a hairline). Once it's on three things in the same frame, remove two.
- Honor the warm-neutral grade in the UI palette. Cream foreground, never `#ffffff`. Warm shadow background, never `#000000`.
- Treat motion as breath. `sine.inOut`, 0.9s entrances, 1.1s transitions. Nothing snaps; nothing overshoots.
- Let pauses be visible. The strategy says "preserve natural pauses" — the visual must too. Hold final frames an extra 0.4s after the audio resolves.

**Don't:**

- No gradient text — looks like an AI landing page from 2024 and breaks the intimate, unstyled tone.
- No cyan-on-dark, no purple→blue gradients, no neon accents — those are the exact "AI Lazy Defaults" the house-style canon flags, and they fight the warm grade.
- No equal-weight centered layouts and no full-frame symmetric type. The speaker is off-center by composition; the UI must be too — anchor lower-third and top-left, leave the diagonals empty.
- No `#333` placeholder grey, no `#3b82f6` placeholder blue, no Roboto / Arial fallback. The HARD-GATE in the canon is real.
- No exit animations on captions, plates, or pull-lines. The transition between beats is the exit. Animating opacity to 0 before the transition empties the frame and breaks Soft Signal's continuity.
- No drop shadows, no glassmorphism, no neumorphic UI. Depth comes from the camera grade, not the interface.
- No more than two text elements visible at once. This is a monologue, not a dashboard.
