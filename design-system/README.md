# Design system

Status: **PLACEHOLDER**. Visual brand to be designed later. Current values
are working defaults inspired by iOS 18 frosted-glass aesthetic. Do not
treat current tokens as final brand decisions.

## Aesthetic direction (working)
- iOS 18 frosted-glass / liquid-glass surfaces.
- High contrast, white-dominant typography over colorful backdrops.
- Soft shadows, generous radii, ample padding.
- Captions are pure typography — no glass behind, no drop-shadow.

## Layout
- `tokens/tokens.json` — single source of truth for all visual values.
- `components/` — reusable HTML templates (added in Phase 3).

## When the brand is finalized
1. Update `tokens/tokens.json`. That is the only file you should need to touch.
2. Components must read tokens through CSS variables. They never hardcode color, size, or blur.
3. `standards/captions.md` and `standards/motion-graphics.md` may reference token *names* but never their *values*.

---

## Phase 6a state (2026-04-28)

`tokens/` and `components/` were emptied during the HF-native foundation
refactor. The visual contract now lives at the repo-root `DESIGN.md`; the
compositor parses its `hyperframes-tokens` JSON block to emit CSS
variables. Layout-shell sub-compositions (`split-frame`, `overlay-plate`)
will be re-authored here as HyperFrames sub-compositions during Phase 6b.
