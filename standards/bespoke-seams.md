# Bespoke seam authoring guide

For Phase 6b coding subagents (and humans authoring per-seam sub-compositions). The captions sub-composition (`tools/compositor/src/captionsComposition.ts`) is the reference example — read it before writing a new sub-composition.

## Layout before animation

Source: `tools/hyperframes-skills/hyperframes/SKILL.md` §"Layout Before Animation".

Position every element at its **hero-frame** in static CSS first. Then animate *toward* that position with `gsap.from()`. Never use `position: absolute; top: Npx` on a content container as a layout primitive — that's a layout bug masquerading as motion.

```html
<!-- correct: hero-frame in CSS, animate from offset -->
<div class="title">…</div>
<style>.title { position: absolute; left: 50%; top: 40%; transform: translate(-50%, -50%); }</style>
<script>gsap.from(".title", { y: 40, autoAlpha: 0, duration: 0.4 });</script>
```

## Scene phases (build / breathe / resolve)

Source: `tools/hyperframes-skills/hyperframes/references/motion-principles.md`.

Every multi-second seam allocates time across three phases:

- **0–30 % entrance:** elements fade/slide/scale in.
- **30–70 % breathe:** held still — no idle motion, no looping shimmer.
- **70–100 % resolve:** outgoing scene is fully visible; the seam transition (handled by `transitions.html`) is the exit. No per-element fade-out tweens.

Dumping all motion at `t=0` and holding for the rest of the seam is a bug.

## fitTextFontSize is the canonical overflow primitive

Source: `tools/hyperframes-skills/hyperframes/references/captions.md`.

For any dynamic-content text (caption groups, lower-thirds, name plates, overlay headers, bespoke seam copy), call `window.__hyperframes.fitTextFontSize(el, { maxFontSize, minFontSize })` on first show. This sizes the text to the available canvas without overflow and without manual font-size juggling.

**Anti-patterns:**
- Per-comp font-size clamps (`Math.min(window.innerWidth/N, …)`).
- `text-overflow: ellipsis` as the overflow strategy.
- Hand-tuned `font-size: clamp(...)` rules per text element.

## Shader-compat CSS rules

Even if the seam doesn't use shader transitions today, follow these rules so 6b can adopt them later without an audit. See `DESIGN.md` § "What NOT to Do" items 6–11 for the full list:

- Literal hex/RGBA in element styles, no `var(--…)`.
- No `transparent` keyword in gradients — use `rgba(target,0)`.
- No gradients on elements thinner than 4 px.
- Mark uncapturable decorative elements with `data-no-capture`.
- No gradient opacity below 0.15.
- Every `.scene` div has explicit `background-color`.

## Inspect annotations

Use `data-layout-allow-overflow` on entrance/exit-animated elements that legitimately overflow the canvas during their tween. Use `data-layout-ignore` on purely decorative elements that should not be audited at all. Do NOT weaken the inspect gate at the script level — annotate at source.
