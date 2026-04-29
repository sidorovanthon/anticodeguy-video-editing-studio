# Generative Sub-Composition

Write one HyperFrames-compliant sub-composition for the scene below.

## Inputs

### Scene
{{SCENE_JSON}}

### Neighbour context
{{NEIGHBOUR_JSON}}

### Project DESIGN.md
{{DESIGN_MD_PATH}}

### Project standards/motion-graphics.md
{{MOTION_GRAPHICS_PATH}}

### standards/bespoke-seams.md (canonical layout pattern)
{{BESPOKE_SEAMS_PATH}}

### HF skill
Use the `hyperframes` skill via the Skill tool. Read SKILL.md, then references/transitions.md and references/motion-principles.md.

### Output path
{{OUTPUT_PATH}}

## Contract

1. `<template>` wrapper with `id` matching the file stem.
2. `data-composition-id` matching the file stem.
3. Scoped styles, no `var(--…)` on captured elements (use literal hex/RGBA from project tokens).
4. GSAP timeline registered: `window.__timelines["<composition-id>"] = tl`.
5. Build / breathe / resolve scene phases (~0–30%, 30–70%, 70–100%).
6. Entrance animations on every visible element.
7. **No exit animations** unless this is the final scene (the dispatcher tells you via `is_final`).
8. All visual tokens from `hyperframes-tokens` JSON in DESIGN.md. No hardcoded colours.
9. Pass `npx hyperframes lint --strict-all`, `validate --strict-all`, `inspect --strict` (HF v0.4.x: `inspect` uses `--strict`, not `--strict-all`).

If the scene mode is `split`, fill the right-side panel only. If `broll`, fill the full frame. If `overlay`, place in lower third unless brief says otherwise.

Same-graphic prohibition: if the previous scene's mode equalled this scene's mode and was non-`head`, the hero frame must be visibly distinct.

Write the file to `{{OUTPUT_PATH}}`. Output only "OK" on stdout.
