# Step-debug node inventory (HOM-334 Phase A + A.5)

Canonical list of every graph node that the `HOMESTUDIO_STEP_DEBUG=1`
interrupt wrapper covers. Phase B step-debug runs reference this table —
the run-log artifact (`docs/step-debug-runs/`) walks the table
top-to-bottom.

Phase A wired LLM nodes via `wrap_llm_node_call` inside `LLMNode.__call__`.
Phase A.5 extended coverage to every deterministic node and every gate
(via the `Gate.__call__` base hook + per-node wraps), so an operator-driven
step-debug session pauses at every reachable transition in the graph.
The only graph nodes that do NOT pre/post-interrupt are the four HITL
interrupt nodes (already pause via canonical `langgraph.types.interrupt()`)
and the `p4_redispatch_beat` retry node — see §"Intentionally excluded"
below.

Columns:

| col | meaning |
| --- | --- |
| node | LangGraph node name (matches `graph.py` `add_node` first arg). |
| kind | `llm` (dispatches through `LLMNode` / `BackendRouter`) or `deterministic` (no LLM dispatch). |
| brief | Jinja2 template path under `graph/src/edit_episode_graph/briefs/` — `—` for deterministic. |
| schema | Pydantic output schema class — `—` for deterministic. |
| cached | `cache_policy=` present on the node in `graph.py`. |
| upstream interrupt | HITL interrupt that already fires just BEFORE this node (in addition to the new step-debug pre-interrupt). |
| downstream interrupt | HITL interrupt that already fires just AFTER this node. |
| reads (state) | Top-level state keys / paths the node body reads. |
| writes (state) | Top-level state keys the returned update sets. |

## Phase 3 LLM chain

| node | kind | brief | schema | cached | upstream interrupt | downstream interrupt | reads (state) | writes (state) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `p3_pre_scan` | llm | `p3_pre_scan.j2` | `PreScanReport` | yes | — | — | `slug`, `edit.transcripts` (via `EpisodePaths`); reads `episodes/<slug>/edit/takes_packed.md` from disk | `edit.pre_scan`, `llm_runs` |
| `p3_strategy` | llm | `p3_strategy.j2` | `Strategy` | yes | — | `strategy_confirmed_interrupt` (Studio HITL — approve/revise loop) | `slug`, `edit.pre_scan`, `strategy_revisions`; reads `takes_packed.md` body | `edit.strategy`, `llm_runs` (+ persists `<edit>/strategy.json`) |
| `p3_edl_select` | llm | `p3_edl_select.j2` | `EDLDoc` | yes | `strategy_confirmed_interrupt` (HOM-128 gate, HR 11) | — | `slug`, `edit.strategy`, gate-retry violations | `edit.edl`, `llm_runs` |
| `p3_self_eval` | llm | `p3_self_eval.j2` | `EvalReport` | yes | — | — | `slug`, `edit.render`, `edit.edl`; reads `final.mp4` indirectly (the dispatched sub-agent runs `timeline_view.py`) | `edit.eval`, `llm_runs` |
| `p3_persist_session` | llm | `p3_persist_session.j2` | `PersistSessionResult` | yes | — | `p3_review_interrupt` (Phase 3→4 bridge, HOM-146) | `slug`, `edit.edl`, `edit.eval` | `edit.persist`, `llm_runs` |

## Phase 4 LLM chain

| node | kind | brief | schema | cached | upstream interrupt | downstream interrupt | reads (state) | writes (state) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `p4_design_system` | llm | `p4_design_system.j2` | `DesignDoc` | yes | `p3_review_interrupt` (Phase 3→4 bridge, HOM-146) | — | `slug`, transcripts (via `EpisodePaths`) | `compose.design`, `llm_runs` |
| `p4_prompt_expansion` | llm | `p4_prompt_expansion.j2` | `ExpandedPrompt` | yes | — | — | `slug`, `compose.design.design_md` (in-state body, HOM-265) | `compose.expansion`, `llm_runs` |
| `p4_plan` | llm | `p4_plan.j2` | `CompositionPlan` | yes | — | — | `slug`, `compose.design.design_md`, `compose.expansion.expanded_prompt` | `compose.plan`, `llm_runs` |
| `p4_captions_layer` | llm | `p4_captions_layer.j2` | `CaptionsOutput` | yes | — | — | `slug`, `compose.design.design_md`, transcripts JSON path | `compose.captions.html`, `llm_runs` |
| `p4_beat` | llm (per-Send fan-out) | `p4_beat.j2` | `BeatOutput` | yes | — | — | `_beat_dispatch` (per-Send: `scene_id`, `plan_beat`, timing), `compose.design.design_md`, `compose.expansion.expanded_prompt`, `compose.catalog` | `scenes[scene_id].html`, `llm_runs` |
| `p4_persist_session` | llm | `p4_persist_session.j2` | `PersistSessionResult` | yes | — | — | `slug`, `compose.assemble`, `compose.plan` | `compose.persist`, `compose.session_persisted`, `llm_runs` |
| `gate_animation_map_classify` | llm (cheap) | `gate_animation_map_classify.j2` | `ClassifyReport` (advisory) | yes | — | — | latest `gate_results[gate:animation_map].advisory_findings.pending_classify`, `compose.design.design_md` (via `EpisodePaths`) | appended `gate_results[gate:animation_map]` record with `decision`/`reason` per flag |

## Factory-based deterministic nodes (HOM-334 Phase A.5)

These nodes are built via `nodes/_deterministic.deterministic_node(...)`.
The factory's returned closure invokes `wrap_deterministic_node` around the
subprocess + parser body. No per-node edit was needed once the factory was
wired.

| node | kind | cached | reads (state) | writes (state) |
| --- | --- | --- | --- | --- |
| `pickup` | deterministic | no | `slug` (optional); reads `inbox/` / `episodes/` via `scripts.pickup` subprocess | `slug`, `episode_dir`, `pickup.*` |
| `isolate_audio` | deterministic | yes | `episode_dir`, `pickup.raw_path`; spawns `scripts.isolate_audio` (ElevenLabs Scribe — PAID) | `audio.*` |

## Non-factory deterministic nodes (HOM-334 Phase A.5)

Each of these nodes carries an inline `wrap_deterministic_node` call at the
top of its body, gated on `_step_debug.is_enabled()`. Production behavior is
unchanged when `HOMESTUDIO_STEP_DEBUG` is unset.

| node | kind | cached | reads (state) | writes (state) |
| --- | --- | --- | --- | --- |
| `preflight_canon` | deterministic | no | `slug`; reads `scripts/bare_repros/state.json` sidecar; spawns per-watchlist bare-repro scripts | `preflight.checked`, `notices` (sidecar update is a disk side-effect) |
| `rehydrate_skip_phase3` | deterministic | no | `slug`; reads `<edit>/strategy.json` from disk | `edit.strategy`, `notices` |
| `glue_remap_transcript` | deterministic | yes | `slug`; reads `transcripts/raw.json` + `<edit>/edl.json`; spawns `scripts.remap_transcript` | `transcripts.edl_hash`, `transcripts.bodies.final`, `edit.edl` |
| `p4_scaffold` | deterministic | yes | `slug`; spawns `scripts.scaffold_hyperframes` (`npx hyperframes init`) | `compose.scaffold.index_html`, `notices` |
| `p4_catalog_scan` | deterministic | yes | `slug`; spawns `npx hyperframes catalog --json` in a materialized tmpdir | `compose.catalog` |
| `p4_dispatch_beats` | deterministic | no | `compose.plan.beats`, viewport from scaffold HTML | `Command(goto=[Send("p4_beat", …) per beat])` |
| `p4_assemble_index` | deterministic | yes | `compose.plan.beats`, `scenes[*].html`, `compose.captions.html`, `compose.scaffold.index_html` | `compose.index_html`, `compose.assemble` |
| `p4_transitions` | deterministic | yes | `compose.plan.transitions`, `compose.index_html` | `compose.index_html` (rewrites transitions block), `compose.transitions` |
| `p3_inventory` | deterministic | yes | `slug`; spawns `transcribe_batch.py` (ElevenLabs Scribe — PAID) + `pack_transcripts.py` | `edit.transcripts`, `edit.inventory` |
| `p3_render_segments` | deterministic | yes | `slug`, `edit.edl.ranges`; spawns `render.py` | `edit.render` (segments, duration, delta) |
| `p4_materialize_disk` | deterministic | yes | `slug`, `compose.{design,expansion,plan,captions,scaffold,persist,index_html}`, `scenes[*].html`; performs atomic disk writes | `compose.materialize.{materialized_at,files_written}`, `session.project_md` |
| `studio_launch` | deterministic | no | `slug`, `compose.hyperframes_dir`, `compose.preview_port`; spawns `npx hyperframes preview` (Popen) | `compose.{studio_pid,preview_log_path,preview_port,studio_launched_at,studio_reused}` |
| `halt_llm_boundary` | deterministic | no | `edit.*`, `compose.*`, `gate_results` | `notices` (single string explaining halt reason) |

## Gates (HOM-334 Phase A.5)

Twelve graph-level gate nodes; all 12 are wrapped. Eleven inherit
`wrap_deterministic_node` through the base-class hook in
`gates/_base.Gate.__call__` (the topology name `gate_<x>` is derived from
the canonical `gate:<x>` Gate.name with `:` replaced by `_`); two have
custom wrap sites because they bypass `Gate.__call__`:

- `gate_animation_map` overrides `Gate.__call__` to return advisory +
  blocking findings separately; its body carries an inline
  `wrap_deterministic_node` call (animation_map.py).
- `gate_static_guard` is a free function (not a `Gate` subclass) because
  the time-budget sleep doesn't match `Gate.checks` shape; its body
  carries an inline `wrap_deterministic_node` call (static_guard.py).

| node | kind | reads (state) | writes (state) |
| --- | --- | --- | --- |
| `gate_edl_ok` | deterministic | `edit.edl`, `edit.strategy` | appended `gate_results[gate:edl_ok]` |
| `gate_eval_ok` | deterministic | `edit.eval` | appended `gate_results[gate:eval_ok]` |
| `gate_design_ok` | deterministic | `compose.design`, `edit.edl` | appended `gate_results[gate:design_ok]` |
| `gate_plan_ok` | deterministic | `compose.plan`, `edit.edl` | appended `gate_results[gate:plan_ok]` |
| `gate_lint` | deterministic | spawns `npx hyperframes lint` against materialized HF tmpdir | appended `gate_results[gate:lint]` |
| `gate_validate` | deterministic | spawns `npx hyperframes validate` | appended `gate_results[gate:validate]` |
| `gate_inspect` | deterministic | spawns `npx hyperframes inspect` | appended `gate_results[gate:inspect]` |
| `gate_design_adherence` | deterministic | `compose.design.design_md`, `compose.index_html` | appended `gate_results[gate:design_adherence]` |
| `gate_animation_map` | deterministic (custom `__call__`) | spawns `animation-map.mjs` helper against materialized HF tmpdir | appended `gate_results[gate:animation_map]` with advisory + blocking split |
| `gate_snapshot` | deterministic | spawns `npx hyperframes snapshot` | appended `gate_results[gate:snapshot]` |
| `gate_captions_track` | deterministic | spawns headless probe against captions html | appended `gate_results[gate:captions_track]` |
| `gate_static_guard` | deterministic (free function) | sleeps scan window, reads `compose.preview_log_path` | appended `gate_results[gate:static_guard]` |

## Intentionally excluded

Four HITL interrupt nodes already call `langgraph.types.interrupt()` for
human-in-the-loop; wrapping them with a second step-debug interrupt would
fire two interrupts per node and split the operator's resume action across
them (the step-debug resume would also have to mirror the HITL semantics —
neither is desirable). These remain unwrapped:

- `strategy_confirmed_interrupt` — Studio HITL approve/revise for `p3_strategy`.
- `edl_failure_interrupt` — HITL on `gate_edl_ok` exhaustion.
- `eval_failure_interrupt` — HITL on `gate_eval_ok` exhaustion.
- `p3_review_interrupt` — Phase 3→4 bridge HITL (HOM-146).

One retry-loop node is excluded for the same reason as the original Phase A
note:

- `p4_redispatch_beat` — re-authors one offending scene on a cluster-gate
  failure with `iter < 3`. The original `p4_beat` pre/post pair is the
  cheaper observation surface; a fourth interrupt around the retry loop
  would burn operator attention without adding signal. Phase B can revisit
  if a redispatch loop is the only way to reproduce a defect.

## Notes

* **Caching is universal across LLM nodes.** Every LLM node above has
  `cache_policy=` wired in `graph.py`. That is what makes `interrupt()`
  resume safe with `HOMESTUDIO_STEP_DEBUG=1`: when the operator resumes and
  the node body re-executes, the LLM call lands on the `SqliteCache` hit
  path and never re-charges. The `_caching.make_llm_key` fingerprint
  already covers the canonical inputs (brief, state subset, routing
  config) per HOM-157.
* **`p4_beat` is per-Send fan-out.** A single graph step produces N
  parallel `p4_beat` invocations (one per beat in the plan). Step-debug
  fires N pre/post pairs in that step; the runbook spells out how the
  operator pages through them.
* **`gate_animation_map_classify` is conditional.** Only reached when the
  upstream `gate_animation_map` produces `advisory_findings.pending_classify`
  entries. On a clean pass the classifier branch is skipped — no interrupt
  fires for it.
* **Snapshot integration (A4) fires at three points.** After each
  `p4_beat`, after `p4_assemble_index`, and after `p4_transitions`. The PNG
  path is published in the post-node report; the orchestrator reads it
  out-of-band. The deterministic factory + non-factory wrap sites
  introduced in Phase A.5 do NOT add new snapshot points — A4 stays as is.
* **Paid subprocesses are NOT pre-empted.** The pre-interrupt fires
  BEFORE ElevenLabs Scribe (`isolate_audio`, `p3_inventory`) and other
  paid spawns; if the operator aborts on the pre-interrupt no money is
  spent, but if they approve the subprocess runs to completion. There is
  intentionally no pre-execution skip mechanism — operator-driven aborts
  are the only safety net.
