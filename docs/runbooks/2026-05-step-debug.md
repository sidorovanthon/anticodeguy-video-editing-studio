# Step-debug runbook (HOM-369 model)

Pause-between-nodes walkthrough of the LangGraph pipeline on a real episode. Used during the HOM-334 Phase B audit to surface canon-vs-orchestrator drift before the next paid prewarm.

This runbook supersedes the original PR #183/#184 version, which wrapped every node body with an in-place `interrupt()` call. That approach was architecturally wrong (HOM-369 retro): the wrapper fired `interrupt()` AFTER the body ran but BEFORE the function returned, which LangGraph treats as a dynamic interrupt — on resume the entire body re-executes, producing a second paid LLM dispatch and non-deterministic committed state. The current model uses the native `interrupt_after="*"` compile-time parameter, which pauses at the superstep boundary AFTER state has already been committed.

---

## How it works

`graph/src/edit_episode_graph/graph.py::build_graph()` reads `HOMESTUDIO_STEP_DEBUG` at compile time:

```python
step_debug_on = os.environ.get("HOMESTUDIO_STEP_DEBUG") == "1"
compile_kwargs = {"cache": _build_cache()}
if step_debug_on:
    compile_kwargs["interrupt_after"] = "*"  # langgraph.types.All
return build_graph_uncompiled().compile(**compile_kwargs)
```

When the flag is unset (default — production), no static interrupts are wired. When set, LangGraph pauses after every node via the native `pregel._loop.should_interrupt` boundary check. The check fires BETWEEN ticks, AFTER the previous tick's results are already in the checkpoint and the `SqliteCache`. On resume only the next tick executes — the previous node does NOT re-execute.

This is structurally different from the dynamic `interrupt()` primitive used by the four HITL nodes (`strategy_confirmed_interrupt`, `p3_review_interrupt`, `eval_failure_interrupt`, `edl_failure_interrupt`). Those nodes' bodies are *only* an `interrupt()` call — re-execution on resume is a no-op. Static interrupts plus dynamic HITL interrupts coexist; neither interferes with the other.

Empirical billing test: `tests/test_step_debug_billing.py::test_no_double_llm_dispatch_under_static_interrupts` asserts that the fixture `cache.db` (recorded under the static-interrupt model) carries exactly ONE `llm_runs` append per LLM node — not two. Run it at $0 against the committed fixture:

```powershell
& 'C:\Users\sidor\repos\anticodeguy-video-editing-studio\graph\.venv\Scripts\python.exe' `
    -m pytest tests/test_step_debug_billing.py -v
```

---

## Operator workflow

Stack: TrueNAS at `http://192.168.1.115:8124`. Never use `langgraph dev` for step-debug (checkpoint loss on restart — see CLAUDE.md §"Thread-state persistence across Studio restarts"). The env file on TrueNAS (`/var/lib/homestudio-langgraph/.env`) already carries `HOMESTUDIO_STEP_DEBUG=1`.

1. **Drop the episode.** Move the raw video into `S:\anticodeguy-video-editing-studio\inbox\` (SMB share over TrueNAS). For prewarm sessions you may also pre-stage `script.txt`, `isolated.mp3`, `transcript.json` per the HOM-334 §B-prefab convention.

2. **Start a thread in Studio.** Browse to `http://192.168.1.115:8124`, pick the graph, POST a run with `{"slug": "<slug>"}`. The run pauses after `pickup`.

3. **At every pause, run the observability helper** from the dev box:

   ```powershell
   cd C:\Users\sidor\repos\anticodeguy-video-editing-studio
   $env:PYTHONPATH = "graph\src"
   & 'graph\.venv\Scripts\python.exe' -m scripts.step_debug_observe `
       --thread-id <thread> `
       --node <node_name>
   ```

   This dumps four artifacts to `tmp/step-debug/<thread>/<node>/`:

   | Artifact            | Source                                             | What it tells you                                                                  |
   | ------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------- |
   | `brief.md`          | Rendered Jinja brief via prod `_BRIEF_ENV`         | What the LLM saw (LLM nodes only). Diff vs canon §X to spot embed-vs-cite drift.   |
   | `context.json`      | The render context dict                            | Every state field the brief consumed. Surfaces "missing key" silent fallbacks.    |
   | `post_output.json`  | State-delta vs the prior checkpoint                | What this node committed to state. Pair with on-disk side effects.                |
   | `cli.txt`           | Resolved tier/model/timeout from `graph/config.yaml` | What the router would have dispatched (or did dispatch on a real call).            |

   Deterministic nodes (no Jinja brief) get only `post_output.json` and `cli.txt`. That's by design — the 4-point report's "What it did" is the substantive review for them; the brief diff is N/A.

   **Caveat — `brief.md` is an approximation, not a byte-for-byte replay.** `scripts/step_debug_observe.py::_render_brief_for_node` splats the committed state directly into the Jinja template under the prod `_BRIEF_ENV` (which uses Jinja's permissive `Undefined`, silently rendering empty for missing keys). Production nodes build a node-specific `_render_ctx` that often derives fields from upstream state at dispatch time — those derived fields are NOT reconstructible post-hoc and may silently render as empty in `brief.md`. Treat the rendered brief as a high-fidelity approximation for spotting canon embed-vs-cite drift; for byte-exact reproduction reach into the node's `_render_ctx` helper directly.

4. **Write the 4-point report** (canon / what-it-did / clean-session / discrepancy) into `docs/step-debug-runs/2026-05-XX-<slug>.md`. Use the artifacts as evidence; cite line refs to canon. For deterministic / orchestrator-internal nodes mark clean-session as **"N/A — no canon analog, orchestrator-only"** rather than skipping the section.

5. **Resume the thread.** From the dev box:

   ```powershell
   $apiKey = $env:LANGSMITH_API_KEY
   $body = @{ command = @{ resume = "approved" } } | ConvertTo-Json
   Invoke-RestMethod "http://192.168.1.115:8124/threads/<thread>/runs" `
       -Method Post `
       -Headers @{ "Content-Type" = "application/json" } `
       -Body $body
   ```

   Or from Studio: click "Resume" with payload `{"resume": "approved"}`. For HITL nodes (`strategy_confirmed_interrupt`, `p3_review_interrupt`) the payload is the same string token.

6. **Stop at any time** by issuing `{"resume": "abort"}` or by killing the run from Studio. Thread + cache persist across restarts (TrueNAS LangGraph Self-Hosted Lite, HOM-347).

---

## Empirical validation

The HOM-369 acceptance criteria require validating that the static-interrupt model does NOT double-charge per node. Two checks, both included in this PR:

1. **Wiring smoke** (always green, no fixture needed):

   ```powershell
   & 'graph\.venv\Scripts\python.exe' -m pytest `
       tests/test_step_debug_billing.py::test_interrupt_after_wired_only_under_step_debug_flag -v
   ```

   Asserts that the flag toggles `compiled.interrupt_after_nodes` between `[]` (production) and `["*"]` (step-debug).

2. **Empirical billing** (replay against committed `cache.db`, $0):

   ```powershell
   & 'graph\.venv\Scripts\python.exe' -m pytest `
       tests/test_step_debug_billing.py::test_no_double_llm_dispatch_under_static_interrupts -v
   ```

   Walks `p3_pre_scan` and `p3_strategy` via the fixture-replay harness, counts `llm_runs` appends in each recorded cache row, asserts each is exactly 1. The reverted PR #183/#184 wrapper would have produced 2 — running this test in a future regression session catches that regression before it lands.

For paid real-tier validation (operator-only, not CI), record a fresh fixture under the static-interrupt model and verify:

```powershell
$env:HOMESTUDIO_STEP_DEBUG = "1"
$env:HOMESTUDIO_TEST_MODE = "record"
& 'graph\.venv\Scripts\python.exe' -m pytest `
    tests/test_graph_replay.py -k "p3_pre_scan or p3_strategy" -v
# Then re-run in replay mode and inspect llm_runs counts:
$env:HOMESTUDIO_TEST_MODE = "replay"
& 'graph\.venv\Scripts\python.exe' -m pytest tests/test_step_debug_billing.py -v
```

Anthropic billing for the recording run should show exactly one dispatch per LLM node walked, not two.

---

## Why we don't wrap node bodies

Trying to wrap the body with `interrupt({...})` is appealing — it would let us emit a rich JSON payload at the pause directly from inside the node. Don't do it. The semantic contract is:

* **Dynamic `interrupt()` inside a body:** raises `GraphInterrupt`, body never returns, writes never commit, cache never writes. On resume the body re-executes from the top. For an LLM node: cache miss, second dispatch, different committed state. Empirically verified in Run 4 of `docs/step-debug-runs/2026-05-23-pending-slug.md` (thread `019e58ea-19c9-76f3-bf0a-13ef43d4d328`): `p3_pre_scan` first dispatch showed 4 slips, committed state had 3 with one slip's reason rewritten; `p3_strategy` first dispatch showed 7 takes + neutral grade, committed state had 6 annotated takes + warm-teal grade. Two paid dispatches per node.
* **Static `interrupt_after` at compile time:** raises `GraphInterrupt` BETWEEN ticks, after the previous tick committed to checkpoint and cache. On resume only the next tick executes. One paid dispatch per node. The rich payload is built out-of-band by the observability helper, which reads committed state via `client.threads.get_state(thread_id)`.

The "rich payload at the pause" UX is preserved — it just moves from graph-side to orchestrator-side. The graph stays clean (no instrumentation, no per-node hooks); observability is a read-only operation against committed state. This is the same pattern CLAUDE.md §"LangGraph primitives — search docs before rolling custom" preaches: use the native primitive, build orchestration on top of state inspection.

---

## References

- HOM-369 brief — the retro that produced this runbook.
- HOM-334 v3 brief (amended in the HOM-369 PR) — operational umbrella for the walkthrough.
- `graph/src/edit_episode_graph/graph.py::build_graph` — the wiring.
- `scripts/step_debug_observe.py` — the observability helper.
- `tests/test_step_debug_billing.py` — empirical billing assertion.
- CLAUDE.md memory `feedback_langgraph_static_interrupts_for_step_debug` — short-form rule.
- CLAUDE.md memory `feedback_langgraph_native_primitives` — the broader principle this case study illustrates.
- LangGraph: `langgraph.graph.state.StateGraph.compile` accepts `interrupt_after: All | list[str] | None`; `All = Literal["*"]`. `pregel._loop.should_interrupt` is the boundary-check site.
