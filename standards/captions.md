# Caption standards

## Purpose
Typography and timing rules for per-word karaoke captions burned into the final video.

## Style
- Pure typography. **No background plate, no glass surface, no drop shadow** — captions never sit on glass.
- Single line on screen at any moment. **Maximum 3 words visible at once.**
- Per-word karaoke: the active word renders in `color.caption.active` (DESIGN.md); surrounding (already-spoken or upcoming) words in `color.caption.inactive`.

## Layout
- Baseline position: `safezone.bottom` (default 22% of frame height from bottom).
- Horizontal centering, no left-aligned captions.
- Font: `type.family.caption`. Weight: `type.weight.bold` for active, `regular` for inactive.
- Size: `type.size.caption`.

For overflow, captions call `window.__hyperframes.fitTextFontSize` per group on first show — the project-wide primitive. See `standards/bespoke-seams.md` for the rationale and anti-patterns.

## Timing
- Word visibility window starts at the word's `start_ms` from `transcript.json` and ends at `end_ms`.
- Active-word highlight duration matches `[start_ms, end_ms]` of that word.
- The visible 3-word window slides forward word-by-word; never wraps to a second line.

## Hard rules
- Never sit on a glass surface or any motion-graphics element.
- Never wrap to two lines.
- Never go below the safe-zone baseline.
- Never display more than 3 words simultaneously.

## Promoted 2026-04-27
- timing-source master-aligned-via-edl (episode 2026-04-27-desktop-software-licensing-it-turns-out; raw-timeline word timings drift by accumulated EDL gaps; fixed by remapWordsToMaster)

## Promoted 2026-04-27
- field-contract start_ms-end_ms-only (episode 2026-04-27-desktop-software-licensing-it-turns-out; caption components consume ms-fields; compositor normalizes; component must not assume other naming)

## Technical implementation
This standard is the editorial layer (typography, position, karaoke
timing rules, anti-patterns specific to this channel). The technical
implementation pattern — per-word entrance/exit guarantees,
tone-adaptive styling, overflow prevention — follows HyperFrames'
`references/captions.md` (vendored at
`tools/hyperframes-skills/hyperframes/references/captions.md`). When
authoring or modifying captions, read both files together.
