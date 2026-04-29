# Phase 6b Tech-Debt Cleanup — Design

**Date:** 2026-04-29
**Scope:** four open items from the Phase 6b shake-out (`docs/operations/planner-pipeline-fixes/findings.md`), bundled with a narrow upstream-audit pass to prevent reinvention. A separate spec covers the full pipeline-wide HF reinvention audit (see §6).
**Goal:** safely resumable Stage-2 pipeline + closure of the documented small-and-medium tech debt before cosmetic preview tuning.
**Out of scope:** gated PROMOTE items (D10 AGENTS.md tooling list, D1 SCENE_MS_TOLERANCE drift, D6/D7/D18 — wait for macro-retro).

---

## §0 — Narrow HF Audit (foundational, runs first)

Before designing or building any of §1–§4, read HF docs to confirm we are not building a parallel manifest.

**Reading list (time-boxed ~2 h):**

- `tools/compositor/node_modules/hyperframes/dist/docs/*.md` — all six files
- `tools/compositor/node_modules/hyperframes/dist/skills/{hyperframes,hyperframes-cli,gsap}/**` if present
- `tools/compositor/node_modules/hyperframes/dist/templates/_shared/{AGENTS,CLAUDE}.md`
- `tools/compositor/node_modules/hyperframes/README.md`

**Targeted questions (not open-ended):**

1. **D19 relevance:** does HF expose any concept of episode/run-state, checkpoints, resume, or manifest *outside the composition document itself*? If yes — D19 changes from "design our own state.json schema" to "use HF API X."
2. **D3 relevance:** does HF runtime/CLI expose configurable timeouts or retry policy for subagent-style invocations or render passes?
3. **Catalog authoring:** do HF docs prescribe selector conventions inside catalog blocks (`#<id>` vs attribute selectors)? Confirms our §3 upstream-issue framing.
4. **Composition resolution:** does HF resolve `data-composition-src` lazily (per-instance scope) or via composer-side inlining? Affects how we frame §4.

**Deliverable:** add a `## HF-audit findings (narrow)` block to this spec, in-place, with one bullet per question. Format:

```
- [pertains-to: D19] <what HF has / lacks>. Decision: <D19 design unchanged | D19 changes to X>.
- [pertains-to: D3] ...
```

**Stop condition:** all four questions answered, even if the answer is "not found, proceed as designed." Do not expand into a full pipeline audit — that is §6 (separate spec).

### HF-audit findings (narrow)

- [pertains-to: D19] HF exposes no concept of episode/run-state, checkpoints, resume, or cross-run manifests outside the composition document. All CLI commands (`init`, `lint`, `preview`, `render`, `compositions`) are stateless per-invocation; `hyperframe.manifest.json` (dist root) is a package descriptor, not a run-state store. Not found in audited docs. Decision: D19 unchanged — `state.json` and `generate.manifest.json` design proceeds as specified.

- [pertains-to: D3] HF `render` exposes `--workers`, `--fps`, `--quality`, `--crf`, `--gpu` flags (rendering.md:17-27, hyperframes-cli/SKILL.md:101-113) but no per-scene or per-subagent timeout or retry policy. No env-var surface for invocation time limits. Not found in audited docs. Decision: D3 unchanged — `HF_GENERATIVE_TIMEOUT_MS` override and wallclock aggregator proceed as designed.

- [pertains-to: D15/D21] HF's own SKILL.md (dist/skills/hyperframes/SKILL.md:148-158) prescribes `[data-composition-id="my-comp"] { /* scoped styles */ }` attribute selectors as the canonical scoping pattern for sub-compositions — `#id` selectors are not recommended. Catalog blocks authored to this convention are following HF guidance; the bug is that HF does not enforce isolation between sibling instances when the same block is embedded twice (both match the same attribute selector). The upstream issue framing needs adjustment: it is a **nesting isolation gap** (HF does not scope embedded sub-document CSS per-instance), not merely a catalog-block authoring anti-pattern. Decision: upstream issue framing revised — issue 1 should describe the isolation gap and request per-instance CSS scoping; `#id` recommendation remains valid as a workaround but should not be the primary ask.

- [pertains-to: flowchart aspect] `data-composition-src` is loaded lazily per-instance (compositions.md:19-20; SKILL.md:142-164 shows `<template>` wrapper loaded at runtime, not compile-time inlined by our composer). Each sub-composition controls its own `data-width`/`data-height`; the parent composer does not override dimensions. Therefore the landscape `flowchart` block's 1920×1080 dimensions are fixed in the block itself, and portrait episodes cannot fix the mismatch composer-side. Decision: §4 framing confirmed unchanged — gating `flowchart` out of vertical episodes (Path B) is correct; portrait variant must come from upstream catalog (Path A).

---

## §1 — D19: Crash-Safe Resumable Pipeline State

### Problem

Stage-2 pipeline (`plan` → `generate` → `compose` → `preview`) has only partial resume:
- `generateOne` early-returns on file existence ≥256 B (D7 fix). Saved 7-of-9 once, but verifies file size, not content validity.
- `plan`, `compose`, `preview` recompute everything on rerun.
- No single source of truth for "what is done." Operator inspects filesystem manually.
- System BSODs mid-pipeline (`feedback_render_bsods.md`); a partially-written state file would be worse than no state file.

### Goal

Every Stage-2 step records its progress to disk atomically. After any crash (BSOD, Ctrl-C, hung process, fresh Claude session), rerunning the wrapper picks up exactly where it stopped without re-paying LLM cost for completed scenes.

### Architecture

**Two-tier state model.** Confirmed: granularity hybrid (Q2 = C).

```
episodes/<date-slug>/
├── state.json                          # top-level overview
└── stage-2-composite/
    ├── plan.manifest.json              # per-step manifest: plan inputs/outputs
    ├── generate.manifest.json          # per-scene manifest with prompt hashes
    └── compose.manifest.json           # per-step manifest: compose inputs/outputs
```

- `state.json` — single read for an LLM/operator to understand episode status. Stage-level granularity.
- Per-step manifests — owned by the step that produces them. Scene-level granularity in `generate.manifest.json` only (the only step where per-item resume matters).

**Single writer module.** Confirmed: Q3 = B.

- TypeScript module: `tools/compositor/src/state/episodeState.ts`
- CLI wrapper: `tools/compositor/src/bin/episode-state.ts` (built to `tools/compositor/dist/bin/episode-state.js`)
- All writes go through this module — bash wrappers shell out to the CLI, the dispatcher imports the module directly.
- Atomic write: write to `state.json.tmp` in same dir, `fs.renameSync` to `state.json`. Same for manifests. Rename is atomic on NTFS and tmpfs.

### `state.json` schema (v1)

```json
{
  "schemaVersion": 1,
  "episode": "2026-04-29-desktop-software-licensing-it-turns-out",
  "stage": "stage-2",
  "lastCheckpoint": "CP2",
  "completedSteps": ["plan", "generate"],
  "inProgressStep": "compose",
  "stepStartedAt": "2026-04-29T14:32:11Z",
  "fixesApplied": ["D17-host-wrapper-pad", "D21-flowchart-rescope"],
  "lastUpdate": "2026-04-29T14:35:42Z"
}
```

- `schemaVersion` — bumped on breaking schema change. Reader rejects unknown versions with a clear error.
- `inProgressStep` is `null` between steps, set when a wrapper starts, cleared when the wrapper finishes.
- `fixesApplied` — free-text strings used by operator/LLM handoff to convey what manual interventions happened. Append-only, dedup on insert.
- `stepStartedAt` lets us detect stuck-in-progress states (e.g., crashed wrappers) by age.

### `generate.manifest.json` schema (v1)

```json
{
  "schemaVersion": 1,
  "scenes": {
    "B-1": {
      "kind": "generative",
      "outputPath": "compositions/scene-B-1-3.html",
      "promptHash": "sha256:9f1a...",
      "outputBytes": 4231,
      "wallclockMs": 312418,
      "completedAt": "2026-04-29T14:25:18Z"
    },
    "B-2": { "...": "..." }
  }
}
```

- `promptHash` is sha256 of the exact prompt text the dispatcher would send today (see §1.5 below).
- `kind` matches `seam-plan` scene kind so we don't try to resume a `catalog` scene through `generative` logic.
- `wallclockMs` — measured by the dispatcher, used by §2 for timeout calibration. Includes only the dispatcher's `claude.run` call, not surrounding orchestration.

### Resume semantics (per step)

**`run-stage2-plan.sh`:**
1. On start, read `state.json`. If `inProgressStep === "plan"` and `stepStartedAt` is recent (< 1 h), warn but continue. Otherwise mark `inProgressStep = "plan"`, write atomically.
2. Plan step always re-derives `seam-plan.md` (it's cheap and deterministic given EDL); no per-item manifest needed.
3. On success: `completedSteps += ["plan"]`, `inProgressStep = null`, `lastCheckpoint = "CP1"`. Write `plan.manifest.json` with input EDL hash + output hash for downstream invalidation checks.

**`run-stage2-generate.sh`:**
1. Mark `inProgressStep = "generate"`.
2. Read `generate.manifest.json` if exists. For each scene the dispatcher would generate:
   - Compute current prompt hash.
   - If manifest entry exists AND `promptHash` matches AND `outputBytes >= 256` AND file at `outputPath` exists with matching size → skip (resume hit).
   - Else → regenerate, update manifest entry on success (atomic write).
3. On all scenes complete: `completedSteps += ["generate"]`, `lastCheckpoint = "CP2"`.

**`run-stage2-compose.sh`:**
1. Mark `inProgressStep = "compose"`.
2. Compose is fast (seconds); always re-runs end-to-end. No per-item manifest, but `compose.manifest.json` records input hashes (seam-plan, scene HTMLs, design.md) for §1.6 stale-check.
3. On success: `completedSteps += ["compose"]`, `lastCheckpoint = "CP3"`.

**Preview render (within compose wrapper or separate):**
1. Mark `inProgressStep = "preview"`.
2. Always reruns. (HF render is the dominant wallclock; not skippable without confidence checks.)
3. On success: `completedSteps += ["preview"]`, `lastCheckpoint = "CP4"`.

### §1.5 — What goes into `promptHash`

The hash must change if and only if regenerating would produce different output. Inputs:
- The full prompt text the dispatcher would send (already a deterministic function of scene plan + design.md tokens + the prompt template).
- The model identifier (e.g., `claude-opus-4-7`) — model swap invalidates cached output.
- The dispatcher's allowedTools list.

Computed via `crypto.createHash('sha256')` over a canonical JSON-stringification of the above. Order-stable.

### §1.6 — Stale-state handling (Q4 = D)

Hash-based invalidation for the expensive step (`generate`); trust-the-operator for the cheap steps (`plan`, `compose`, `preview`).

- **`generate`:** on resume, prompt-hash mismatch → regenerate that scene only. Other scenes untouched. Directly serves the "7-of-9 partial completion" use case.
- **`plan`/`compose`/`preview`:** state records what completed and when. No automatic invalidation. Operator override:
  ```bash
  episode-state invalidate --episode <slug> --step compose
  ```
  → removes `compose` from `completedSteps`, deletes `compose.manifest.json`.
  Provides a clear escape hatch without surprising auto-invalidations on Windows mtime drift.

### CLI surface

```
episode-state init --episode <slug>
episode-state mark-step-started --episode <slug> --step <name>
episode-state mark-step-done --episode <slug> --step <name> [--checkpoint CP<N>]
episode-state record-fix --episode <slug> --label <D-id-string>
episode-state record-scene --episode <slug> --scene <id> --output-path <p> --prompt-hash <sha> --output-bytes <n>
episode-state invalidate --episode <slug> --step <name>
episode-state read --episode <slug>                # prints state.json (for handoff/debug)
```

All commands write atomically. `read` is the only non-mutating command.

### Failure modes

- **Corrupt `state.json` after BSOD:** rename-based writes guarantee either the old version or the new version is on disk, never partial. If somehow corrupt (disk-level fault), the CLI errors out with `state.json corrupt: <parse error>` — operator must fix manually. This is acceptable; tradeoff is no transactional log.
- **Concurrent wrappers (two processes writing simultaneously):** out of scope. State assumes one wrapper at a time per episode. Document this in CLI help text.
- **Missing `state.json`:** any command except `init` errors with a clear message; `init` is the only bootstrap.

### Migration

- Existing episodes have no `state.json`. First read of a non-existent state by a wrapper → wrapper auto-creates a fresh one with all `completedSteps = []` (or, if manifests can be reconstructed: derive from existing files). Default to fresh and require an explicit `--reconstruct-from-files` flag for backfill.

### Touched files

- **New:** `tools/compositor/src/state/episodeState.ts`, `tools/compositor/src/bin/episode-state.ts`, tests in `tools/compositor/test/state/`.
- **Modified:** `tools/scripts/run-stage2-plan.sh`, `tools/scripts/run-stage2-generate.sh`, `tools/scripts/run-stage2-compose.sh`, possibly `tools/scripts/render-with-trace.sh`.
- **Modified:** `tools/compositor/src/planner/generativeDispatcher.ts` to call `recordScene` on success, `markStepStarted`/`markStepDone` from a thin orchestrator.
- **Updated:** `tools/compositor/package.json` adds the new bin entry.

---

## §2 — D3: Subagent Timeout Calibration

### Problem

`realDispatcher.timeoutMs` is hardcoded at `4 * 60 * 1000` ms. Picked as a guess, not measured. Too low → false kills on long but legitimate runs. Too high → real hangs waste time before timeout fires.

### Approach

Measure, don't guess.

1. Across the next 3 production-episode runs (or a synthetic batch if not 3 are available), record per-scene wallclock from `generativeDispatcher` for every successful run. The `wallclockMs` field added to `generate.manifest.json` in §1 persists this; aggregate across all episodes with a small read-only script.
2. Compute p50, p95, p99 across all recorded scenes.
3. Set `timeoutMs = round(p99 * 1.5)` clamped to a minimum of 3 min and a maximum of 12 min.
4. Make it configurable via env var `HF_GENERATIVE_TIMEOUT_MS` (already supported in code via `RealDispatcherOptions.timeoutMs` — wire it through wrappers).
5. Document the calibration date and sample size in the code comment near the default value, so the next operator knows when it was last touched.

### Deliverable

- One commit changing `realDispatcher.ts` default + a comment header with the date and sample size.
- One env var documented in `tools/scripts/run-stage2-generate.sh` header.

No design surface beyond the above. Implementation = measure + tune.

---

## §3 — Catalog Selector Leakage (D15/D21)

### Problem

`flowchart.html` (catalog block) uses 22 attribute selectors `[data-composition-id="flowchart"]` instead of `#flowchart`. When HF renders the parent composition, *something* causes those selectors to match cross-document during the render pass — D21 fixed it manually for the current episode by rewriting all 22 selectors to `#flowchart`. Without a systematic fix, every new vertical episode using `flowchart` re-incurs this manual patch, and every other catalog block with the same anti-pattern will leak similarly.

### Root cause (confirmed via `dist/docs/compositions.md`)

- HF supports proper isolation via `data-composition-src` (nested compositions, separate documents).
- Our composer (`tools/compositor/src/composer.ts:62-102`) already uses `data-composition-src` for both seam scenes and catalog blocks. **We are not the bug.**
- The catalog block's CSS/JS uses **attribute selectors that work when the block renders standalone but conflict under nesting/inlining**. The block was authored for solo preview, not for embed.
- The right fix is at the source: catalog block authoring conventions, with a lint rule enforcing them.

### Decision: A + B (both upstream, no local shim)

**A. Open issue against the `hyperframes` catalog repo:**

- Title: "Catalog block `flowchart` uses attribute selectors that conflict with nested composition reuse"
- Body: minimal repro using two instances; show that `[data-composition-id="flowchart"]` in CSS scope rules is unsafe; recommend `#flowchart` or class-scoped selectors for any rule meant to apply *only* inside the block.
- Audit other catalog blocks (`yt-lower-third`, etc.) for the same anti-pattern, list them in the issue.

**B. Feature request to `hyperframes lint`:**

- New rule: warn when a catalog block's CSS/HTML contains `[data-composition-id="<own-id>"]` selectors. Suggest `#<own-id>`.
- Cite real-world case (D21) in the issue rationale.

**No local shim.** Per HF-native methodology (`feedback_hyperframes_native.md`): we do not maintain a parallel rewriter for catalog HTML. If upstream is slow, we accept manual D21-style patches per affected episode and track them in `state.fixesApplied` until upstream lands. This is honest and methodologically clean.

### Deliverable

- Two GitHub issues opened against `heygen-com/hyperframes`:
  - Issue 1 (selector isolation gap): https://github.com/heygen-com/hyperframes/issues/556
  - Issue 2 (lint rule): https://github.com/heygen-com/hyperframes/issues/557
- A note in `docs/operations/planner-pipeline-fixes/findings.md` linking to both issues, replacing the current "consider a composer-side rewrite" line.

No code changes in our repo for §3.

---

## §4 — Flowchart Aspect Ratio Mismatch

### Problem

Catalog `flowchart.html` is authored at 1920×1080. Vertical episodes (1440×2560) render it letterboxed-or-stretched. Visually wrong for portrait episodes.

### Decision

Stop using the landscape `flowchart` block in vertical episodes. Two follow-up paths, **either** is acceptable:

- **Path A (preferred if catalog accepts contributions):** open an issue against the catalog repo for a portrait variant `flowchart-vertical.html` at 1440×2560. If accepted, add it to our planner's allowed catalog set for vertical episodes only.
- **Path B (immediate):** for vertical episodes, do not list `flowchart` as an allowed catalog reference in the planner's prompt. The planner will fall through to a `generative` scene if the beat needs a flowchart-like graphic.

Either path leaves us methodologically clean: we do not author a parallel `flowchart-vertical.html` in our own repo (would be a parallel manifest).

### Deliverable

- One issue against the catalog repo proposing the portrait variant (Path A): https://github.com/heygen-com/hyperframes/issues/558
- One commit removing `flowchart` from the planner's allowed-catalog list when target dimensions are portrait (Path B as immediate mitigation).

### Touched files

- `tools/compositor/src/planner/prompts/generative.md` (or wherever the catalog allowlist is expressed) — gate `flowchart` on landscape only.

---

## §5 — Sequencing & Scope Discipline

**Order:**

1. §0 (HF audit, narrow) — runs first, may amend §1.
2. §1 (D19) — largest design surface; unblocks safe iteration on everything else.
3. §2 (D3) — depends on §1 (uses `generate.manifest.json` to harvest wallclocks).
4. §3 (catalog leakage) — independent, can be done in parallel with §2 if helpful (no code conflict).
5. §4 (flowchart) — independent, smallest, last.

**Out of scope for this spec:**

- Gated PROMOTE items (D1, D6, D7, D10, D18) — wait for macro-retro session.
- Cosmetic preview tuning — unblocked once §1–§4 land.
- Full pipeline-wide HF reinvention audit — covered in §6 below.

---

## §6 — Companion Spec: Full HF Reinvention Audit

This spec only includes a **narrow** audit (§0) targeted at §1–§4. The user's broader question — "what else are we reinventing?" — deserves its own spec because:

- Scope is large: every `tools/scripts/*.sh`, every module under `tools/compositor/src/`, every file under `standards/`, every wrapper around HF, every prompt template.
- Deliverable is a findings document + N follow-up tickets, not a single-feature design.
- Risk of scope-creep into the present spec is high; bundling delays §1.

**Action:** create `docs/superpowers/specs/2026-04-29-hf-reinvention-audit-design.md` as a separate spec **after** §1 lands. That spec will define method, scope, and stop conditions for the broader audit.

---

## Acceptance criteria for this spec as a whole

- [ ] §0 findings block populated with answers to all four questions.
- [ ] `episode-state` CLI installed, with at least one episode (the current 2026-04-29 episode) carrying a valid `state.json` after a clean rerun.
- [ ] `realDispatcher.ts` default timeout rederived from real measurements; comment header updated.
- [ ] Two upstream issues opened (catalog selectors, lint rule) with URLs recorded in this spec.
- [ ] One catalog issue opened (portrait flowchart variant) and planner prompt gated on landscape for `flowchart`.
- [ ] Companion audit spec (§6) drafted and committed.

End of design.
