# Step-debug runbook — `HOMESTUDIO_STEP_DEBUG=1` (HOM-334 Phase A)

Operator-driven step-debug of the production LangGraph pipeline. Pauses
before and after every step-debug-eligible node (see
`docs/step-debug-inventory.md`), publishes a structured stop-report the
orchestrator session reads, lets the operator triage in conversation,
and resumes via native LangGraph `Command(resume=...)`.

The goal is **context-pass audit** — at each pre-node interrupt, the
operator and orchestrator inspect what the LLM is about to see, compare
it to what a canonical free-form `/hyperframes` or `/video-use` agent
would see at the same point, and capture the diff. Findings drive Phase
B (HOM-334 §B) without burning paid `record_fixture` prewarms on
brief-edit / gate-carve-out cycles.

## Prerequisites

* A fixture or inbox episode in scope. The canonical fixture
  (`tests/fixtures/episodes/canonical-portrait-talking-head/`) is the
  cheapest target — its `cache.db` is committed, so every LLM dispatch
  hits the cache on resume and the run costs $0.
* `langgraph dev` running (see CLAUDE.md §"Studio replay (operator runbook)").
* Orchestrator session (this assistant) attached to the same thread.

## Start a step-debug run

```powershell
# 1. Seed the cache (fixture replay — $0).
copy tests\fixtures\episodes\canonical-portrait-talking-head\cache.db `
     graph\.cache\langgraph.db
$env:HOMESTUDIO_PROJECT_ROOT = "$PWD\tests\fixtures"

# 2. Turn on step-debug.
$env:HOMESTUDIO_STEP_DEBUG = "1"
# Optional: pin the dump dir somewhere other than tmp/step-debug/.
# $env:HOMESTUDIO_STEP_DEBUG_DUMP_ROOT = "$PWD\.run-logs\step-debug"

# 3. Launch the graph.
cd graph
.venv\Scripts\langgraph.exe dev --allow-blocking --no-browser

# 4. In a separate terminal (or Studio UI): POST a run with
#    slug = canonical-portrait-talking-head
```

Once the first node interrupts, the orchestrator session reads the
stop-report payload (see §"What the stop-report contains" below) and
walks the operator through the resume vocabulary.

To run against a live `inbox/` episode instead of the fixture: drop the
`HOMESTUDIO_PROJECT_ROOT` override, drop the `copy` cache-seed step
(but expect real LLM charges on the first walk-through if the cache.db
is cold).

## What the stop-report contains

### Pre-node payload

```jsonc
{
  "phase": "pre",
  "node": "p4_beat",
  "ts": "2026-05-23T07:30:00+00:00",
  "brief_path": "graph/src/edit_episode_graph/briefs/p4_beat.j2",
  "brief_rendered_excerpt": "<first 4000 chars of the rendered Jinja>",
  "context_keys": ["beat_index", "design_md_body", "expanded_prompt_body", ...],
  "context_dump_path": "tmp/step-debug/<thread>/p4_beat/pre_context.json",
  "expected_schema": "edit_episode_graph.schemas.p4_beat.BeatOutput",
  "upstream_gate_findings": [{"gate": "gate:lint", "passed": true, ...}],
  "resume_vocabulary": ["approve", "rerun-with-edit:<state-patch-json>", "abort"]
}
```

* `brief_rendered_excerpt` — first 4000 chars of the rendered brief.
  Reads the *exact* string the sub-agent will receive. If it's
  truncated, read the full text from `context_dump_path`.
* `context_dump_path` — full pre-node render context dumped as JSON
  (this is what the brief consumes, plus the top-level state-key list
  for orientation).
* `expected_schema` — fully-qualified Pydantic class name. Use it to
  sanity-check what shape the LLM is expected to return.
* `upstream_gate_findings` — last 3 `gate_results` entries. Empty `[]`
  on a clean first pass; populated when the gate cluster has fired.

### Post-node payload

```jsonc
{
  "phase": "post",
  "node": "p4_beat",
  "ts": "...",
  "output_excerpt": "<first 4000 chars of stringified output>",
  "output_dump_path": "tmp/step-debug/<thread>/p4_beat/post_output.json",
  "tokens": {"input": 12345, "output": 678, "backend": "claude", "model": "..."},
  "latency_s": 42.7,
  "snapshot_png_path": "tmp/step-debug/<thread>/p4_beat/2026-05-23T07-30-00.png",
  "lint_findings": [],
  "resume_vocabulary": ["approve", "rerun-with-edit:<state-patch-json>", "abort"]
}
```

* `output_dump_path` — full parsed output (Pydantic `model_dump` when
  the schema matched, raw text otherwise).
* `tokens` — pulled from the last entry in `state.llm_runs`. `None`
  for deterministic nodes.
* `snapshot_png_path` — set after `p4_beat`, `p4_assemble_index`,
  `p4_transitions`. `None` everywhere else, and `None` when the
  `npx hyperframes snapshot` call failed (see stderr for reason —
  snapshot failures never halt the graph).

### Where artifacts land

```
tmp/step-debug/
  <thread_id>/
    <node>/
      pre_context.json   # full pre-node render context
      post_output.json   # full post-node parsed output
      <iso-timestamp>.png  # snapshot (p4_beat / p4_assemble_index / p4_transitions only)
```

`tmp/` is gitignored. Override the root with
`$env:HOMESTUDIO_STEP_DEBUG_DUMP_ROOT`. Each `langgraph dev` thread
gets its own subdirectory keyed by `thread_id`.

## Resume vocabulary

The orchestrator session resolves the operator's intent into one of
three resume payloads:

### `approve` — continue

Empty payload, `"approve"`, `"approved"`, `"yes"`, `"ok"`, `True`, or
`{"approved": True}`. The wrapper interprets all of these as approval;
the graph advances to the next node.

```python
client.runs.create(thread_id, assistant_id, input=None, command={"resume": "approved"})
```

### `abort` — terminate cleanly

`"abort"`, `"stop"`, `"cancel"`, `"halt"`, or `{"action": "abort"}`.
The wrapper raises `StepDebugAborted`; LangGraph treats it as a
terminal exception, the run halts, and no further state is committed.

```python
client.runs.create(thread_id, assistant_id, input=None, command={"resume": "abort"})
```

### `rerun-with-edit:<state-patch-json>` — mutate state and re-run the producer

This is **orchestrator-side dispatch**, NOT graph-side code. The
wrapper passes the resume payload through (does not abort, does not
"approve"); the orchestrator then uses native LangGraph midpoint
dispatch per CLAUDE.md §"LangGraph primitives":

```python
# 1. Mutate the relevant state slice with the operator's patch.
client.threads.update_state(
    thread_id,
    values={"compose": {"plan": {"beats": [..., {"duration": 4.0}, ...]}}},
    as_node="p4_plan",          # name of the node whose output we're overriding
)

# 2. Re-launch the run; graph treats `p4_plan` as just-completed and
#    follows its outgoing edge, re-running `p4_dispatch_beats` / `p4_beat`
#    against the patched plan.
client.runs.create(thread_id, assistant_id, input=None)
```

#### Concrete example — extend beat 2 by 1 second

Step-debug stops the run at the **post** interrupt of `p4_plan`. The
operator says "beat 2 is too tight, give it another second". The
orchestrator:

1. Reads the `output_dump_path` from the post-payload to see the
   current plan.
2. Builds a JSON patch overriding `compose.plan.beats[2].duration`.
3. Calls `update_state(as_node="p4_plan", values=<patch>)`.
4. Calls `runs.create(thread_id, ..., input=None)` — the graph picks
   up just downstream of `p4_plan` (`gate_plan_ok`), re-fans out the
   beats against the new durations, and step-debug stops again at the
   pre-interrupt of the next node.

No code changes in the graph layer are needed for this — the wrapper
already publishes `rerun-with-edit:<state-patch-json>` in
`resume_vocabulary` so the orchestrator knows the option is supported.
The graph-side wrapper is intentionally agnostic about WHAT the patch
contains; that's a conversation between the operator and the
orchestrator.

## Idempotency on resume (HOM-334 acceptance §1)

LangGraph's `interrupt()` is replay-safe by construction: when the
thread resumes, the node body re-executes from the start, and
`interrupt()` returns the resume payload **without re-firing the
side-effects above it** (the publish + disk write happen on the
first invocation only — replay sees the cached `__interrupt__` value).

Every LLM node in the inventory (`docs/step-debug-inventory.md`)
carries `cache_policy=` in `graph.py`, so the LLM dispatch lands on
the `SqliteCache` hit path on replay. No re-charge: the
`_caching.make_llm_key` fingerprint covers (brief snapshot, state
subset, routing config) per HOM-157, and the operator's resume
payload does not change any of those inputs.

If you ever observe a paid re-dispatch on resume:

* Check the node has `cache_policy=` wired in `graph.py`. Every LLM
  node currently does — a missing one is a bug, not expected.
* Check `make_llm_key` extras for the node — is the resume payload
  somehow leaking into the fingerprint?

## Capturing observations for Phase B

Per HOM-334 §B.2, findings get captured **as ordered Linear comments
on HOM-334**, not as new tickets. Premature ticket-splitting is the
failure mode the methodology replaces.

The single end-of-session artifact is
`docs/step-debug-runs/2026-05-XX-<slug>.md` — one row per node
walked, with the operator's verdict + context-gap notes.

Example shape (canonicalize once the first session completes):

```markdown
## p3_pre_scan

- Tokens: 1,234 in / 567 out (claude / claude-haiku-4-5)
- Latency: 8.2s
- Brief excerpt: ...
- Context the LLM saw: `takes_packed.md` path, slips=[]
- Canonical free-form video-use Step 2 sees: takes_packed.md content +
  Phase 3 plan brief + operator intent statement
- Gap: <describe>
- Operator verdict: approve
```

Capture commands (PowerShell, run in main repo root):

```powershell
# Read the pre payload's full context dump
Get-Content tmp\step-debug\<thread>\p4_beat\pre_context.json | Out-String

# Read the post output dump
Get-Content tmp\step-debug\<thread>\p4_beat\post_output.json | Out-String

# View a snapshot PNG inline in the orchestrator session
# (the assistant uses Read on the path published in snapshot_png_path)
```

After the session ends, attach the artifact path as an HOM-334 Linear
comment via `linear-pp-cli`:

```powershell
& 'C:\Users\sidor\go\bin\linear-pp-cli.exe' issues comment HOM-334 `
    --body "Step-debug run docs/step-debug-runs/2026-05-23-canonical.md: ..."
```

## Negative-result escape hatch (HOM-334 §"Non-acceptance signals")

If after the first full session there are no clear context-gap
findings, the hypothesis is wrong and the next iteration is **visual
feedback loop integration** (retro `Secondary observation` line 113) —
give the LLM nodes a `snapshot --at <t>` tool in their `allowed_tools`
and let them self-eval before persisting. Document the negative result
in the step-debug artifact and pivot.

## References

* HOM-334 ticket body (`& linear-pp-cli.exe issues HOM-334 --json`).
* `docs/step-debug-inventory.md` — the canonical node list this
  runbook walks.
* CLAUDE.md §"LangGraph primitives" — native `interrupt()` +
  `update_state(as_node=...)` + `runs.create()`.
* CLAUDE.md §"Studio replay (operator runbook)" — fixture cache.db
  seeding + `HOMESTUDIO_PROJECT_ROOT`.
* `docs/retros/retro-2026-05-17-gate-animation-map-canonical-false-positives.md`
  — the retro that established free-form `/hyperframes` ships working
  videos because the agent has full context + visual self-eval + lint
  triage; the graph has none of those. Step-debug is the operator
  step toward bridging that gap.
