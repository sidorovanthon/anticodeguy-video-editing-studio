# Motion graphics standards

## Purpose
The four-scene system, transition matrix at seams, and visual language for motion graphics overlays.

## Scenes
- **(a) plain talking-head** — head fills frame, no overlay.
- **(b) split-screen** — head reduced to one half, frosted-glass graphic on the other.
- **(c) full-screen B-roll** — head hidden, motion graphics fills the frame.
- **(d) talking-head + overlay** — head fills frame, frosted-glass info plate floats over it.

## Core rule
Across each seam, the talking-head must visibly **shrink, disappear, or return from a smaller/hidden state**. If the head stays full-frame on both sides of the seam, the cut is exposed regardless of overlay content.

## Transition matrix

|  from \ to    | (a) head | (b) split | (c) full | (d) head+overlay |
|---|---|---|---|---|
| (a) head             | ✗ | ✓ | ✓ | ✗ |
| (b) split            | ✓ | ✓ if different graphic | ✓ | ✓ |
| (c) full             | ✓ | ✓ | ✓ if different graphic | ✓ |
| (d) head+overlay     | ✗ | ✓ | ✓ | ✗ |

Forbidden transitions: `a↔a`, `a↔d`, `d↔d`, same-graphic `b→b`, same-graphic `c→c`.

## Scene length
Bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of resulting duration.

## Visual language
- Frosted glass surfaces use `tokens.color.glass.fill`, `tokens.blur.*`, `tokens.color.glass.stroke`, `tokens.color.glass.shadow`.
- Corners use `tokens.radius.*`.
- Padding inside glass surfaces: at least `tokens.spacing.md`.
- Captions never sit on these surfaces — see `standards/captions.md`.

## Hard rules
- Every seam must produce a scene transition that satisfies the matrix.
- Scene-mode metadata travels in `seam-plan.md`, one entry per seam.
- Components live in `design-system/components/`. Never inline raw HTML in `composition.html` — always reference a component template.
- All component styling reads from `design-system/tokens/tokens.json` via CSS variables. No hardcoded color/size/blur values.

## Promoted 2026-04-27
- outro-scene overlay-with-subscribe (episode 2026-04-27-desktop-software-licensing-it-turns-out; OUTRO must end on subscribe CTA; if previous scene is overlay, demote to split)
