# Section 7 retro fixes — design

**Status:** draft, awaiting user review.
**Date:** 2026-05-01.
**Source retro:** [`docs/retros/retro-2026-05-01-section7-verification.md`](../../retros/retro-2026-05-01-section7-verification.md).
**Brainstorm transcript:** this session, ending with the canon audit that downgraded several retro-proposed fixes from "canon-mandated" to "orchestrator extension" or "rejected".

## Context

The Section 7 verification run uncovered nine findings on the orchestrator side and nine more from comparison with a clean HyperFrames executor session. The retro proposed a tier-1 fix list, but several proposals were framed as "canon-mandated" without verifying against live `SKILL.md` / `references/`. This spec walks each proposal through a canon audit and lands the corrected scope.

## Goals

1. Eliminate the studio-preview audio doubling that blocks delivery to the user.
2. Close the orchestrator-side canon-decay gaps (mandatory reading, Step 2 prompt expansion, catalog discovery, captions) that Phase 4 brief currently leaves to executor discretion.
3. Restore re-cut idempotency for `transcripts/final.json`.
4. Capture durable-feedback memory so future sessions don't re-litigate the same lessons.
5. File the upstream HyperFrames CLI issues that this orchestrator can't fix locally.

## Non-goals

- Patching upstream `video-use` or `hyperframes` source. Per `CLAUDE.md`, all glue lives in this orchestrator.
- LUFS-target tuning (retro §2.4) — observability note, not a fix.
- Re-litigating media placement (retro §3.9) — already canon-correct.
- Adding new QA tooling — our instrumentation already exceeds the clean-session baseline (retro §3.8); this is a win, not a backlog item.

## Canon audit summary

The brainstorm session's audit (HF `SKILL.md`, all `references/`, video-use `SKILL.md`, local cheatsheets in `docs/cheatsheets/`) reclassified each retro proposal:

| Proposal | Canon verdict | Adjustment |
|---|---|---|
| Audio scaffold patch (`data-has-audio="false"`) | 🆕 not in agent-facing canon, only in HF CLI docs (`packages/cli/src/docs/data-attributes.md`) | Frame as orchestrator extension filling a documented HF lint contract. Reference upstream issue [heygen-com/hyperframes#586](https://github.com/heygen-com/hyperframes/issues/586). |
| Phase 4 mandatory reading list | ❌ proposed list over-mandated captions and transcript-guide | Use canon's exact "Always read" set; mark captions/transcript-guide as orchestrator-house additions with explicit justification. |
| Captions mandatory | 🆕 canon treats captions as conditional (`captions.md:13`, `SKILL.md:393` "when adding any text synced to audio") | Keep mandatory as orchestrator-house rule with explicit basis: every episode in this pipeline produces talking-head audio with synchronous text, so canon's conditional trigger always fires. |
| Step 2 prompt-expansion artifact | ⚠️ canon specifies `.hyperframes/expanded-prompt.md` (`prompt-expansion.md:57-68`), not `PROMPT.md` | Use canon name. |
| `npx hyperframes catalog` discovery gate | 🆕 canon mentions `catalog` only in Step 1 / Design Picker context | Frame as orchestrator productivity practice; not canon-required. |
| Sub-compositions per beat | ⚠️ `data-composition-src` is canonical mounting; per-beat split is design choice (`SKILL.md:50`), supported by lint warning | Recommend, do not mandate. Cite the lint warning as basis. |
| Parallel-agent dispatch | 🆕 not in HF canon | Frame as orchestrator pattern via `superpowers:dispatching-parallel-agents`. |
| Shader transitions for translucent overlays | ❌ `transitions.md:85-95` says CSS and shader are equal first-class options | **Drop the mandate.** Replace with explicit per-beat transition-mechanism choice in `DESIGN.md`. |
| Delete `final.json` on re-cut | 🆕 `final.json` is orchestrator-named (canon uses `<name>.json` pattern in video-use `SKILL.md:37-56`) | Frame as orchestrator hygiene; the file is a derived artifact of `edl.json`. |

The audit's full per-proposal verdicts live in the brainstorm transcript. The corrected design below incorporates every adjustment.

## Design

### PR-1 — Scaffold audio fix

**File:** `scripts/scaffold_hyperframes.py`.
**Scope:** add `data-has-audio="false"` to the `<video>` element in `VIDEO_AUDIO_PAIR_TEMPLATE`. Add a comment block above the template explaining: (a) the attribute is documented in HF CLI docs (`packages/cli/src/docs/data-attributes.md`) and recognized by HF lint/StaticGuard but is not in agent-facing `SKILL.md` canon; (b) without the attribute, HF `timingCompiler.ts:104-106` auto-injects `data-has-audio="true"` on every `<video>`, which combined with `muted` trips StaticGuard's "invalid contract" rule (`media.ts:274`); (c) link to upstream issue [heygen-com/hyperframes#586](https://github.com/heygen-com/hyperframes/issues/586) for context and resolution path.

**Test plan:**
- Re-run `scripts/scaffold_hyperframes.py` on the `2026-04-30-desktop-software-licensing-it-turns-out-is` episode (idempotent on existing artifacts) to verify the new template injects.
- `npx hyperframes validate` in the resulting `hyperframes/` dir — confirm StaticGuard no longer fires the `invalid contract` warning.
- `npx hyperframes preview` — confirm studio audio is clean (no distortion / doubling).

**Out of scope for this PR:** changing the two-element shape, splitting streams via ffmpeg, or any other "deeper" fix to the I/O contract — see brainstorm transcript for why split-streams was rejected (compiler doesn't probe the file, so audio-stripped video still gets `data-has-audio="true"` injected).

### PR-2 — Phase 4 brief: canon-aligned reading + Step 2 + catalog discovery + captions house-rule

**File:** `.claude/commands/edit-episode.md`.
**Scope:** rewrite the Phase 4 brief block on inputs and pre-composition discovery. Concretely:

1. **Mandatory reading list — verbatim.** Insert a "Required reading before composing" block listing exactly the canon's "Always read" set:
   - `~/.agents/skills/hyperframes/SKILL.md`
   - `~/.agents/skills/hyperframes/references/video-composition.md` — *Always read*
   - `~/.agents/skills/hyperframes/references/typography.md` — *Always read*
   - `~/.agents/skills/hyperframes/references/motion-principles.md` — *Always read*
   - `~/.agents/skills/hyperframes/references/beat-direction.md` — *Always read for multi-scene compositions*
   - `~/.agents/skills/hyperframes/references/transitions.md` — *Always read for multi-scene compositions*

   Plus, marked explicitly as **orchestrator-house additions** (with the basis spelled out — every episode here produces audio-synced text):
   - `~/.agents/skills/hyperframes/references/captions.md` — orchestrator-house addition
   - `~/.agents/skills/hyperframes/references/transcript-guide.md` — orchestrator-house addition

   The brief MUST require the Skill executor to confirm in its first response which files were read; empty confirmation means stop, do not proceed.

2. **Step 2 prompt expansion — mandatory artifact.** After reading, executor runs Step 2 per `references/prompt-expansion.md`. Output goes to `<hyperframes-dir>/.hyperframes/expanded-prompt.md` (canon-specified path and name). The brief flags this as mandatory for multi-scene compositions per canon `SKILL.md:39-43`.

3. **Catalog discovery — orchestrator-house gate.** Before writing custom HTML for any beat, executor runs `npx hyperframes catalog --json > .hyperframes/catalog.json`. For each narrative beat, one sentence in `DESIGN.md` → `Beat→Visual Mapping`: which catalog block was considered, and why custom HTML is justified (or which block was installed). Frame this as **orchestrator productivity rule**, not canon mandate. Cite that canon mentions `catalog` only in Step 1 / Design Picker context.

4. **Captions — orchestrator-mandate.** Replace the current "Captions are produced downstream by Phase 4" line with: "Captions track is mandatory in this orchestrator. Use `hyperframes/transcript.json` per `references/captions.md`. The only acceptable reason to omit captions is an explicit user request — never a Skill-author decision documented in `DESIGN.md`." Followed by an Output Checklist item: "captions track present in `index.html` referencing `transcript.json`." The brief MUST clarify this is an orchestrator-house rule, not HF canon — canon treats captions as conditional.

5. **Studio post-launch validation.** After studio launch, the brief listens to preview logs for the first 5 seconds. Any `[StaticGuard]` warning fails the phase. Justification: PR-1 fixes the known StaticGuard contract; any future StaticGuard warning is a real new issue and should fail-fast, not be silently shipped.

**Test plan:**
- Dry-run the updated brief mentally against a fresh episode: enumerate which files an executor would read in order, check that the canonical-reading-only path produces a confirmation message that matches the verbatim list.
- Verify that `expanded-prompt.md` is created at the canonical path, not at a renamed location.
- Verify catalog scan produces a per-beat justification list inside `DESIGN.md`.
- Verify captions track is in the final `index.html`.

### PR-3 — Phase 4 brief: composition structure

**File:** `.claude/commands/edit-episode.md`.
**Scope:** rewrite the Phase 4 brief block on HTML authoring shape. Concretely:

1. **Sub-compositions per beat — strong recommendation.** Each beat ≥ 3 SHOULD live in `compositions/beat-{N}-{slug}.html`, mounted via `<div data-composition-id data-composition-src="compositions/beat-N.html">` per canon `SKILL.md:149-185`. Root `index.html` SHOULD stay ≤ 100 lines (video + audio + captions + mount points). Cite the HF lint warning `composition_file_too_large` as the basis: "Agents produce better results when large scenes are split."

2. **Parallel-agent dispatch — orchestrator pattern.** "Beats are independent and parallelizable. Consider dispatching beat authoring to parallel sub-agents via the `superpowers:dispatching-parallel-agents` skill." Frame explicitly as orchestrator pattern, not HF canon.

3. **Translucent overlays + Scene Transitions — explicit per-beat transition mechanism.** Replace the (rejected) shader-mandate with: "Scene Transitions canon (`SKILL.md:245-260`) requires entrance animations and forbids exit animations on non-final beats. With translucent overlays (e.g., glass panels), entrance-only-cover does NOT visually clear the previous scene. Choose one of these per inter-beat boundary, document in `DESIGN.md`:
   - **CSS clip-path / mask transition** — canon-allowed, simpler;
   - **Shader transition** via `npx hyperframes add transition-shader-<name>` — canon-allowed, more capable;
   - **Final-scene fade** — only between beat-N and beat-(N+1) where N+1 is final.

   Do not rely on entrance-only-cover with translucent panels."

   Cite `transitions.md:85-95` for the CSS-vs-shader choice ("CSS transitions are simpler... Choose based on the effect you want, not based on which is easier").

**Test plan:**
- Verify a fresh Phase 4 run produces `compositions/beat-N.html` files and a slim root `index.html`.
- Verify `DESIGN.md` has a per-beat-boundary transition-mechanism row.
- Verify `npx hyperframes lint` produces no `composition_file_too_large` warning on the root.

### PR-4 — Re-cut idempotency: `transcripts/final.json`

**Files:** `.claude/commands/edit-episode.md` (rebuild guidance), `scripts/remap_transcript.py` (mtime check).
**Scope:**

1. In the rebuild guidance block of `edit-episode.md`, add: "`transcripts/final.json` MUST be deleted on Phase 3 re-cut. It's a derived orchestrator artifact of `edl.json`; if EDL changes, `final.json` is invalidated. The current `Skip if final.json already exists — idempotent` rule is correct only when EDL is unchanged."
2. In `scripts/remap_transcript.py`, optionally compare `edl.json` mtime / hash with a stored metadata field in `final.json`. On mismatch, regenerate. (This makes the script self-healing instead of trusting the rebuild-guidance.)

Frame both changes as orchestrator-internal — `final.json` is not a canon-named file in video-use; the cache rule in canon (`video-use SKILL.md:30`) is "don't re-transcribe", not "delete on re-cut".

**Test plan:**
- Force a Phase 3 re-cut: delete `final.mp4` only, keep stale `final.json`. Run `/edit-episode`. Verify the orchestrator deletes `final.json` (or `remap_transcript.py` regenerates it on mtime mismatch) before Phase 4.
- Verify caption alignment in the final composition matches the new EDL, not the old one.

### PR-5 — CLAUDE.md docs: Windows bootstrap note

**File:** `CLAUDE.md`.
**Scope:** add to the "Skill copies: docs vs. runnable" block:

> **Known Windows blocker:** both `animation-map.mjs` and `contrast-report.mjs` bootstrap `@hyperframes/producer` (and `sharp` for contrast-report) via `npm.cmd` `spawnSync`, which on Windows-Node yields `EINVAL`. Workaround: once per project, `npm i -D @hyperframes/producer@<exact-version> sharp@<exact-version>` inside the `hyperframes/` project. Versions are taken from the script's missing-deps error.

This is documentation, no code. Trivial change. Per `CLAUDE.md` branching policy, MAY land direct-to-main with explicit go-ahead, but default is branch + PR — we'll use the PR path for consistency with the rest of this design.

**Test plan:** none — pure docs.

### Memory entries (8) — orchestrator durable feedback

Each saved as its own file in `memory/` with the schema documented in the auto-memory section of system instructions:

1. `feedback_design_md_opt_outs.md` — "Don't opt out via DESIGN.md from anything mandated either by canon OR by this orchestrator's brief. Captions = orchestrator-mandated; transitions = canon-mandated."
2. `feedback_multi_beat_sub_compositions.md` — "Multi-beat HF composition: split per-beat into `compositions/`. Orchestrator best practice, supported by HF `composition_file_too_large` lint warning. Not canon-mandated."
3. `feedback_bundled_helper_path.md` — "External skill helper scripts (`animation-map.mjs`, `contrast-report.mjs`): always invoke from project's bundled `node_modules/<skill>/dist/...`, never from `~/.agents/...`. Verified working in retro 2026-05-01."
4. `feedback_hf_always_read_canon.md` — "HF `SKILL.md` 'Always read' = contract, not recommendation. Canon list: `video-composition.md`, `typography.md`, `motion-principles.md` (general); `beat-direction.md`, `transitions.md` (multi-scene)."
5. `feedback_hf_step2_prompt_expansion.md` — "HF Step 2 prompt expansion mandatory for multi-scene. Canonical artifact path: `<hyperframes-dir>/.hyperframes/expanded-prompt.md` (per `references/prompt-expansion.md:57-68`)."
6. `feedback_hf_catalog_orchestrator_gate.md` — "`npx hyperframes catalog` scan = orchestrator-house gate before custom HTML. Canon does not mandate this. Per-beat justification lives in `DESIGN.md`."
7. `feedback_translucent_transitions.md` — "Translucent overlays + entrance-only-cover do NOT visually clear the previous scene. Choose explicit per-beat transition (CSS clip-path / shader / final-scene fade); canon allows all three. Not 'shader required'."
8. `feedback_hf_video_audio_canon_bug.md` — "HF `SKILL.md` 'Video and Audio' canonical example with same `src` on both elements triggers StaticGuard 'invalid contract'. Workaround in this orchestrator: `data-has-audio='false'` on `<video>` (documented in HF CLI docs, not in `SKILL.md`). Upstream tracking: heygen-com/hyperframes#586."

Each entry follows the structure: rule, **Why:** line, **How to apply:** line.

`MEMORY.md` index gets one-line pointers to each new file.

### Upstream HyperFrames issues to file (separate from PR work)

Both filed as bug reports in `heygen-com/hyperframes` after PR-1 lands:

1. **Snapshot portrait viewport** (retro §2.5): `npx hyperframes snapshot` defaults to 1920×1080 viewport regardless of root `data-width` / `data-height`. Portrait composition (1080×1920) renders in upper-left, lower 840px clipped. Request: `--width` / `--height` flags or auto-detect from root attributes.
2. **`validate` and `contrast-report.mjs` `null:1` false-positives** (retro §2.6): both samplers iterate all text elements at fixed timestamps regardless of clip activity. Out-of-window elements return invalid `getComputedStyle` colors that present as `null:1` ratio failures, drowning real findings. Request: filter text elements by clip-activity at sample time.

Each gets a minimal-repro repo on the lines of #586 (`sidorovanthon/hyperframes-repro-snapshot-portrait` and `…-contrast-out-of-clip`).

## Implementation order

1. Memory entries (8 files + MEMORY.md update) — lands as part of PR-1 commit.
2. **PR-1** scaffold audio fix — blocking delivery.
3. **PR-4** re-cut `final.json` deletion — independent, can be parallel with PR-1 (different files).
4. **PR-2** Phase 4 brief: reading + Step 2 + catalog + captions.
5. **PR-3** Phase 4 brief: composition structure (sequential after PR-2; same file).
6. **PR-5** CLAUDE.md Windows note — any time.
7. Upstream issues — async, after PR-1 verifies the working-state we describe.

## Risks / open questions

- **PR-1 verification limit:** We've confirmed `data-has-audio="false"` silences StaticGuard on validate. We have NOT yet runtime-verified that studio preview audio sounds clean (the user's original symptom). The retro speculated doubling was the cause, but the brainstorm raised intersample-clipping as an alternative explanation that PR-1 might not address. Test plan must include a real ear-test in studio after the fix lands; if distortion persists, that's a second bug we'll need to chase separately (likely loudnorm headroom — retro §2.4).
- **Captions mandate friction:** Forcing captions on every episode may produce noise on some compositions where the user genuinely wants none (e.g., music videos, abstract visuals). The "explicit user request" opt-out should be tested early — we don't want a brief that the user has to argue against every time.
- **PR-2 first-response confirmation:** Requiring the Skill executor to confirm which files were read is enforced by brief language only, not by tooling. If executor lies / hallucinates the confirmation, we have no programmatic check. Acceptable risk for now; could be tightened later via a hook that scans the executor's tool-use history for required Read calls.
- **Upstream issue cadence:** §2.5 / §2.6 issues require building two more minimal-repro repos. Doable but time investment. Optional to defer if the user prefers.

## Open decisions

None blocking — all proposals locked after the canon audit. Awaiting user review of this spec.
