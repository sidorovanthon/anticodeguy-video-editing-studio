# Retro: HOM-164 — HF Phase 4 black-screen investigation

Date: 2026-05-08. Linear: HOM-164 (parent HOM-154). HF version: **0.5.3**.
Episode under investigation: `2026-05-06-who-else-is-tired-of-endless-monthly`.

---

## TL;DR

**Decision: orchestrator-side bug.** The `p4_assemble_index` v4 visibility
shim added each per-scene `gsap.timeline({ paused: true })` into root via
`tl.add(child)` — but never cleared the child's `paused` flag. GSAP does
**not** advance a paused child timeline when the parent is `seek()`'d, so
HF's snapshot/preview seek of `__timelines["root"]` left every scene at its
`fromTo` from-state (mostly `opacity: 0`) — the Phase 4 black-screen. Fix:
one extra line in the shim, `sceneTl.paused(false)` immediately before
`root.add(sceneTl, t)`. Verified in a bare `npx hyperframes init` scaffold
with the episode's verbatim `index.html` — fix takes the snapshot from
36 KB (effectively black) to 80–1000 KB (full scene content) at every
sample timestamp.

---

## Bare-repro execution (per CLAUDE.md investigation methodology)

1. `npx hyperframes init bare-test --example blank` → fresh scaffold,
   HF 0.5.3 (latest as of today).
2. Copied our episode's `index.html`, `final.mp4`, `compositions/*` verbatim
   into the bare scaffold.
3. `npx hyperframes snapshot --at 2.5,10,18,25,40,55,70` → identical black-
   screen result to the in-repo episode. **Bug is in the composition itself,
   not in our project wrapper** (`hyperframes.json` / `meta.json` /
   `package.json`). Investigation-plan item 1 localised the bug.

## Bisect

- Investigation-plan item 2 (orientation mismatch — 6 portrait + 2 landscape
  scenes) was **not** the cause. Compositions of mixed orientation render
  fine when the timeline plays.
- Investigation-plan item 3 (runtime-version / `__timelines` registration
  timing) was the right neighbourhood. `npx hyperframes compositions`
  initially reported `5.0s, 2 elements` for our root — only the `<video>`
  + `<audio>` direct children were detected, because beats are inlined
  before `</body>` (i.e. **after** the root `<div>` already closed). Moving
  beats inside the root `<div>` raised the report to `71.9s, 10 elements`
  — but the snapshots stayed black. **Element accounting was a red herring**;
  the runtime still drives playback off `__timelines["root"]` regardless.
- Investigation-plan item 4 (sub-comp loader / `<template>` + `data-composition-src`)
  is **not** in play here. We use Pattern A (single-file inline scenes,
  no sub-comp wrapping) per the existing HOM-122 design.

The decisive bisect step was injecting a JS diag block that called
`getComputedStyle` + `root.time()` from inside `requestAnimationFrame` (so
it runs after framework setup):

```
rT=0.00 rDur=65.25 rCh=213 sh:op=1 hl:op=0 tr=matrix(1,0,0,1,0,60)
```

Even at `--at 1.5s`, `root.time()` is **0.00**. Every scene-local timeline
is registered as a child (`rCh=213` total tweens), and the headline-word's
`fromTo` from-state (`opacity 0`, `y=60`) is correctly applied via
immediate-render. But the **HF runtime never advances the parent timeline
past 0** — because the *children* are paused, GSAP's `seek()` on the parent
doesn't bring the playhead forward through the child's tween range, leaving
the document at scene-1 from-state forever.

Verified by reducing to a 30-line fixture in the bare scaffold:
- Direct `tl.fromTo("#scene-hook #title", ...)` on root → renders correctly.
- `__sceneTimelines["hook"] = gsap.timeline({ paused: true })` + `root.add(sceneTl, 0)`
  → black.
- Same fixture but with `sceneTl.paused(false)` before `root.add(...)` →
  renders correctly.

## Decision

**Our bug.** Fix in `graph/src/edit_episode_graph/nodes/p4_assemble_index.py`,
`build_visibility_shim()`. One extra line in the emitted JS, `_CACHE_VERSION`
bumped 1 → 2 to invalidate the existing assemble cache for future runs.

The earlier symptom of `compositions` reporting `5.0s, 2 elements` *is* a
real shape divergence (beats are siblings of `#root` in the DOM rather than
descendants), but it does not affect runtime playback because HF's `class="clip"`
visibility logic and `__timelines["root"]` seek both work against globally-queried
elements. Element accounting is a separate `lint`/`inspect` concern, not the
black-screen cause. Leaving that as-is here; if a follow-up wants to make
`hyperframes compositions` accurate, that's a small p4_assemble_index v3
revision (move beats injection from `</body>` to `</div>` of root) — not
in scope for HOM-164.

## What changed

| File | Change |
| --- | --- |
| `graph/src/edit_episode_graph/nodes/p4_assemble_index.py` | `build_visibility_shim()` emits `sceneTl.paused(false)` before `root.add(sceneTl, starts[i])`. `_CACHE_VERSION 1 → 2` to invalidate stale assemble cache. Module docstring + comment explain the GSAP semantics. |
| `graph/tests/test_p4_assemble_index_node.py` | New `test_build_visibility_shim_unpauses_child_timeline_before_nesting` regression test pinning the unpause+order. |

No brief changes (per-scene fragments still author `paused: true` per HF canon
— the fix is exclusively in the shim). No graph topology changes (deterministic
node body fix, no new node).

## Test plan

- [x] Unit tests: `pytest tests/test_p4_assemble_index_node.py` — 34 / 34 pass.
- [x] Full suite: `pytest tests/` — 568 / 568 pass.
- [x] Bare-repro snapshot end-to-end: `npx hyperframes snapshot --at 1,3,8,18,40,60,70`
  in `bare-test/` (HF 0.5.3) on the patched assembly. All 7 frames render
  the expected scene content (sizes 80 KB – 1 MB; pre-fix all were 10–37 KB).

## Memory candidates (flagged, not written)

- HF 0.5.3 release uplifted from 0.4.44 — sub-comp loader status is no longer
  necessarily relevant for HOM-122 design (separate ticket if anyone wants to
  re-test Pattern B).
- GSAP nested-timeline semantics: a paused child does NOT advance under
  parent `seek()`. Generic gotcha worth a memory entry — applies anytime we
  programmatically nest `__sceneTimelines` into a registered root timeline.

## Refs

- Linear: HOM-164.
- Parent epic: HOM-154 (M5 — Phase 3 decomposition hardening).
- Related memory: `feedback_hf_pattern_a_vs_b`, `feedback_studio_player_empty_state`.
- Bare-repro working dir (machine-local): `C:\Users\sidor\tmp\hom-164-bare-repro\bare-test\`.
