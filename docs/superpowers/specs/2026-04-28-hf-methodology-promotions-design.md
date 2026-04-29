# HyperFrames Methodology Audit — Promotions

**Status:** design (spec)
**Date:** 2026-04-28
**Closes retro deltas:** D6 (HF methodology audit required) + Delta 4 promotion (≤5 s scene cap, scene ≠ seam)

## Problem

The pipeline was built before we read HyperFrames' own methodology end-to-end. HF ships substantial guidance — transition catalogs, motion-principle guardrails, scene-structure rules, quality gates — and we have been authoring our own analogues in parallel without checking what HF already encodes. Two consequences:

1. We risk reinventing rules HF already provides (transition matrix, ease/duration/direction guardrails, scene phases).
2. We may be skipping HF-recommended gates (`lint`, `validate`, `inspect --strict-all`, `doctor`) that would catch issues earlier.

A separate question — Delta 4 of the pilot retro — established that `≤5 s` is now a hard cap on scene duration, *and* that scenes are no longer 1:1 with EDL seams (scenes are script-driven, seams are structural). `standards/motion-graphics.md` currently says the opposite ("Scene length: bounded by phrase boundaries... runs from one seam to the next regardless of resulting duration"). That contradiction must be resolved.

## Goal

Promote concrete findings from the HF audit into the project's standards and operational rules, and update `standards/motion-graphics.md` to reflect the Delta 4 decisions. After this spec lands, `standards/motion-graphics.md` is the canonical source of truth for the project's overlay layer on top of HF's general rules.

## Audit findings

### What HF already provides — and we should defer to, not duplicate

1. **Transition catalog and selection axes.** `references/transitions.md` defines a three-axis matrix:
   - Energy (calm/medium/high) → primary transition + duration + easing
   - Mood (warm/cold/editorial/tech/tense/playful/dramatic/premium/retro) → transition type
   - Narrative position (opening/topic-change/climax/wind-down/outro) → modifier on the choice

   We pick from this matrix; we do not write our own.

2. **Motion guardrails.** `references/motion-principles.md` codifies: vary eases (≥3 per scene), vary durations (slowest 3× fastest), vary entry direction, offset first animation 0.1–0.3 s, never `t=0`, ambient motion limited to one per scene. These are HF's; our standards reference them, do not restate.

3. **Scene phases — build / breathe / resolve.** Every multi-second scene allocates ~0–30 % entrance, 30–70 % ambient breathe, 70–100 % resolve. HF's rule. Our motion-graphics standard already references this; keep it.

4. **Layout-before-animation.** Hero-frame static CSS first, then `gsap.from()` toward the end-state. HF's pattern. Already referenced in `standards/bespoke-seams.md`.

5. **Visual identity gate.** `DESIGN.md` exists in this repo and follows HF's prescribed format (Style Prompt, Colors, Typography, What NOT to Do) plus the structured `hyperframes-tokens` JSON block. No further work.

6. **Quality gates — `lint`, `validate`, `inspect`.** Already integrated in `run-stage2-compose.sh`. The audit confirms they should run with `--strict-all` (fail on warnings) before any preview/final, not just in optional/best-effort mode.

### What HF does *not* give us — our scope

1. **Scene-mode axis (head / split / broll / overlay).** HF doesn't model talking-head video; it doesn't have an opinion on whether the host is visible. This axis is ours and is orthogonal to HF's transition axes.

2. **Script-driven scene segmentation.** HF assumes scene boundaries are decided externally; our planner has to decide them from script + transcript.

3. **EDL-seam-to-scene reconciliation.** HF doesn't see footage cuts. The interplay between editorial cuts and visual scenes is a property of talking-head pipelines.

These three are exactly the scope of Phase 6b (separate spec).

## Promotions to land in this spec

### P1 — Required HF gates before preview/final

Update `tools/scripts/run-stage2-compose.sh` and `tools/scripts/run-stage2-preview.sh` so that `npx hyperframes lint`, `npx hyperframes validate`, and `npx hyperframes inspect --strict-all` are required-pass before render. Currently they run; some warnings do not abort. Move to `--strict-all` (errors AND warnings fail). Confirm `--strict` is at least passed where `--strict-all` is unsupported.

Promote into `AGENTS.md` Hard Rules: "No preview/final render runs without `lint` + `validate` + `inspect --strict-all` all green." Override only via explicit `--allow-warnings` flag with a written justification in the run log.

Add `npx hyperframes doctor` as a one-shot pre-flight on first use of a fresh dev environment, captured in `docs/operations/render-environment.md` (new file). Not gated per-render; gated per-environment.

### P2 — `standards/motion-graphics.md` edit: Delta 4 reconciliation

Replace the current Scene length section:

> Scene length
> Bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of resulting duration.

With:

> Scene length and seam mapping
>
> A **scene** is the unit of visual planning. Scenes are derived from script semantics, not from EDL seams.
>
> - **Hard cap: 5 seconds per scene.** No scene exceeds 5 s, regardless of script structure. A 12 s narrative beat is subdivided into 2–3 sub-scenes by the planner. The cap is enforced at planner output, not as a soft preference.
> - **Scene boundaries are independent of EDL seams.** EDL seams are structural (where the footage cuts); scene boundaries are semantic (what the viewer should see). A scene may contain 0, 1, or N seams inside it; one seam does not imply a new scene.
> - **`max_seams_per_scene` per mode:**
>   - `head` — 1 seam max (the visible cut would expose itself on a fullscreen face).
>   - `split`, `broll`, `overlay` — N seams allowed (graphic coverage hides the cut).
> - **Snap pass.** After semantic segmentation, scene boundaries are snapped to the nearest transcript phrase boundary (silence > ~150 ms between words) within ±300 ms tolerance. Snapping is deterministic and runs as a separate pass between the segmenter and the decorator.

This change supersedes the prior rule. The retro-changelog entry that introduced "scene = seam-to-seam" is updated to retired.

### P3 — `standards/motion-graphics.md` edit: orthogonality of `scene_mode` and HF transition

Add a new section near the top:

> Two orthogonal axes
>
> Every scene is described by two independent decisions:
>
> 1. **Scene mode** (head / split / broll / overlay) — *how visible is the host*. Project-specific axis. Constrains what graphics may appear (see catalog table below).
> 2. **HF transition** (selected via `references/transitions.md`) — *how this scene gives way to the next*. HF's axes apply: energy + mood + narrative position. The project's default primary is set in `DESIGN.md` (calm / crossfade 0.4 s / `power2.inOut`); deviations are justified per-scene.
>
> The axes do not collapse. Choosing `mode = broll` does not imply a particular transition; choosing `transition = blur-crossfade` does not imply a particular mode.

This formalises the lesson from the 6a-aftermath retro item about `head` / `full` naming confusion: the two axes were tangled; they are now explicitly separated.

### P4 — Project-fixed mood, per-scene optional override

DESIGN.md fixes the project mood at *calm* (Style Prompt: "calm, deliberate, frosted-glass aesthetic"). Add to `standards/motion-graphics.md`:

> Mood inheritance
>
> Project mood is fixed in `DESIGN.md`'s Style Prompt and applies to every scene unless explicitly overridden. The seam-plan's `mood_hint` field is optional; populate it only when a specific scene deliberately departs from project mood (e.g. project is *calm* but a climax scene is *dramatic*). Default mood = project mood.

### P5 — Retro-changelog entry

Add a single dated entry to `standards/retro-changelog.md`:

> 2026-04-28 — Promoted from D6 + Delta 4 (`episodes/2026-04-28-desktop-software-licensing-it-turns-out/retro.md`):
> - HF gates (`lint`, `validate`, `inspect --strict-all`) are required-pass before render. AGENTS.md hard rule.
> - Scene length: ≤5 s hard cap. Scene ≠ seam. `max_seams_per_scene` per mode (head=1, others=N).
> - `scene_mode` and HF transition are orthogonal axes; both decided independently per scene.
> - Project-fixed mood (calm); per-scene `mood_hint` is an optional override.
> - Retired prior rule "Scene length bounded by phrase boundaries, runs seam-to-seam regardless of duration."

## What this spec does NOT do

- It does not introduce the planner. The planner that consumes these rules is the Phase 6b spec.
- It does not ship the new `seam-plan.md` schema. That schema is part of the Phase 6b spec.
- It does not change the compositor. Compositor changes (transition matrix lookup, mode validator) are part of Phase 6b.
- It does not patch HF. Any HF-side bug discovered during the audit is filed upstream; surgical patches go in `tools/compositor/patches/` only when there is no upstream path (see `534fe66`).

## Pointers

- `tools/hyperframes-skills/hyperframes/SKILL.md` — root methodology.
- `tools/hyperframes-skills/hyperframes/references/transitions.md` — full transition matrix.
- `tools/hyperframes-skills/hyperframes/references/motion-principles.md` — guardrails, scene phases.
- `tools/hyperframes-skills/hyperframes-cli/SKILL.md` — CLI gates: `lint`, `validate`, `inspect`, `doctor`.
- `DESIGN.md` — project visual identity (no change).
- `standards/motion-graphics.md` — target of P2/P3/P4 edits.
- `standards/retro-changelog.md` — target of P5 entry.
- `AGENTS.md` — target of P1 hard-rule promotion.
- `episodes/2026-04-28-desktop-software-licensing-it-turns-out/retro.md` — D4, D6 source.
