# Architecture audit — is the LangGraph approach right, and where to go next

**Date:** 2026-05-31
**Trigger:** operator asked, mid-HOM-334, for an honest assessment — is building this system on LangGraph justified, are we overengineering, should we rebuild, and what's the optimal direction. This doc consolidates the session's findings (read from **live skill sources**, not the synthesized `docs/canon/*` snapshots) into one planning anchor.
**Companion:** `docs/north-star.md` (the goal + why LangGraph). This doc = the *audit against reality* + the *plan*.
**How to use:** this is the single source of truth for the next planning/implementation sessions. Each finding is tagged `[NEW]` / `[TICKETED HOM-NNN]` / `[DONE HOM-NNN]` so no work is duplicated. Sequencing in §7. Open operator decisions in §9.

---

## 1. Verdict (the core question)

**LangGraph is justified. This is not overengineering. Do NOT rebuild from scratch.**

Two architectural decisions are bundled under "the graph"; separate them:

- **Decision A — durable orchestrator chains the pipeline stages** (checkpoint/resume, per-node fingerprint cache = $0 re-runs, `Send` fan-out for beats, conditional routing, HITL interrupts). This is textbook LangGraph. And it is **the only way to reach the north-star**: a free-form skill run is structurally non-deterministic (3–5 revision rounds per video, different style every time — see §3). "Remove the operator + guarantee consistency across videos" is *by definition* an orchestration problem. No overengineering here.
- **Decision B — decompose the skill's INTERNAL canonical steps into separate cold-context nodes.** This is where the pain in every retro lives. Not LangGraph's fault — a **granularity** choice plus **two divergences from canon** (§4).

**Rebuild = wrong.** It would discard the working ~80% (deterministic backbone: pickup/isolate/inventory/render/assemble; backend abstraction; cache; fixture-replay; HITL plumbing) — all orthogonal to the problem — and would not fix the real ~20% (granularity + canon-divergence), which are fixable in place. Retro 2026-05-17 explicitly disproved "decomposition is the problem."

---

## 2. North star (one-line recap)

Scalable video editing with **predictable output + minimal operator intervention**: edit one config (`brand/<id>/palette.yaml`) → all future videos change; point it at a folder of raw videos → batch-processed with **style consistency**. Full statement: `docs/north-star.md`. Memory: `project_north_star`.

---

## 3. The problem the system exists to kill (operator-stated, source-confirmed)

Isolated `/video-use` + `/hyperframes` runs are **structurally non-deterministic** even with the algorithm written in the skill. The agent executes it loosely, skips steps, forgets under context overload. Canonical example (operator): the skill mandates **animation sub-agents** (video-use Hard Rule 10; HF scene sub-agents), but the agent often forgets and **inlines huge HTML** → context overload → recurring errors. Every video differs in captions/transitions/animations.

Source confirmation that this is real, not vibes:
- video-use `SKILL.md` Principle 5: *"Artistic freedom is the default. The only things you MUST do are in the Hard Rules."* → the skill is **deliberately** non-deterministic outside Hard Rules.
- Retro 2026-05-17 measured the free-form transcripts: **not** one-shot — 3–5 operator-driven revisions per video. Free-form "wins" via two loops the graph lacks: **triage** of advisory warnings (~3×/session) and **visual snapshot self-eval** (PNG comparison).

Root cause is **execution architecture** (one overloaded context, no structural step boundaries), not instruction text. Prompt-tuning the skill cannot fix it. → decomposition is the right lever.

---

## 4. Root-cause model — why the decomposed graph hurts

### 4.1 Uniformly narrow context (canon keeps some steps wide)
Decomposition cut context to narrow slices even where the monolith's value was a **wide** context: strategy, taste, cross-scene coherence. video-use canon only spawns **two** sub-agent kinds — editor (one agent, full context, EDL) and parallel animations (HR10). Everything else (pre-scan, converse, strategy, self-eval) is **main-agent reasoning in ONE context**. The graph sliced exactly those reasoning steps into cold nodes → diverged from canon's own structure. Symptom: HOM-154 (semantic phrase dup, missing brand, cold fan-out beats).

Canon itself prescribes the fix: HF `prompt-expansion.md:33` — *"The quality gap between a single-pass composition and a multi-scene-pipeline composition comes from this step"* (the expanded-prompt intermediate that every downstream agent reads identically). Cross-agent coordination via a shared rich intermediate is **canonical**, not invented. → this is exactly M6 (`brief.resolved.yaml`).

### 4.2 Deterministic gates over the "artistic freedom" zone
HF `SKILL.md` §Output Checklist **itself** splits the classes:
- **Fast (block on results):** `lint`, `validate` — mechanical/correctness.
- **Slow (run in parallel while presenting to the user):** `inspect` *"or every reported overflow is intentionally marked"*, contrast *warnings*, animation choreography — **triage-able advisory**. Plus native waiver attributes: `data-layout-allow-overflow`, `data-layout-ignore`, `data-no-capture`.

The graph took the **advisory** class and made it **hard-blocking redispatch gates** → false positives on canonical patterns (z-stacked scenes, opacity-0 captions, full-bleed atmosphere) → `p4_redispatch_beat` exhaustion → burned budget. This inverted canon's own classification.

### 4.3 Version drift of frozen workarounds (NEW — only visible from source)
Four hyperframes version surfaces are simultaneously live and disagree:

| Surface | Version | Role |
|---|---|---|
| Project memory (`feedback_multi_beat_*`, etc.) | **0.4.41 / 0.4.44** | what workarounds are pinned to |
| Installed skill `~/.agents/.../hyperframes/SKILL.md` (what the sub-agent reads as canon) | copy dated **2026-05-14**, 490 lines (~0.5.x era) | canon the agent sees |
| `npx hyperframes` → npm `latest` (what actually RENDERS) | **0.6.63** | the renderer |
| Local dev repo `~/repos/hyperframes` | 0.6.38 (behind origin 165) | dev clone, not used at runtime |

The canon the agent reads (~0.5.x) and the code that renders (0.6.63) are **already two different versions**, and both diverged from memory (0.4.x). Workarounds froze against a moving upstream nobody re-validated. Confirmed: HF sub-comp loader was **rewritten** in 0.6.x (`packages/core/src/compiler/inlineSubCompositions.ts` + `inlineSubCompositions.test.ts`, `<template>` form supported) — "single source of truth … eliminating divergence that previously caused bugs." Our memory `feedback_multi_beat_sub_compositions` still says "0.4.41 produces black renders; author beats inline; revert when #589 lands" — and **"author beats inline" is the very context-overload anti-pattern the operator is trying to escape.** If the loader is fixed, that prohibition is a treadmill tax against already-fixed upstream.

---

## 5. Findings (each tagged; evidence from live source)

| # | Finding | Status | Evidence |
|---|---|---|---|
| F1 | **Brief line-number pins to canon are fragile; at least one is already broken.** `p4_beat.j2` sends the sub-agent to `SKILL.md L227 + L240` → those lines are now **empty** (sections moved to 295/350 by auto-update). Scope: `p4_beat.j2` (10 tokens), `p4_redispatch_beat.j2` (7), `p4_captions_layer.j2` (2 × `motion-principles.md L115-123`), gate `animation_map.py` (5 × `SKILL.md:74`). Some still resolve (SKILL.md:74, motion-principles L115-123 currently OK) but the whole class is fragile by construction; the L227/L240 pair is confirmed dead. | **[NEW]** — adjacent to but not covered by HOM-366 (paraphrase drift). The *line-pin* mechanism + the runtime-pull fix belong to HOM-114. | `sed -n '227p;240p'` on live SKILL.md = empty; section headers at 295/350 |
| F2 | **Advisory-class gates were hard-blocking** (collision/invisible/decorative-vocab) → redispatch exhaustion on canonical patterns. | **[DONE HOM-317]** — `animation_map.py` now hard-blocks only `offscreen`/`degenerate`/dead-zones; routes `collision`/`invisible`/`paced-*` to `gate_animation_map_classify` LLM-triage. **My earlier "do this next" was already shipped.** | `gates/animation_map.py` §"Pass criteria — narrow hard-blocking + LLM-triage (HOM-317)" |
| F3 | **Version drift** (memory 0.4.x · skill ~0.5.x · runtime 0.6.63). Frozen workarounds may be obsolete; "author beats inline" prohibition may be liftable. | **[PARTIAL — HOM-378, 2026-05-31]** install-side synced to **0.6.63** on every surface (renderer + skill docs + dev clone); memory re-validation deferred to **HOM-379 (M7-d)**. See §10. | §4.3; `npm view hyperframes version` = 0.6.63; loader rewrite in source |
| F4 | **No canon loader exists.** Briefs embed/paraphrase canon (rots) instead of pulling verbatim at runtime by section anchor. | **[TICKETED HOM-114, Backlog, not impl]** — operator's verbatim-pull proposal = activate + extend this (§6) | `grep load_skill_section` = absent; only `preflight_canon.py` (staleness, different thing) |
| F5 | **Lost wide-context** at decomposed reasoning nodes (strategy/taste/cross-scene). | **[TICKETED — M6 epic HOM-161]** waves 1-2 (`resolve_episode_brief`, neighbors_summary) | spec 2026-05-07 §1, §8, §10; HOM-154 retro |
| F6 | **No visual feedback loop.** Graph uses `inspect` (headless DOM) but never looks at a rendered frame; free-form's edge is `snapshot --at` PNG self-eval. video-use canon Step 7 (self-eval on rendered output via `timeline_view`) may be under-used by `p3_self_eval`. | **[NEW]** — partially; verify `p3_self_eval` coverage first | retro 2026-05-17 §"no visual snapshot loop"; video-use SKILL.md:91-99 |
| F7 | **`brief-references-canon` is the right model and IS followed for section-name cites** (0 `SKILL.md:NN` pins in briefs; all use `§"section"`). The line-pin issue is a localized regression, not a systemic embed problem. | **[OK]** — reaffirm, don't over-correct | `grep` of briefs/ |
| F8 | video-use fork divergence: our `fix(render)` landed upstream under a different sha → `git pull` won't fast-forward. Auto-updaters pull from **npm**, not the repo. | **[DONE — HOM-378, 2026-05-31]** clean mirror of upstream `main` (cf12ac3); divergent commit + obsolete branch retired; updater bat fixed. **Correction:** the video-use updater is **git-based** (fetch/checkout/pull), not npm — only the HF *renderer* is npm. See §10. | `git log @{u}..HEAD`; scheduled-task actions |

HOM-334 has already spawned its own sub-findings (do not dup): **HOM-352** (errors[] don't halt graph), **HOM-353** (no canon verify-list gate — ffmpeg/API/Node), **HOM-354** (preflight_canon WATCHLIST 1/4), **HOM-355** (node names don't signal canon-vs-orchestrator), **HOM-356** (container infra audit). All Backlog, `(none)` milestone.

---

## 6. The verbatim-pull architecture (operator proposal + HOM-114)

**Proposal (operator, this session):** don't copy canon prose into the graph where it rots; at node execution, pull the verbatim section from the live skill **by section anchor** (not line number) and splat it into the agent's context.

**Verdict: correct, and already designed.** Spec 2026-05-07 §9 specifies exactly this (`load_skill_section(skill_path, anchor)`, anchor-based, **index/line-based extraction explicitly forbidden** as fragile). Ticket = HOM-114 (Backlog). The operator's proposal = activate + adopt as the canon-delivery mechanism. Make it sound with:

1. **Anchor, never line number.** Heading-`startswith` match; reject the `L227` style entirely (F1). Snapshot test must FAIL the build if any brief/gate contains `L\d+` / `\.md:\d+` pointing at external canon.
2. **Fail loud.** Empty extraction → raise `CanonAnchorMissing(skill_path, anchor)`; a build-time `verify_anchors()` walks every registered anchor once per process. Converts today's *silent* drift into a *loud* startup failure (strictly better).
3. **Cache-correct.** Put `sha256(extracted_block)` in the node cache-key (HOM-157 machinery exists). Canon edited upstream → that node auto-invalidates → regenerates; unchanged → cache hit, no re-read. "Go to the skill every run" becomes "every cache-miss," which is exactly right.
4. **Verbatim where canon demands it.** `motion-principles.md:142`: *"these are the exact rules with the exact code examples — don't summarize or shorten them."* The load-bearing GSAP block must be pulled verbatim, live — the strongest case for runtime-pull over embed.

This single mechanism closes F1 (no more line-pins), F4 (no embed/paraphrase rot), and makes auto-updating skills **safe for the graph** (closes the operator's "I hope nothing in the graph contradicts skill updates" — verified it currently DOES, via F1).

---

## 7. Proposed sequencing (layers — each has an architectural reason to wait)

This refines, not replaces, spec 2026-05-07 §21. The new insight: **version re-validation + canon-delivery hardening come BEFORE further content hardening**, because both upstream drift (F3) and broken canon pointers (F1) corrupt every downstream signal.

```
L-A  Canon delivery + version truth      [NEW — do first]
       • Fix line-pins → section anchors (F1) + snapshot guard
       • Activate HOM-114 verbatim-pull loader (§6) + fail-loud + cache-key
       • Update HF skill (npm) + resolve video-use fork (F8); sync memory to 0.6.63
       • Bare-repro re-validate 0.4.x workarounds vs 0.6.63 (sub-comp loader / #586 / #590);
         retire what upstream fixed (esp. "author beats inline" — F3)
L-B  Confirm advisory/visual loops       [mostly DONE/verify]
       • HOM-317 triage — DONE; verify on a real run
       • Visual snapshot self-eval (F6): verify p3_self_eval coverage; add Phase-4 snapshot→eval if missing
L-C  Context resolution (M6 waves 1-2)   [F5 — the north-star machinery]
       • resolve_episode_brief + state.brief + profile/brand skeleton (HOM-166/167)
       • neighbors_summary (HOM-169)
L-D  Vertical slice to a GOOD video      [the real acceptance gate]
       • one profile + one brand, end-to-end, eyeball the video — BEFORE finishing horizontal gate hardening
L-E  Horizontal hardening + cutover      [M3-close, M4 — only real bugs that survive L-A..L-D]
```

HOM-334 is **not discarded** — it becomes diagnosis *inside* L-D (the vertical slice), not a standalone "report on all 30 nodes" phase. Re-scope it from "every node incl. deterministic" to "creative/reasoning nodes + gates," and make it converge to commits/tickets, not a reports folder.

---

## 8. Linear reconciliation (what exists / file / close / re-sequence)

**Already covers a finding — link, don't dup:**
- HOM-114 → F4 + §6 (verbatim-pull). Re-scope title to "runtime canon-section loader (anchor-based, fail-loud, cache-keyed)"; raise priority (it's now foundational, was P3).
- HOM-317 (Done) → F2. Reference as the triage precedent.
- HOM-366 (Todo, paraphrase-drift audit) → overlaps F1; **merge line-pin fix into HOM-366 or make it a sub-task of HOM-114** (decide in §9).
- HOM-161 / M6 waves → F5.
- HOM-352..356 → HOM-334 sub-findings, keep.

**Candidate NEW tickets (propose, file after operator approval):**
- **[F3] Version re-validation:** bare-repro 0.4.x workarounds vs HF 0.6.63; retire obsolete memories/brief-prohibitions (esp. sub-comp inline). Blocks accurate hardening.
- **[F1] Line-pin → anchor fix + snapshot guard** (if not folded into HOM-114/366).
- **[F6] Phase-4 visual snapshot self-eval** (if `p3_self_eval` check shows the gap).
- **[F8] video-use fork resolution + memory version sync** (small, operational).

**Re-sequence:** L-A items ahead of M3-close content hardening (HOM-76/77 family) — hardening on top of broken canon pointers + stale version chases ghosts.

---

## 9. Open decisions for the operator

1. **Home for the F1 line-pin fix:** fold into HOM-114 (canon loader makes line-pins obsolete wholesale — cleanest), into HOM-366 (paraphrase-drift audit — adjacent), or its own ticket?
2. **Version policy:** the runtime is `npx … latest` (floats to 0.6.63 today, moves every run — a risk to *consistency*, the north-star). Pin a known-good HF version in scaffold/briefs, or keep floating latest and rely on re-validation? (Updaters pulling npm is fine; the question is whether the orchestrator pins what it builds against.)
3. **HOM-334 re-scope:** agree to narrow it to creative-nodes+gates and fold it into the L-D vertical slice (converge to commits), vs keep the full every-node walkthrough?
4. **Order:** start L-A now (canon delivery + version truth), or file the full ticket set first then execute from clean Linear state next session?

---

## 10. HOM-378 resolution log (2026-05-31) — version truth + fork resolution

Closes the install-side of **F3** and all of **F8**. Memory re-validation against 0.6.63 (bare-repro of the 0.4.x workarounds) is **HOM-379 (M7-d)**, deliberately out of scope here — this ticket establishes the *known, current* version to repro against.

### Confirmed running versions + where each is sourced

| Surface | Version (2026-05-31) | Source / mechanism |
|---|---|---|
| **video-use skill** (`~/.claude/skills/video-use` → junction → `~/repos/video-use`) | upstream `main` @ `cf12ac3` (incl. #29 portrait-render fix, #34) — no semver, tracked by git HEAD | `~/bin/video-use-update.bat` daily: `git fetch origin` → `checkout main` → `pull --ff-only origin main` → `uv sync`. Now a **clean mirror** of `github.com/browser-use/video-use`. |
| **hyperframes — renderer/CLI** (`npx hyperframes`: init/lint/inspect/preview/render) | **0.6.63** | npm registry, `latest` tag. This is what actually renders. |
| **hyperframes — skill docs** (`~/.agents/skills/hyperframes/` → junctioned `~/.claude/skills/hyperframes/`) | tracks `github.com/heygen-com/hyperframes` HEAD; **no semver marker**; re-synced 2026-05-31 (was stale at 2026-05-14) | `~/bin/hf-skills-update.bat` daily: `npx --yes skills add heygen-com/hyperframes -y -g`. |
| **hyperframes — dev clone** (`~/repos/hyperframes`, source-reading only, not on the runtime path) | **0.6.63** (monorepo packages `@hyperframes/{core,cli,engine,player,producer,...}`); was 0.6.38, ff'd 165 commits | manual `git pull`; not used at runtime. |

The "four surfaces disagree" (§4.3) is resolved on the install side: **all three install/runtime surfaces are now 0.6.63**; the only remaining laggard is *memory* (→ HOM-379).

### What was wrong and fixed

1. **video-use fork (F8).** Local branch `fix/vertical-source-scale` was **ahead 1 / behind 5** of upstream. Our commit `3cb8edd` (`fix(render): preserve vertical aspect`) was *not* patch-identical to upstream's `#29` (`git cherry` → `+`), i.e. a different solution to the same problem. Plus two uncommitted edits to read-only canon: `pack_transcripts.py` utf-8 (= upstream #10, redundant) and `render.py` `-r 24 → -r 60` (a frame-rate hand-edit). Resolution: discarded both working-tree edits, checked out `main` (= origin/main, `0 0`), deleted the obsolete local branch, and rewrote `video-use-update.bat` to track `main` only (dropped the now-dead rebase-on-fork-branch block; added the missing `if errorlevel 1` guard after `checkout main`).
2. **HF skill updater was silently failing since ~2026-05-14.** `hf-skills-update.bat` ran `npx skills add …` without `--yes`, so **npx's own** "install `skills@x`? (y)" prompt was never auto-confirmed under the non-interactive scheduled run → it hung (`Exit code 1073807364`), leaving **zombie node processes** holding the log open (5 found, incl. one from 07:58 today). The bat's `echo Exit code` masked the failure as task "success". Fix: `npx --yes` + `exit /b %ERRORLEVEL%`. Force-ran → skill copy refreshed to 0.6.63-tree; killed the zombie.
3. **Audit assumption corrected.** F8's "auto-updaters pull from **npm**, not the repo" is imprecise: the *video-use* updater is **git-based** and the *HF skill-docs* updater is **GitHub-based** (`skills add`). Only the HF **renderer** (`npx hyperframes`) comes from npm.

### Out of scope (filed separately)

- **Memory re-validation** — the 0.4.x bug-workaround memories (sub-comp loader / #586 / #590 / compositions-CLI) are now each flagged "⚠ re-validate against HF 0.6.63 (M7-d / HOM-379)"; bodies preserved, version pins clarified, **not** retired. → **HOM-379**.
- **60fps as orchestrator-owned brand config.** The discarded `-r 60` hand-edit was the *only* working 60fps path: HOM-117's `target_fps → --fps` forwarding targets a `--fps` flag that **has never existed** in video-use (any branch), and no node populates `target_fps` yet (HOM-188, deferred behind HOM-166). The forwarding test is green only because its runner is mocked — so `target_fps=60` would crash canon `render.py` with `unrecognized arguments: --fps` once HOM-188 lands (a latent mine). Canon is read-only and CLAUDE.md forbids upstream patches, so brand fps must be injected by the orchestrator at dispatch (e.g. run a throwaway copy of `render.py` with `-r` rewritten per-run) — **not** by editing the checkout. → filed as a follow-up ticket.

---

*Sources read this session (live, not synthesized): `~/repos/video-use/SKILL.md`; `~/.agents/skills/hyperframes/SKILL.md` + `references/{motion-principles,captions,prompt-expansion,video-composition,transitions/catalog}.md`; `~/repos/hyperframes/packages/{core,engine,cli}` (inlineSubCompositions, frameCapture, commands); the graph (`graph.py`, `p4_beat.py`, briefs/, gates/); retros 2026-05-07 (HOM-154) + 2026-05-17 (gate FP); spec 2026-05-07; Linear migration project (74 tickets, 6 milestones).*
