---
name: Velvet Standard — Enduring Craft
colors:
  background: "#0d0b08"
  background-stop-1: "#0a0907"
  background-stop-2: "#060504"
  background-highlight-1: "#1a1611"
  background-highlight-2: "#272118"
  foreground: "#f4ede0"
  foreground-stop-1: "#dcd5c9"
  foreground-highlight-1: "#ffffff"
  accent: "#c8a04b"
  accent-stop-1: "#b48f43"
  accent-stop-2: "#a07e3b"
  accent-highlight-1: "#d6b466"
  midtone: "#6b5e48"
  midtone-stop-1: "#5f5440"
typography:
  headline:
    fontFamily: Inter
    fontSize: 4rem
    fontWeight: 300
    letterSpacing: 0.12em
    textTransform: uppercase
  body:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 300
    lineHeight: 1.6
  serif-pull:
    fontFamily: Playfair Display
    fontSize: 3rem
    fontWeight: 400
    fontStyle: italic
rounded:
  none: 0px
  sm: 2px
spacing:
  sm: 16px
  md: 32px
  lg: 64px
  xl: 96px
motion:
  energy: calm
  easing:
    entry: "sine.inOut"
    exit: "power1.in"
    ambient: "sine.inOut"
  duration:
    entrance: 1.0
    hold: 2.5
    transition: 1.2
  atmosphere:
    - hairline-rules
    - subtle-grain
    - ambient-glow
  transition: cross-warp-morph
---

## Overview

A reflective, portrait-orientation monologue contrasting the noisy "Age of artificial intelligence" with the quiet appeal of pay-once software you keep for life. The visual identity must read as **enduring craft, not AI launch**: warm near-black canvas, ivory body, muted brass accent — the patina of a tool that ages well rather than the chrome of a product page.

Architecturally Velvet Standard (Vignelli/Unimark — generous gutters, hairline rules, slow glides) but warmed away from corporate indigo toward an aged-brass accent that pairs with the spoken nostalgia. Type is restrained sans for labels and headlines; an italic serif appears only on the PIVOT to mark the rhetorical turn ("I thought…") — a single editorial gesture that earns its place.

The talking-head video plate is the hero on every beat. Overlay typography frames the speaker, never competes — kept to the upper or lower third of the 1080×1920 portrait frame, anchored by a hairline rule rather than a card.

## Colors

Palette is dark, warm, and tightly bounded. Every gradient stop and shadow tint is pre-baked so beat sub-agents never improvise an off-palette hex.

- **background `#0d0b08`** — warm ink (not pure black; tinted toward the brass accent so blacks read as paper-stained, not OLED-dead).
  - `background-stop-1 #0a0907` — gradient bottom for vignette.
  - `background-stop-2 #060504` — deepest stop for radial vignette / shader fades.
  - `background-highlight-1 #1a1611` — surface elevation under hairlines.
  - `background-highlight-2 #272118` — rim light on hairline rules.
- **foreground `#f4ede0`** — ivory, never `#fff`. Reads warm against the ink ground.
  - `foreground-stop-1 #dcd5c9` — secondary text, captions, attribution.
  - `foreground-highlight-1 #ffffff` — reserved for a single PAYOFF emphasis word.
- **accent `#c8a04b`** — aged brass / unlacquered gold. The ONE accent hue across all four beats. Used for hairlines, key-word fills, and the italic pull-quote on PIVOT.
  - `accent-stop-1 #b48f43` — gradient mid for accent rules.
  - `accent-stop-2 #a07e3b` — shadow base, deeper edge of glow.
  - `accent-highlight-1 #d6b466` — rim / quick pulse on key terms.
- **midtone `#6b5e48`** — warm grey for tertiary labels (timecode, role chips). Tints toward the brass hue so it never reads as dead grey.
  - `midtone-stop-1 #5f5440` — divider lines below body copy.

WCAG: foreground on background ≈ 13:1 (AAA); accent on background ≈ 6.4:1 (AA normal text). Body and labels stay above 4.5:1 with no color invented per-element.

## Typography

Two families only. **Inter** carries 95% of the surface — `300` for body and headlines, with letterspacing and case carrying the editorial tone instead of weight. **Playfair Display** italic appears exactly once per composition: on PIVOT, sized at 3rem, to render the "I thought…" inflection as a literary aside, not a title.

- **Headline** — Inter 300, 4rem, uppercase, `letter-spacing: 0.12em`. Used only on HOOK ("AGE OF / ARTIFICIAL / INTELLIGENCE" — three lines, deliberate).
- **Body / caption** — Inter 300, 1.5–2rem in portrait, `line-height: 1.6`, sentence case. Captions burned in lower rail.
- **Pull / pivot serif** — Playfair Display italic, 3rem, mixed case. PIVOT only.
- **Label / timecode** — Inter 400, 0.875rem, uppercase, `letter-spacing: 0.18em`, midtone. Used on HOOK and PAYOFF as orientation marks.

Numbers use `font-variant-numeric: tabular-nums`. Banned: Roboto, default Helvetica fallback, gradient text, faux italic.

## Layout

Portrait 1080×1920. Safe zone keeps overlays in the upper or lower **third** so they never crash the speaker's face on the middle third.

- Container fills full scene via `width: 100%; height: 100%; padding: 96px 64px; box-sizing: border-box;` (per Layout-Before-Animation rule). No absolute-positioned content containers.
- One vertical hairline rule (1px, `accent-stop-1`) anchors the left rail across all beats — visual continuity through transitions.
- 12-column logical grid; copy stays in columns 1–8, leaving columns 9–12 for accent marks and timecode.
- Generous negative space — at least 35% of any hero frame is empty ground. No edge-to-edge content.
- No cards. Surfaces are implied by hairlines and tonal shifts in the background, never by borders or panels.

## Elevation

Flat with hairline depth.

- No drop shadows on text or overlays.
- A single `radial-gradient` ambient glow (`accent` at 8% opacity, large radius) sits behind the speaker on HOOK and PAYOFF, breathing on a 6s `sine.inOut` cycle (finite repeat count, never `repeat: -1`).
- Hairline rules at 1px (`accent-stop-1`) carry separation duties that drop shadows would in a web-UI context.
- Decoratives per beat: hairline rule, subtle procedural grain (low opacity), ambient brass glow, optional ghost word at 4% opacity (HOOK + PIVOT only). 3 decoratives per beat sharing one breath cycle.

## Components

- **Caption strip (all beats)** — burned-in word-grouped captions, `foreground-stop-1`, sentence case, lower rail. No background plate; relies on grain + hairline for legibility. Marker sweep on the key term per beat (HOOK: "intelligence"; PROBLEM: "AI agents"; PIVOT: "I thought"; PAYOFF: "for life").
- **Hairline rule** — vertical 1px, `accent-stop-1`, full height, x = 64px. One ambient breath (opacity 0.6 → 0.9 → 0.6 over 6s, finite repeat).
- **Timecode chip** — top-right, midtone, Inter 400 0.875rem, uppercase. Format `EP·01 / 00:00`. Static after entrance.
- **Pull quote (PIVOT only)** — Playfair Display italic, 3rem, foreground, indented from left rail, with a 1px `accent-stop-1` rule beneath. Entrance: `sine.inOut`, 1.0s, y +24 → 0, opacity 0 → 1.
- **Emphasis word (PAYOFF only)** — single word in `accent-highlight-1`, same Inter weight as surrounding body. No underline, no box. The color shift carries the emphasis.
- **Ambient glow** — `radial-gradient(circle at 50% 60%, accent 8%, transparent 65%)` behind speaker. 6s breath, 0.05 → 0.10 opacity.

## Do's and Don'ts

### Do

- Tint blacks and whites toward the brass hue (background `#0d0b08`, foreground `#f4ede0`).
- Let the speaker's face be the visual subject — overlays support, never compete.
- Use one accent hue across all four beats. The brass IS the brand.
- Use hairlines and tonal shifts for separation. Implied structure beats explicit borders.
- Hold the PIVOT serif italic as a single rhetorical gesture — one beat, one quote, no repeats.
- Vary entrance eases across the four beats (`sine.inOut`, `power2.out`, `expo.out`, `power3.out`) so beats don't feel mechanically identical.

### Don't

- **No AI-launch palette.** No cyan-on-dark, no purple-to-blue gradients, no neon. The episode argues AGAINST that aesthetic — using it would betray the content.
- **No gradient text.** `background-clip: text` is the first lazy default of every LLM-styled landing page; this brand's accent appears as fills and rules only.
- **No card grids or repeated cards.** Surfaces are hairlines. There are no boxes.
- **No ALL-CAPS shouting beyond the HOOK.** PROBLEM, PIVOT, PAYOFF stay in mixed case — this is a quiet argument, not a hype reel.
- **No drop shadows or colored glows behind text.** Depth comes from grain and hairlines, not blur.
- **No pure `#000` or `#fff`.** Every black is `#0d0b08` or its stops; every white is `#f4ede0` or its stops. The single `#ffffff` highlight is reserved for one PAYOFF word.
- **No serif on body copy.** Playfair appears once (PIVOT pull-quote). Everywhere else is Inter.
- **No exit animations on HOOK / PROBLEM / PIVOT.** Transitions handle the exits; entrances only on those beats. PAYOFF (final) may fade out.
- **No infinite repeats** (`repeat: -1`) on ambient breaths — calculate finite repeat counts from beat duration.
