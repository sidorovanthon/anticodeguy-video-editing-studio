# HOM-379 — re-validation of HF 0.4.x workarounds against HF 0.6.63

**Date:** 2026-05-31 · **Runtime under test:** `npx hyperframes` = npm `latest` = **0.6.63** (verified `npx hyperframes@latest --version` == `npm view hyperframes version`). **Method:** clean `npx hyperframes init` scaffold, canonical pattern per the live 0.6.63 `SKILL.md`, per CLAUDE.md §"Investigation methodology — bare-repro before upstream-blame".

All four 0.4.x-era HF workaround memories were bare-repro'd. **Verdict: all four are FIXED on 0.6.63.**

| # | Bug (memory) | Upstream | 0.4.x symptom | 0.6.63 verdict |
|---|---|---|---|---|
| 1 | Sub-comp loader (`feedback_hf_subcomp_loader_data_composition_src`, `feedback_multi_beat_sub_compositions`) | #589 | `<template>`+`data-composition-src` → black render / `0 elements` | **FIXED** |
| 2 | compositions-CLI zero-elements (`feedback_hf_compositions_cli_template_zero_elements`) | #589 | `compositions` reports `0 elements / 0.0s` for template-wrapped sub-comps | **FIXED** |
| 3 | video+audio StaticGuard (`feedback_hf_video_audio_canon_bug`) | #586 | same-src `<video muted>`+`<audio>` → StaticGuard "invalid contract" + audio doubling in studio preview | **FIXED** |
| 4 | lint regex `repeat:-1` in comments (`feedback_lint_regex_repeat_minus_one_in_comments`) | #590 | `gsap_infinite_repeat` false-positives on the literal substring inside JS comments | **FIXED** |

## 1 + 2 — sub-comp loader / compositions-CLI (#589)

A 2-scene composition was authored exactly per the 0.6.63 canon (`SKILL.md` §"Composition Structure": standalone root with NO `<template>`; sub-comps `<template id="…-template">`-wrapped, mounted via `data-composition-src`, timing on the root host stub):

- `index.html` → root `data-composition-id="main"` with two host divs (`data-composition-src="compositions/scene-a.html"` @ 0–4s, `…/scene-b.html` @ 4–8s).
- `compositions/scene-a.html`, `compositions/scene-b.html` → `<template>`-wrapped, each a gradient bg + a `gsap.fromTo()` title, timeline registered on `window.__timelines["<id>"]`.

Results:
- `npx hyperframes compositions` → `main 2 elements`, `scene-a 2 elements ← compositions/scene-a.html`, `scene-b 2 elements ← compositions/scene-b.html`. **Non-zero element counts** — the loader unwraps `<template>.content` (the 0.4.x signature was `0 elements / 0.0s`).
- `npx hyperframes lint` → 0 errors, 0 warnings.
- `npx hyperframes snapshot --at 1,5` → **non-black frames**: t=1 renders the blue→purple "SCENE A", t=5 renders the red→orange "SCENE B" — each sub-comp renders its own content at its own timeline position. No black render.

The pre-existing harness `scripts/bare_repros/feedback_hf_subcomp_loader_data_composition_src.py` independently returned exit 1 (`VERDICT: fixed — sub-comp 'beat-one' reports non-zero element count`).

## 3 — video+audio StaticGuard (#586)

The current 0.6.63 canon "Video and Audio" example (`SKILL.md` §"Video and Audio") STILL uses the same `src="video.mp4"` on both `<video muted>` and `<audio>`, and STILL omits `data-has-audio` — i.e. canon itself would trip the bug if it persisted. Reproduced that exact bare pattern (no `data-has-audio`) against a real muxed clip (ffmpeg `testsrc`+`sine`, video+audio streams):

- `npx hyperframes render` → clean. Compiler metadata: `"videoCount":1,"audioCount":1` — the muted video is NOT double-routed as a second audio source (the 0.4.x mechanism would have yielded `audioCount:2`). No `[StaticGuard]` / "Invalid HyperFrame contract" diagnostic.
- `npx hyperframes inspect` → 0 layout issues.
- **Studio preview** (`npx hyperframes preview`, loaded in a real browser via Playwright, the exact #586 path): 0 console errors; the only messages were a HyperFrames telemetry notice + generic Chromium iframe-sandbox boilerplate. **No StaticGuard, no contract violation.**

## 4 — lint regex `repeat:-1` in comments (#590)

A/B on one file:
- A: `// NOTE: never use repeat:-1 here` (literal substring in a JS comment) → lint clean.
- B: same file + a real `tl.to("#root", { rotation: 360, repeat: -1, duration: 1 })` → lint reports **exactly 1 error** (`gsap_infinite_repeat`).

The rule is still active (fires on real code) but no longer false-positives on the comment (0.4.41 produced 2 errors). **Fixed.**

## Decision

- The four memories are **annotated RESOLVED** (not deleted — code-comment references stay valid); the stale "⚠ re-validate" flags and the `data-has-audio` / inline-only / `repeat:-1`-in-comments *prohibitions* are retired. `feedback_skill_version_drift` and `feedback_hf_pattern_a_vs_b` updated to drop the version-pinned "broken" claims.
- False "upstream broken" *claims* in load-bearing briefs/scaffold corrected to truthful current-state text (canon delivery — M7 goal).
- `preflight_canon` watchlist cleared (the designed human-clear action after a confirmed exit-1 fix).
- **DoD #3 (restore canonical Pattern-B sub-composition authoring in `p4_beat`/`p4_assemble_index`) is deferred to HOM-383** — it changes a creative node's output shape + disk I/O, requiring a paid fixture re-record + wave acceptance per CLAUDE.md. The loader being fixed is the unblock; the migration is its own focused, properly-gated PR.
