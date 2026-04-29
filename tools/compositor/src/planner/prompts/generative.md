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

## HF Non-Negotiables (transcribed from `hyperframes` SKILL.md §Rules)

Several of these are NOT caught by lint/validate/inspect — retry-on-gate-fail will not save you. Follow them by hand.

**Determinism**
- No `Math.random()`, `Date.now()`, or any time-based logic. If you need pseudo-random values use a seeded PRNG (e.g. mulberry32).

**GSAP property whitelist**
- Animate only visual properties: `opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms.
- Do NOT animate `visibility` or `display`. Do NOT call `video.play()` / `audio.play()` — the framework owns playback.
- Never animate the same property on the same element from multiple timelines simultaneously.

**Timeline construction**
- Build timelines synchronously. No `async`/`await`, no `setTimeout`, no `Promise`. The capture engine reads `window.__timelines` synchronously after page load.
- No `repeat: -1`. Compute finite repeats from duration: `repeat: Math.ceil(duration / cycleDuration) - 1`.
- Do NOT use `gsap.set()` on clip elements from later scenes (they aren't in the DOM at page load). Use `tl.set(selector, vars, timePosition)` inside the timeline at/after the clip's `data-start`.

**HTML / DOM**
- Top-level container MUST have `data-composition-id`. Never forget `window.__timelines` registration.
- Use `data-track-index` (not `data-layer`) and `data-duration` (not `data-end`).
- `data-track-index` is for capture/timing layering — NOT visual stacking. Use `z-index` for visual layering.
- For audio: muted `<video>` + separate `<audio>`. Never use a video element solely for audio. Never nest a video inside a timed div — use a non-timed wrapper.
- Animate a wrapper div, not the `<video>` element's dimensions.
- No `<br>` in content text — let `max-width` wrap. Exception: deliberate short display titles with one word per line.

**Scene transitions (multi-scene compositions)**
- Always transition between scenes — no jump cuts.
- Every scene element gets an entrance animation via `gsap.from()`. No element appears fully-formed. 5 elements → 5 entrance tweens.
- Never write exit animations except on the final scene. The transition IS the exit; outgoing content must be fully visible when the transition starts. The dispatcher tells you `is_final` — only then may you `gsap.to(..., { opacity: 0 })` etc.

**Animation guardrails**
- Offset the first entrance ~0.1–0.3s (not `t=0`).
- Use at least 3 different eases across entrance tweens within a scene; do not repeat an entrance pattern within a scene.
- Avoid full-screen linear gradients on dark backgrounds (H.264 banding) — prefer radial or solid + localized glow.
- Minimum sizes: headlines 60px+, body 20px+, data labels 16px+.
- Apply `font-variant-numeric: tabular-nums` on number columns.

**Layout-Before-Animation discipline**
- Build the hero frame as static CSS first. Verify the layout reads end-to-end with no animation. Only then layer in entrance tweens. See SKILL.md §Layout-Before-Animation.

**Visual Identity Gate**
- All colors and fonts come from `DESIGN.md` (or its `hyperframes-tokens` JSON if present). No hardcoded colors that aren't in the token set. The composition must read as part of this project's brand.

## Mode-specific layout

If the scene mode is `split`, fill the right-side panel only. If `broll`, fill the full frame. If `overlay`, place in lower third unless brief says otherwise.

Same-graphic prohibition: if the previous scene's mode equalled this scene's mode and was non-`head`, the hero frame must be visibly distinct.

Write the file to `{{OUTPUT_PATH}}`. Output only "OK" on stdout.
