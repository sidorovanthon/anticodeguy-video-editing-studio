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
