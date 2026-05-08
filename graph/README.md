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
