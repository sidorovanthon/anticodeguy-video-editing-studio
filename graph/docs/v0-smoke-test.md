# v0 smoke test results

**Date:** 2026-05-02
**Linear:** HOM-84
**Spec:** `docs/superpowers/specs/2026-05-02-langgraph-pipeline-design.md` §9.8
**Run by:** initial v0 validation pass on Windows 11 / Python 3.12.0

## Summary

All 6 DoD criteria from spec §9.8 pass after **three corrections** to the v0 implementation that landed via PR #27. The corrections ship in this PR. Runtime in v0 is `langgraph-runtime-inmem` (default for `langgraph dev`); persistent SQLite checkpointing is deferred — it requires Postgres or explicit cloud config and is out of scope until v6+.

## DoD checklist

| # | Criterion (per spec §9.8) | Status | Evidence |
|---|---------------------------|--------|----------|
| 1 | `langgraph dev` starts cleanly; Studio UI opens | ✅ | Boot log shows `🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` and `graph_id=edit_episode` loads via `module=edit_episode_graph.graph` with no errors. In-memory runtime + cron + queue + workers all start. |
| 2 | Real `inbox/<slug>.<ext>` → `episodes/<slug>/raw.<ext>` | ✅ | Server-side run via `POST /threads/<id>/runs/wait` with `inbox/raw.mp4` produced `episodes/raw-3/raw.mp4` (slug fell to legacy `raw-N` because user-supplied `script.txt` had stem `script`, not `raw` — pickup pairs by stem, not by directory). |
| 3 | Empty `inbox/` + no slug → `pickup.idle = true` | ✅ | Programmatic `pickup_node({})` against emptied inbox returns `pickup.idle = true`, graph routes to END. |
| 4 | Re-run with same slug → `pickup.resumed = true`, no duplication | ✅ | `pickup_node({"slug": "raw-2"})` returns `resumed: true`; `episodes/raw-2/` still has exactly 1 `raw.*` file. |
| 5 | Failure case → `errors[]` populated, run terminates | ✅ | Decoy `raw.mov` planted next to existing `raw.mp4` in episode dir; resume produced `errors: [{node: "pickup", message: "pickup error: ambiguous: multiple raw.* in episodes/raw-2/", ...}]`. |
| 6 | Checkpoint persisted; thread history visible in Studio | ✅ (revised) | Original spec text said "SQLite at `graph/.langgraph_api/checkpoints.sqlite`" — see [§Spec correction: checkpointer](#spec-correction-checkpointer). Verified: `GET /threads/<id>/state` after a server-side run returns the full GraphState (`slug`, `episode_dir`, `pickup`, `errors`) — runtime persistence is wired. Programmatic `compiled.get_state(cfg)` against an explicit `InMemorySaver` shows the same. |

## Corrections applied (also in this PR)

### 1. `langgraph.json` — module-import path

**Before:** `"edit_episode": "./src/edit_episode_graph/graph.py:graph"`
**After:** `"edit_episode": "edit_episode_graph.graph:graph"`

The path-style entry made `langgraph dev` load the module via `importlib` against a file path, which strips the parent-package context and breaks the `from .nodes.pickup import pickup_node` relative import. Module-style import works because the package is installed via `pip install -e .`.

### 2. `graph.py` — drop user checkpointer

**Before:**
```python
return g.compile(checkpointer=SqliteSaver.from_conn_string(str(_CHECKPOINT_PATH)))
```
**After:**
```python
return g.compile()
```

Two compounding problems with the spec sketch:

- `SqliteSaver.from_conn_string()` is a `@contextmanager`, not a saver instance. It yields a saver inside a `with` block; binding it to `compile(checkpointer=...)` raised `TypeError: Invalid checkpointer ... Received _GeneratorContextManager`.
- Even after constructing `SqliteSaver(sqlite3.connect(...))` directly, the langgraph-api runtime (used by `langgraph dev`) **rejects** any user-bound checkpointer with a hard `ValueError`: "With LangGraph API, persistence is handled automatically by the platform". Persistence backend is configured via env vars (`POSTGRES_URI`) — out of scope for v0.

Direct invocation contexts that need persistence (smoke tests, ad-hoc scripts) attach an explicit checkpointer at compile time instead — see `smoke_test_v0.py` case 6 for the pattern.

### 3. `nodes/pickup.py` — already factored via `deterministic_node` (HOM-82)

No change in this PR; mentioned for completeness.

## Spec correction: checkpointer

Spec §9.6 and §9.8 case 6 should be updated:

- §9.6 sketch shows `SqliteSaver.from_conn_string(...)` bound at compile — **wrong** for both reasons above.
- §9.8 case 6 expects "SQLite checkpoint at `graph/.langgraph_api/checkpoints.sqlite`" — **wrong**: under `langgraph dev` the runtime is in-memory; `.langgraph_api/` is the runtime's own scratch dir, not our checkpoint. The user-visible signal is "thread state survives across requests within the dev session" (verified via `GET /threads/<id>/state`).

A persistent SQLite (or Postgres) checkpointer is a v6+ concern, paired with the HITL `interrupt()` work that needs cross-process resumability.

## Files added/modified in this PR

| Path | Change |
|------|--------|
| `graph/langgraph.json` | path → module import |
| `graph/src/edit_episode_graph/graph.py` | remove SqliteSaver; document why |
| `graph/smoke_test_v0.py` | new — headless cases 2/3/4/5/6 reproducible |
| `graph/docs/v0-smoke-test.md` | this report |

## How to reproduce

```powershell
cd graph
.\.venv\Scripts\python.exe smoke_test_v0.py        # cases 2,3,4,5,6 headless
.\.venv\Scripts\langgraph.exe dev --no-browser     # case 1: Studio + boot
# In another shell, drop a video into ../inbox/, then visit the Studio URL.
```

The smoke test consumes `inbox/raw.mp4` for case 2; restore it from `episodes/raw-2/raw.mp4` (or whatever `raw-N` was created) before re-running.

## Out of scope / known gaps

- Pickup pairs `<video>.mp4` ↔ `<video>.txt` by stem. A generic `script.txt` next to `raw.mp4` does **not** count as paired and triggers the legacy stem-based slug fallback. Documented behavior, not a bug — but worth flagging for future test fixtures.
- The `.langgraph_api/` scratch dir created by `langgraph dev` triggered watchfiles hot-reload churn during the failed-load attempts (server kept rebuilding the failing graph). After the load fix the loop stops; long-term, adding `.langgraph_api/` to a watch-ignore would harden this. Not blocking for v0.
