# Step-debug node inventory (HOM-334 Phase A.1)

Canonical list of LLM (and adjacent deterministic) nodes that the
`HOMESTUDIO_STEP_DEBUG=1` interrupt wrapper covers. Phase B step-debug
runs reference this table — the run-log artifact (`docs/step-debug-runs/`)
walks the table top-to-bottom.

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

## Phase 4 LLM chain

| node | kind | brief | schema | cached | upstream interrupt | downstream interrupt | reads (state) | writes (state) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `p4_design_system` | llm | `p4_design_system.j2` | `DesignDoc` | yes | `p3_review_interrupt` (Phase 3→4 bridge, HOM-146) | — | `slug`, transcripts (via `EpisodePaths`) | `compose.design`, `llm_runs` |
| `p4_prompt_expansion` | llm | `p4_prompt_expansion.j2` | `ExpandedPrompt` | yes | — | — | `slug`, `compose.design.design_md` (in-state body, HOM-265) | `compose.expansion`, `llm_runs` |
| `p4_plan` | llm | `p4_plan.j2` | `CompositionPlan` | yes | — | — | `slug`, `compose.design.design_md`, `compose.expansion.expanded_prompt` | `compose.plan`, `llm_runs` |
| `p4_catalog_scan` | deterministic | — | — | yes | — | — | `slug`, `hyperframes/` dir (subprocess `npx hyperframes catalog --json`) | `compose.catalog` |
| `p4_captions_layer` | llm | `p4_captions_layer.j2` | `CaptionsOutput` | yes | — | — | `slug`, `compose.design.design_md`, transcripts JSON path | `compose.captions.html`, `llm_runs` |
| `p4_beat` | llm (per-Send fan-out) | `p4_beat.j2` | `BeatOutput` | yes | — | — | `_beat_dispatch` (per-Send: `scene_id`, `plan_beat`, timing), `compose.design.design_md`, `compose.expansion.expanded_prompt`, `compose.catalog` | `scenes[scene_id].html`, `llm_runs` |
| `p4_assemble_index` | deterministic | — | — | yes | — | — | `compose.plan.beats`, `scenes[*].html`, `compose.captions.html` | `compose.index_html`, `compose.assemble` |
| `p4_transitions` | deterministic | — | — | yes | — | — | `compose.plan.transitions`, `compose.index_html` | `compose.index_html` (rewrites the transitions block), `compose.transitions` |
| `gate_animation_map_classify` | llm (cheap) | `gate_animation_map_classify.j2` | `ClassifyReport` (advisory) | yes | — | — | latest `gate_results[gate:animation_map].advisory_findings.pending_classify`, `compose.design.design_md` (via `EpisodePaths`) | appended `gate_results[gate:animation_map]` record with `decision`/`reason` per flag |

## Notes

* **Caching is universal.** Every LLM node above has `cache_policy=` wired in `graph.py`
  (verified 2026-05-23). That is what makes `interrupt()` resume safe with `HOMESTUDIO_STEP_DEBUG=1`:
  when the operator resumes and the node body re-executes, the LLM call lands on the
  `SqliteCache` hit path and never re-charges. The `_caching.make_llm_key` fingerprint
  already covers the canonical inputs (brief, state subset, routing config) per HOM-157.
* **`p4_beat` is per-Send fan-out.** A single graph step produces N parallel `p4_beat`
  invocations (one per beat in the plan). Step-debug fires N pre/post pairs in that step;
  the runbook spells out how the operator pages through them.
* **`gate_animation_map_classify` is conditional.** Only reached when the upstream
  `gate_animation_map` produces `advisory_findings.pending_classify` entries. On a clean
  pass the classifier branch is skipped — no interrupt fires for it.
* **`p4_redispatch_beat` is intentionally excluded.** It re-authors one offending scene
  using the same `p4_beat` brief shape but is reached only on a gate failure with
  `iter < 3`. The cheaper observation surface for the operator is the original `p4_beat`
  pre/post pair — adding a fourth interrupt around the retry loop would burn operator
  attention without adding signal. Phase B can revisit if a redispatch loop is the only
  way to reproduce a defect.
* **Snapshot integration (A4) fires at three points.** After each `p4_beat`, after
  `p4_assemble_index`, and after `p4_transitions`. The PNG path is published in the
  post-node report; the orchestrator reads it out-of-band.
