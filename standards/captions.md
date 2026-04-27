# Caption standards

## Purpose
Typography and timing rules for per-word karaoke captions burned into the final video.

## Style
- Pure typography. **No background plate, no glass surface, no drop shadow** — captions never sit on glass.
- Single line on screen at any moment. **Maximum 3 words visible at once.**
- Per-word karaoke: the active word renders in `tokens.color.caption.active`; surrounding (already-spoken or upcoming) words in `tokens.color.caption.inactive`.

## Layout
- Baseline position: `tokens.safezone.bottom` (default 22% of frame height from bottom).
- Horizontal centering, no left-aligned captions.
- Font: `tokens.type.family.caption`. Weight: `tokens.type.weight.bold` for active, `regular` for inactive.
- Size: `tokens.type.size.caption`.

## Timing
- Word visibility window starts at the word's `start_ms` from `transcript.json` and ends at `end_ms`.
- Active-word highlight duration matches `[start_ms, end_ms]` of that word.
- The visible 3-word window slides forward word-by-word; never wraps to a second line.

## Hard rules
- Never sit on a glass surface or any motion-graphics element.
- Never wrap to two lines.
- Never go below the safe-zone baseline.
- Never display more than 3 words simultaneously.
