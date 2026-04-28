# Phase 6a HF-alignment audit (2026-04-28)

Session-end audit of how the Phase 6a implementation diverges from HyperFrames' authoring methodology and CLI surface. Not a plan; an input for the next session deciding **wipe-and-rebuild-on-HF vs. fix-individual-points**.

## Context

- Phase 6a closed at tag `phase-6a-hf-native-foundation` (commit `c6e481a`).
- Smoke render produced `episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/preview.mp4` (33.7 MB, draft, 30 fps) — wiring proven end-to-end.
- HF skills vendored at `tools/hyperframes-skills/` (v0.4.31). Audit cross-references `tools/hyperframes-skills/hyperframes/SKILL.md`, `references/captions.md`, `hyperframes-cli/SKILL.md`.
- Phase 6a plan was written treating HF as a "render+lint engine"; HF is in fact a full authoring methodology (HTML-as-source-of-truth, mandated authoring rules, reference docs that are authoritative). Methodology layer was largely ignored.

## Confirmed divergences (high confidence — verified against vendored docs)

### 1. Captions implementation contradicts `references/captions.md`

`tools/compositor/src/captionsComposition.ts` produces `compositions/captions.html` with:
- per-word `tl.set` className toggle on a single `.caption-row` containing all words
- no word grouping
- no `tl.set(groupEl, {opacity:0, visibility:"hidden"}, group.end)` exit guarantee
- no use of `window.__hyperframes.fitTextFontSize()` for overflow control
- no self-lint timeline traversal

HF `references/captions.md` mandates: word grouping (2–3 / 3–5 / 4–6 words depending on energy, one group visible at a time), per-group hard kill at `group.end`, `fitTextFontSize` for sizing to canvas, post-build self-lint sweep. The 770 contrast warnings and 8 text_box_overflow errors from `hyperframes validate`/`inspect` are symptoms of this divergence, not validator artifacts.

The irony: Task 3 added a pointer to `references/captions.md` from `standards/captions.md` ("read both files together"), then Task 5 wrote captionsComposition.ts ignoring it.

### 2. No scene transitions — direct violation of HF non-negotiable rule

`tools/compositor/src/composer.ts` emits per-seam sub-compositions as adjacent `data-composition-src` clips with no transition between them. SKILL.md (line 228, "Scene Transitions (Non-Negotiable)"): "ALWAYS use transitions between scenes. No jump cuts. No exceptions." Our seams are jump cuts. The synthetic Phase 6a smoke fixture (seam 4 plate) appears and disappears with hard cuts to neighbouring talking-head seams.

HF provides `references/transitions.md` + `references/transitions/catalog.md` + `references/transitions/css-*.md` (12 categories) for selecting transitions by energy/mood. Unused.

### 3. Inspect overflow handled by weakening the gate, not by HF's escape hatch

`tools/scripts/run-stage2-compose.sh` was changed from `inspect || exit 1` to `inspect || echo WARN`. HF provides `data-layout-allow-overflow` (mark intentional entrance/exit overflow) and `data-layout-ignore` (mark decorative elements never to audit). Correct fix is to mark the affected elements; current fix masks the diagnostic.

## Likely-correct-but-not-yet-proven points (need verification)

### 4. `npx hyperframes init` — never invoked

Could provide canonical scaffolding + Whisper transcription + per-project skills install. Verify by `npx hyperframes init test-scaffold --non-interactive` and diffing against our `episodes/<slug>/stage-2-composite/` structure. May or may not be a meaningful gap.

### 5. `npx hyperframes preview` — never invoked

Hot-reload studio at `localhost:3002`. Phase 6b agent retry-loop is currently render-based (minutes per iteration); preview-based iteration would be near-instant. Confirm actual page-load behaviour and whether headless agent can drive it.

### 6. `npx hyperframes doctor` — never invoked

Checks Chrome / FFmpeg / Node / **memory**. Likely would have flagged the host's RAM pressure before the smoke render wedged Windows. Cheap to add as preflight in `run-stage2-compose.sh`.

### 7. `npx hyperframes transcribe` vs our Stage 1 transcript

Stage 1 produces `episodes/<slug>/stage-1-cut/transcript.json` with shape `{words: [{text, startMs, endMs}]}`. HF transcribe accepts SRT/VTT/openai-response.json, presumably emits HF's expected `[{text, start, end}]`. Verify whether formats can be unified to drop our translation layer.

### 8. `npx hyperframes upgrade` vs our `tools/scripts/check-updates.sh`

Per `standards/retro-changelog.md` (2026-04-27 entry), check-updates.sh runs `npm view hyperframes version` against installed. HF's upgrade does the same. Likely duplicate.

### 9. `npx hyperframes compositions` vs our seam-file discovery

Our `tools/compositor/src/index.ts` (compose branch) walks `compositions/seam-*.html` via `existsSync`. HF has a built-in listing command. Minor; could simplify the compose step.

### 10. `--strict` / `--strict-all` on render

HF render flags can fail on lint errors / lint warnings. Could replace some of the orchestration in `run-stage2-compose.sh` (lint+validate as pre-render gate), shrinking the script.

### 11. Skills installed by `init` (per-project) vs vendored at repo-root

`init` "installs AI coding skills" — likely into a per-project `.hyperframes/` or similar. We vendor at `tools/hyperframes-skills/` (repo-root). Both layers may have legitimate purpose (repo-root for cross-episode coordination subagents; per-project for authoring agents). Need to verify what `init` actually does before deciding on consolidation.

## Confirmed correct

- **DESIGN.md is HF-native.** SKILL.md "Visual Identity Gate" lists DESIGN.md FIRST in the lookup order ahead of `visual-style.md`. Our four-section file (`Style Prompt` / `Colors` / `Typography` / `What NOT to Do`) matches the minimal schema HF prescribes. Our addition — fenced `hyperframes-tokens` JSON block — is a project-specific machine-parseable extension; not in conflict.
- **Compositor track-index discipline** (video=0, captions=1, audio=2, seams=3+) — passes the test "distinct track indexes per layered element" and aligns with HF's "same-track clips cannot overlap" data-attribute semantics.
- **Sub-composition structure** (`<template>` wrapper, scoped styles, `window.__timelines["<id>"] = tl` registration) — matches SKILL.md "Composition Structure" verbatim.
- **HF skills vendoring infra** (`tools/scripts/sync-hf-skills.sh` + tarball-based pull) — sound regardless of whether `init` would also install per-project copies.

## Operational issue surfaced (not a methodology divergence)

`hyperframes render` against 1440x2560 wedged Windows during smoke runs. Workaround: `--workers 1 --max-concurrent-renders 1 -q draft` — works but soft. Architecturally correct fix: `--docker` (cgroup hard memory cap, deterministic toolchain). Already noted in `feedback_long_running_renders.md` memory.

## The wipe-vs-incremental decision

Strategic context for the call:

**Arguments for incremental fix (Phase 6a-aftermath):**
- Tests stay green throughout, no blast radius.
- DESIGN.md, vendoring, sub-composition wiring, track discipline are all correct and don't need redo.
- Captions and transitions are localised: rewrite captionsComposition.ts and add transition emission to composer.ts. Touches `tools/compositor/src/`, leaves the rest.
- `init` / `preview` / `doctor` adoption is purely additive — no existing code to remove.

**Arguments for wipe-and-rebuild on `npx hyperframes init`:**
- Forces HF methodology adoption from the ground up; no chance of carrying over divergent patterns by inertia.
- Project layout would be exactly what HF expects, not a layout that *also passes* HF lint.
- Phase 6b agentic planner has cleaner foundation; less surface for "it works because of our compositor's quirks" failures.
- Sunk cost is small in absolute terms (Phase 6a was ~9 commits); the bespoke compositor logic worth preserving (DESIGN.md parser, seam-plan generator, Stage 1↔Stage 2 contract) can be ported across in hours.

**Hybrid:** scaffold a fresh `episodes/<slug>` via `npx hyperframes init`, port our compositor's value-adding pieces (DESIGN.md parser, seam-plan, sub-composition wiring) into the HF-init layout, drop everything else. Less destructive than full wipe; more invasive than fix-in-place.

The decision should be informed by:
- What `npx hyperframes init` actually outputs (run it once and inspect).
- Whether our seam-plan abstraction has a 1:1 HF equivalent we missed.
- Phase 6b's planned agent architecture — if it depends on HF-canonical layout features we don't have, wipe wins; if it sits cleanly on top of what we have plus the captions/transitions fixes, incremental wins.

## Recommended next-session entry point

1. Run `npx hyperframes init test-scaffold --non-interactive --example blank` in a tmp dir; tree-diff against `episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/`.
2. Run `npx hyperframes doctor` against the host once.
3. Read `references/transitions.md` end-to-end (was vendored but not consulted during Phase 6a authoring).
4. Decide: full wipe / hybrid / incremental fix.
5. If incremental: open Phase 6a-aftermath spec covering points 1, 2, 3, plus Docker render mode (item 6a-1 noted in retro).
