# Skill-canon parity plan: context, brand defaults, and production gates

> ⚠️ **SUPERSEDED 2026-05-07** by
> [`2026-05-07-resolved-brief-profiles-brand-architecture.md`](2026-05-07-resolved-brief-profiles-brand-architecture.md).
> This document is kept in git as a reasoning anchor (resolved-brief
> framing, profile concept, canon vs brand split, milestone structure).
> The final source of truth is the successor, which generalizes the
> two-profile (`canonical` / `anticodeguy`) framing into a first-class
> profile slot (video-class) and adds the music library layer.

**Date:** 2026-05-07
**Status:** Superseded
**Original status:** Draft for implementation planning  
**Scope:** Required changes to make the LangGraph video pipeline match clean `video-use` + `hyperframes` sessions, while adding an Anticodeguy brand/style layer without forking or weakening upstream skill canon.

## 1. Problem statement

The current graph executes many of the same high-level phases as `video-use` and `hyperframes`, but it does not yet reproduce the same operating conditions as a clean agent session.

Clean sessions work because the same agent keeps a large working context:

- original user request;
- source script and/or narrative intent;
- edit settings such as output format, padding, grading, subtitles, and animation constraints;
- visual observations from timeline samples;
- previous decisions and corrections;
- brand/style wishes expressed through follow-up prompts.

The graph currently provides structural determinism, but not full context determinism. It guarantees that nodes run in order, but not that each creative node sees the same brief a skilled agent sees in a clean session. It also validates many technical invariants while missing some user-visible outcomes such as semantic duplicate removal, brand adherence, seam coverage, and final CTA presence.

## 2. Canon baseline

### 2.1 Video Use canon

Source reviewed:

- `C:\Users\sidor\repos\video-use\SKILL.md`
- `C:\Users\sidor\repos\video-use\README.md`
- installed skill mirror at `~/.claude/skills/video-use`

Load-bearing requirements:

- The primary reasoning surface is `takes_packed.md`, backed by word-level Scribe JSON.
- Visuals are used on demand through `timeline_view.py`, especially at ambiguous cut decisions and during self-eval.
- The required process is: inventory, pre-scan, converse, propose strategy, wait for confirmation, execute, preview, self-eval, iterate, persist.
- Strategy confirmation before execution is a hard rule.
- Never cut inside a word; every cut edge must have 30-200 ms padding.
- Per-segment extract and concat, 30 ms audio fades, subtitles last when subtitles are used.
- Animations and style are conversation-derived unless the user supplies a style guide.

Graph implication: the graph may decompose the process, but it must preserve the conversation-derived inputs and the on-demand visual loop. If a node gets only `takes_packed.md` and a narrow schema, it is no longer executing the same editorial task as `video-use`.

### 2.2 HyperFrames canon

Source reviewed:

- `C:\Users\sidor\repos\hyperframes\skills\hyperframes\SKILL.md`
- `C:\Users\sidor\repos\hyperframes\skills\hyperframes-cli\SKILL.md`
- `C:\Users\sidor\repos\hyperframes\skills\hyperframes-registry\SKILL.md`
- `C:\Users\sidor\repos\hyperframes\README.md`
- installed skill mirror at `~/.agents/skills/hyperframes`

Load-bearing requirements:

- `design.md` / `DESIGN.md` is the source of truth for visual identity.
- Multi-scene work should run design system, prompt expansion, and plan before HTML authoring.
- Layout is authored before animation.
- Timelines are deterministic, registered synchronously, and seekable.
- Multi-scene compositions require transitions; no hard jump cuts.
- CLI checks are part of the workflow: lint, validate, inspect, preview/render. Snapshot is useful for visual proof.
- Registry blocks/components should be used when they match the job instead of re-inventing everything.

Graph implication: P4 cannot reach clean HyperFrames parity until root-level scene transitions, seam coverage, and final preview/review are real graph behavior rather than planned-but-unimplemented intent.

## 3. Architecture direction

Keep upstream skill canon clean. Add project-specific behavior as a separate layer:

```text
video-use canon
+ hyperframes canon
+ Anticodeguy house style
+ episode-specific overrides
= resolved episode brief consumed by graph nodes
```

The graph should support two modes:

- `canonical`: minimal skill-canon runner, no brand opinions except explicit run input. Used for regression and upstream-canon parity.
- `anticodeguy`: same runner plus default brand kit, edit profile, motion language, CTA contract, and delivery defaults.

This avoids forking the skills. The graph simply gives the skills the same kind of concrete user brief that a clean session receives through natural conversation.

## 4. New core artifact: resolved episode brief

Add a deterministic `resolve_episode_brief` node before Phase 3.

Inputs:

- repository defaults;
- selected profile, e.g. `canonical` or `anticodeguy`;
- brand kit;
- optional `settings_reference.md`;
- optional `script.txt`;
- optional run overrides supplied by the operator/UI/API;
- source metadata discovered by `pickup` and `p3_inventory`.

Outputs:

- `episodes/<slug>/brief.yaml` - editable per-run input;
- `episodes/<slug>/brief.resolved.yaml` - normalized, deterministic source of truth;
- `state.brief.resolved_brief_path`;
- `state.brief.profile`;
- `state.brief.fingerprint`.

Suggested shape:

```yaml
profile: anticodeguy

output:
  width: 1080
  height: 1920
  fps: 60
  format: mp4

edit_style:
  pacing: tight_conversational
  remove:
    - false_starts
    - repeated_takes
    - corrected_phrases
    - dead_air
  padding:
    head_ms: 50
    tail_ms: 80
  subtitles_in_phase3: false

color_grade:
  preset: anticodeguy_default
  notes: clean, sharp, controlled skin tones

brand:
  logo_path: assets/brand/logo.svg
  colors:
    ink: "#141414"
    paper: "#F7F4EF"
    accent: "#FF3B1F"
  typography:
    heading: Space Grotesk
    body: Inter

hyperframes:
  motion_language: liquid_glass_editorial
  seam_policy: cover_every_cut_boundary
  captions:
    enabled: true
    mode: karaoke
    safe_zone: lower_third_do_not_cover_face
  cta:
    enabled: true
    type: subscribe
    logo_path: assets/brand/logo.svg
    placement: final_scene
```

## 5. Required changes

### 5.1 Context bridge

Add a first-class `brief` namespace to graph state.

Required fields:

- `resolved_brief_path`;
- `brand_kit_path`;
- `script_path`;
- `settings_reference_path`;
- `original_user_prompt`;
- `run_overrides_path`;
- `fingerprint`.

Propagate the resolved brief into:

- `p3_pre_scan`;
- `p3_strategy`;
- `strategy_confirmed_interrupt`;
- `p3_edl_select`;
- `gate:edl_ok`;
- `p3_self_eval`;
- `p4_design_system`;
- `p4_prompt_expansion`;
- `p4_plan`;
- `p4_beat`;
- `p4_captions_layer`;
- `p4_assemble_index`;
- all P4 gates.

This should replace the current scattered/potentially-empty fields such as `compose.style_request` as the main source of style and run intent.

### 5.2 P3 semantic edit quality

Add cross-range semantic duplicate detection.

Minimum implementation:

- Extend `p3_pre_scan` to identify repeated or corrected phrases across takes/ranges.
- Extend `p3_edl_select` brief with an explicit rule: adjacent or nearby selected ranges must not repeat the same semantic phrase unless intentionally used as a rhetorical device and documented.
- Add deterministic `gate:edl_semantic_ok` or fold into `gate:edl_ok`.

Suggested gate checks:

- normalize selected range quotes;
- detect repeated 4-8 word shingles across adjacent ranges;
- detect repeated sentence starts across ranges within 15 seconds of output timeline;
- compare selected transcript sequence against `script.txt` when available;
- emit prescriptive violations pointing to range indexes and duplicated phrase.

This gate would have caught the HOM-154 duplicate between EDL range 2 and range 3.

### 5.3 Video Use tool-loop parity

Current `p3_strategy` is text-only, and `p3_edl_select` is effectively `Read`-only. That is weaker than Video Use canon.

Required changes:

- Pass `timeline_view_samples` from `p3_inventory` into `p3_strategy`.
- Allow `p3_edl_select` to use controlled visual tools for ambiguous cuts.
- Add deterministic helper context for cut windows, e.g. a generated table of silence gaps and nearby word boundaries.
- During `p3_self_eval`, generate rendered-output timeline views at every cut boundary and persist them under `edit/verify/self_eval/`.

If the graph keeps P3 decomposed, every creative P3 node must receive enough context to make the same decision a clean `video-use` agent would make. Otherwise, consider making P3 a "fat node": one Video Use executor wrapped by deterministic pre/post gates.

### 5.4 Brand kit and house-style layer

Add a versioned brand kit outside the skills.

Suggested location:

```text
graph/brand/anticodeguy.yaml
graph/brand/assets/
```

The brand kit should define:

- logos and asset paths;
- colors and allowed contrast pairs;
- typography and fallbacks;
- motion language;
- caption style;
- CTA components;
- color grade defaults;
- negative rules, e.g. no generic blue/purple gradients, no stock decorative blobs, no face/caption overlap.

Brand kit is an input, not a skill fork. HyperFrames still treats `DESIGN.md` as source of truth; the graph generates `DESIGN.md` from the resolved brief and brand kit.

### 5.5 Operator preflight UI / editable settings

Before running expensive nodes, the operator should be able to inspect and edit the resolved run settings.

Minimum v1:

- create `episodes/<slug>/brief.yaml`;
- pause at an interrupt with a concise summary and file path;
- accept empty submit to continue only in non-production mode, or require explicit approval in `anticodeguy` mode;
- store the approved brief fingerprint in state.

Future UI:

- small local form for profile, output format, edit pacing, color grade, animation intensity, CTA enabled/disabled, logo path, captions mode.

### 5.6 P4 root choreography and seam coverage

HOM-122 explicitly defers root transitions to HOM-77/v5. This must become production scope for clean-session parity.

Required behavior:

- consume `compose.plan.transitions[]`;
- author root-level transitions between scenes;
- support overlapping tracks where needed;
- ensure every EDL cut boundary is either visually acceptable or covered by an intentional fullscreen/opaque transition;
- keep global layers separate: A-roll, captions, CTA, music, transition overlays, scene accents.

The current v4 hard-cut visibility shim is acceptable for smoke tests, not for production Anticodeguy mode.

### 5.7 Standard CTA component

Add a deterministic CTA contract.

Required fields in resolved brief:

- enabled;
- placement;
- duration;
- logo path;
- copy;
- animation preset;
- safe zone.

Implementation options:

- install/use a HyperFrames registry component if suitable;
- otherwise maintain a local component template under `graph/brand/components/subscribe_cta.html`;
- inject or require it during `p4_plan` and `p4_assemble_index`.

Add `gate:cta_present`:

- final beat/scene exists;
- CTA text exists;
- logo asset referenced and file exists;
- CTA appears within final N seconds;
- CTA does not overlap captions or face-safe zone.

### 5.8 Brand and brief adherence gates

Add gates after assemble:

- `gate:brand_adherence`: colors and fonts are from `DESIGN.md` / brand kit unless explicitly allowed.
- `gate:brief_adherence`: required brief features exist, prohibited features absent.
- `gate:cta_present`: see above.
- `gate:seam_policy`: cut boundaries and scene boundaries obey the resolved seam policy.

Existing `gate:design_adherence` is a start, but it is not enough for production style consistency.

### 5.9 Model-tier cleanup

Production creative nodes must not be pinned to smoke-tier models.

Required:

- remove Haiku overrides from production `p4_beat` and `p4_captions_layer`;
- keep smoke overrides in smoke scripts or per-run config only;
- add a config guard: if `profile=anticodeguy` and a creative node resolves to a cheap model, fail fast unless an explicit `allow_cheap_creative=true` override is set.

Relevant existing intent:

- HOM-118/HOM-119/HOM-120 already established that visual identity, prompt expansion, and plan are smart-tier work.
- HOM-122 text also says scene authoring is smart-tier.
- HOM-123 establishes that captions are smart-tier because tone-adaptive caption authoring is creative styling.
- If current production config still pins `p4_beat` or `p4_captions_layer` to Haiku for smoke-cost reasons, that is a production config bug, not a change in tier policy.

### 5.10 HITL semantics

Keep strategy approval lightweight, but make production review meaningful.

Required changes:

- For `p3_review_interrupt`, empty submit should not approve in `anticodeguy` production mode.
- The interrupt payload should include:
  - final.mp4 path;
  - EDL summary;
  - duplicate detector result;
  - duration and cut count;
  - rendered cut-boundary verification artifact paths.
- Approval should record the brief fingerprint and EDL hash.

Future:

- HOM-78/v6 user review after Studio preview should support targeted feedback routing to P3, P4 design, P4 plan, or specific P4 beat.

### 5.11 Cache and retry reliability

Already mostly covered by HOM-132/HOM-157/HOM-158/HOM-160. The remaining production item is:

- Fix HOM-160: cross-thread cache replay must hydrate state channel writes, or fresh-thread reruns on cached slugs remain unsafe.

Add the resolved brief fingerprint to all relevant cache keys. A brand kit edit, settings edit, or run override must invalidate downstream creative nodes.

Verification note: HOM-158 is Done in Linear, but any future reliability pass should still include a regression test proving timeout-induced retry behavior works with the current `_llm.py` / `RetryPolicy` exception types. Treat this as verification, not a known open backlog item.

## 6. Backlog mapping

Linear audit 2026-05-07: the LangGraph project backlog was checked through Linear. Search/list access is working; the mapping below reflects live issue status as of that audit.

Already represented:

- HOM-132: node-level caching and idempotency. Status: Done.
- HOM-150/HOM-151/HOM-152: concrete HOM-132 waves for Phase 4 LLM nodes, Phase 3 LLM nodes, and deterministic heavy nodes. Status: Done.
- HOM-157: config fingerprint invalidates LLM cache keys. Status: Done.
- HOM-158: LLM failure routing and retry groundwork. Status: Done.
- HOM-160: cross-thread cache replay drops state channel writes. Status: Backlog, High.
- HOM-114: mechanically preload relevant live `SKILL.md` sections into LLM-node briefs. Status: Backlog. This helps canon-context reliability but does not solve episode/user/brand context.
- HOM-118: generic HyperFrames design-system node and `gate:design_ok`. Status: Done.
- HOM-119/HOM-120: prompt expansion and plan, including transition planning. Status: Done.
- HOM-123: tone-adaptive captions layer. Status: Done.
- HOM-122: P4 beat fan-out and current Pattern A hard-cut architecture. Status: Done.
- HOM-137: `p4_transitions` root-timeline scene-to-scene transitions. Status: Backlog, High, parent HOM-77.
- HOM-155: deterministic `beat_kills` auto-inserter for final scene + captions. Status: Backlog, Medium, parent HOM-77.
- HOM-156: `gate:animation_map` LLM "fix or justify" helper. Status: Backlog, Medium, parent HOM-77.
- HOM-77/v5: Phase 4 canonical gaps umbrella. Status: Backlog.
- HOM-78/v6: HITL preview review and feedback routing. Status: Backlog.
- HOM-124/HOM-127/HOM-148: cluster gates and retry-with-feedback. Status: represented; HOM-148 Done.
- HOM-146: Phase 3 to Phase 4 review checkpoint. Status: represented.
- HOM-154: current clean E2E attempt. Status: In Progress, High.

Missing or should be explicit new work:

1. `Episode Brief / Context Bridge`
   - Adds `brief` state namespace.
   - Resolves defaults + brand kit + run overrides + script/settings into `brief.resolved.yaml`.
   - Propagates the brief to all creative nodes and cache keys.

2. `P3 Semantic Edit Quality Gate`
   - Cross-range duplicate detector.
   - Script-aware transcript diff.
   - Brief amendments for `p3_pre_scan` and `p3_edl_select`.

3. `Video Use Tool Loop Parity`
   - Timeline samples in strategy.
   - Controlled visual drill-down during EDL selection.
   - Rendered-output timeline views during self-eval.

4. `Anticodeguy Brand Kit`
   - Versioned brand config and assets.
   - Deterministic resolved `DESIGN.md` generation.
   - Default edit/color/motion/caption/CTA profile.
   - Distinct from HOM-118: HOM-118 creates generic visual identity per episode; this creates a persistent Anticodeguy identity source of truth and constrains `DESIGN.md` generation.

5. `Production Creative Model Guard`
   - Fail if production creative nodes resolve to cheap models.
   - Move smoke model overrides out of production config.

6. `CTA Component and Gate`
   - Standard final subscribe scene.
   - Logo validation.
   - CTA timing/safe-zone validation.

7. `Seam Coverage Gate`
   - Validates `compose.plan.transitions[]` is actually implemented.
   - Validates visual coverage around EDL and scene cut boundaries.
   - Complements HOM-137: HOM-137 implements transitions; this gate proves the transitions actually cover the user-visible seams required by the resolved brief.

Potential Linear hygiene:

- If implementation starts from this spec, create the seven missing items above as Linear issues under `LangGraph pipeline migration`.
- Link `Seam Coverage Gate` to HOM-137 rather than duplicating it.
- Link `Anticodeguy Brand Kit` to HOM-118/HOM-123, but keep it separate because it is product-specific rather than generic HyperFrames canon.
- Link `Episode Brief / Context Bridge` to HOM-114 and HOM-132 because it affects brief rendering and cache keys.

## 7. Suggested implementation order

### Milestone A: Stop losing context

1. Add `brief` state namespace and `resolve_episode_brief`.
2. Add `brief.yaml` and `brief.resolved.yaml` artifacts.
3. Pass resolved brief into P3/P4 creative nodes.
4. Include brief fingerprint in cache keys.
5. Add tests that changing brand color, CTA enabled, or settings reference invalidates P4 cache keys.

### Milestone B: Fix P3 editorial failures

1. Add semantic duplicate detector.
2. Amend `p3_pre_scan` and `p3_edl_select` briefs.
3. Add script-aware checks when `script.txt` exists.
4. Make `p3_review_interrupt` production-mode approval explicit.

### Milestone C: Make Anticodeguy profile real

1. Add `graph/brand/anticodeguy.yaml`.
2. Add brand asset validation.
3. Generate or constrain `DESIGN.md` from brand kit.
4. Add `gate:brand_adherence`.
5. Remove production Haiku overrides for creative nodes.

### Milestone D: P4 parity with clean HyperFrames

1. Implement HOM-137 `p4_transitions` under HOM-77/v5.
2. Implement HOM-155 `beat_kills` and HOM-156 animation-map "fix or justify" if not already done.
3. Replace hard-cut shim for production mode.
4. Add `gate:seam_policy`.
5. Add standard CTA component and `gate:cta_present`.
6. Run an E2E comparison against `docs/clean-skills-usage-examples`.

### Milestone E: Reliability cleanup

1. Fix HOM-160.
2. Add HOM-158 regression coverage if current tests do not prove timeout retry behavior end-to-end.
3. Add production E2E smoke: cold run, warm run, edited-brief rerun.

## 8. Acceptance criteria

For a representative talking-head episode:

- The graph uses the same source script/settings/style intent visible in the clean session examples.
- No repeated corrected phrase remains in `edit/final.mp4`.
- P3 review payload shows semantic duplicate check passed.
- P4 uses brand colors, fonts, logo, captions, and CTA from the resolved brief.
- Every planned transition is implemented in root timeline or explicitly waived with a reason.
- Final CTA scene appears with logo and Subscribe animation.
- Snapshot/inspect/render checks prove nonblank, portrait-correct output.
- Warm rerun on unchanged inputs performs no expensive LLM/subprocess work.
- Editing `brief.yaml` invalidates exactly the affected downstream nodes.

## 9. Design principle

Do not make the graph more deterministic by removing creative context. Make it deterministic around complete context.

The target shape is:

- deterministic input resolution;
- context-rich creative nodes;
- deterministic gates for user-visible outcomes;
- explicit HITL only where the operator can make a real judgment;
- brand defaults as configuration, not skill forks.
