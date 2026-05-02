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
