# Retro 2026-05-17 — gate:animation_map over-strict on canonical caption + z-stack patterns

## TL;DR

`gate:animation_map`'s BLOCKING findings on HOM-216 phase 2A (and earlier paid prewarms) are **false positives** — the gate flags canonical HF patterns as authoring defects, triggering `p4_redispatch_beat` retry-with-feedback exhaustion (HOM-148, 3 attempts) and burning LLM budget on content that doesn't need fixing.

Three carve-out gaps cause this. Each is a small (~10 LOC) fix in `graph/src/edit_episode_graph/gates/animation_map.py`. After the fix, the canonical fixture should run clean through `p4_persist_session` without a paid re-record.

The deeper observation: free-form `/hyperframes` runs succeed because the agent **triages** lint warnings (~3× per session across the studied transcripts). The graph treats every warning as ground truth and redispatches, which is structurally wrong for an advisory class of findings.

## Why this retro exists

Three HOM-216 paid prewarms (HOM-189 era → 2026-05-17) halted on the same gate. Each cycle blamed a different upstream cause (helper env bootstrap → design adherence → animation-map content). Each fix expanded the surface area without addressing the underlying issue: the gate's blocking criteria don't match HF canon.

Without this retro, the next operator hitting the halt repeats the diagnostic chain from scratch (read canon → read gate code → inspect recordings → spot carve-out gaps). All three sources need to be cross-referenced — none alone is decisive.

## What kicked this off

Operator observation (this session): *"При этом я в свободном режиме просто прося агента отредактировать видео с помощью HF получаю результат с первого раза. ... Уже в 50-й раз нода валится на контенте."*

That's a real signal — free-form runs ship working videos in 1-shot conversational mode (with operator-driven revisions), while the graph halts on content gates for the same underlying skill. Initial hypothesis: decomposition strips context from sub-agents and they author broken HTML. Verified by inspection — that hypothesis was **mostly wrong**.

## Method

Three parallel investigations:

1. **Free-form transcripts** (`docs/clean-skills-usage-examples/{hyperframes,video-use}/*.jsonl`) — 7 production-work sessions, ~3357 total lines, ~20MB. Studied by dispatched research agent ([`a5315186a2ea59052`](#) — completed 2026-05-17). Brief asked: how does the free-form agent succeed where the graph fails? Specifically context propagation, workflow shape, self-correction events, multi-scene strategy, sub-agent patterns.

2. **HF canon** — re-read `~/.agents/skills/hyperframes/SKILL.md`, `references/prompt-expansion.md`, `references/video-composition.md`, `references/transitions/catalog.md`. Looking for: does canon support independent scene authoring? what coordination mechanism does it prescribe?

3. **Graph artifacts** — read `graph/src/edit_episode_graph/gates/animation_map.py` (full), `tests/snapshots/briefs/p4_beat.txt`, and recordings under `tests/fixtures/episodes/canonical-portrait-talking-head/recordings/` (`gate_animation_map_classify.json`, `p4_captions_layer.json`, `p4_beat.json`).

## Findings — what's true

### 1. Free-form ≠ first-try. The "first try" framing was overstated.

Research agent's measurements across 6 production transcripts:

- `bd562b6c` (motion-graphics for edit-03/final.mp4): 49 sequential `Edit` operations on one `index.html`, **5 operator-driven revisions**, multiple `snapshot`-based visual self-corrections.
- `f442aa01` (video-use, aggressive grading): 4 grade iteration cycles with operator approval at each step.
- `0e14ed30`: 3 operator-feedback rounds.

The free-form agent is not magic. It's **conversational with the operator** + has **visual feedback loops** the graph lacks.

### 2. Free-form succeeds because of triage, not because of one-shot.

In all three studied hyperframes transcripts, the agent dismisses contrast / lint warnings as false positives with a documented reason (e.g. `bd562b6c` L120: *"Контрастные warnings — sampling artefacts (элементы скрыты в этих кадрах)"*). It does NOT redispatch on every warning. It triages, verifies via `inspect`/`snapshot`, and ships.

The graph's `p4_redispatch_beat` treats every BLOCKING finding as ground truth. There is no triage step. This is the structural failure mode.

### 3. Canonical HF scene pattern is z-stacked, not side-by-side.

From `~/.agents/skills/hyperframes/references/transitions/catalog.md` L36-90 (scene template):

```html
<div id="scene1" class="scene">  <!-- z-index: 1, opacity: 1 -->
<div id="scene2" class="scene">  <!-- z-index: 2, opacity: 0; GSAP reveals -->
```

`.scene { position: absolute; top: 0; left: 0; width: 1920px; height: 1080px; }`. **All scenes occupy the exact same screen rect.** Cross-scene spatial collision is built-in to canonical pattern; temporal collision (two scenes visible simultaneously) is what's actually forbidden — and the canonical opacity-driven transitions prevent it.

The `p4_beat` brief mirrors this correctly (`#scene-hook { position: absolute; inset: 0; }`). The output of `p4_beat` in the recording confirms it (e.g. `scene-payoff` with `position: absolute; inset: 0; opacity: 0;`).

### 4. The gate's carve-out logic has three blind spots vs canon.

Reading `gates/animation_map.py`:

**Gap A — `span.w` (caption word-spans).** `_is_caption_canon` (L227-281) matches only the regex `^#cg-\d+$` (caption group IDs). Caption word-spans inside groups carry a `.w` class (or similar) that the regex doesn't match. The HOM-216 halt notice had dozens of `span.w` blocking collision flags — all canonical caption word elements.

**Gap B — `invisible` flag has no carve-out at all.** Lines 530-533 and 559-563/582-586 flag every `invisible`-tagged tween as blocking, regardless of selector. The captions canonical pattern (`p4_captions_layer.json` output verified: `<div class="cg" id="cg-N" style="opacity:0;visibility:hidden">`) keeps non-active groups in opacity-0 hidden state. The bbox sampler sees this and emits `invisible` — canonical, not a defect. The gate's own comment (L222-226) acknowledges this canonical pattern for `collision`, but the carve-out was never extended to `invisible`.

**Gap C — Cross-scene `#scene-*` collisions.** `_collision_is_blocking` (L318-326) considers a selector blocking unless caption-canon OR in `_DEFAULT_DECORATIVE_ALLOWLIST` (grain, glow, hairline, etc.). `#scene-hook`, `#scene-problem`, `#scene-pivot`, `#scene-payoff` are in neither bucket → blocking. But by canon they're z-stacked at the same rect — collision-by-construction.

### 5. The Haiku-tier `gate_animation_map_classify` LLM agreed with canon.

`gate_animation_map_classify.json` (recorded run): for **every** pace flag, decision was `justify` with reasoning citing DESIGN.md ambient-motion mandates and beat energy. The LLM triage layer already exists and works. Problem: it only triages `paced-fast`/`paced-slow`. The hard-blocking categories (collision, invisible, offscreen) bypass it entirely.

### 6. No real authoring bugs in the HOM-216 halt notice.

Cross-referencing the 6 BLOCKING strings in the halt-notice against canon: every flagged element fits a canonical pattern. I see NO finding that points to a real beat / captions defect. This doesn't mean none exists — only that the gate's current noise level hides any signal.

## What I was wrong about earlier in the session

For honesty, recording the corrections:

- **"Decomposition is the problem"** — overstated. Canon explicitly supports independent scene authoring; coordination happens via `expanded-prompt.md` per `references/prompt-expansion.md` L3 (*"consistent intermediate that every downstream agent reads the same way"*). Our brief includes this. The decomposition isn't the structural problem; the gate's blocking criteria are.

- **"Test infrastructure is tech debt"** — wrong framing. The fixture-replay cache.db IS the integration test for the production graph. When fixture halts, production halts. The user pushed back on this and was correct.

- **"Free-form works first-try"** — operator-side framing was sharp, my echo of it was sloppy. Real measurement: 3-5 revisions per video.

## Action items

### Primary fix (filing as HOM-316 — see Linear)

`graph/src/edit_episode_graph/gates/animation_map.py` — three carve-outs:

1. Extend `_is_caption_canon` to match caption word-span selectors (regex like `(?:^#cg-\d+$|^span\.w$)` — exact selector format TBD by looking at one helper output).
2. Add `invisible`-flag carve-out for caption canon. Currently L530-533 unconditionally adds to `invisible`/`blocking`; insert `_is_caption_canon` check first.
3. Add cross-scene-collision carve-out — `#scene-*` selectors are canonical z-stack containers. Either: (a) extend `_DEFAULT_DECORATIVE_ALLOWLIST` with `scene-`, or (b) add a separate `_is_scene_container(selector)` predicate.

Bump `_CACHE_VERSION` to 10. Add tests for each carve-out (the existing test suite under `graph/tests/test_*animation_map*` is the pattern).

Verification path: after the fix, run `pytest tests/test_graph_replay.py` in replay mode against committed cache.db — gate should now emit `passed=True` with `advisory_findings` populated but `violations=[]`. The fixture should advance past gate cluster to `p4_persist_session` → `studio_launch` without redispatch.

### Secondary observations (file separately if pursued)

- **Triage layer for hard-blocking findings.** `gate_animation_map_classify` already does Haiku-tier triage for pace flags. Extend the same pattern to `collision` / `invisible` / `offscreen` would catch carve-out gaps systematically rather than expanding the allowlist forever. Cost: +1 Haiku call per finding category.

- **`p4_scaffold` pin regression** — separately HOM-310.

- **Recordings leak operator-specific paths** — separately HOM-312.

- **`gate:animation_map` lacks a visual snapshot loop.** The helper analyzes the DOM via headless Chrome but does not surface visual screenshots like `npx hyperframes snapshot --at` does. The free-form agent's success leans heavily on visual self-eval via PNG comparisons — the graph has no analog. Larger architectural change; not on the critical path for HOM-216 closure.

## Session-trail breadcrumbs

For the next operator/agent investigating similar halts:

- This investigation lives at `docs/retros/retro-2026-05-17-gate-animation-map-canonical-false-positives.md` (this file).
- Free-form transcripts that diverge from the graph: `docs/clean-skills-usage-examples/{hyperframes,video-use}/*.jsonl`. Use a dispatched agent — they're 20MB+ collectively.
- Gate code under audit: `graph/src/edit_episode_graph/gates/animation_map.py`, especially L222-281 (carve-out comment that admits the canonical-FP problem) and L513-586 (the flag extraction with the three blind spots).
- Recordings to cross-reference: `tests/fixtures/episodes/canonical-portrait-talking-head/recordings/{gate_animation_map_classify,p4_captions_layer,p4_beat}.json`.
- Canon to verify any proposed carve-out against: `~/.agents/skills/hyperframes/references/transitions/catalog.md` L36-90 (scene template), `references/captions.md` (captions canon), `references/prompt-expansion.md` (coordination mechanism), `SKILL.md` §"Quality Checks" §"Animation Map" (advisory mandate).

## Related Linear

- HOM-216 — the ticket that halted on this (phase 2A merged with the halt as recorded baseline, PR #170).
- HOM-294 — fixed an earlier design_adherence halt; revealed animation_map as the next gate.
- HOM-203, HOM-204, HOM-211, HOM-212 — earlier passes at this gate's blocking criteria; established the advisory model but did not catch the three gaps documented here.
- HOM-148 — the redispatch retry-with-feedback mechanism; correct behavior, wrong upstream signal (false positives in, retries out).
- HOM-310, HOM-311, HOM-312 — orthogonal follow-ups from the same prewarm.
- HOM-316 (filed by this retro) — the gate fix.
