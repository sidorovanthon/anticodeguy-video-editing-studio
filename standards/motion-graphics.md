# Motion graphics standards

## Purpose
The four-scene system, transition matrix at seams, and visual language for motion graphics overlays.

## Scenes
- **(a) `head` — plain talking-head** — head fills frame, no overlay.
- **(b) `split` — split-screen** — head reduced to one half, frosted-glass graphic on the other.
- **(c) `broll` — full-screen B-roll** — head **HIDDEN behind broll**, motion graphics fills the frame. (was: `full`)
- **(d) `overlay` — talking-head + overlay** — head fills frame, frosted-glass info plate floats over it.

**Naming note.** The compositor identifiers `head` / `split` / `broll` / `overlay`
are the canonical machine names; `(a)/(b)/(c)/(d)` are documentation aliases.
Read `broll` as "head HIDDEN, broll covers the frame" — **not** "talking-head
fullscreen" (that case is `head`). The legacy name `full` is rejected by the
compositor's `parseSceneMode()` — use `broll` in all new plans.

## Core rule
Across each seam, the talking-head must visibly **shrink, disappear, or return from a smaller/hidden state**. If the head stays full-frame on both sides of the seam, the cut is exposed regardless of overlay content.

## Transition matrix

|  from \ to    | (a) head | (b) split | (c) broll | (d) head+overlay |
|---|---|---|---|---|
| (a) head             | ✗ | ✓ | ✓ | ✗ |
| (b) split            | ✓ | ✓ if different graphic | ✓ | ✓ |
| (c) broll            | ✓ | ✓ | ✓ if different graphic | ✓ |
| (d) head+overlay     | ✗ | ✓ | ✓ | ✗ |

Forbidden transitions (canonical names):
`head↔head`, `head↔overlay`, `overlay↔overlay`,
same-graphic `split→split`, same-graphic `broll→broll`.

(Equivalent in alias form: `a↔a`, `a↔d`, `d↔d`, same-graphic `b→b`/`c→c`.)

## Scene length
Bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of resulting duration.

## Visual language
- Frosted glass surfaces use `color.glass.fill`, `blur.*`, `color.glass.stroke`, `color.glass.shadow` (resolved from `DESIGN.md` `hyperframes-tokens` JSON block).
- Corners use `radius.*`.
- Padding inside glass surfaces: at least `spacing.md`.
- Captions never sit on these surfaces — see `standards/captions.md`.

## Graphic specs are mandatory for non-`head` seams
A scene mode is only a label until a seam carries a `graphic:` (component +
data) spec. The compositor's `renderSeamFragment` emits visible content
**only** when the seam supplies `{component, data}`; without it, `split` /
`broll` / `overlay` render as plain talking-head and the scene-mode decision is
silently lost.

Therefore:
- A `split`, `broll`, or `overlay` seam without a `graphic:` line is a
  planner error, not a valid editorial choice.
- A `head` seam may legitimately have no graphic.
- Whatever produces `seam-plan.md` (today: hand-edited; Phase 5: agentic
  planner) must satisfy this rule.

## Scene-mode → component catalog (WATCH)
Working catalog of which graphic sources each scene mode admits as of
2026-04-28. Will harden into a hard rule once the agentic planner
exists (Phase 6b). The list is not frozen — Phase 6b refines it
based on real seam-by-seam tests.

| Scene mode | Allowed sources                                                                                                       |
|---|---|
| `head`     | (none — talking-head only)                                                                                             |
| `split`    | `bespoke` via `split-frame` shell (shell ships in 6b; not available in 6a)                                            |
| `broll`    | `bespoke` ∪ catalog: `data-chart`, `flowchart`, `logo-outro`, `app-showcase`, `ui-3d-reveal`                          |
| `overlay`  | `bespoke` via `overlay-plate` shell (shell ships in 6b) ∪ catalog: `yt-lower-third`, `instagram-follow`, `tiktok-follow`, `x-post`, `reddit-post`, `spotify-card`, `macos-notification` |

`bespoke` means a per-seam HTML sub-composition written by a coding
subagent into `episodes/<slug>/stage-2-composite/compositions/seam-<id>.html`,
following the HyperFrames skill methodology vendored at
`tools/hyperframes-skills/hyperframes/`. Catalog entries are HF
registry blocks installed via `npx hyperframes add <name>`.

A compositor lint that warns when a `split` / `overlay` / `broll`
seam has no graphic, and rejects components outside the allowed set,
is part of Phase 6b.

## Hard rules
- Every seam must produce a scene transition that satisfies the matrix.
- Scene-mode metadata travels in `seam-plan.md`, one entry per seam.
- A `split` / `broll` / `overlay` seam without a `graphic:` spec is invalid.
- Per-seam graphics live in `episodes/<slug>/stage-2-composite/compositions/seam-<id>.html` as HyperFrames sub-compositions. Layout shells (`split-frame`, `overlay-plate`) live in `design-system/components/` and are populated during Phase 6b. The compositor never inlines raw HTML in `index.html` — it references sub-compositions via `data-composition-src`.
- All composition styling reads CSS variables emitted from the `hyperframes-tokens` JSON block in `DESIGN.md` at the repo root. No hardcoded color/size/blur values; no parallel token files.

## Promoted 2026-04-27
- outro-scene overlay-with-subscribe (episode 2026-04-27-desktop-software-licensing-it-turns-out; OUTRO must end on subscribe CTA; if previous scene is overlay, demote to split)

## Layout Before Animation

Source: `tools/hyperframes-skills/hyperframes/SKILL.md#layout-before-animation`.

Position elements at their hero-frame in static CSS first. Animate *toward* that position with `gsap.from()`. Never use `position: absolute; top: Npx` on a content container as a layout primitive. See `standards/bespoke-seams.md` for the canonical pattern.

## Scene phases (build / breathe / resolve)

Source: `tools/hyperframes-skills/hyperframes/references/motion-principles.md`.

Every multi-second seam allocates ~0–30 % entrance, ~30–70 % ambient breathe, ~70–100 % resolve. The seam-to-seam transition (handled by `transitions.html`) is the exit; per-element fade-outs before a transition are a bug.
