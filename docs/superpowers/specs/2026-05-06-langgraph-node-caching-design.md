# LangGraph Node-Level Caching — Design

**Date:** 2026-05-06
**Status:** Draft (awaiting user review)
**Linear:** [HOM-132](https://linear.app/home-budget/issue/HOM-132/v-adopt-langgraph-node-level-caching-for-pipeline-idempotency-epic) — epic
**Scope:** Adopt LangGraph's native node-level caching primitive (`CachePolicy` + `SqliteCache`) to make graph re-runs on the same `slug` resume from the first missing artifact without re-executing completed nodes. Closes the gap between CLAUDE.md §Idempotency (which claims this property) and current behaviour (which does not deliver it).

---

## 1. Problem

Re-running the graph with the same `slug` is supposed to "resume from the first missing artifact" (CLAUDE.md §Idempotency). It does not. Today every node re-executes on every run — the only thing keeping costs down is happenstance: `route_after_preflight` short-circuits Phase 3 only when `final.mp4` is on disk, and Phase 4 has no equivalent skip-edge between its internal LLM nodes (`p4_design_system` → `p4_prompt_expansion` → `p4_plan` → ...). Empirically observed 2026-05-04: a re-run on a slug with successful Phase 3 + DESIGN.md + expanded-prompt.md from a prior session was attempting to re-run from `pickup` → `isolate_audio`, which would have re-spent ElevenLabs Scribe credits and re-dispatched Opus on canon work that was already completed.

The original LangGraph migration spec (`docs/superpowers/specs/2026-05-02-langgraph-pipeline-design.md` §4.5) framed idempotency as "conditional edges, not in-node early returns". That framing handles coarse phase boundaries (Phase 3 → Phase 4 skip when `final.mp4` exists) but does not cover within-phase node-to-node skipping. Two Phase 4 LLM nodes (`p4_beat`, `p4_captions_layer`) carry self-rolled "poor-man's cache" stubs in their bodies with literal comments pointing at HOM-132 — confirmation that the gap was known at write-time and deferred.

## 2. Goals

The value is in **resume scenarios** — situations where a re-run of the graph has real work to do, but should not redo the work already done in prior runs:

1. **Forward continuation across sessions.** A slug whose Phase 3 completed yesterday reaches Phase 4 today: Phase 3 nodes cache-hit, Phase 4 actually runs. This is the common case and the original CLAUDE.md §Idempotency promise.
2. **Crash / interrupt recovery.** A run that died mid-Phase-4 (e.g. `gate:lint` failed and the user aborted) resumes from the failing node when restarted: all upstream nodes cache-hit, no Scribe re-spend, no Opus re-dispatch.
3. **Targeted re-do.** Deleting or editing one upstream artifact (e.g. user re-cuts the EDL by hand, or wipes `DESIGN.md` to force a fresh palette) invalidates exactly the cache entries that depend on the changed file; downstream propagates naturally.
4. **Correctness property — no work without input change.** A re-run on identical inputs performs no LLM invocations and no expensive subprocesses (ffmpeg, ElevenLabs). This is the *test* that the cache is wired correctly, not a primary use case — but it must hold, otherwise #1–#3 silently regress to "everything re-runs".

Plus two implementation constraints:

5. Cache invalidation has a documented escape hatch (per-node version bump + manual cache-DB nuke).
6. Implementation uses **only** native LangGraph primitives plus one minimal helper module — no parallel cache framework, no on-disk artifact-existence checks in node bodies.

## 3. Non-goals

- Replacing `route_after_preflight` skip-edges. They remain correct as routing — they short-circuit Phase 3 when `final.mp4` is on disk; caching is an orthogonal node-body optimisation.
- Caching gates, interrupts, `pickup`, `studio_launch`, or fan-out dispatch nodes (see §6).
- Cross-episode cache sharing. Each `slug` is its own namespace.
- Replacing the `SqliteSaver` checkpointer. Cache and checkpointer are independent stores.

## 4. Canon survey — what LangGraph provides

Source-of-truth verification (per `feedback_langgraph_native_primitives` and `feedback_external_skill_canon`): inspected `langchain-ai/langgraph` repo at `libs/langgraph/langgraph/types.py` and `libs/langgraph/langgraph/_internal/_cache.py`.

**`CachePolicy` (in `langgraph/types.py`)** is a two-field dataclass:

- `key_func: Callable[..., str | bytes]` — defaults to `default_cache_key`. Docstring: *"Function to generate a cache key from the node's input."*
- `ttl: int | None = None` — *"Time to live for the cache entry in seconds. If `None`, the entry never expires."*

**`default_cache_key` (in `langgraph/_internal/_cache.py`)** receives `*args, **kwargs` exactly as passed to the node, normalises them through a `_freeze` helper that handles `Mapping`/`Sequence`/numpy buffers, and returns a serialised digest of that frozen tuple. The exact serialisation format is irrelevant to us — we override `key_func` with a string-based key, sidestepping the default entirely.

**Cache backends:** `langgraph.cache.memory.InMemoryCache`, `langgraph.cache.sqlite.SqliteCache`. Wired via `add_node(..., cache_policy=...)` and `builder.compile(cache=...)`.

**What canon does not ship (deliberate):**

- No `version` / `prefix` field on `CachePolicy`.
- No file-content-hash helper.
- No "exclude these state keys" helper.
- No decorator sugar (`@cache_on(slug, files=[...])`).

LangGraph's design intent is clear: `key_func` is the only knob, and user code is expected to put whatever logic it needs in there. Writing a custom `key_func` is therefore not "reinventing"; it is the canonical extension point. A small reusable helper that constructs keys consistently across our ~18 cached nodes is a DRY factoring of the same canonical pattern, not a parallel framework.

**Reviewed-and-resolved issue [#5980](https://github.com/langchain-ai/langgraph/issues/5980):** During scoping this was flagged as "`InMemoryCache + InMemorySaver` cache-misses every run". Independent canon-check (2026-05-06) found it **closed 2025-09-16 as not-a-bug**: the maintainer clarified that `InMemorySaver` accumulates state across runs, so the *default* pickle-based `key_func` correctly cache-misses (the input genuinely differs run-to-run). The recommended resolution — *configure `CachePolicy.key_func`* — is exactly the architecture this spec adopts. The issue therefore does not block our rollout. We still keep a small sanity smoke in HOM-132.1 (§10) to confirm `SqliteCache + SqliteSaver` cross-thread hits work as expected, but it is not a stop-gate.

## 5. Architecture

### 5.1 Top-level wiring

```python
# graph/src/edit_episode_graph/graph.py
from langgraph.cache.sqlite import SqliteCache

_CACHE_PATH = REPO_ROOT / "graph" / ".cache" / "langgraph.db"
_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

return g.compile(
    checkpointer=SqliteSaver.from_conn_string(...),  # unchanged
    cache=SqliteCache(path=str(_CACHE_PATH)),         # new
)
```

**Cache location:** `graph/.cache/langgraph.db`, gitignored, lifecycle independent from `graph/.langgraph_api/checkpoints.sqlite`. Rationale: cache and checkpoint history are logically independent — wiping the cache to force re-execution must not lose thread history, and resetting `langgraph dev` state must not invalidate cache.

**Version requirement.** `CachePolicy` + `compile(cache=...)` shipped in the langgraph 0.x cache-feature wave. The current `graph/pyproject.toml` pins `langgraph>=0.2.60`; HOM-132.1 will verify this pin actually resolves to a release that exposes both APIs and bump the floor if not. `SqliteCache` is re-exported from `langgraph.cache.sqlite` but lives in the `langgraph-checkpoint-sqlite` distribution (already a dependency for `SqliteSaver`); no new install.

### 5.2 Per-node application pattern

Each cached node module exposes a `CACHE_POLICY` constant; `graph.py` passes it to `add_node(..., cache_policy=CACHE_POLICY)`.

```python
# nodes/p4_plan.py
from langgraph.types import CachePolicy
from .._caching import make_key

_CACHE_VERSION = 1  # bump on brief / schema / tools change

def _key(state, *_args, **_kwargs):
    return make_key(
        node="p4_plan",
        version=_CACHE_VERSION,
        slug=state["slug"],
        files=[
            state["compose"]["design_md_path"],
            state["compose"]["expanded_prompt_path"],
            state["transcripts"]["final_json_path"],
        ],
    )

CACHE_POLICY = CachePolicy(key_func=_key)
```

```python
# graph.py
from .nodes.p4_plan import p4_plan_node, CACHE_POLICY as p4_plan_cache_policy
g.add_node("p4_plan", p4_plan_node, cache_policy=p4_plan_cache_policy)
```

The `key_func` is defined at import time (no closure over runtime state) and reads the live `state` argument that LangGraph passes at invocation. Topology stays in `graph.py`; per-node knowledge of upstream artifacts stays in the node module.

### 5.3 The `_caching.py` helper (~40 LOC)

```python
# graph/src/edit_episode_graph/_caching.py
import hashlib
from pathlib import Path

def _file_fingerprint(path: str | None) -> str:
    """sha256 of file content, or 'absent' if file missing."""
    if not path or not Path(path).exists():
        return "absent"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def make_key(*, node: str, version: int, slug: str,
             files: list[str | None] = (),
             extras: tuple = ()) -> str:
    """Canonical cache key for a node.

    - `node` + `version` literal makes brief/schema bumps invalidate.
    - `slug` namespaces per-episode.
    - `files` are content-hashed: edits or deletions invalidate.
    - `extras` = optional tuple of stable scalars (e.g. iteration counter).
    """
    parts = [node, f"v{version}", slug]
    parts += [_file_fingerprint(p) for p in files]
    parts += [repr(x) for x in extras]
    return "|".join(parts)
```

**Design choices:**

- **sha256 over mtime+size.** mtime lies after `git checkout`, after `cp -p`, after restore-from-trash. Content hash is the only reliable signal. Cost: ~50 ms per 100 MB. The largest file in any cache key is `final.mp4` (50–200 MB), and only a few Phase 4 nodes include it. Acceptable; revisit per-node if cold-start timing becomes painful.
- **Missing file → `"absent"` literal.** Delivers Goal 2 (delete artifact → cache miss → resume from that node) automatically: the deletion changes the key.
- **Per-node integer `_CACHE_VERSION`.** Bumped on brief / schema / tool-list changes. Diff review enforces (see §8).
- **`extras` tuple for rare scalars.** E.g. `p3_self_eval` includes `(edit.iteration,)` so iteration N+1 doesn't cache-hit iteration N's verdict.

**What is deliberately not in the key:**

- No `state["llm_runs"]`, `state["errors"]`, no timestamps. Including them would defeat caching entirely.
- No raw `state` dict. The default `default_cache_key` would hash the full input — too brittle (any telemetry write invalidates), so we override.
- No path to the artifact this node *produces* (key is for input, not output).

## 6. Per-node application table

The following 18 nodes carry `cache_policy=`. The `files=` column lists upstream artifacts whose content makes the node's output deterministic; bumping `_CACHE_VERSION` is required when this list changes (see §8).

| Node | `files=` | `extras=` |
|---|---|---|
| `isolate_audio` | `[pickup.raw_path]` | — |
| `p3_inventory` | `[pickup.raw_path, audio.wav_path]` | — — spec originally said `[audio.cleaned_path]`; there is no `audio.cleaned_path` field on `AudioState` (the canonical isolated-audio output tracked in state is `audio.wav_path`). Keying on `pickup.raw_path` (always set by `pickup`) gives the upstream-invalidation parity the spec intended; `audio.wav_path` is included as a secondary signal so a re-isolated WAV under the same raw still invalidates (HOM-132.4 amendment) |
| `p3_pre_scan` | `[transcripts.takes_packed_path]` | — |
| `p3_strategy` | `[transcripts.takes_packed_path]` | `(pre_scan_slips_hash, strategy_revisions_hash)` — both are rendered verbatim into the brief (`pre_scan_slips_json`, `strategy_revisions_json`) and live in-memory on `state.edit.pre_scan.slips` / `state.strategy_revisions`, not on disk; spec originally said `edit.pre_scan_path` — there is no on-disk pre-scan artifact (HOM-132.3 amendment) |
| `p3_edl_select` | `[transcripts.takes_packed_path] + transcript_paths` | `(pre_scan_slips_hash, strategy_hash, prior_violations_hash, prior_iteration)` — pre-scan slips and strategy are in-memory; the gate-retry feedback (`prior_violations`, `prior_iteration` from `gate_retry_context("gate:edl_ok")`) is rendered into the brief on retry attempts and MUST invalidate so the retry-with-feedback loop is not short-circuited; spec originally said `edit.strategy_path` — there is no on-disk strategy artifact (HOM-132.3 amendment) |
| `p3_render_segments` | `[edit.edl_path]` | — — spec originally said `(edit.iteration,)`; there is no `edit.iteration` field on `GraphState`, and gate retries rewrite `edl.json` in place (changing its content hash), so file invalidation already covers retry-driven re-renders. `final.mp4` is the node's OUTPUT and is deliberately NOT in `files=` (mirrors the `p3_persist_session` `project.md` rule — listing a mutated output forces every cold→warm to cache-miss, defeating idempotency); the node body's own `cached = final_path.exists()` check provides missing-output recovery (HOM-132.4 amendment) |
| `p3_self_eval` | `[edit.final_mp4_path, edit.edl_path]` | `(eval_iteration,)` — count of `gate:eval_ok` records in `state.gate_results`; there is no `edit.iteration` field on `GraphState`, so the de-facto counter (also used by `p3_persist_session`'s brief) is derived from gate history (HOM-132.3 amendment) |
| `p3_persist_session` | `[edit.final_mp4_path, edit.edl_path]` | `(strategy_hash, edl_hash, eval_hash, today)` — `strategy_json` / `edl_json` / `eval_report_json` are rendered verbatim from in-memory state, and `today` is rendered into the appended Session-block heading so day-rollover MUST invalidate (mirrors the `p4_persist_session` HOM-150 amendment); spec originally listed no extras (HOM-132.3 amendment). `project.md` is deliberately NOT in `files=`: the node's first run mutates it, so listing it would force every re-run to cache-miss, defeating idempotency. |
| `glue_remap_transcript` | `[edit.edl_path, transcripts.raw_json_path]` | — |
| `p4_scaffold` | `[]` (depends on slug only) | — |
| `p4_design_system` | `[transcripts.final_json_path, edit.edl.edl_path]` | `(strategy_hash,)` — sha256 of strategy dict modulo `source_path`/`skipped`/`skip_reason`; the brief feeds `strategy_json` directly |
| `p4_prompt_expansion` | `[compose.design_md_path, transcripts.final_json_path]` | `(style_request_hash,)` — sha256 of `compose.style_request`, the operator-supplied prompt seed; brief renders it as `style_request_json`; not produced by any upstream node so transitive invalidation does not cover it (HOM-150 amendment) |
| `p4_plan` | `[compose.design_md_path, compose.expanded_prompt_path, transcripts.final_json_path]` | `(strategy_hash, edl_beats_hash)` — both are rendered verbatim into the brief (`strategy_json`, `edl_beats_json`); they live in-memory on `state.edit.strategy` / `state.edit.edl.ranges`, not on disk, so transitive file-fingerprint invalidation does not cover them (HOM-150 amendment) |
| `p4_catalog_scan` | `[]` (deterministic, reads npm registry) | — |
| `p4_beat` (per-`Send`) | `[compose.design_md_path, compose.expanded_prompt_path]` | `(beat_id, plan_beat_hash)` — `plan_beat_json` (concept / mood / energy / duration for this beat) is rendered verbatim into the brief but lives in-memory on `_beat_dispatch.plan_beat`; transitive design_md / expanded_prompt invalidation does not catch a plan-only change for the same beat_id (HOM-150 amendment) |
| `p4_captions_layer` | `[compose.design_md_path, transcripts.final_json_path]` | — |
| `p4_assemble_index` | `[<hyperframes_dir>/compositions/<scene_id>.html for beat in compose.plan.beats] + ([compose.captions_block_path] if set)` | — — spec originally said `[b.html_path for b in beats]` referencing the deprecated `compose.beats[]` state echo. HOM-133/134 moved beats fan-out to FS-truth (`<hyperframes_dir>/compositions/<scene_id>.html`); the live `_cache_key` rebuilds the path list on the same FS basis the node body iterates. `index.html` is the node's OUTPUT (atomic-write-mutated) and is NOT in `files=` (HOM-132.4 amendment) |
| `p4_persist_session` | `[compose.assemble.index_html_path]` (with `assemble.assembled_at` as legacy fallback) | `(today,)` — UTC YYYY-MM-DD; brief renders `today` and the appended Session block carries that date, so day-rollover MUST invalidate (HOM-150 amendment; spec originally said `compose.index_html_path` — the actual location is `compose.assemble.*`) |

**Explicitly NOT cached:**

- All `gates/*` — node bodies are validation logic; re-running on retry is the point.
- All `*_interrupt` (`strategy_confirmed_interrupt`, `edl_failure_interrupt`, `eval_failure_interrupt`, `p3_review_interrupt`, `halt_llm_boundary`) — semantics are "pause and ask"; caching breaks HITL.
- `pickup` — source-of-truth for `slug`/`episode_dir`; cheap; skipping breaks invariants.
- `p4_dispatch_beats` — produces a `Send` list, not a result; potential incompatibility with caching the dispatch decision.
- `p4_redispatch_beat` — behaviour depends on `phase_feedback`; cache-hit would break the retry-with-feedback loop.
- `studio_launch` — side-effect on the live preview server; must run.

## 7. Lifecycle and invalidation

Three native mechanisms:

1. **Content invalidation.** User edits `DESIGN.md` → sha256 differs → cache miss → node re-runs. Covers ~95% of cases.
2. **`_CACHE_VERSION` bump.** When the brief, output schema, or tool list of a node changes, the per-node integer increments. Code review enforces (see §8).
3. **Manual nuke.** `rm graph/.cache/langgraph.db` resets all entries. Documented in `graph/README.md` as "when in doubt"; not expected in normal flow.

**TTL policy: `ttl=None` everywhere.** No use case for time-based expiry — artifacts stay valid until the user edits them.

**`graph/.gitignore` add:** `/.cache/` (one line).

## 8. Process — keeping `_CACHE_VERSION` honest

Stale cache hits are the dominant risk. Mitigation extends `feedback_code_review_before_merge`:

> **Cache-version review checkpoint.** When a PR diff touches `briefs/<node>.j2`, `schemas/<node>.py`, or the `cmd_factory` / tool-list of a deterministic node, the reviewer verifies `_CACHE_VERSION` was bumped in the same PR. If the change is logic-equivalent (e.g. wording-only docstring change in a brief), the bump is optional — note the rationale in the PR body.

Escape hatch (`rm graph/.cache/langgraph.db`) covers honest mistakes; the review checkpoint catches them in advance.

## 9. Rollout — sub-issues under HOM-132

Per `feedback_linear_subissues_for_epics`, decompose the epic into shippable sub-issues. Sub-issues are created **after** HOM-132.1 merges (the design note plus pilot node anchors the rest).

| # | Title | Scope | Smoke |
|---|---|---|---|
| HOM-132.1 | Design note + caching foundation + pilot | this spec; `_caching.py`; `SqliteCache` in `compile()`; `cache_policy` on `p4_design_system`; `graph/.cache/` in `.gitignore`; bare-repro for #5980-class regression | `graph/smoke_hom149_cache_hit.py`: one-node graph runs twice on identical state → second run shows `__metadata__.cached == True` for `p4_design_system` |
| HOM-132.2 | Phase 4 LLM nodes | `p4_prompt_expansion`, `p4_plan`, `p4_beat`, `p4_captions_layer`, `p4_persist_session`; **delete** the poor-man's cache stubs in `p4_beat.py:14` and `p4_captions_layer.py:20` | re-run on episode with complete Phase 4 → zero LLM invocations |
| HOM-132.3 | Phase 3 LLM nodes | `p3_pre_scan`, `p3_strategy`, `p3_edl_select`, `p3_self_eval`, `p3_persist_session` | re-run on episode with complete Phase 3 → zero LLM invocations |
| HOM-132.4 | Deterministic heavy nodes | `isolate_audio` (Scribe credits — primary prize), `p3_inventory`, `p3_render_segments`, `glue_remap_transcript`, `p4_scaffold`, `p4_catalog_scan`, `p4_assemble_index` | re-run with artifacts present → zero subprocess calls to ElevenLabs / ffmpeg |
| HOM-132.5 | E2E re-run + docs | real e2e re-run on a stable episode; update CLAUDE.md §Idempotency to reflect structural enforcement; close HOM-132 | manual; cold-vs-warm timing in PR body |

Topology check (`tests/test_p4_topology.py`) is unaffected — caching does not change edges. No `expected_edges` updates required for any sub-issue.

## 10. Test plan

**Per-PR real-CLI smokes** (per LLM-node DoD §1):

- HOM-132.1 ships `graph/smoke_hom149_cache_hit.py` (top-level under `graph/` to match the existing `smoke_hom*.py` convention — `tests/` is reserved for pytest). Builds a minimal one-node graph wrapping the real `p4_design_system_node` + `CACHE_POLICY`, runs twice on identical state, and asserts the per-step `__metadata__.cached` flag (this is the channel that surfaces cache-hit status — only visible via `graph.stream(..., stream_mode="updates")`; `invoke()`'s return value does not expose it):
  - Run 1: `__metadata__.cached` is False/absent for `p4_design_system`.
  - Run 2 (identical input): `__metadata__.cached == True`, zero LLM dispatch.
- Subsequent sub-issues extend the same smoke pattern: edit one upstream file → assert miss; delete → assert miss.
- Cost: $0 for the pilot — the smoke triggers `p4_design_system_node`'s early-return `skipped=True` branch (no `episode_dir` / empty EDL), so the cache wraps a cheap dict and we exercise the LangGraph mechanism end-to-end without an Opus dispatch. Sub-issues that test real LLM invocation budget the cheap-tier model (Haiku) via per-node `model:` override in `graph/config.yaml` (~$0.001 per smoke run).

**`SqliteCache + SqliteSaver` sanity smoke (HOM-132.1, non-blocking):**

`graph/smoke_hom149_sqlite_pair.py`: `StateGraph` + one noop node with `cache_policy=CachePolicy(key_func=...)` + `SqliteSaver` + `SqliteCache`. Confirms cross-thread cache hit on identical input via `__metadata__.cached`. Originally framed as a blocking gate due to flagged issue #5980; downgraded to sanity smoke after canon-check confirmed #5980 was closed not-a-bug (see §4). If the smoke unexpectedly shows misses, stop the epic, file an upstream issue, and document mitigation in CLAUDE.md.

**Topology test:** `tests/test_p4_topology.py` runs unchanged for every sub-issue.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Cross-thread hit regression on `SqliteCache + SqliteSaver` (low — #5980 was closed not-a-bug, but unverified for this exact pair) | Sanity smoke in HOM-132.1 (§10). Halt + escalate only if the smoke fails. |
| `_CACHE_VERSION` not bumped when brief/schema changes → stale cache returns wrong-shaped output for new requirements | Code-review checkpoint (§8); manual nuke escape hatch. |
| sha256 on large `final.mp4` (50–200 MB) inflates cold-start | Only Phase 4 captions / persist nodes hash it; on warm re-run hash is computed once. Acceptable; per-node fallback to `(size, mtime_ns)` available if empirically painful. |
| Cache DB grows unboundedly | One valid key per (node, slug) — bounded by episode count. Manual cleanup via `rm -rf graph/.cache/` documented in README. |
| Concurrent writes from `Send` fan-out (5 parallel `p4_beat` processes) compete for SQLite write lock | SQLite WAL handles this; verify empirically in HOM-132.2 smoke. |

## 12. Open for future sessions

- `SqliteCache` concurrent-write behaviour under `Send` fan-out (HOM-132.2 will provide the empirical answer).
- Possible future optimisation: shared precomputed-fingerprint in state for files read by multiple Phase 4 nodes (so `design_md_path` is sha256'd once per re-run, not three times). Not done now — premature optimisation; YAGNI until cold-start timing is measured and complained about.

## 13. References

- Live source: `langchain-ai/langgraph` at `libs/langgraph/langgraph/types.py` (`CachePolicy`), `libs/langgraph/langgraph/_internal/_cache.py` (`default_cache_key`), `libs/langgraph/langgraph/graph/state.py` (`StateGraph.compile(cache=...)`, `StateGraph.add_node(..., cache_policy=...)`), `libs/checkpoint-sqlite/langgraph/cache/sqlite/__init__.py` (`SqliteCache(*, path, serde=None)` — sets `PRAGMA journal_mode=WAL`).
- Docs: [Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api), [Types reference](https://langchain-ai.github.io/langgraph/reference/types/), [#5980](https://github.com/langchain-ai/langgraph/issues/5980).
- Prior spec: `docs/superpowers/specs/2026-05-02-langgraph-pipeline-design.md` (§4.5 idempotency framing — superseded for within-phase caching by this spec).
- Memory: `feedback_langgraph_native_primitives` (search docs before rolling custom), `feedback_external_skill_canon` (verify against live source), `feedback_linear_subissues_for_epics` (decomposition pattern), `feedback_code_review_before_merge` (extended in §8).
- CLAUDE.md §Idempotency (will be updated in HOM-132.5 to reflect structural enforcement).
