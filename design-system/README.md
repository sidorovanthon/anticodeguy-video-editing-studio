# design-system/

Phase 6b layout-shell home. **Currently empty** — populated when Phase 6b's agentic graphics planner lands.

## Phase 6a state (current)

- **Visual contract source of truth:** `DESIGN.md` at the repo root (the `hyperframes-tokens` JSON block + prose). The compositor parses this directly; the legacy `tokens/tokens.json` was deleted in 6a.
- **Compositor:** `tools/compositor/src/` reads DESIGN.md, parses seam-plan, emits `index.html` + `compositions/captions.html` + `compositions/transitions.html` + per-seam `compositions/seam-<id>.html` (when authored), plus `hyperframes.json` and `meta.json`.
- **Standards:** `standards/{motion-graphics,captions,typography,bespoke-seams,pipeline-contracts}.md` carry the editorial / methodology layer.
- **Vendored HF skills:** `tools/hyperframes-skills/` (read-only, version-pinned to `tools/compositor/package.json`).

## What goes here in Phase 6b

- `design-system/components/` — layout-shell sub-compositions for `split` and `overlay` scene modes (e.g., `split-frame.html`, `overlay-plate.html`). These hold the brand-level frame; per-seam bespoke fills live in each episode's `compositions/seam-<id>.html`.
- Catalog of named patterns (lower-third, name-plate, broll-frame) the agentic planner can compose from.

Do NOT add `tokens/`, `tokens.json`, or any other parallel design-token file — DESIGN.md is the contract.
