# Phase 6 — Decomposition

**Status:** decomposition note, not a spec. Locks in the split between 6a and 6b after the 2026-04-28 brainstorming session reframed Phase 6 around HyperFrames-native conventions.
**Date:** 2026-04-28
**Supersedes:** the original single-phase framing in `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md` (still valid as motivation; scope and dispatch model in that brief are obsolete).

## Why decompose

Initial Phase 6 framing ("agentic graphics planner") was scoped against a homemade component manifest in `design-system/components/`. Brainstorming surfaced two corrections:

1. **HyperFrames is the chosen platform — don't reinvent.** `npx hyperframes catalog --json` already exposes 42 production-ready blocks (yt-lower-third, data-chart, flowchart, logo-outro, transitions, social cards). `npx hyperframes skills` ships a 364-line agent-authoring methodology (Visual Identity Gate, Layout Before Animation, sub-composition contract, scene-transition rules, `lint`/`validate`/`inspect`/`animation-map` feedback loop). We were about to author parallel infrastructure.
2. **Project mission is bespoke, code-written motion graphics per video.** Catalog blocks are supplementary (subscribe CTAs, social cards, generic transitions). The dominant subagent activity is **writing new HTML/GSAP sub-compositions per seam**, not template-filling.

Combined scope (HF-native foundation + agentic planner + first bespoke episode) is too large for a single spec. Split into 6a → 6b.

## Phase 6a — HF-native foundation (no planner)

**Goal:** move the existing pipeline onto HyperFrames' canonical project shape, without introducing the agentic planner. Same editorial output as today (talking-head + captions, no graphics on `split` / `broll` / `overlay` seams), but the underlying composition architecture is HF-canonical and ready to host bespoke per-seam compositions.

**Scope:**

1. Install HF skills into the repo via `npx hyperframes skills` (or vendor the relevant subset).
2. Author a **single project-level `DESIGN.md`** at the repo root — the brand identity persists across episodes (palette, typography, motion signature). Reconcile with `design-system/tokens/tokens.json` (one source of truth, the other generated or tightly synced).
3. Rewrite `tools/compositor/`: emit a **root `index.html`** that loads **per-seam `compositions/seam-<id>.html` sub-compositions** via `data-composition-src`, instead of one inline monolithic `composition.html`. Each sub-composition follows the HF contract (`<template>`, `data-composition-id`, scoped styles, registered `window.__timelines[id]`).
4. Migrate `caption-karaoke` to the HF captions pattern (`hyperframes/references/captions.md`). Captions become a sub-composition, not a hand-rolled template.
5. **Deprecate** `design-system/components/glass-card.html`, `title-card.html`, `overlay-plate.html`, `fullscreen-broll.html`. They are placeholder fragments not in HF sub-composition form; bespoke compositions in 6b will replace them.
6. Decide `split-frame.html`'s fate: most likely re-author as an HF sub-composition template (split-screen talking-head + content area is project-specific, no HF analog).
7. Re-derive the WATCH catalog in `standards/motion-graphics.md` from the real HF registry (`hyperframes catalog --json`) plus `bespoke`. Drop the obsolete aspirational list (`side-figure`, `code-block`, `chart`, `quote-card`, `lower-third`, `subscribe-cta`, `name-plate`, `full-bleed-figure`, `b-roll-clip`).
8. Wire `hyperframes validate` + `hyperframes inspect` + `animation-map` into the Stage 2 pipeline (we already call `hyperframes lint`).

**Acceptance test:** the pilot episode (or a copy of it) renders end-to-end through the rewritten compositor and produces a video equivalent to today's output (talking-head, captions, no graphics on non-`head` seams). `lint` + `validate` + `inspect` all green.

**Explicitly NOT in 6a:** the agentic graphics planner, any subagent dispatch, any new bespoke graphics.

## Phase 6b — Agentic graphics planner

**Goal:** ship the first episode with bespoke, code-written motion graphics on every non-`head` seam.

**Scope (to be brainstormed separately after 6a closes):**

1. Per-seam orchestrator. Reads `master/bundle.json` + `seam-plan.md` + project-level `DESIGN.md`.
2. Per-seam decision: **catalog block vs bespoke**. Catalog path → `hyperframes add <name>` + variable-values wire-up. Bespoke path → coding subagent writes `compositions/seam-<id>.html` per HF skill.
3. Coding subagent prompt: hands over seam transcript window, `scene_mode`, `DESIGN.md`, target file path, references to installed HF skills.
4. Validation feedback loop: orchestrator runs `lint` + `validate` + `inspect` + `animation-map` after each subagent output; on failure, retry with violation message in prompt.
5. CP2.5 protocol unchanged: host reviews planner output in `seam-plan.md` and the generated sub-compositions before approving.
6. First production episode end-to-end with bespoke graphics; retro feeds back into Phase 7 candidates.

**Why 6b waits for 6a:** running the rewritten HF-canonical compositor on real material will surface unknowns (resolution scaling 1920×1080 catalog blocks → 1440×2560 final, music merge interactions, sub-composition overhead) that materially affect the orchestrator's design. Building the planner against today's monolithic compositor would be wasted work.

## Locked decisions from 2026-04-28 brainstorming

These are settled — do not relitigate when picking 6a back up:

- **MVP scope is option A** (minimum-minimum) at the planner level, but the planner is 6b. 6a is a prerequisite refactor, not the MVP.
- **Brand identity is project-level**, not per-episode (option A on the DESIGN.md scoping question).
- **Architectural path is option C** (canonical HF sub-composition model + simultaneous captions migration), not minimal adaptation (option A) and not B-without-captions.
- **HF catalog blocks are supplementary, bespoke is primary.** The planner's dominant path is "coding subagent writes new HTML/GSAP per seam." Catalog is a fallback for standard overlays.
- **Project mission is bespoke contextual motion graphics**; this is why the project exists. See memory `project_mission.md`.

## Pointers for the next session

- Original brief (motivation still valid, scope obsolete): `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md`
- Current standards: `standards/motion-graphics.md`, `standards/pipeline-contracts.md`
- HF reference notes: `docs/notes/hyperframes-cli.md`
- HF skills source: unpack `npm view hyperframes dist.tarball` → `package/dist/skills/{hyperframes,hyperframes-cli,gsap}/`
- Compositor entrypoint to rewrite: `tools/compositor/src/index.ts`, called from `tools/scripts/run-stage2-compose.sh`
- Pilot frozen: `episodes/2026-04-27-desktop-software-licensing-it-turns-out/` — do not migrate; use a copy or next episode to validate 6a.

## Next step

Brainstorm Phase 6a in detail → write `docs/superpowers/specs/2026-04-28-phase-6a-hf-native-foundation-design.md` → plan → execute.
