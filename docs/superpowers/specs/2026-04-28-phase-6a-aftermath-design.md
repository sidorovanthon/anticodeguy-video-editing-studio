# Phase 6a-aftermath — HF-alignment fixes (design)

**Status:** approved design, ready for implementation plan.
**Date:** 2026-04-28
**Predecessor:** Phase 6a closed at tag `phase-6a-hf-native-foundation` (commit `c6e481a`).
**Audit input:** `docs/superpowers/notes/2026-04-28-phase-6a-hf-alignment-audit.md`.
**Sequel:** Phase 6b — agentic graphics planner (unchanged scope).

## Goal

Resolve the three confirmed HF-methodology divergences surfaced in the post-6a audit, plus add the operational guardrails that would have prevented the smoke-render wedge. After this phase, Stage 2 output complies with HyperFrames' non-negotiable authoring rules (captions, transitions, inspect gate) and renders deterministically inside Docker without wedging the host. No new graphics, no agentic planner, no architectural changes — fixes localised to two compositor files and one orchestration script.

## Non-goals

The following adoption points from the audit are deferred — they are additive, none blocks 6b, and bundling them dilutes scope:

- `npx hyperframes preview` (hot-reload studio for 6b agent iteration).
- `npx hyperframes transcribe` vs. our Stage 1 transcript.
- `npx hyperframes upgrade` vs. `tools/scripts/check-updates.sh`.
- `npx hyperframes compositions` vs. seam-file discovery.
- `--strict` / `--strict-all` render flags.
- Per-project skills installed by `init` vs. our repo-root vendoring.

Not in scope either: revisiting the wipe-vs-rebuild question (decided: incremental — `hyperframes init` scaffolds a single-composition project, not our episode pipeline; the layer above HF is correct and stays).

All findings from the independent HF-vs-architecture audit are folded into this phase. Nothing is deferred. The list is closed; if a new item surfaces during implementation, raise it explicitly rather than letting it slide.

## Acceptance

Running `tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test` followed by `tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test` produces `preview.mp4` such that:

1. **Captions** in `compositions/captions.html` are word-grouped per `tools/hyperframes-skills/hyperframes/references/captions.md`. One group is visible at a time. Each group has an explicit `tl.set(groupEl, {opacity:0, visibility:"hidden"}, group.end)` exit. Per-group sizing is set via `window.__hyperframes.fitTextFontSize()` so groups don't overflow the canvas. A self-lint sweep (timeline traversal) runs at the end of the captions sub-composition's `<script>`; failures throw before render.
2. **Transitions** are emitted between every seam. The composition uses one primary CSS transition + at most two accents, picked from `references/transitions.md`. No two adjacent seams are jump-cut. The final seam is allowed to end on a fade-out; no other seam carries an exit animation.
3. **Inspect gate** in `tools/scripts/run-stage2-compose.sh` is restored to `npx hyperframes inspect <dir> || exit 1`. Any element that genuinely needs entrance/exit overflow is annotated in source with `data-layout-allow-overflow`. Decorative elements that should be skipped entirely carry `data-layout-ignore`. The smoke-test fixture passes `inspect` strictly.
4. **Doctor preflight** runs at the head of `run-stage2-compose.sh` (`npx hyperframes doctor`). Failure on any critical check (Node, FFmpeg, Chrome) aborts the script. Docker-not-found is downgraded to a warning when render mode ≠ docker.
5. **Docker render** is the default on `run-stage2-preview.sh` (and `render-final.sh` if it shells render): pass `--docker` to `npx hyperframes render`. The synthetic 1440×2560 smoke render completes without wedging the host. An env override (`HF_RENDER_MODE=local`) bypasses Docker for users without it.
6. `npx hyperframes lint`, `validate`, `inspect`, `animation-map` are all green on the smoke-test episode. Caption contrast warnings and `text_box_overflow` errors from the pre-fix run are absent.
7. **All seams ride a single `data-track-index` value (3).** No track-laddering. `animation-map` shows seams stacked on one track with no overlap.
8. **No `var(...)` references on captured elements.** Grepping the emitted `index.html` + `compositions/*.html` for `var(--` matches only declarations inside `<style>` blocks meant for documentation, not inside element `style="..."` attributes or class rules consumed by html2canvas.
9. **`standards/motion-graphics.md` carries a "Layout Before Animation" section and a "Scene phases" section**, each linking into the vendored HF skill (`tools/hyperframes-skills/hyperframes/SKILL.md` and `references/motion-principles.md` respectively).
10. **`DESIGN.md` "What NOT to Do" lists the shader-compat anti-patterns** verbatim from `references/transitions.md` §"Shader-Compatible CSS Rules".
11. **`standards/typography.md` exists** with the weight-contrast / tracking / dark-bg compensation rules; DESIGN.md `Typography` section carries an explicit one-line rationale for the Inter override.
12. **`DESIGN.md` `Colors` section names a base palette** from `tools/hyperframes-skills/hyperframes/palettes/` (or explicitly declares "no base — fully custom") and lists deviations as a bullet list.
13. **`standards/bespoke-seams.md` exists** and names `window.__hyperframes.fitTextFontSize` as the canonical overflow primitive, with the captions sub-composition cited as the reference example.
14. **Each `episodes/<slug>/stage-2-composite/` carries `hyperframes.json` and `meta.json`** at the root, emitted by the compositor. The smoke-test fixture is updated to include them.

The pilot `episodes/2026-04-27-desktop-software-licensing-it-turns-out/` remains FROZEN. All acceptance is run against the smoke-test fixture.

## Architecture decisions (locked)

Settle these now; do not relitigate during implementation.

1. **Captions: word-grouped per HF spec, energy = "medium" by default.** Grouping uses 3–5 words/group as the medium-energy default. Group boundaries snap to natural pauses where word `endMs - nextWord.startMs > 120ms`; otherwise they fall on the 5-word cap. Each group is an `<div class="caption-group" data-group-id="g{i}">` with `<span>` per word; the timeline animates `groupEl` (not individual words) for entrance, hard-kills at `group.end`. Per-word highlight is **out of scope** for this phase — the reference's "current word" emphasis is a 6b enhancement.
2. **Transition selection: project-level, one primary.** A new optional field in `DESIGN.md`'s fenced JSON, `"transition": { "primary": "blur-crossfade", "duration": 0.5, "easing": "sine.inOut" }`, names the canonical transition for the channel. The compositor emits this transition at every seam boundary. If absent, the compositor defaults to `crossfade` / 0.4s / `power2.inOut`. Energy-driven per-seam selection (different transitions for topic-change vs. wind-down) is deferred to 6b — that requires seam-plan metadata we don't yet emit.
3. **Transition implementation: CSS, not shader.** The smoke-test stays CSS-only; shader transitions (which require all transitions in the comp to be shader and impose `data-no-capture` rules) are a larger change deferred to a later phase if/when needed.
4. **Inspect annotations live in source.** Bespoke seam sub-compositions and `captions.html` carry `data-layout-allow-overflow` / `data-layout-ignore` directly where intentional overflow occurs. The orchestration script does not whitelist; it runs strict `inspect` and exits on any unannotated overflow.
5. **Docker is the default render mode; doctor preflight is mandatory.** The orchestration scripts assume Docker by default. Users without Docker set `HF_RENDER_MODE=local` and accept the workload-specific tuning (`--workers 1 --max-concurrent-renders 1 -q draft`) the script applies in that branch. `doctor` is mandatory at the head of compose; failure of Node/FFmpeg/Chrome is fatal, Docker-missing is fatal only when `HF_RENDER_MODE != local`.
6. **Single-track seam emission.** Seams tile the master timeline non-overlapping. Per HF SKILL.md "Data Attributes" (`data-track-index` does not affect visual layering — use CSS `z-index`) and `patterns.md` slide-show pattern, all per-seam compositions ride one track (track index `3`, after video=0/captions=1/audio=2). The previous track-laddering scheme in `composer.ts` is removed. Z-stacking, if ever needed, is via CSS `z-index`, not track index.
7. **Compositor inlines literal hex on captured elements.** `references/transitions.md` shader-compat rule explicitly forbids `var()` on elements visible during capture (html2canvas does not reliably resolve custom properties). The compositor resolves all DESIGN.md token references to literal hex/RGBA strings at compose time and emits literal values into element styles. `:root { --... }` declarations may remain in the head as documentation/fallback, but no captured element references them via `var()`. This is forward-protection for 6b's eventual shader-transition adoption — it is cheaper to do once now than to audit every bespoke seam later.
8. **Methodology rules propagated into `standards/motion-graphics.md`.** Two HF-native gates currently absent from our standards become mandatory authoring rules for any sub-composition (captions, transitions, future bespoke seam plates):
   - **Layout Before Animation** (per SKILL.md §"Layout Before Animation"): position elements at their hero-frame in static CSS first, then animate *toward* that position with `gsap.from()`. Never use `position:absolute; top:Npx` on content containers as a layout primitive.
   - **Scene phases** (per `references/motion-principles.md`): every multi-second scene allocates ~0–30% to entrance, ~30–70% to ambient breathe, ~70–100% to resolve. Seams must not dump all motion at t=0 and hold.
   These are codified in `standards/motion-graphics.md` with anchor links into the vendored skills, so 6b agents have a single canonical entry point.
9. **Shader-compat CSS rules pre-codified in `DESIGN.md` "What NOT to Do".** Even though shader transitions are deferred (decision 3), the rules from `references/transitions.md` §"Shader-Compatible CSS Rules" (no `transparent` keyword in gradients, no gradients on <4px elements, no `var()` on captured elements, mark uncapturable elements with `data-no-capture`, no gradient opacity below 0.15, every `.scene` div carries explicit `background-color` matching `init({bgColor})`) are recorded now as anti-patterns. Bespoke seams authored in 6b will already comply by default.
10. **Typography compensation rules adopted into `standards/typography.md`.** Drawn from `tools/hyperframes-skills/hyperframes/references/typography.md`: weight-contrast pairs (300 vs 900 for display vs body), tracking guidance for display sizes (−0.03 to −0.05em), and dark-background weight compensation (bump body/caption weights one step on dark surfaces — captions on talking-head footage are dark-on-dark by default, so this is load-bearing for legibility). The DESIGN.md `Typography` section explicitly overrides HF's banned-fonts list (Inter is HF-banned but our channel font); the override is now documented with a one-line rationale instead of being a silent contradiction.
11. **Named-palette discipline.** DESIGN.md's color section names a base palette from `tools/hyperframes-skills/hyperframes/palettes/*.md` (or explicitly states "custom palette, no derivative") and lists deviations explicitly. This gives 6b agents a reasoning surface — "we're a `frosted-cool` derivative, with these specific overrides" — instead of a free-form palette they can't relate to HF's catalog.
12. **`fitTextFontSize` formalised as the project-wide overflow primitive.** A new section `standards/bespoke-seams.md` (authoring guide for 6b graphics agents) names `window.__hyperframes.fitTextFontSize` as the canonical answer for any dynamic-content text overflow — captions, lower-thirds, name plates, overlay headers, future bespoke seams. Per-comp clamps, `text-overflow: ellipsis`, and manual font-size juggling are anti-patterns. The captions implementation (decision 1) becomes the reference example.
13. **HF-canonical project files scaffolded per episode.** `episodes/<slug>/stage-2-composite/` will carry `hyperframes.json` (paths config matching our layout: `{ "blocks": "compositions", "components": "compositions/components", "assets": "assets" }`) and `meta.json` (`{ "id": "<slug>", "name": "<slug>", "createdAt": "<iso>" }`) emitted by the compositor. Currently absent — `init`'s scaffold has them, our hand-rolled output skips them. Closing this is what the wipe-vs-rebuild question came down to once everything else is fixed; doing it directly is cheaper than the wipe.

## HF upgrade strategy

This phase closes a real gap: the version of `hyperframes` resolved at runtime can drift away from the version of skills vendored at `tools/hyperframes-skills/`. The contract surface we depend on (CLI flags + their output formats, DOM data-attributes, runtime `window.__hyperframes.*` APIs, JSON schemas, and — critically — the methodology rules in SKILL.md / references) changes across HF releases. Drift means green tests with broken methodology. The transitions non-negotiable that Phase 6a missed is exactly that failure mode.

### Locked decisions

1. **Exact-version pin, no caret.** `tools/compositor/package.json` carries `"hyperframes": "0.4.31"` (no `^`, no `~`). One source of truth. CLI invoked via `npx hyperframes` resolves from `node_modules`, deterministic.
2. **Skills sync from the pinned version, not from npm latest.** `tools/scripts/sync-hf-skills.sh` reads the version out of `tools/compositor/package.json` and pulls that exact tarball. The previous behaviour (`npm view hyperframes version`) is removed — it caused CLI/skills version skew.
3. **`tools/hyperframes-skills/VERSION` always equals the pinned package.json version.** A pre-commit or CI check asserts this; out-of-sync state is a hard failure.
4. **Upgrade is a documented procedure, not an ad-hoc bump.** A single PR carries: package.json bump, `npm install` lockfile update, `sync-hf-skills.sh` re-run, the smoke-test pass, and a short note on any methodology changes spotted in the skills diff. No part can be split across PRs.
5. **Smoke-test fixture is the upgrade gate.** `episodes/2026-04-28-phase-6a-smoke-test/` already exercises captions, transitions, seam wiring, and Docker render. Every HF bump must pass it before merge. No exceptions.
6. **Contract surface is registered in one document.** Future audits and upgrade reviews check changes in HF's CHANGELOG against this single list, not against scattered grep hits.

### Upgrade procedure (documented in `docs/hyperframes-upgrade.md`)

1. Bump `tools/compositor/package.json` `"hyperframes"` to the new exact version. Run `npm install` in `tools/compositor/` to refresh the lockfile.
2. Run `tools/scripts/sync-hf-skills.sh`. The script reads the new pinned version from `package.json` and refreshes `tools/hyperframes-skills/` + `VERSION` to match.
3. `git diff tools/hyperframes-skills/` — read the full diff. Particular attention: `SKILL.md` "non-negotiable" sections, new files under `references/`, removed APIs, deprecated patterns. Capture findings in the PR description.
4. `npx hyperframes doctor` against the local host. All critical checks must pass.
5. `tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test` and `run-stage2-preview.sh` — both must exit 0 with `lint`/`validate`/`inspect`/`animation-map` green and `preview.mp4` rendering. If anything regresses, fix in the same PR or revert the bump.
6. PR with the title `chore(hf): upgrade to <version>`, body summarising methodology changes from step 3.

Cadence is operator-driven; an opt-in `/schedule`-able background agent that opens upgrade PRs weekly is a follow-up after this phase.

### Contract surface registered in `docs/hyperframes-integration.md`

Single living document, updated whenever we adopt a new HF surface:

- **CLI commands and parsed flags / output formats**: `lint`, `validate`, `inspect`, `animation-map`, `render` (incl. `--docker`, `--workers`, `--max-concurrent-renders`, `-q`), `doctor`.
- **DOM data-attributes**: `data-composition-id`, `data-start`, `data-duration`, `data-width`, `data-height`, `data-track-index`, `data-composition-src`, `data-layout-allow-overflow`, `data-layout-ignore`, `data-no-capture`.
- **Runtime globals**: `window.__timelines["<id>"]`, `window.__hyperframes.fitTextFontSize` (and any future `window.__hyperframes.*` we adopt).
- **JSON schemas**: `hyperframes.json` paths config, `meta.json` shape.
- **Methodology rules from SKILL.md** (paraphrased pointers to source): Visual Identity Gate ordering, Composition Structure (template + scoped styles + timeline registration), Scene Transitions Non-Negotiable, Captions authoring rules, animation entrance/exit policy.

The document is the diff target during step 3 of the upgrade procedure: changes to anything in this list are a methodology event, not a routine bump.

## Artifacts

### Created

- `episodes/<slug>/stage-2-composite/compositions/transitions.html` — sub-composition emitting the project's primary transition between adjacent seams. (The composer references it from `index.html`; transitions are NOT inlined into each seam.)
- `tools/compositor/src/transitionsComposition.ts` — generator for the above, parameterised by `DESIGN.md`'s `transition` block.
- `tools/scripts/lib/preflight.sh` — small shared script that runs `hyperframes doctor`, parses pass/fail, and exits non-zero on critical failures. Sourced by `run-stage2-compose.sh` and `run-stage2-preview.sh`.
- `docs/hyperframes-upgrade.md` — the upgrade procedure documented in the section above.
- `docs/hyperframes-integration.md` — the contract surface registry described above.
- `standards/typography.md` — weight-contrast / tracking / dark-bg compensation rules drawn from `references/typography.md`, plus the documented Inter override rationale for our channel.
- `standards/bespoke-seams.md` — authoring guide for 6b graphics subagents. Names `fitTextFontSize` as the project-wide overflow primitive, links into HF SKILL.md for Layout-Before-Animation and motion-principles for scene phases, and lists the shader-compat rules.
- `episodes/<slug>/stage-2-composite/hyperframes.json` — emitted by the compositor; paths config mapping to our layout (`compositions/`, `compositions/components/`, `assets/`).
- `episodes/<slug>/stage-2-composite/meta.json` — emitted by the compositor; `{id, name, createdAt}` per HF init's schema.

### Modified

- `tools/compositor/src/captionsComposition.ts` — rewritten per decision 1: group words, animate group containers (not individual words), `tl.set` exit at `group.end`, call `fitTextFontSize`, append a self-lint timeline sweep.
- `tools/compositor/src/composer.ts` — emit transitions between seams via the new transitions sub-composition; remove jump-cut adjacency.
- `tools/compositor/src/designParser.ts` (or the existing DESIGN.md parser) — read the optional `transition` block from the fenced `hyperframes-tokens` JSON; pass through to the transitions generator.
- `tools/scripts/run-stage2-compose.sh` — source `lib/preflight.sh` at the top; restore `inspect || exit 1`; remove the `WARN`-only branch.
- `tools/scripts/run-stage2-preview.sh` — source `lib/preflight.sh`; switch render to `--docker` by default; honour `HF_RENDER_MODE=local` to fall back to the current `--workers 1 --max-concurrent-renders 1 -q draft` workaround.
- `tools/scripts/render-final.sh` — same Docker-by-default switch (final renders are the most memory-hungry; this is where Docker matters most).
- `tools/compositor/package.json` — pin `"hyperframes": "0.4.31"` exactly (drop the caret).
- `tools/scripts/sync-hf-skills.sh` — read pinned version from `tools/compositor/package.json`; remove the `npm view hyperframes version` call.
- `tools/scripts/check-updates.sh` — keep the notice for hyperframes drift but also flag CLI/skills version mismatch (`package.json` pin ≠ `tools/hyperframes-skills/VERSION`).
- `tools/compositor/src/composer.ts` (further) — drop the `TRACK_SEAM_BASE + i` laddering; emit all seams at a single track index (`3`).
- `tools/compositor/src/designMd.ts` (or designParser equivalent) — extend the parser to expose a `resolveToken(name)` API that returns literal hex/RGBA. Compositor + caption + transition generators call this when emitting element styles; `var()` references are no longer written into captured elements.
- `tools/compositor/src/captionsComposition.ts` (further) — adopt GSAP `autoAlpha` for the per-group hard-kill (replaces the two-call `tl.to({opacity:0}) + tl.set({opacity:0, visibility:"hidden"})` pattern with a single `tl.set({autoAlpha:0})` at `group.end`).
- `standards/motion-graphics.md` — add "Layout Before Animation" and "Scene phases (build / breathe / resolve)" sections, each linking into the vendored HF skill source.
- `DESIGN.md` — extend "What NOT to Do" with the shader-compat CSS anti-patterns from `references/transitions.md` (literal-color rule, no-thin-gradient rule, no-var-on-captured rule, `data-no-capture` directive, gradient-opacity floor, scene background-color rule). Extend `Colors` section with the base-palette declaration. Extend `Typography` section with the Inter-override rationale.
- `tools/compositor/src/index.ts` (compose entrypoint) — emit `hyperframes.json` and `meta.json` into the episode's `stage-2-composite/` alongside `index.html`. Both files are deterministic from episode metadata; no new state.
- `DESIGN.md` (repo root) — extend the fenced `hyperframes-tokens` JSON with the optional `transition` field documented in decision 2. Add a `## Transitions` prose section above it explaining the rationale for the chosen primary.
- `episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/compositions/seam-4.html` — add `data-layout-allow-overflow` on the entrance-animated text element if `inspect` flags it once the gate is re-strict.

### Deleted

- The `inspect || echo WARN` branch in `run-stage2-compose.sh`. No new files, no rename of existing ones.
- `tools/scripts/run-stage2.sh` — thin wrapper around `run-stage2-compose.sh` + `run-stage2-preview.sh`. Sole caller (`test-run-stage2.sh`) is broken anyway (asserts the obsolete `composition.html` path); fix the test to invoke the underlying scripts directly with doctor preflight, then delete this wrapper.
- `.gitignore` line `episodes/*/stage-2-composite/hf-project/` — the staging dir was removed in 6a; rule has no future producer.

### Pre-HF rudiment cleanup (rolled into this phase)

Surfaced by an independent rudiments audit. All edits are mechanical and contained:

- `AGENTS.md` pipeline-overview line still mentions building `composition.html` — rename to `index.html`. Add a one-line note that the FROZEN pilot `episodes/2026-04-27-desktop-software-licensing-it-turns-out/` predates 6a and its `stage-2-composite/` layout (`composition.html`, `hf-project/`) is non-canonical; do not use it as a reference.
- `standards/pipeline-contracts.md` carries the same FROZEN-pilot note.
- `standards/captions.md` references `tokens.color.caption.active`, `tokens.safezone.bottom`, `tokens.type.family.caption` — token namespace deleted in 6a. Rewrite to DESIGN.md `hyperframes-tokens` keys (`color.<role>`, `type.family.*`); add an explicit `safezone` group to DESIGN.md (currently no equivalent), or drop the reference.
- `standards/motion-graphics.md` references `tokens.color.glass.fill`, `tokens.blur.*`, `tokens.radius.*`, `tokens.spacing.md` — same namespace rot. Rewrite to DESIGN.md keys.
- `design-system/README.md` still claims `tokens/tokens.json` is "the single source of truth" and contradicts itself in a "Phase 6a state" note. Rewrite to lead with the 6a state: DESIGN.md is the contract; `design-system/components/` is the 6b layout-shell home (currently empty).
- `tools/scripts/test/test-run-stage2.sh` asserts `[ -f .../composition.html ]` — fix to `index.html`. The test was silently broken since 6a; the fix re-arms it.
- `tools/compositor/src/types.ts` carries `Seam.graphic?: { component, data }` field; `seamPlanWriter.ts` round-trips `graphic:` lines that no compositor reads (file-existence is the trigger). Keep both — Phase 6b will resurrect the field for catalog/bespoke selection — but mark with a `// TODO(6b): consumed by graphics planner; currently round-trip only` comment so the dead-looking code doesn't get removed by an over-eager cleanup pass.
- `tools/compositor/src/sceneMode.ts` rejects the legacy `full` scene-mode name — keep, costs nothing, but add a `// transitional shim — remove once pilot is unfrozen and re-cut on 6a-aftermath` comment.
- `tools/scripts/check-updates.sh` upstream-version probe (`npm view hyperframes version`) is partly duplicated by `npx hyperframes upgrade --check`. With exact-pin in place (decision 1 of upgrade strategy), keep the probe but mark it as the trigger for the documented upgrade procedure; do not replace with `hyperframes upgrade` in this phase (premature surface adoption).

## Component contracts

### `captionsComposition.ts`

**Input:** `master/bundle.json` words `[{text, startMs, endMs}, ...]`, plus design tokens for color/typography.
**Output:** `compositions/captions.html` containing:
- `<template data-composition-id="captions" data-duration="<total-ms>">` wrapping the DOM.
- One `<div class="caption-group" data-group-id="g{i}">` per group; one `<span class="caption-word">` per word inside it.
- Scoped `<style>` using DESIGN.md tokens; explicit `background-color` on the canvas root.
- `<script>` that:
  1. Builds groups by walking words, breaking on `endMs - nextStartMs > 120ms` OR group word-count == 5.
  2. For each group, pushes `gsap.from(groupEl, {...entrance})` at `group.start` and `tl.set(groupEl, {opacity: 0, visibility: "hidden"}, group.end)` to hard-kill at end.
  3. Calls `window.__hyperframes.fitTextFontSize(groupEl, {maxFontSize: <token>, minFontSize: <token>})` per group on first show.
  4. Registers `window.__timelines["captions"] = tl`.
  5. Self-lint: walk `tl.getChildren()`, assert each group has both an entry and a hard-kill at the expected times; throw on mismatch.

**Failure modes:** if `bundle.json` has zero words, emit an empty `<template>` and no timeline (no `__timelines["captions"]` registration); composer must tolerate an absent captions timeline.

### `transitionsComposition.ts`

**Input:** seam list `[{id, startMs, endMs}, ...]` plus the design's `transition` block `{primary, duration, easing}`.
**Output:** `compositions/transitions.html` containing one `<template data-composition-id="transitions">` whose timeline emits the primary transition at each `seam[i].endMs` (= `seam[i+1].startMs`). The transition is implemented per `references/transitions/catalog.md` for the chosen primary (e.g., `blur-crossfade`: animate outgoing scene's `filter: blur()` + `opacity` while incoming animates in symmetrically).

**Failure modes:** if `seams.length < 2`, emit an empty timeline. If the primary name is unknown, throw at compose time with a list of valid transition names from the catalog.

### `composer.ts`

**Change:** in the loop that emits per-seam `data-composition-src` clips, also emit a single `<div data-composition-src="compositions/transitions.html" data-start="0" data-track-index="<seams+1>">` clip spanning the full episode duration. Sub-composition handles the per-seam transition events internally; composer doesn't loop them.

### `lib/preflight.sh`

**Behaviour:** runs `npx hyperframes doctor`; greps for `✗`. Distinguishes "Node / FFmpeg / Chrome" failures (always fatal) from "Docker / Docker running" failures (fatal only when `HF_RENDER_MODE != local`, default fatal). Echoes a one-line summary on success.

## Risks & mitigations

- **Risk: Docker-by-default breaks contributors without Docker installed.** Mitigation: `HF_RENDER_MODE=local` opt-out documented in `AGENTS.md` and the script's `--help`. The preflight prints the exact env-var hint when it aborts on Docker missing.
- **Risk: word-grouping heuristic produces awkward breaks (e.g., splits "United States" across groups).** Mitigation: the 120ms-pause heuristic is a starting point; if smoke-test output looks wrong, tune to 150–200ms or add a punctuation-aware break before tuning further. Acceptance is "no overflow / no contrast errors / one group at a time" — *visual* caption pacing polish is a 6b concern.
- **Risk: chosen transition (default `crossfade`) is inappropriate for the channel's "tense / edgy" mood.** Mitigation: the smoke-test is deliberately neutral content; the project-level `DESIGN.md` `transition.primary` is set per channel during 6b polish. 6a-aftermath ships with `crossfade` / 0.4s as a safe baseline.
- **Risk: re-strict `inspect` flags real overflow in existing bespoke seams.** Mitigation: phase the rollout — annotate each flagged element with `data-layout-allow-overflow` (or fix the layout) one at a time; gate the strict-mode flip on the smoke-test passing, not on a broader sweep.

## Verification plan

1. Unit / static: TypeScript build of `tools/compositor/` passes. `tools/scripts/sync-hf-skills.sh` re-run matches vendored version (no drift).
2. Smoke-test episode: `run-stage2-compose.sh` exits 0; `lint` / `validate` / `inspect` / `animation-map` all green; `compositions/captions.html` and `compositions/transitions.html` exist and self-lint; visual diff of `preview.mp4` shows: word-grouped captions, no jump cuts between seams, the synthetic "6A WIRING OK" plate still appears at seam 4 with a transition into and out of it.
3. Render mode: `run-stage2-preview.sh` with default (Docker) completes without wedging Windows; same script with `HF_RENDER_MODE=local` completes with the existing workaround knobs.
4. Doctor preflight: artificially break PATH (rename `ffmpeg`); compose script aborts at preflight with a clear error; restore PATH; resume.
5. Upgrade strategy dry-run: bump `tools/compositor/package.json` to a fake/non-existent `0.4.99` and re-run `sync-hf-skills.sh` — must fail clearly (tarball not found), not silently fall back to latest. Revert and bump to current latest (`0.4.32`); follow the documented procedure end-to-end; smoke-test must pass before merging the bump.
6. Captured-element grep: after a successful smoke-test compose, run a check that `compositions/*.html` and `index.html` contain no `var(--` inside `style="..."` attributes nor inside class declarations applied to `.scene` / `.caption-group` / seam-root elements. This is automatable as a one-liner in `run-stage2-compose.sh` post-emit.
7. Standards check: `standards/motion-graphics.md` contains the two new sections, each with a working anchor into `tools/hyperframes-skills/`.
