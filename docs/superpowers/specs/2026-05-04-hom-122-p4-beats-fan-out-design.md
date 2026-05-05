# HOM-122 — `p4_beats` Send fan-out (per-scene authoring, Pattern A)

**Status:** brainstorm-approved 2026-05-04, post-canon-audit revision. Ready for Linear breakdown.
**Linear:** HOM-122 (parent HOM-76, M3).
**Predecessors:** HOM-118 (p4_design_system), HOM-119 (p4_prompt_expansion), HOM-120 (p4_plan + gate:plan_ok), HOM-121 (p4_catalog_scan + p4_assemble_index).
**Defers to HOM-77/v5:** transitions node (root-timeline-scope), per-scene retry sub-graph, sub-comp Pattern B switchover when upstream #589 actually lands.

## Goal

Author one HTML fragment per beat in parallel, via Send fan-out to a smart-tier LLM scene sub-agent. The pre-existing deterministic `p4_assemble_index` inlines those fragments into the root `index.html` per Pattern A (`transitions/catalog.md` L13). Per-scene sub-graph (layout → animate → kills → validate) is deferred to v5/HOM-77.

## Architectural decision (2026-05-04)

Bare-repro on HF 0.4.44 (issue #589 closed but **not fixed** — `compositions` CLI still reports `0 elements` and snapshot still renders pure black on a `<template>+data-composition-src` sub-comp). Memory `feedback_hf_subcomp_loader_data_composition_src` remains valid. Pattern B (sub-compositions) is unavailable; we author Pattern A fragments and inline them.

Canon-audit findings adopted:

- **Transitions are root-timeline scope** (`transitions/catalog.md` L13: *"Only the root div gets `data-composition-id`/`data-start`/`data-duration`"*; canon scene template L36-80 shows transitions tweening sibling `<div id="scene1" class="scene">` containers from a root timeline). Per-scene sub-agents author entrance-only content; the transitions node is **out of HOM-122 scope** (new ticket under HOM-77).
- **`tl.fromTo()` mandatory inside scene boundaries** (`motion-principles.md` L115-123: `tl.from()` sets `immediateRender: true`, fires before scene's `data-start` is active, breaks under non-linear seek). Brief surfaces this as load-bearing.
- **Density floor surfaced in brief** (`video-composition.md` L15-23: 8-10 elements; `house-style.md` L37: 2-5 BG decoratives) — sub-agent must check expanded-prompt.md and add atmosphere if underspecified.
- **Final-scene fade-out flag** in `_beat_dispatch` (HR 4 exception per SKILL.md §"Scene Transitions").
- **CSS scoping discipline** — every rule prefixed `#scene-<id>`, no bare class selectors.

## Canon anchors

- `~/.agents/skills/hyperframes/SKILL.md` §"Composition Structure" L161 (Pattern B), §"Composition Clips" L150-157 (data-* attrs), §"Scene Transitions" HR 1–4 L249-252.
- `~/.agents/skills/hyperframes/references/transitions/catalog.md` L9, L13, L36-80 — Pattern A canonical scene template; root owns data-composition-id/start/duration.
- `~/.agents/skills/hyperframes/references/motion-principles.md` L115-123 — `tl.fromTo()` over `tl.from()` inside scene boundaries.
- `~/.agents/skills/hyperframes/references/video-composition.md` L15-23 — 8-10 elements per scene.
- `~/.agents/skills/hyperframes/references/beat-direction.md` — per-beat planning format (consumed via `compose.plan`).
- `~/.agents/skills/hyperframes/references/prompt-expansion.md` L14, L24-31 — atmosphere layers per scene.
- `~/.agents/skills/hyperframes/house-style.md` §"Background Layer" — 2-5 decoratives per scene with ambient motion.

## Memory anchors

- `feedback_graph_decomposition_brief_references_canon` — briefs reference canon paths, never embed.
- `feedback_creative_nodes_flagship_tier` — scene authoring = smart tier.
- `feedback_hf_subcomp_loader_data_composition_src` — HF Pattern B loader broken on 0.4.41 AND 0.4.44 (verified 2026-05-04); inline workaround stands.
- `feedback_hf_always_read_canon` — multi-scene Always-read list is contract.
- `feedback_lint_regex_repeat_minus_one_in_comments` — avoid the `repeat: -1` literal in JS comments (HF lint false-positive).
- `feedback_langgraph_native_primitives` — `Send`/`update_state(as_node=…)` are first-class.

## Source-of-truth choice

**Filesystem.** Each beat sub-agent writes one HTML fragment file; `p4_assemble_index` reads from disk. State carries only LLM telemetry (`llm_runs`, `errors`, `notices`) — no `compose.beats[]` echo.

## Topology

```
gate_plan_ok ─► p4_catalog_scan ─► p4_dispatch_beats ─┬─ Send(p4_beat, payload₁) ─┐
                                                      ├─ Send(p4_beat, payload₂) ─┼─► p4_assemble_index ─► halt_llm_boundary
                                                      └─ Send(p4_beat, payload_n) ─┘
```

- `p4_dispatch_beats` (deterministic): builds the Send list from `state["compose"]["plan"]["beats"]`, validates uniqueness of `scene_id`s, computes cumulative `data_start_s`, marks `is_final` for the last beat. Returns `Command(goto=[Send(...), ...])`. Skip cases route to `p4_assemble_index` (or `END` if plan is empty).
- `p4_beat` (LLM, smart, has_tools): one Send per scene. Backend semaphore `claude=2` caps real concurrency.
- `p4_assemble_index` (deterministic, from HOM-121): edited to read scene fragments from `compositions/<scene_id>.html` in `plan.beats[]` order, inline as-is between markers — no `<template>` strip needed under Pattern A.

## On-disk artefacts

```
episodes/<slug>/edit/hyperframes/
  index.html                          ← root composition (p4_scaffold + p4_assemble_index)
  compositions/<scene-id>.html        ← Pattern A fragment, inlined into root by assemble
```

(`compositions/` matches HF scaffold convention per `hyperframes.json` `paths.blocks`. When upstream #589 lands and Pattern B becomes viable, file location stays the same; only file shape and root-loader-stub generation change — separate ticket.)

### Per-scene fragment shape (Pattern A, per `transitions/catalog.md` L13 + L36-80)

```html
<div id="scene-{{scene_id}}" class="scene"
     data-start="{{data_start_s}}" data-duration="{{data_duration_s}}" data-track-index="1">
  <style>
    /* ALL rules prefixed with the id selector — no bare class selectors */
    #scene-{{scene_id}} { position: absolute; inset: 0; opacity: {{0 if beat_index>0 else 1}}; }
    #scene-{{scene_id}} .scene-content { width: 100%; height: 100%; padding: 120px 160px;
                                          display: flex; flex-direction: column; gap: 24px; box-sizing: border-box; }
    #scene-{{scene_id}} .title { font-size: 120px; ... }
    /* … */
  </style>
  <div class="scene-content">
    <!-- content -->
  </div>
  <script>
    (function() {
      window.__sceneTimelines = window.__sceneTimelines || {};
      const tl = gsap.timeline({ paused: true });
      // entrance-only via tl.fromTo() per motion-principles.md L115-123
      tl.fromTo("#scene-{{scene_id}} .title", { y: 50, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, ease: "power3.out" }, 0.3);
      // … more fromTo entrances; ≥3 distinct eases per Animation Guardrails
      // (final scene only — fade-out per HR 4)
      window.__sceneTimelines["{{scene_id}}"] = tl;
    })();
  </script>
</div>
```

Notes per canon:

- **NO** `data-composition-id` on the scene div (`transitions/catalog.md` L13). Only root has it.
- **NO** `<template>` wrapper (Pattern B only).
- **NO** `<script src=".../gsap...">` — root scaffold supplies GSAP once; per-scene scripts assume it's loaded.
- `data-start`/`data-duration`/`data-track-index` on the scene div drive timing within root composition.
- `data-width`/`data-height` on the scene div mirror **root viewport**, parsed from root `index.html` by `p4_dispatch_beats` and propagated via `_beat_dispatch`. Resolution-agnostic — supports horizontal (1920×1080), vertical (1080×1920), and any other HF-supported viewport without per-orientation branching. Sub-agents render these as Jinja variables, never hardcode.
- Initial `opacity: 0` on the container for non-first scenes (`transitions/catalog.md` L9: *"Scenes 2+ have `opacity: 0` on the CONTAINER div"*) — the future transitions node will animate this to 1. First scene starts visible.
- Timelines registered on `window.__sceneTimelines` (separate namespace from root's `window.__timelines`); the future transitions node composes them into the root timeline via labels. For v4 hard-cut behaviour, `p4_assemble_index` adds a fallback root-timeline aggregator that sets each scene's `opacity: 1` at its `data_start_s` and unconditionally seeks each `__sceneTimelines[id]` — TBD in implementation, see "v4 visibility shim" below.

### v4 visibility shim (hard-cut behaviour pending transitions node)

Until the transitions node ships under HOM-77/v5, scenes need to **become visible** at their `data_start_s` even without canonical transitions. `p4_assemble_index` appends a generated root-timeline `<script>` after inlining all scenes:

```js
(function() {
  const root = window.__timelines["root"];
  const ids = [/* injected list of scene_ids in order */];
  const starts = [/* data_start_s per scene */];
  ids.forEach((id, i) => {
    if (i > 0) root.set(`#scene-${id}`, { opacity: 1 }, starts[i]);
    root.add(window.__sceneTimelines[id], starts[i]);  // nest scene timeline at start time
  });
})();
```

This produces hard-cut between scenes. The transitions node will replace this shim with proper crossfade/shader/CSS transitions on root timeline.

### `scene_id` derivation

```python
def scene_id_for(beat_label: str) -> str:
    s = unicodedata.normalize("NFKD", beat_label).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:64] or "scene"
```

Uniqueness validated in `p4_dispatch_beats`; collisions surface both labels in the error message.

## Send payload

`p4_dispatch_beats` builds, per beat:

```python
Send("p4_beat", {
    **state,
    "_beat_dispatch": {
        "scene_id": "hook",
        "beat_index": 0,
        "total_beats": 5,
        "is_final": False,
        "data_start_s": 0.0,
        "data_duration_s": 4.5,
        "data_track_index": 1,
        "data_width": 1920,               # parsed from root index.html — 1920×1080 or 1080×1920 or any other HF-supported viewport
        "data_height": 1080,              # never hardcoded; orientation-agnostic
        "plan_beat": {…},                 # PlanBeat dump
        "scene_html_path": ".../hyperframes/compositions/hook.html",
    },
})
```

`_beat_dispatch` is a transient namespace, not declared in `GraphState`. `p4_beat`'s `extra_render_ctx(state)` reads from it plus state-resident upstream artefacts (`compose.design_md_path`, `compose.expanded_prompt_path`, `compose.catalog`).

Catalog stays in state (`p4_catalog_scan` populates it; ~8 KB), `extra_render_ctx` summarises it into the brief. Single source of truth.

**No `transition_in`/`transition_out`** in payload — transitions are root-scope, not per-scene.

## `p4_beat` node

```python
LLMNode(
    name="p4_beat",
    requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
    brief_template=_load_brief("p4_beat"),
    output_schema=None,
    result_namespace="compose",
    result_key="_beat_unused",
    timeout_s=300,
    allowed_tools=["Read", "Write"],
    extra_render_ctx=_render_ctx,
)
```

### Cached skip

```python
scene_path = Path(state["_beat_dispatch"]["scene_html_path"])
if scene_path.is_file() and scene_path.stat().st_size > 0:
    return {"notices": [f"p4_beat[{scene_id}]: cached, skipping"]}
```

Replaces full `CachePolicy + SqliteCache` (HOM-132) with a poor-man's variant scoped to the FS artefact.

### Failure handling

- `AllBackendsExhausted` → `_llm.py` already routes to `errors` + `notices`. File not created. Other Send branches unaffected.
- Sub-agent emits malformed HTML → caught by `gate:lint`/`gate:validate` after assemble (HOM-124).

## Brief — `briefs/p4_beat.j2`

Path-references-only. ~70 rendered lines.

Mandatory canon read-list (no paraphrase):

1. `~/.agents/skills/hyperframes/SKILL.md` — §"Layout Before Animation", §"Scene Transitions" HR 1–4 (HR 4 final-scene exception applies iff `is_final == True`), §"Animation Guardrails", §"Rules (Non-Negotiable)"
2. `~/.agents/skills/hyperframes/references/transitions/catalog.md` — Hard Rules (CSS) L9 + L13 + scene template L36-80 — your fragment shape MUST match this (no `data-composition-id` on scene div, no `<template>`, opacity-0 initial state for non-first scenes).
3. `~/.agents/skills/hyperframes/references/motion-principles.md` — Always read; especially L115-123 `tl.fromTo()` mandate inside scene boundaries (`tl.from()` causes silent breakage with non-linear seek).
4. `~/.agents/skills/hyperframes/references/video-composition.md` — Always read; density floor (8-10 elements per scene, L15-23).
5. `~/.agents/skills/hyperframes/references/typography.md` — Always read.
6. `~/.agents/skills/hyperframes/references/beat-direction.md` — Always read for multi-scene.
7. `~/.agents/skills/hyperframes/references/transitions.md` — Always read for multi-scene (energy/mood selection — informs your scene's internal motion choreography even though scene-to-scene transitions are authored elsewhere).
8. `~/.agents/skills/hyperframes/house-style.md` — applies per scene (2-5 BG decoratives with ambient motion).
9. (conditional) `~/.agents/skills/hyperframes/references/techniques.md` — only if `plan_beat` references a specific technique (lottie, canvas, variable-fonts, etc.).

Brief variables: `scene_id`, `beat_index`, `total_beats`, `is_final`, `data_start_s`, `data_duration_s`, `data_track_index`, `data_width`, `data_height`, `plan_beat_json`, `design_md_path`, `expanded_prompt_path`, `catalog_summary`, `scene_html_path`.

Brief-level imperatives (orchestrator-house, derived from canon — surface them so the agent doesn't miss):

- Every CSS rule in your fragment MUST be prefixed with `#scene-{{scene_id}}` (no bare `.title` etc.) — collision-safety after inlining.
- Use `tl.fromTo()` for every entrance, not `tl.from()` — see motion-principles.md L115-123.
- ≥ 3 distinct eases (Animation Guardrails); first entrance offset 0.1–0.3s.
- Density floor: ≥ 8 elements visible at hero frame, ≥ 2 BG decoratives with ambient motion (`tl.to()` on the seekable `tl`, never bare `gsap.to()`).
- Final-scene fade-out (HR 4): permitted iff `is_final == True`; otherwise NO `tl.to(..., {opacity: 0})`.
- Avoid the literal substring `repeat: -1` even in comments (HF lint regex false-positive — memory `feedback_lint_regex_repeat_minus_one_in_comments`).

Output instruction: write ONE file via Write to `{{ scene_html_path }}` in the Pattern A fragment shape above. Reply with one line: `"Wrote <path> (<N> elements, <M> tweens)."`.

## `p4_assemble_index` edits (in HOM-122 PR)

The assemble node already exists (HOM-121). Edits:

1. **Source of beats** — replace `compose.beats` iteration with `state["compose"]["plan"]["beats"]` order. Build path = `compositions/<sanitize(beat)>.html`.
2. **Inline as-is** — no `<template>` strip (Pattern A fragments are already direct `<div>`). Drop the previously-planned `extract_inner_div`.
3. **Missing-scenes aggregation** — collect every missing scene first, then skip with reason `"missing scenes: hook, payoff"`.
4. **v4 visibility shim** — append the root-timeline aggregator script (sets `opacity: 1` at scene start times, nests `__sceneTimelines[id]` into root). Marked between markers `<!-- p4_assemble_index: shim begin -->` … `<!-- p4_assemble_index: shim end -->` so the future transitions node can replace it cleanly.

Existing `compose.assemble.beat_names` field repurposed as the `scene_id` list (informational).

## State changes

None to `GraphState` schema. The transient `_beat_dispatch` namespace lives only inside Send-spawned states; it never reaches the parent thread checkpoint as a stable channel.

`compose.beats: list[BeatArtifact]` defined in `state.py` becomes dead code under FS-truth. Kept with a deprecation comment pointing to this spec; mechanical removal out of HOM-122 scope.

## Routing

Update `nodes/_routing.py`:

- `route_after_catalog_scan` — extend mapping with `"p4_dispatch_beats"` when `compose.plan.beats` is non-empty; existing skip paths preserved.
- New `route_after_dispatch_beats(state) -> Sequence[Send] | str` — returns the Send list when dispatch built one; returns `"p4_assemble_index"` on skip; returns `END` when plan is empty.
- `g.add_edge("p4_beat", "p4_assemble_index")` — static edge; LangGraph waits for all parallel Send branches before firing.

`graph.py` registers `p4_dispatch_beats_node` and `p4_beat_node`, wires edges, updates topology comment.

## Halt notice update

`halt_llm_boundary_node`: text changes from "render requires `p4_assemble_index` (catalog populated)" to:

> "v4 halt: scenes assembled from `compositions/*.html` into root `index.html` (hard-cut between scenes — transitions node ships under HOM-77/v5); next gate cluster ships in HOM-124."

## Tests

### Unit (mocked, ~30 cases)

- `tests/test_p4_dispatch_beats.py` — skip cases × 4, payload shape, scene_id collision, sanitisation, cumulative timing
- `tests/test_p4_beat.py` — cached skip, AllBackendsExhausted handling, brief render context completeness, mocked happy path
- `tests/test_p4_assemble_index.py` (extend) — Pattern A fragment inlining, plan-order preservation, missing-scenes aggregation, v4 visibility shim emission

### Topology (`tests/test_p4_topology.py`)

Extend `expected_edges` set:

```python
("p4_catalog_scan", "p4_dispatch_beats"),
("p4_dispatch_beats", "p4_beat"),                # via Send
("p4_dispatch_beats", "p4_assemble_index"),      # skip path
("p4_dispatch_beats", "END"),                    # empty plan
("p4_beat", "p4_assemble_index"),                # static, post-fan-in
```

Extend `EXPECTED_NODES` in `smoke_hom107.py`: `p4_dispatch_beats`, `p4_beat`.

### Real-CLI smoke (`graph/smoke_hom122.py`)

Resumes a real episode with primed Phase 4 artefacts (`2026-05-04-desktop-software-licensing-it-turns-out-is` per handoff) via LangGraph native primitives:

```python
from langgraph_sdk import get_client
client = get_client()
thread_id = find_thread_for_slug(SLUG)
state = client.threads.get_state(thread_id)["values"]
client.threads.update_state(thread_id, values=state, as_node="p4_catalog_scan")
client.runs.create(thread_id, assistant_id="agent", input=None)
```

Per-node `model:` override in `graph/config.yaml` pins `p4_beat` to Haiku (~$0.001 × N beats).

Verify post-run:
- `episodes/<slug>/edit/hyperframes/compositions/*.html` — N fragment files, one per beat, no `<template>`, no `data-composition-id`, all CSS prefixed with `#scene-<id>`, all entrances `tl.fromTo()`.
- `index.html` after assemble: scene fragments inlined between markers, v4 visibility shim block appended.
- `npx hyperframes lint` clean on the project (assemble produces lint-valid HTML).
- `npx hyperframes snapshot --at <mid-of-scene-2>` — visible content from scene 2 (validates the v4 visibility shim works end-to-end).
- Studio trace: `p4_dispatch_beats → p4_beat (×N parallel, cap 2) → p4_assemble_index → halt_llm_boundary`.

Re-running is free under cached-skip.

## Per-ticket DoD (per CLAUDE.md)

1. **Real-CLI smoke** ✓ — `smoke_hom122.py` on real slug via `update_state(as_node=…)`.
2. **Topology wiring in same PR** ✓.
3. **Topology check green** ✓.
4. **Halt notice updated** ✓.

## Files touched

New:
- `graph/src/edit_episode_graph/nodes/p4_dispatch_beats.py`
- `graph/src/edit_episode_graph/nodes/p4_beat.py`
- `graph/src/edit_episode_graph/briefs/p4_beat.j2`
- `graph/src/edit_episode_graph/_scene_id.py`
- `graph/tests/test_p4_dispatch_beats.py`
- `graph/tests/test_p4_beat.py`
- `graph/smoke_hom122.py`

Edited:
- `graph/src/edit_episode_graph/graph.py`
- `graph/src/edit_episode_graph/nodes/_routing.py`
- `graph/src/edit_episode_graph/nodes/p4_assemble_index.py` (FS-truth iteration + v4 visibility shim)
- `graph/src/edit_episode_graph/nodes/halt_llm_boundary.py`
- `graph/src/edit_episode_graph/state.py` (deprecation comment on `compose.beats`)
- `graph/tests/test_p4_assemble_index.py`
- `graph/tests/test_p4_topology.py`
- `graph/smoke_hom107.py`
- `graph/config.yaml`

## Risks & mitigations

- **v4 visibility shim is non-canonical.** It mimics what the future transitions node will do, but does not match `transitions/catalog.md` template literally. Mitigated by: (a) shim is bracketed with markers so the transitions node replaces it cleanly; (b) `gate:lint`/`gate:validate` after assemble (HOM-124) catches if the shim produces lint errors.
- **Cached-skip ignores brief drift.** Re-running after a brief change won't re-author. Mitigation: documented in PR description; user deletes `compositions/*.html` to force regeneration. HOM-132's `CachePolicy.key_func` solves it properly.
- **Pattern A fragment density floor enforced only via brief.** Sub-agent might still under-deliver. Mitigated by HOM-124's `gate:design_adherence` and `gate:inspect` post-assemble.

## Sub-issue breakdown (Linear, under HOM-122)

Per memory `feedback_linear_subissues_for_epics`. HOM-122 stays as the umbrella; sub-issues:

1. **HOM-122a** `_scene_id` util + `p4_dispatch_beats` deterministic node + topology wiring + tests (~1 pt)
2. **HOM-122b** `p4_beat` LLM node + brief + tests (~2 pts)
3. **HOM-122c** `p4_assemble_index` Pattern A retrofit + v4 visibility shim + tests (~1 pt)
4. **HOM-122d** Real-CLI smoke + halt notice + smoke_hom107 EXPECTED_NODES + config.yaml model override (~0.5 pt)

Plus separate ticket under HOM-77/v5:

5. **(new)** `p4_transitions` LLM-or-deterministic root-timeline transitions node — replaces v4 visibility shim with canonical `transitions/catalog.md` mechanisms (CSS / shader / final-fade) per `compose.plan.transitions[]`.
