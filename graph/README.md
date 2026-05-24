# edit-episode-graph

LangGraph orchestrator for the anticodeguy video editing pipeline.

This package replaces (over v0..v7) the brief-driven `/edit-episode` slash command with a
deterministic graph that has structural enforcement of canon gates, full Studio
visibility, SQLite-checkpointed resumability, and subscription-only multi-CLI LLM access.

See `docs/superpowers/specs/2026-05-02-langgraph-pipeline-design.md` (repo root) for the
full design and phased build sequence.

## v0 scope

Single-node graph wrapping `scripts/pickup.py`. Validates that the harness (state schema,
checkpointer, Studio) works end-to-end on a real episode. No LLM calls. No replacement of
`/edit-episode` — parallel implementation only.

## v1 scope (HOM-73)

Full deterministic-pipeline coverage. Adds three subprocess-wrapped nodes
(`isolate_audio`, `glue_remap_transcript`, `p4_scaffold`), a `preflight_canon`
passthrough stub (real impl in v3), and three conditional skip-edges:

- `skip_phase2?` — ffprobes the container for `ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1`;
  routes around `isolate_audio` when present so ElevenLabs is not called.
- `skip_phase3?` — checks `<episode_dir>/edit/final.mp4`; if missing, halts at the LLM
  boundary (Phase 3 nodes ship in v3) by routing to `halt_llm_boundary`.
- `skip_phase4?` — checks `<episode_dir>/hyperframes/index.html`; if present, ends
  cleanly (already scaffolded).

State namespaces: `audio`, `transcripts`, `compose`. Top-level append-only
`notices` list carries human-readable halt reasons (e.g. "v1 halt: scaffold
complete; next phase `p4_design_system` requires LLM (v2+)").

Happy path on an episode where `final.mp4` already exists: pickup → preflight_canon
(skip_phase2 fires if tag present, otherwise via isolate_audio) → glue_remap_transcript
→ p4_scaffold → END with notice. Re-run is fully idempotent — every script in the
chain self-heals and the skip-edges short-circuit re-work.

**Replaces in `/edit-episode`:** Phase 1, Phase 2, glue, scaffold for users with a
pre-existing `final.mp4`. The slash command is unchanged.

### Headless smoke test

```powershell
$env:PYTHONPATH = "graph/src;."
graph/.venv/Scripts/python.exe graph/smoke_test_v1.py
```

Exercises each routing decision against a fixture episode without invoking ElevenLabs
or `npx hyperframes`.

## Run

```bash
cd graph
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# Bash:       source .venv/Scripts/activate
pip install -e ".[dev]"
langgraph dev
```

Open the Studio URL printed to stdout. Create a thread; run with input `{"slug": "<inbox-stem>"}`
or `{}` for auto-pick.

### Postgres-backed step-debug walkthroughs (HOM-346)

`langgraph dev` runs the in-memory runtime (`langgraph-runtime-inmem`). It
serialises thread state to `graph/.langgraph_api/.langgraph_checkpoint.*.pckl`
on a 10s background flush, but on Windows that state does NOT reliably survive
a hard `langgraph dev` process restart — thread metadata persists, but
checkpoint state and interrupt position are lost, so `Command(resume=…)`
returns `'NoneType' object is not iterable`. This breaks the HOM-334 Phase B
operator step-debug walkthrough, which is structurally multi-session
(pause on interrupt → close Studio → reopen later → resume).

The native LangGraph primitive for persistence-across-restart is `langgraph up`
(Postgres + Redis stack). `POSTGRES_URI` is NOT consumed by `langgraph dev` —
verified against `langgraph-cli` 0.4.24 + `langgraph-runtime-inmem` 0.28.0.

**Setup (one-time):**

```powershell
# 1. Copy env template
copy graph\.env.example graph\.env
# 2. Fill in graph/.env:
#    - POSTGRES_URI=postgres://postgres:postgres@localhost:5433/postgres?sslmode=disable
#    - LANGSMITH_API_KEY=lsv2_...   (langgraph up requires this)
# 3. Bring up the Postgres container
docker compose -f graph/docker-compose.yml up -d langgraph-postgres
```

**Each session:**

```powershell
cd graph
langgraph up --postgres-uri "$env:POSTGRES_URI"
# Studio is now backed by Postgres. Threads survive `langgraph up` restarts.
# Resume an interrupted thread via the Studio UI or
# POST /threads/<id>/runs/wait with body {"command":{"resume":"approved"}}.
```

**Decision (HOM-346):** Postgres is required for step-debug walkthroughs
(HOM-334 Phase B) but is NOT mandated for routine `langgraph dev` runs.
Rationale: `langgraph up` requires Docker + a LangSmith API key, which
adds operator friction we don't want to impose on every Phase 4 dispatch.
The two-config split is acceptable because (a) the underlying graph code
is identical, (b) the node-result cache (`graph/.cache/langgraph.db`) is
shared and orthogonal — re-bootstrap on `langgraph dev` after a restart
costs $0 in API spend; only the interrupt position is lost.

**Verification:** `graph/scripts/verify_postgres_resume.py` proves the
checkpointer round-trips correctly across distinct Python processes:

```powershell
# No Docker required — uses langgraph-checkpoint-sqlite (bundled):
graph\.venv\Scripts\python.exe graph\scripts\verify_postgres_resume.py --backend sqlite
# Against the docker-compose Postgres:
graph\.venv\Scripts\python.exe graph\scripts\verify_postgres_resume.py --backend postgres
```

Expected last line: `"verdict": "PASS"`. The script spawns two real
subprocesses (start → exit → resume in a fresh interpreter) so it
genuinely simulates a Studio restart — there is no shared in-process
state between the two phases.

**Verification scope — what's NOT verified end-to-end on this machine.**
Docker Desktop is not installed in the environment HOM-346 landed from,
so the full `langgraph up --postgres-uri ...` CLI path was not exercised
against a live Postgres container. What IS verified: the SQLite round-trip
above (`--backend sqlite`) proves `BaseCheckpointSaver` honors its
cross-process contract — the same contract `langgraph up` relies on to
keep thread state alive across container restarts. The Postgres-specific
wiring (compose container health, `langgraph up` consuming
`--postgres-uri`, Studio attaching to the durable backend) is documented
but unobserved. Per CLAUDE.md §"LangGraph primitives", this caveat is the
explicit "this is the unverified part" signpost — operators bringing up
the Docker stack for the first time should confirm Studio actually picks
up a paused thread after `langgraph up` restart before relying on it for
a long step-debug walkthrough.

## Tier mapping

LLM nodes pick a `tier` (or pin an explicit `model`); the backend resolves the tier
to a concrete model id at dispatch time. Three tiers, defined in
`backends/claude.py::_MODEL_BY_TIER` (HOM-115):

| Tier        | Claude model                  | Codex model | When to use |
| ----------- | ----------------------------- | ----------- | --- |
| `cheap`     | `claude-haiku-4-5-20251001`   | `gpt-5-mini`| Mechanical structured-write, tool loops with cheap retry, smoke |
| `smart`     | `claude-sonnet-4-6`           | `gpt-5`     | General reasoning, EDL-style numeric precision work |
| `expensive` | `claude-opus-4-7`             | `gpt-5`*    | Highest-stakes creative judgment (design / expansion / plan / beat / captions) |

\* Codex offers two production models, so `expensive` aliases `smart` (gpt-5) on the
Codex backend; cross-backend failover from a claude `expensive` request lands on
gpt-5 — the closest available.

**Creative LLM nodes default to `expensive`.** Per memory
`feedback_creative_nodes_flagship_tier` and the HOM-154 retro: cheap-tier output
on creative work hollows out brand-defining decisions and triggers gate redispatch
loops costing more than one successful Opus run. Do not silently downgrade
`p3_strategy`, `p4_design_system`, `p4_prompt_expansion`, `p4_plan`,
`p4_beat`, `p4_redispatch_beat`, or `p4_captions_layer` from `expensive` without
running a recorded fixture-replay diff against the canonical fixture episode and
eyeballing the output (see the cost-experiment follow-up ticket to HOM-115).

**`tier:` vs explicit `model:`.** Prefer `tier:` — it documents intent
(*"this is creative work"*) and survives model id changes when Anthropic ships a
new Sonnet/Opus revision. Use an explicit `model:` pin only for transient cost
experiments (e.g. comparing Haiku vs Opus on a specific node against a fixture
recording) — pinning bypasses the tier semantics and silently desyncs from any
future tier remap. The HOM-115 cleanup dropped every then-current model pin in
`graph/config.yaml` because each pin's intent is now expressible via `tier:`.

## Layout

```
graph/
├── pyproject.toml
├── langgraph.json
├── .env                                  # process env for `langgraph dev` (empty in v0)
└── src/edit_episode_graph/
    ├── state.py                          # GraphState TypedDict (v0: pickup namespace only)
    ├── graph.py                          # build_graph() + module-level `graph`
    ├── nodes/
    │   ├── _deterministic.py             # factory for class-1 nodes (v1+)
    │   └── pickup.py                     # wraps scripts/pickup.py
    ├── gates/_base.py                    # gate skeleton (real gates v3+)
    ├── briefs/                           # Jinja2 templates for LLM nodes (v2+)
    └── backends/                         # LLMBackend protocol + per-CLI impls (v2+)
```
