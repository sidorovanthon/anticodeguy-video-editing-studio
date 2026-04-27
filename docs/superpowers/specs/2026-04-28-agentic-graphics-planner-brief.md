# Agentic Graphics Planner — Brief

**Status:** brief, not a spec. Input to a future Phase 6 brainstorming session.
**Date:** 2026-04-28
**Source:** Phase 4 retro (macro-retro item 1) + Phase 5 design context.

## Motivation

Without a planner, scene modes (`split` / `broll` / `overlay`) are silent decorative labels: `composer.ts` `renderSeamFragment` only emits visible content when a seam carries `{component, data}`. The pilot episode shipped with no graphics — talking-head + captions only — and was deliberately not published because of this. The compositor is a renderer; the system was designed around a planner that does not yet exist.

## Decision: agentic, not LLM API

The planner will dispatch coding subagents in-pipeline (one per seam, or batched), not call an LLM API. Reasoning:
- A coding subagent reads the standards, the seam transcript, the component catalog with data shapes, and writes the `graphic:` / `data:` lines directly into `seam-plan.md`. Same trust model as the existing EDL subagent at `run-stage1.sh:159`.
- LLM API would require its own prompt scaffolding, validation, retry, and contract glue — code we already have for subagents.
- Subagents already inherit the repo's standards files as context, which is exactly what the planner needs.

## Inputs (per-seam)

- Spoken text in the seam window (from `master/bundle.json` words filtered to `[seam.atMs, seam.endsAtMs]`).
- Scene mode (`head` / `split` / `broll` / `overlay`).
- `standards/motion-graphics.md` excerpt — the WATCH catalog + transition matrix + "Graphic specs are mandatory" section.
- Component catalog: `design-system/components/*.html` plus a manifest of data shapes per component (does not yet exist; component manifest is a Phase 6 task).
- Adjacent seams' scene modes (to enforce transition matrix locally).

## Outputs

- `graphic: <component-name>` and `data: <json>` lines patched into the seam's entry in `seam-plan.md`.
- One subagent invocation produces output for one seam (or for a batch); the orchestrator merges all outputs back into a single `seam-plan.md`.

## Validation layer

Enforced at write time, not runtime:
- Transition matrix from `standards/motion-graphics.md`.
- `scene_mode → allowed_components` from the WATCH catalog.
- Per-component data-shape conformance (component manifest defines the expected fields; planner output must match).
- A `head` seam is allowed to have no graphic; any other mode without a graphic is a planner error.

If a subagent's output fails validation, the orchestrator can retry with the violation message in the prompt.

## Dispatch model — open question

Two shapes plausible:
- **Per-seam:** N subagents in parallel, one per seam. Simple, no coordination, every seam decided in isolation.
- **Batched:** one subagent per N seams (e.g. 3-4). Less startup overhead, the subagent sees a wider context and can balance graphic variety across the batch.

Phase 6 brainstorming should pick one based on observed seam counts (pilot had 8) and cost.

## Other open questions for Phase 6

- Retry policy on validation failure: max retries, prompt format for the retry, fallback to manual editing.
- Cost estimate: subagent invocations per episode, expected wall time.
- Ambiguous-seam handling: when the spoken text doesn't suggest an obvious graphic (e.g. transition phrases), what's the fallback?
- How does the planner integrate with the host's CP2.5 review? Today the host edits `seam-plan.md` by hand; with a planner, the host reviews and edits planner output. The CP protocol stays the same.
- Component manifest format: where does it live (`design-system/components/manifest.json`?), who maintains it, how is it kept in sync with component HTML.

## Pointers

- `standards/motion-graphics.md` — canonical scene-mode names, transition matrix, "Graphic specs are mandatory" section, WATCH catalog `scene_mode → allowed_components`.
- `standards/pipeline-contracts.md` — master-aligned bundle (created in Phase 5); the planner consumes seam transcripts from `master/bundle.json`.
- `episodes/2026-04-27-desktop-software-licensing-it-turns-out/retro.md` — Macro-retro section, "Phase 5 candidate scope" item 1, "Scene modes are label-only without graphic specs" CP2.5 PROMOTE.
- `standards/retro-changelog.md` — entries dated 2026-04-27 and 2026-04-28.
- `tools/scripts/run-stage1.sh:159` — reference for subagent dispatch shape (current EDL author).

## What this brief is NOT

- Not a spec. The next brainstorming session will produce the spec.
- Not a commitment to a specific dispatch model, validation depth, or retry policy — those are open questions above.
- Not bound to Phase 5's tag. Phase 6 is its own brainstorm → spec → plan → execute cycle.
