# Phase 6b — Agentic Graphics Planner

**Status:** design (spec)
**Date:** 2026-04-28
**Closes retro deltas:** D2 (no bespoke graphics), D4 (script-driven scene segmentation, ≤5 s cap)
**Supersedes:** `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md` — that document is a brief, not a spec; this spec is the brainstormed answer to its open questions.
**Depends on:** `2026-04-28-hf-methodology-promotions-design.md` (this spec assumes the standards updates from that one have landed).

## Problem

Without a planner, scene-mode metadata in `seam-plan.md` is decorative. The compositor's `renderSeamFragment` emits visible content only when a seam carries `{component, data}`. The pilot episode shipped with no graphics. The decision from the pilot retro is: build the planner; do not run another episode without it.

The user's correction in the brainstorm sharpened the problem statement: scene segmentation has been seam-driven, but it must be script-driven. Seams are structural (footage cuts); scenes are semantic (what the viewer should see). The two are no longer 1:1.

## Goal

Build a three-phase planner that turns `script.txt` + `transcript.json` + EDL into an enriched `seam-plan.md` with full scene-mode + transition + graphic specs, then dispatches per-scene generative subagents to produce HF-compliant sub-compositions. Output: a complete HF project ready for `hyperframes lint/validate/inspect --strict-all` and render.

The planner is a thin layer over HyperFrames. It does not duplicate HF's transition catalog, motion principles, scene phases, or layout methodology — it picks from those and ensures inputs are well-formed. Consistency between scenes comes from shared static rules (HF SKILL.md + project `DESIGN.md` + `standards/motion-graphics.md`), not from a runtime coordinator.

## Architecture

Four components run in sequence, gated by host review at the editorial checkpoint (CP2.5):

```
Stage 1 outputs (script, transcript, EDL, master.mp4)
        │
        ▼
┌───────────────────────┐
│ 1. Segmenter (LLM)    │  hierarchical: beats → scenes
└───────────┬───────────┘
            │   scenes: {start_ms, end_ms, beat_id, narrative_position,
            │            energy_hint, key_phrase, script_chunk}
            ▼
┌───────────────────────┐
│ 2. Snap pass (det.)   │  ±300 ms to nearest transcript phrase boundary
└───────────┬───────────┘
            │   same shape, snapped boundaries
            ▼
┌───────────────────────┐
│ 3. Decorator (LLM)    │  scene_mode + transition_out + graphic spec
│    one subagent       │  rules-first; LLM only for ambiguous cases
└───────────┬───────────┘
            │
            ▼
       seam-plan.md  ────────────►  Host CP2.5 review (edit by hand)
            │
            ▼
┌───────────────────────┐
│ 4. Generative dispatch│  N parallel subagents, one per generative scene
│   (parallel agents)   │  shared static rules; no runtime coordinator
└───────────┬───────────┘
            │   compositions/scene-<id>.html per scene
            ▼
   Compositor extension  ─────────►  index.html + sub-compositions
            │
            ▼
   HF gates (lint / validate / inspect --strict-all)
            │
            ▼
   render-stage2-preview / render-final
```

Phases 1–3 are one CLI stage (`run-stage2-plan.sh`). Host edits seam-plan.md by hand if desired. Phase 4 is a second stage (`run-stage2-generate.sh`) that the host invokes after CP2.5 approval.

## Component 1 — Segmenter

**Type:** single LLM agent invocation, hierarchical (two passes).

**Input:**
- `episodes/<slug>/source/script.txt` — author-written script.
- `episodes/<slug>/master/bundle.json` — master-aligned transcript with per-word timings (already produced in Phase 5; see `standards/pipeline-contracts.md`).
- HF narrative-position vocabulary loaded from `references/transitions.md` ("Narrative Position" section).

**Algorithm:**
1. **Beat pass.** Prompt the LLM with the full `script.txt` and ask for narrative beats — typically 4–8 for a 60 s episode. For each beat: `{beat_id, beat_summary, narrative_position, energy_hint, mood_hint?}` where `narrative_position` ∈ {opening, setup, main, topic_change, climax, wind_down, outro} and `energy_hint` ∈ {calm, medium, high}. Beats are time-bounded to script paragraph runs at this stage; absolute timings are resolved from `bundle.json` by alignment.
2. **Scene pass.** For each beat, if the beat duration ≤ 5 s, it is one scene with `start_ms`, `end_ms`, the full beat as `script_chunk`, and inherited `narrative_position` / `energy_hint` / optional `mood_hint`. If the beat duration > 5 s, sub-divide: prompt the LLM with the beat's script chunk and ask for `ceil(duration / 5)` sub-scene splits, each ≤ 5 s, with a per-sub-scene `key_phrase` (5-8 words capturing the visual hook for that slice). Sub-scenes inherit `beat_id`, `narrative_position`, `energy_hint`, `mood_hint` from the parent beat.

**Output:** ordered list of `Scene` records; written into `seam-plan.md` (overwriting the prior shape) by phase 3.

**Failure modes:**
- LLM returns scenes that exceed 5 s — reject and re-prompt with the offending scene highlighted; max 2 retries; on third failure, abort with a clear error pointing the host at manual seam-plan authoring.
- LLM returns empty or fewer scenes than there are sentences — same retry / abort flow.
- LLM hallucinates `narrative_position` outside the vocabulary — reject + re-prompt.

## Component 2 — Snap pass (deterministic)

**Input:** segmenter output + `bundle.json`.

**Algorithm:**
1. Compute phrase boundaries from `bundle.json`: a phrase boundary is the gap between word *i*'s `end_ms` and word *i+1*'s `start_ms` when the gap exceeds 150 ms (approximately one breath). Build a sorted array `phraseBoundaries[]` of midpoint timestamps.
2. For each scene boundary `b` (excluding `start_ms = 0` of the first scene and `end_ms = master_duration` of the last):
   - Find the nearest `phraseBoundary` within ±300 ms.
   - If found: replace `b` with the boundary timestamp.
   - If not found: leave `b` as-is, emit a debug log line ("scene boundary at <ms> has no nearby phrase boundary, kept semantic value"). This is a soft event; not an error.
3. Validate: scenes must remain monotonic, no scene ≤ 0 ms, every scene still ≤ 5 s. If snapping pushes a boundary past the next scene's `end_ms` (rare, when two scenes are very tight and a phrase boundary lies in an awkward spot), revert that snap and keep the semantic boundary.

**Output:** scene records with snapped boundaries.

**Why deterministic:** LLM dependency in the snap pass would re-introduce seam-driven thinking through the back door. The semantic decision lives in component 1; snapping is pure alignment.

## Component 3 — Decorator

**Type:** single LLM agent (subagent) invocation. Rules-first; LLM fills only the ambiguous slots.

**Input:**
- Snapped scene records from component 2.
- `episodes/<slug>/edl.json` — for `seams_inside_scene` count per scene (used to gate `head` mode by hard rule 6).
- `DESIGN.md` (project-level) — for default mood, primary transition, mode-distribution preferences.
- `standards/motion-graphics.md` — for transition matrix forbidden cells, scene-mode → component catalog, soft rules.
- `tools/hyperframes-skills/hyperframes/references/transitions.md` — for the energy × mood × narrative-position transition matrix lookup.

**Per-scene decisions (in order):**

1. **Determine `seams_inside_scene`** by counting EDL seam timestamps that fall in `[scene.start_ms, scene.end_ms)`.

2. **Pick `mode`.** Apply hard rules in order:
   - `narrative_position == outro` → `mode = overlay` (rule 7).
   - `prev_scene.mode == overlay AND no other constraint forces overlay` → demote prev to `split`, retry-flag (rule 3 lookahead).
   - `seams_inside_scene > 1` → `mode ≠ head` (rule 6).
   - `prev_scene.mode == head AND candidate_mode ∈ {head, overlay}` → reject candidate (rule 1, rule 2).
   - `prev_scene.mode == overlay AND candidate_mode == overlay` → reject (rule 3).
   - `(scene.end_ms - scene.start_ms) < 1500` → `mode ∈ {overlay, head}` (rule 8).

   After hard rules, candidates are typically narrowed to 1–3. If exactly 1, take it. If multiple, dispatch to LLM with the candidate set, scene context, soft rules from `standards/motion-graphics.md`, and `DESIGN.md` style prompt; LLM picks one.

3. **Pick `transition_out`** (deterministic; no LLM).
   - Look up energy × mood × narrative_position in the HF transition matrix.
   - If multiple transitions match, pick the project default from `DESIGN.md` (currently `crossfade 0.4 s power2.inOut`) when energy = calm; otherwise pick the first listed in HF's matrix for that bucket.
   - Honour project-wide cap: at most one accent transition per beat (HF rule "Pick ONE primary (60-70% of scene changes) + 1-2 accents"). Track usage across the scene list; once 30 % of scenes have used a non-primary transition, revert remaining picks to primary.

4. **Validate the transition matrix** in `standards/motion-graphics.md` over the `(prev_mode, current_mode, prev_graphic_brief, current_graphic_brief)` tuple. The same-graphic-split→split and same-graphic-broll→broll constraints (rules 4, 5) must check the *brief* equality (not just the mode) — but at this stage the brief isn't written yet, so this check is deferred to component 4's post-pass. Decorator emits a deferred-constraint marker; generative dispatcher honours it.

5. **Pick `graphic`.**
   - If `narrative_position == outro` → `graphic.source = catalog/subscribe-cta`, no brief, no data.
   - If `mode == head` → `graphic.source = none`.
   - Otherwise: dispatch to LLM. Input: scene's `script_chunk`, `key_phrase`, `mode`, allowed components from `standards/motion-graphics.md` catalog table for the chosen mode, plus the `DESIGN.md` Style Prompt. LLM returns either:
     - `{source: catalog/<name>, data: <json>}` — when a catalog component matches, e.g. `data-chart` for a numbers-heavy scene.
     - `{source: generative, brief: "<1–2 paragraph brief>", data: <optional json>}` — when the scene needs bespoke work.

**Output:** enriched `seam-plan.md` written to disk. Format per the seam-plan schema below.

**Subagent dispatch:** the decorator is one subagent call. It reads all inputs once, processes scenes sequentially within a single LLM context (so the lookahead rules and per-beat accent counters work naturally), and writes the result. Sequential within decorator is correct because mode/transition decisions depend on neighbours; we do not parallelise this phase.

## Component 4 — Generative dispatcher

**Type:** N parallel subagents, one per scene with `graphic.source = generative`. Catalog-source and `none`-source scenes are handled deterministically by the compositor in component 5.

**Per-agent input:**
- The scene's full enriched seam-plan entry: `{start_ms, end_ms, script_chunk, beat_id, narrative_position, energy_hint, mood_hint, mode, transition_out, key_phrase, graphic.brief, graphic.data}`.
- Light neighbour context: `{prev_scene.mode, prev_scene.beat_id, prev_scene.graphic.brief?, next_scene.mode, next_scene.beat_id, next_scene.graphic.brief?}` — enough to enforce rules 4, 5 (same-graphic prohibition) and to coordinate transition handoff.
- Path references — the agent uses the Skill tool to load HyperFrames methodology on demand; we do not duplicate SKILL.md into the prompt:
  - `tools/hyperframes-skills/hyperframes/SKILL.md` (via Skill tool).
  - `DESIGN.md` (read directly).
  - `standards/motion-graphics.md` (read directly).
  - `standards/bespoke-seams.md` (read directly).
- Output path: `episodes/<slug>/stage-2-composite/compositions/scene-<beat_id>-<scene_index>.html`.

**Per-agent output:** one HF-compliant sub-composition file at the output path. Contract:
- `<template>` wrapper with a `data-composition-id` matching the filename stem.
- Scoped styles, GSAP timeline registered at `window.__timelines["<id>"]`.
- All visual tokens read from `:root` CSS variables emitted by the compositor from `DESIGN.md`'s `hyperframes-tokens` JSON block. No hardcoded hex values.
- Build-breathe-resolve scene phases (HF rule).
- Entrance animations on every element, no exit animations except on the final scene of the episode (HF rule).

**Concurrency:** all generative agents dispatch in parallel. The dispatcher is a single Node process spawning N child agents and awaiting all of them. We do not need cross-agent communication; coordination comes entirely from the shared neighbour-context + shared static rules.

**Failure handling:**
- An agent that returns a sub-composition that fails `hyperframes lint` or `validate` or `inspect --strict-all` is retried up to 2 times, with the validator's error message prepended to the retry prompt.
- 3rd failure on the same scene: abort the dispatcher; surface the failing scene to the host for manual authoring or for re-running the decorator with adjusted brief.

**Why no art director:** during the brainstorm we considered a hierarchical agent topology (one art director writing per-scene briefs, N implementor agents executing). HyperFrames' methodology explicitly does not work this way: cross-scene consistency comes from shared rules (SKILL.md, DESIGN.md, standards), not from a runtime coordinator. If we observe drift across early episodes, the fix is to make `DESIGN.md` and `standards/motion-graphics.md` more concrete, not to add an agent layer.

## Component 5 — Compositor extension

**Existing behaviour (untouched):** the compositor reads `seam-plan.md`, lays out the scene clips, mounts captions, references `assets/master.mp4`, and writes `index.html` to `stage-2-composite/`.

**Additions:**

1. **Enriched seam-plan parser.** Read the new markdown format (per schema below); produce typed scene records. Replace the current `at_ms / scene: <mode> / ends_at_ms` flat parser with the new schema parser. Backwards compatibility: not required (old seam-plans were not enriched).

2. **Catalog component instantiation.** When a scene has `graphic.source = catalog/<name>`, look up the component in `tools/hyperframes-skills/hyperframes/registry/` and emit a `data-composition-src="compositions/<name>.html"` reference, mounting `data` as the component's expected props.

3. **Generative sub-composition reference.** When a scene has `graphic.source = generative`, emit a `data-composition-src="compositions/scene-<beat_id>-<scene_index>.html"` reference. The actual file is produced by component 4; the compositor only knows the path.

4. **Transition emission.** Each scene's `transition_out` is rendered into the `transitions.html` sub-composition (or whatever HF's transition layer is wired to in the current compositor). Transition duration and easing are looked up by name from HF's transition catalog at compose time.

5. **Mode validator (post-write).** After writing `seam-plan.md` (component 3) and again after generative output lands (component 4), run a deterministic validator pass that checks every hard rule from `standards/motion-graphics.md` over the final scene list. Same-graphic same-mode constraints (rules 4, 5) are checked here, with `graphic.brief` as the equality key — exact-string match is fine; the agents are unlikely to write identical briefs by accident, and if they do, that is itself a violation.

## Seam-plan schema (enriched)

Pure markdown. ATX `## Scene N` headers, bullet list of fields, indented `script:` and `brief:` for multi-line. Compositor parses with a simple state machine (header → field bullets → indented blocks).

```markdown
# Seam plan: <slug> (master_duration_ms=53566)

## Scene 1
- start_ms: 0
- end_ms: 4200
- beat_id: B1
- narrative_position: opening
- energy_hint: medium
- mood_hint: (default)
- mode: head
- transition_out: crossfade
- key_phrase: "DRM is a moving target"
- graphic:
  - source: none

  script: |
    Hello, today we're talking about desktop software licensing
    and why every approach is wrong in a different way.

## Scene 2
- start_ms: 4200
- end_ms: 8800
- beat_id: B1
- narrative_position: setup
- energy_hint: medium
- mode: split
- transition_out: push-slide
- key_phrase: "three approaches"
- graphic:
  - source: generative
  - brief: |
      Right-side panel: three labelled vertical columns sliding in
      left-to-right with 120 ms staggers. Each column has the approach
      name in display weight and a one-line description in body weight.
      Frosted-glass surface; columns share a single glass card.
  - data:
      items:
        - { name: "Online check", note: "user must be online" }
        - { name: "Hardware key", note: "physical dongle" }
        - { name: "Time-bomb", note: "clock-based expiry" }

  script: |
    There are basically three approaches that actually ship in the wild...
```

**Field semantics** (already locked in brainstorm; recorded here for the parser):

| Field | Required | Notes |
|---|---|---|
| `start_ms`, `end_ms` | yes | After snap pass; integers |
| `beat_id` | yes | Opaque string (e.g. `B1`); shared across sibling sub-scenes |
| `narrative_position` | yes | One of HF's vocabulary values |
| `energy_hint` | yes | calm / medium / high |
| `mood_hint` | optional | Defaults to project mood from DESIGN.md |
| `mode` | yes | head / split / broll / overlay |
| `transition_out` | yes | Name from HF transition catalog |
| `key_phrase` | yes | 5–8-word handle |
| `graphic.source` | yes | none / catalog/`<name>` / generative |
| `graphic.brief` | conditional | Required iff `source = generative` |
| `graphic.data` | optional | JSON-shaped payload |
| `script` | yes | Multi-line, indented under the bullet block |

The host edits this file directly between component 3 and component 4.

## Pipeline integration

New scripts, slotting into the existing pipeline:

- `tools/scripts/run-stage2-plan.sh <slug>` — runs components 1–3, writes enriched `seam-plan.md`. Idempotent: re-running overwrites the file (host should commit before re-running).
- `tools/scripts/run-stage2-generate.sh <slug>` — runs component 4 (parallel generative agents). Reads enriched `seam-plan.md`; writes `compositions/scene-*.html`. Aborts loudly if seam-plan is not enriched (no `graphic:` blocks).
- Existing `tools/scripts/run-stage2-compose.sh` — extended (component 5) to consume enriched seam-plan + generated sub-compositions.
- Existing `tools/scripts/run-stage2-preview.sh` — unchanged (assumes compose ran first).

Pipeline order on a real episode:
```
run-stage1.sh
run-stage2-plan.sh           ← new
[host CP2.5 review/edit of seam-plan.md]
run-stage2-generate.sh       ← new
run-stage2-compose.sh        ← extended (component 5)
run-stage2-preview.sh        ← unchanged
[host CP3 review of preview]
render-final.sh
```

## Code layout

New files in `tools/compositor/src/planner/`:
- `segmenter.ts` — orchestrates the LLM call for components 1 (both passes).
- `snap.ts` — deterministic snap pass (component 2).
- `decorator.ts` — orchestrates the decorator subagent (component 3).
- `mode-validator.ts` — hard rule enforcement, used by both decorator and post-generate validator.
- `transition-picker.ts` — HF matrix lookup (used by decorator).
- `generative-dispatcher.ts` — parallel subagent dispatch (component 4).
- `seam-plan-format.ts` — markdown parser/writer for enriched seam-plan.

Compositor changes in `tools/compositor/src/`:
- Existing `composer.ts:renderSeamFragment` — extend to honour `graphic.source = generative` (reference path) and `catalog/<name>` (registry lookup).
- Existing seam-plan parser — replaced by `seam-plan-format.ts`.

Tests live in `tools/compositor/tests/planner/`. Unit tests for snap, mode-validator, transition-picker, seam-plan-format. Integration test fixture: a tiny synthesised script + transcript + EDL pair that exercises every rule branch (head→split, overlay-demote, outro=subscribe-cta, ≤5 s subdivision, etc.).

## What this spec does NOT do

- It does not write the catalog components (`subscribe-cta`, `data-chart`, etc.). Those are HF registry entries and `design-system/components/` shells; they are listed in `standards/motion-graphics.md`'s catalog table and built incrementally as scenes need them.
- It does not propose a cost model for LLM calls per episode. Cost telemetry is tracked separately (see `tools/compositor/src/observability/` if/when it exists).
- It does not change the host's CP2.5 review protocol. The host still edits `seam-plan.md`; the only change is that the file is now richer.
- It does not address render OOM. That is the Topic 1 spec; this spec assumes preview/render works (whether via the OOM fix or via Docker fallback).
- It does not promote anything to standards. All standards changes live in the Topic 3 spec; this spec consumes those changes as preconditions.

## Open questions deferred to plan stage

- Concrete LLM model choice for segmenter / decorator / generative agents. Not architecturally significant; settled at plan time based on cost and latency.
- Exact JSON shape of `graphic.data` for catalog components — depends on each component's prop contract; deferred to component-by-component work.
- Whether the snap pass runs in TypeScript (in-process with the rest of the planner) or as a separate Python step reusing `tools/scripts/script_diff/align.py`. Lean TypeScript for in-process simplicity; revisit if alignment quality is poor.
- Whether `key_phrase` is set by the segmenter or by the decorator. Current spec puts it in the segmenter (semantic decision); plan may move it to decorator if segmenter can't reliably produce a tight 5–8-word handle.

## Pointers

- `standards/motion-graphics.md` — scene mode definitions, transition matrix, catalog. (Updated by Topic 3 spec.)
- `standards/bespoke-seams.md` — canonical pattern for per-seam HTML sub-compositions.
- `standards/pipeline-contracts.md` — `master/bundle.json` shape consumed by segmenter and snap pass.
- `tools/hyperframes-skills/hyperframes/SKILL.md` — methodology agents follow at generation time.
- `tools/hyperframes-skills/hyperframes/references/transitions.md` — transition matrix lookup table.
- `tools/hyperframes-skills/hyperframes/references/motion-principles.md` — motion guardrails.
- `DESIGN.md` — project visual identity, default mood/transition, mode-distribution preferences (to be added prose).
- `episodes/2026-04-28-desktop-software-licensing-it-turns-out/retro.md` — D2, D4 source.
- `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md` — predecessor brief; superseded.
