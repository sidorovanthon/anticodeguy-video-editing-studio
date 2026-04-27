# Motion graphics standards

## Purpose
The four-scene system, transition matrix at seams, and visual language for motion graphics overlays.

## Scenes
- **(a) `head` — plain talking-head** — head fills frame, no overlay.
- **(b) `split` — split-screen** — head reduced to one half, frosted-glass graphic on the other.
- **(c) `full` — full-screen B-roll** — head **HIDDEN behind broll**, motion graphics fills the frame.
- **(d) `overlay` — talking-head + overlay** — head fills frame, frosted-glass info plate floats over it.

**Naming note.** The compositor identifiers `head` / `split` / `full` / `overlay`
are the canonical machine names; `(a)/(b)/(c)/(d)` are documentation aliases.
Read `full` as "head HIDDEN, broll covers the frame" — **not** "talking-head
fullscreen" (that case is `head`). Misreading `full` is the easiest way to
ship a wrong seam plan.

## Core rule
Across each seam, the talking-head must visibly **shrink, disappear, or return from a smaller/hidden state**. If the head stays full-frame on both sides of the seam, the cut is exposed regardless of overlay content.

## Transition matrix

|  from \ to    | (a) head | (b) split | (c) full | (d) head+overlay |
|---|---|---|---|---|
| (a) head             | ✗ | ✓ | ✓ | ✗ |
| (b) split            | ✓ | ✓ if different graphic | ✓ | ✓ |
| (c) full             | ✓ | ✓ | ✓ if different graphic | ✓ |
| (d) head+overlay     | ✗ | ✓ | ✓ | ✗ |

Forbidden transitions (canonical names):
`head↔head`, `head↔overlay`, `overlay↔overlay`,
same-graphic `split→split`, same-graphic `full→full`.

(Equivalent in alias form: `a↔a`, `a↔d`, `d↔d`, same-graphic `b→b`/`c→c`.)

## Scene length
Bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of resulting duration.

## Visual language
- Frosted glass surfaces use `tokens.color.glass.fill`, `tokens.blur.*`, `tokens.color.glass.stroke`, `tokens.color.glass.shadow`.
- Corners use `tokens.radius.*`.
- Padding inside glass surfaces: at least `tokens.spacing.md`.
- Captions never sit on these surfaces — see `standards/captions.md`.

## Graphic specs are mandatory for non-`head` seams
A scene mode is only a label until a seam carries a `graphic:` (component +
data) spec. The compositor's `renderSeamFragment` emits visible content
**only** when the seam supplies `{component, data}`; without it, `split` /
`full` / `overlay` render as plain talking-head and the scene-mode decision is
silently lost.

Therefore:
- A `split`, `full`, or `overlay` seam without a `graphic:` line is a
  planner error, not a valid editorial choice.
- A `head` seam may legitimately have no graphic.
- Whatever produces `seam-plan.md` (today: hand-edited; Phase 5: agentic
  planner) must satisfy this rule.

## Scene-mode → component catalog (WATCH)
Working catalog of which components each scene mode admits. Treated as
guidance until the agentic planner exists; will harden into a hard rule once
it does.

| Scene mode | Allowed components (working set)                  |
|---|---|
| `head`     | (none — talking-head only)                        |
| `split`    | `side-figure`, `code-block`, `chart`, `quote-card`|
| `full`     | `title-card`, `full-bleed-figure`, `b-roll-clip`  |
| `overlay`  | `lower-third`, `subscribe-cta`, `name-plate`      |

A compositor lint that warns when a `split` / `overlay` / `full` seam has no
graphic, and rejects components outside the allowed set, is the next step
once the planner lands.

## Hard rules
- Every seam must produce a scene transition that satisfies the matrix.
- Scene-mode metadata travels in `seam-plan.md`, one entry per seam.
- A `split` / `full` / `overlay` seam without a `graphic:` spec is invalid.
- Components live in `design-system/components/`. Never inline raw HTML in `composition.html` — always reference a component template.
- All component styling reads from `design-system/tokens/tokens.json` via CSS variables. No hardcoded color/size/blur values.

## Promoted 2026-04-27
- outro-scene overlay-with-subscribe (episode 2026-04-27-desktop-software-licensing-it-turns-out; OUTRO must end on subscribe CTA; if previous scene is overlay, demote to split)
