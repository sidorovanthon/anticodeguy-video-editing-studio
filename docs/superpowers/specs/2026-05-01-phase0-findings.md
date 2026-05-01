# Phase 0 Investigation Findings

**Date:** 2026-05-01
**Worktree:** `investigate/subcomp-loader-bare-repro`
**HF version:** `0.4.41` (from `npx hyperframes --version`)
**Scope:** retro 2026-05-01 findings §2.1 (sub-comp loader emits A-roll-only when `data-composition-src` is used), §2.4 (lint regex `gsap_infinite_repeat` flagging `repeat:-1` inside JS comments), §2.3 (`<template>` wrapper in `compositions/*.html` reporting `0 elements / 0.0s` from `npx hyperframes compositions` CLI).

## Method

Bare-scaffold reproduction via `npx hyperframes init` (scaffolds into `my-video/`). Bare scratch dir: `tmp/bare-hf-repro/my-video/` (gitignored). Each finding tested against the canon-blessed pattern from `~/.agents/skills/hyperframes/SKILL.md` lines 149-185 (sub-comp `<template>` wrapper) and `~/.agents/skills/hyperframes/references/motion-principles.md` "Load-Bearing GSAP Rules" (`gsap.fromTo` over `gsap.from` for deterministic non-linear seeking).

Per CLAUDE.md just-merged Step 3 rule: canon structures (`<template>`, `gsap.fromTo`) were NOT removed as workarounds — that would short-circuit the investigation. Each repro IS the canon pattern verbatim.

## Canon prerequisites read

### `~/.agents/skills/hyperframes/SKILL.md` lines 159-185 (`<template>` + `data-composition-src`)

> Sub-compositions loaded via `data-composition-src` use a `<template>` wrapper. **Standalone compositions (the main index.html) do NOT use `<template>`** — they put the `data-composition-id` div directly in `<body>`. Using `<template>` on a standalone file hides all content from the browser and breaks rendering.
>
> Sub-composition structure:
>
> ```html
> <template id="my-comp-template">
>   <div data-composition-id="my-comp" data-width="1920" data-height="1080">
>     <!-- content -->
>     <style>
>       [data-composition-id="my-comp"] {
>         /* scoped styles */
>       }
>     </style>
>     <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
>     <script>
>       window.__timelines = window.__timelines || {};
>       const tl = gsap.timeline({ paused: true });
>       // tweens...
>       window.__timelines["my-comp"] = tl;
>     </script>
>   </div>
> </template>
> ```
>
> Load in root: `<div id="el-1" data-composition-id="my-comp" data-composition-src="compositions/my-comp.html" data-start="0" data-duration="10" data-track-index="1"></div>`

### `~/.agents/skills/hyperframes/references/motion-principles.md` "Load-Bearing GSAP Rules"

> **Prefer `tl.fromTo()` over `tl.from()` inside `.clip` scenes.** `gsap.from()` sets `immediateRender: true` by default, which writes the "from" state at timeline construction — before the `.clip` scene's `data-start` is active. Elements can flash visible, start from the wrong position, or skip their entrance entirely when the scene is seeked non-linearly (which the capture engine does). Explicit `fromTo` makes the state at every timeline position deterministic.

The bare-repro composition uses `tl.fromTo()` exactly as canon prefers, so this is not the cause of §2.1 failure.

## §2.1 sub-comp loader

**Bare-repro outcome: B (upstream bug confirmed).**

Bare scaffold layout:
- `tmp/bare-hf-repro/my-video/index.html` — root composition, duration 10s, mounts `el-1` referencing `compositions/foo.html` via `data-composition-src`, `data-start="0" data-duration="3" data-track-index="1"`.
- `tmp/bare-hf-repro/my-video/compositions/foo.html` — canon-blessed `<template id="foo-template">` wrapper, single full-bleed `<div class="foo-bg">` with `background:#ff0000; opacity:0`, `tl.fromTo()` opacity 0 → 1 over 0.5s at `t=0` registered on `window.__timelines["foo"]`.

CLI evidence:
- `npx hyperframes lint`: clean for `compositions/foo.html` aside from advisory warnings (`composition_self_attribute_selector` ×2, `root_composition_missing_data_start` for `foo`). The "missing data-start" warning is significant: the linter treats `foo` as a *root* composition, suggesting the CLI does not recognize it is meant to be loaded via `data-composition-src` from a sibling root.
- `npx hyperframes validate`: `No console errors` reported.
- `npx hyperframes compositions`:
  ```
  ◇  my-video — 2 compositions
     main   3.0s   1920×1080   1 element
     foo    0.0s   1920×1080   0 elements ← compositions/foo.html
  ```
- `npx hyperframes snapshot --at 0.0,0.6,1.5,2.5`: all four PNGs are pure black (#000). Evidence files: `tmp/bare-hf-repro/my-video/snapshots/frame-0[0-3]-at-*.png`. Read via the Read tool — no red pixels visible at any timestamp.

**Conclusion:** the `<template>`-wrapped sub-composition referenced via `data-composition-src` is parsed but never mounted/rendered. Its timeline reports 0 duration and 0 elements; the rendered output is black for the full mount window.

**Suggested upstream issue title:** `[CLI 0.4.41] data-composition-src + <template> sub-composition loads to 0 elements / 0.0s; renders as transparent/black at runtime`

**Minimal repro:** the two files in `tmp/bare-hf-repro/my-video/{index.html,compositions/foo.html}` constitute the minimal repro. Reproduce by `npx hyperframes init`, then add the sub-comp + mount. Run `npx hyperframes compositions` to see the `0 elements / 0.0s` symptom and `npx hyperframes snapshot` to see the black frame.

## §2.4 lint regex `gsap_infinite_repeat`

**Bare-repro outcome: B (upstream bug confirmed).**

Test stimulus added to `tmp/bare-hf-repro/my-video/index.html`:

```html
<script>
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true });
  // intentional comment for §2.4 lint regex test:
  // avoid repeat:-1 anywhere in user code
  window.__timelines["main"] = tl;
</script>
```

`npx hyperframes lint` output:

```
✗ [index.html] gsap_infinite_repeat: GSAP tween uses `repeat: -1` (infinite). Infinite repeats break the deterministic capture engine which seeks to exact frame times. ...
◇  1 error(s), 3 warning(s)
```

The lint rule fires on the literal text inside a JavaScript line-comment — a plain `// avoid repeat:-1` triggers a hard error. The regex evidently matches against the raw HTML/JS source without first stripping JS comments.

**Conclusion:** the `gsap_infinite_repeat` linter does not strip JS comments before applying its `repeat:-1` regex match. Any documentation, warning, or pedagogical comment that mentions `repeat:-1` (even to forbid it) trips the linter.

**Suggested upstream issue title:** `[CLI 0.4.41 lint] gsap_infinite_repeat false-positives on "repeat:-1" inside JS comments`

**Minimal repro:** add `// avoid repeat:-1` (or any text containing the substring `repeat:-1`) to any `<script>` block in a scaffolded HF project, run `npx hyperframes lint`. Expect: no error (comment is not executable code). Actual: hard error.

## §2.3 `<template>` in `compositions` CLI

**Bare-repro outcome: B (upstream bug confirmed).**

Same `compositions/foo.html` (canon-blessed `<template id="foo-template">` wrapper). Output of `npx hyperframes compositions`:

```
◇  my-video — 2 compositions

   main   3.0s   1920×1080   1 element
   foo    0.0s   1920×1080   0 elements ← compositions/foo.html
```

The CLI discovers the file and resolves the composition id, width, and height correctly, but reports `0 elements / 0.0s`. The element count and timeline duration are stripped — most likely because the CLI walks the document body and never descends into `<template>.content` (which is an inert DocumentFragment by HTML spec, hidden from `document.querySelectorAll` issued against the live tree).

**Conclusion:** the `compositions` CLI's element/duration probe does not unwrap `<template>.content` before querying. The file is parsed enough to extract `data-composition-id`/`data-width`/`data-height` attributes from the `<template>` wrapper itself, but the inner timeline and child elements are invisible to the probe.

This is the same root mechanism as §2.1 (CLI/loader path does not unwrap `<template>`); it manifests differently in the two CLIs but is plausibly the same upstream bug surface.

**Suggested upstream issue title:** `[CLI 0.4.41] hyperframes compositions reports 0 elements / 0.0s for canon-blessed <template>-wrapped sub-compositions`

**Minimal repro:** identical to §2.1 — just run `npx hyperframes compositions` against the two-file scaffold.

## PR-5 scope recommendation

All three findings are **upstream**, not orchestrator-side. PR-5 should NOT attempt code fixes inside `scripts/scaffold_hyperframes.py`, brief edits, or canon-emulating workarounds for §2.1/§2.3 — those bugs are in the HF CLI loader and the canon-blessed pattern is correct as documented (it just doesn't currently work). PR-5 scope:

1. **Open three upstream HF GitHub issues** (or a single combined issue if §2.1 + §2.3 are confirmed to share a root mechanism) with the minimal repros above. Reference HF version 0.4.41.
2. **Add temporary orchestrator-side workaround** (separate concern; only if a project currently in flight needs it): inline sub-compositions into `index.html` rather than splitting per-beat — i.e., revert the multi-beat split until upstream fixes land. This DIRECTLY conflicts with `feedback_multi_beat_sub_compositions.md` ("split per-beat") and that memory entry should be deleted in Step 9, since the split itself surfaces the bug we cannot reproduce against.
3. **No CLAUDE.md / canon-doc edits.** Canon is correct; the CLI is wrong. Brief edits would be premature.
4. **No change to PR-2 disposition table Row 4.** The "sub-comp split SHOULD→MUST" decision should be **reverted/removed** (or downgraded to MAY) until §2.1 is fixed upstream — splitting per-beat currently produces broken renders.

## Step 9 held memory recommendations

- **Write** `feedback_hf_subcomp_loader_data_composition_src.md` — sub-comp loader produces `0 elements / 0.0s` and renders black against canon-blessed `<template>` + `data-composition-src` pattern (HF 0.4.41). Track the upstream issue once filed.
- **Write** `feedback_lint_regex_repeat_minus_one_in_comments.md` — `gsap_infinite_repeat` linter false-positives on JS comments containing `repeat:-1` (HF 0.4.41). Workaround: avoid the literal substring `repeat:-1` in comments; phrase as `repeat: minus one` or `infinite repeat`.
- **Write** `feedback_hf_compositions_cli_template_zero_elements.md` — `npx hyperframes compositions` reports 0 elements / 0.0s for canon-blessed `<template>`-wrapped sub-comps; same likely root as the loader bug.
- **DELETE** `feedback_multi_beat_sub_compositions.md` — the split-per-beat recommendation it captures presupposes that `data-composition-src` works, which §2.1 disproves at HF 0.4.41. Replace (or update) with a temporary "inline beats into index.html until HF loader bug is fixed upstream" entry.

## Open questions for user

1. **Memory-entry replacement vs. deletion for `feedback_multi_beat_sub_compositions.md`.** Outright delete (PR-5 will then need to re-introduce the split-per-beat advice once upstream fixes land), or replace in place with a "blocked until upstream fix" annotation? Recommendation: replace in place, noting HF 0.4.41 sub-comp loader is broken and listing the pending upstream issue URL — preserves institutional memory of *why* we'd want the split.
2. **File the upstream issues now (before PR-5) or as part of Step 8?** If now, PR-5 can reference real issue URLs in held memory entries; if Step 8, the URLs go in via amend.
3. **Should the version-gated lint comment workaround be encoded in `scripts/scaffold_hyperframes.py`** (strip/avoid the literal `repeat:-1` from any orchestrator-injected comments)? Low effort; prevents one class of false-positive in our own scaffold output.
