# State-first artifacts — single-source-of-truth for graph node outputs

**Date:** 2026-05-10
**Status:** Proposed (awaiting user review)
**Linear:** Epic placeholder `HOM-NEW-state-first-artifacts` (sub-issues to be created on approval — see §10).
**Scope:** Make graph node return values the source of truth for produced artifacts (DESIGN.md, expanded-prompt.md, beat-scene HTML, captions HTML, root index.html, project.md session blocks). Side effects to disk move to a single dedicated terminal materializer node. Eliminates the entire class of "cache stores metadata about a write that may or may not still exist on disk" bugs that produced the seven incidents catalogued in §2.

---

## 1. Problem

Re-running the graph on an already-recorded fixture cache should be deterministic at $0 cost (CLAUDE.md §"Testing infra — fixture replay"; spec `2026-05-08-testing-infra-fixture-replay-design.md` §3 L1). It is not, in a way that has produced seven distinct incidents over three weeks. Each incident was diagnosed and fixed on its own terms; none of the fixes addressed the underlying class. HOM-216 made the pattern legible: committed `cache.db` carries a 3-beat plan (hook / thesis / payoff), the working tree carries a 4-beat plan (hook / problem / pivot / payoff), and the two are claimed to be "the canonical fixture." Neither shape is recoverable from the other, because the cache stores `assemble.assembled_at` and a list of beat names (`p4_assemble_index.py:630-638`), not the HTML bodies of the scenes themselves.

**Honest scoping — the seven incidents are not all the same bug.** State-first artifact storage is necessary for the *artifact-sourcing* class but does not address two adjacent classes that this spec previously conflated with it. Distinguishing them up front prevents this spec from over-promising:

- **Defused cleanly by state-first (3 of 7):** HOM-189 (worktree-bound paths in state), HOM-195 family (`EpisodePaths` echoes leaking into cache keys), HOM-216 (cache-vs-disk drift on scene HTML bodies). These fail because the canonical artifact lives only on disk while the cache fingerprints something else; storing the body in state collapses the two truths into one.
- **Partially defused (1 of 7):** HOM-181 (replay smokes silently skipped). The dominant root cause was the `requires_fixture_cache` skipif treating "file present" as "cache valid" — that's a test-harness bug, not an artifact-sourcing bug. State-first reduces the *blast radius* of a re-record-against-the-wrong-episode mistake (because the JSON dump diff would surface the wrong transcript / palette before commit), but the silent-skip itself is fixed by tightening the skipif predicate.
- **NOT defused — schema-evolution (2 of 7):** HOM-154 `dffe526` (brief-churn re-record cycle) and HOM-154 `752056f` (gate-shape change re-record). Both are `_CACHE_VERSION` / brief / output-schema bumps that legitimately invalidate cache rows. State-first does **nothing** for this class — a version bump still triggers a paid re-record of the bumped node and its dependents. Recovery cost shrinks (the materializer regenerates disk artifacts at $0 from the new cache rows, no extra commit churn), but the LLM dispatch itself is unavoidable. Treating these as artifact-sourcing incidents was a category error in the first draft.
- **NOT defused — process discipline (1 of 7):** HOM-227 ("missing cache row for `gate_animation_map_classify`" filed against a stale `state*.json`). The fix is operator hygiene (verify against a live smoke before filing, per memory `feedback_verify_fixture_state_before_filing_tickets`); architecture is orthogonal. State-first does shrink the surface (operators have one canonical file to interrogate via `sqlite3 cache.db`), but the wrong-stale-file failure mode is a habit, not a shape.

**The architectural mistake state-first does fix:** graph nodes write large produced artifacts to disk as side effects, while their LangGraph cache row stores only a small metadata delta about that write. A `CachePolicy` cache hit rehydrates the metadata delta into state — it does not replay the side effect. Disk and cache drift become the steady state. The schema-evolution and process-discipline incidents share surface symptoms with this class (all manifest as "fixture is wrong on replay") but have different mechanisms and different fixes; §6.0 below discusses why state-first remains worth doing for the 3-or-4 it does cover, and §10 (atomic-record protocol) and §12 (Risks & rollback) add complementary fixes for what state-first leaves on the table.

## 2. Evidence — the seven incidents

| # | Ticket / commit | Surface symptom | Root form |
|---|---|---|---|
| 1 | HOM-181 / `dbcaac4` (PR #102) | Replay smokes silently skipped (`requires_fixture_cache` only checks file presence) — first prewarm of `cache.db` was recorded against the production episode, not the fixture's own `raw.mp4`; cache held absolute paths. | Cached state pointed at production paths. Replay miss invisible until paid LLM call. |
| 2 | HOM-189 / `5a7fa26` (PR #110) | All replay smokes miss; ~$5–10 burnt before halt at `p4_plan AllBackendsExhausted`. Re-record under `HOMESTUDIO_PROJECT_ROOT=tests/fixtures` baked the worktree path (`.worktrees/hom-189/...`) into 13 of 16 cached state values. | State stored worktree-bound absolute strings. Worktree teardown invalidated every replay. |
| 3 | HOM-154 / `dffe526` (PR #115) | "Refresh canonical fixture against post-HOM-191/192/193/194 main." Briefs kept changing → `_CACHE_VERSION` kept bumping → fixture kept becoming stale. | Healthy cache invalidation, but the *recovery cost* is full re-record because produced artifacts only live on disk. |
| 4 | HOM-154 / `752056f` (PR #123) | Same shape post HOM-203 advisory-gate demotion — gate `passed` shape mutated; cached row obsoleted. | Same as 3. |
| 5 | HOM-195 / HOM-222 / HOM-223 / HOM-224 / HOM-225 / HOM-226 / `5f0ae73` (PR #132) | Worktree-bound absolute paths in state break replay across worktrees, machines, renamed episode dirs. EpisodePaths migration removed absolute paths from state and derived from slug. | Real fix for *one* class of identity-corrupting state — but only that class. The artifact class (HTML bodies, caption blocks, design markdown, index.html) was untouched. |
| 6 | HOM-227 (cancelled as duplicate; see memory `feedback_verify_fixture_state_before_filing_tickets`) | "Missing cache row for `gate_animation_map_classify`" — filed against a stale `state3.json` from a different failed run. Cancelled mid-implementation when smoke turned out green. | Operator unable to *describe* the live fixture state without running a smoke. Symptom: "fixture" is a sprawling bundle of files, not a single file. |
| 7 | HOM-216 (current, unmerged) — `c4a4efc` (cache.db update) + `e014830` (hook/payoff beat HTML) | Committed `cache.db` carries a 3-beat plan (hook / thesis / payoff). Disk carries a 4-beat plan (hook / problem / pivot / payoff). `thesis.html` missing on disk; Playwright snapshots fail. Two sources of truth disagree, neither is reconstructible from the other. | Cache stores `compose.assemble.beat_names = ["hook", "thesis", "payoff"]` in 80 bytes; disk has 4 × ~30 KB HTML bodies. A cache hit replays neither. |

Plus near-misses already absorbed by tactical fixes:

- HOM-156 — gate output schema change invalidated all gate cache rows.
- HOM-184 — fixture-replay smoke migration shipped with `pytest.skip`; the real-runtime dispatch path could not exercise the cache deterministically.
- HOM-186 — invented `tests/_helpers/replay_dispatch.py` (see lines 115-127 for `_decode_channel_writes`, 246-247 for the `loads_typed` reconstruction) to read cache.db rows via raw SQL because going through the runtime would re-evaluate `key_func` against the *test machine's* fingerprint inputs and silently miss. The carve-out documented in CLAUDE.md §"Exception — fixture-replay test inspection" is itself evidence that the abstraction is leaking.

## 3. The single underlying architectural mistake

Nodes use disk writes as their *primary* output channel; `cache.db` only fingerprints inputs and stores a small "I succeeded, here's some metadata" delta in state. The actual output is unrecoverable from the cache.

Concrete proof in the codebase:

- **`graph/src/edit_episode_graph/nodes/p4_beat.py:169-180`** — the `LLMNode` is declared with `result_namespace="compose"` and `result_key="_beat_unused"` (literal placeholder name). The brief (`briefs/p4_beat.j2`) instructs the dispatched sub-agent to `Write` to `<hyperframes_dir>/compositions/<scene_id>.html` — disk is the real output. The state delta is throwaway.
- **`graph/src/edit_episode_graph/nodes/p4_assemble_index.py:588`** — `fragments.append((sid, scene_path.read_text(encoding="utf-8")))`. The assembler reads scene HTML back from disk because state does not carry it.
- **`p4_assemble_index.py:630-638`** — the node's return value is `{"compose": {"assemble": {"assembled_at": <iso>, "beat_names": [...], "captions_included": <bool>}}}`. Three fields of metadata, ~80 bytes, for the ~30 KB of authored HTML the node just emitted.
- **`p4_captions_layer.py:187`** — `result_key="_captions_unused"`. Same pattern.
- **`p4_design_system.py:146`** — `result_key="design"`, but the brief renders `design_md_path` (line 133) and instructs the sub-agent to `Write` DESIGN.md to disk; the structured-output echo (line 147 onward) is metadata, not the markdown body.
- **`p4_prompt_expansion.py:142`** — `result_key="expansion"`, same pattern; markdown body lives only at `<edit_dir>/.hyperframes/expanded-prompt.md`.
- **`p4_persist_session.py:209`** — `result_key="persist"`; the appended Session block lives only inside `<edit_dir>/project.md`.

LangGraph's cache machinery (`langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer`, used by `langgraph.cache.sqlite.SqliteCache`) stores the node's return value as a serialised `channel_writes` deque. There is no "side effect" channel; LangGraph cannot re-run side effects on a hit. `CachePolicy(key_func=…)` is purely about *keying*. The serializer happily handles strings, numbers, lists, dicts, datetime, and `Path`; a 30 KB HTML string is unremarkable to it. Storing a `Path` reference to a file that may not exist on the next replay machine is the failure mode we live in.

### 3.1 HOM-134 prior — structured-output extraction was already tried and abandoned

The first draft of this spec proposed reversing a decision the team made deliberately, without acknowledging it. The smoking gun is in `graph/src/edit_episode_graph/nodes/p4_captions_layer.py:172-180`:

```python
def _build_node() -> LLMNode:
    # output_schema=None — same FS-source-of-truth pattern as p4_beat
    # (HOM-134). The output path is deterministic
    # (`<hyperframes_dir>/captions.html`), so requiring the sub-agent to
    # echo it back as JSON adds an extraction failure mode for zero
    # structural value: smoke runs hit `SchemaValidationError` because the
    # canon-shaped reply was prose ("Wrote captions.html (...)") rather
    # than the JSON the schema expected. The post-dispatch check below
    # promotes from disk instead.
```

`p4_beat.py:169-180` carries the same pattern (`output_schema=None`, `result_key="_beat_unused"`, body produced via `Write` tool). HOM-134's empirical conclusion was that for nodes whose canonical instruction is "produce file X", the dispatched sub-agent reliably emits prose acknowledging the write rather than a JSON object containing the body — and the JSON-from-fenced-code-block extractor (`graph/src/edit_episode_graph/backends/_schema_extract.py`) raises `SchemaValidationError` on those replies, triggering retry loops that cost more than the original dispatch.

This is direct counter-evidence to §6.2's premise that creative LLM nodes can return 30 KB HTML bodies in structured output reliably. **Before any of step B lands**, this premise must be re-validated on the current model tier (post-HOM-134 backends, post-HOM-157 routing-config) against the actual canonical fixture. The pre-migration spike (§7) does exactly that, on `p4_beat` only, with a budget cap and an explicit kill-switch to BaseStore (§6.0) if the spike fails.

Counter-evidence to "all creative nodes are pure side-effect": `p4_design_system.py:139-150` ships with `output_schema=DesignDoc` and `result_key="design"` — that node *does* return a structured Pydantic object today, with no FS-source-of-truth fallback comment. The shape it returns is metadata about a design decision (palette tokens, voice/topic), not a 30 KB body — and that distinction matters. HOM-134 retreated specifically from large-body structured output; small-metadata structured output works. The migration's hardest cases are the large-body nodes (`p4_beat`, `p4_captions_layer`, `p4_assemble_index`) where HOM-134's evidence directly applies.

## 4. Goals

1. **Make node return values the source of truth for produced artifacts.** Concretely: a creative LLM node that today writes DESIGN.md / expanded-prompt.md / a scene HTML / captions HTML / index.html / a Session block instead returns the body of that artifact as a string in state.
2. **Disk materialisation moves to a single dedicated node** (`p4_materialize_disk_node`) that runs late in the chain and is idempotent, deterministic, and keyed on the content hash of the entire material set.
3. **Reduce the fixture surface to a single canonical file.** `cache.db` plus immutable inputs (`raw.mp4`, `intent.yaml`) and a regenerable JSON dump (`recordings/*.json`) are sufficient to reconstitute every produced artifact.
4. **Eliminate `EpisodePaths`-bearing reads from cache keys** (HOM-195 family). When the brief input is a string in state, the cache key fingerprints the string; no `file_fingerprint` walk, no project-root resolution, no worktree-binding.
5. **HOM-216 is unblocked without re-recording.** The architecture migration is the cost; HOM-216 collapses to a one-day "verify Playwright greens after cutover" task.

## 5. Non-goals

- Replacing `CachePolicy` / `SqliteCache`. The mechanism stays; only the *contents* of cached values change.
- Caching gates, interrupts, `pickup`, `studio_launch`, fan-out dispatchers (per spec `2026-05-06-langgraph-node-caching-design.md` §6 "Explicitly NOT cached"). Same exclusions apply.
- Inventing a new content-addressable artifact store. State-as-string is sufficient at our scale (§11 sizing).
- Moving Phase 3 artifacts into state. Phase 3 produces `final.mp4` (50–200 MB binary, on disk by necessity) and a `transcripts/final.json` (small, but the canonical interface to ffmpeg / Whisper sub-processes is on-disk file paths). Phase 3 retains `EpisodePaths`-keyed file fingerprinting for now; this spec scopes to Phase 4 LLM-produced text artifacts.
- CI integration. Out of scope per CLAUDE.md §"Testing infra — fixture replay" precedent; the architecture stays CI-ready.
- Re-recording the canonical fixture. Migration runs at $0 against the existing committed `cache.db` (see §10 step F, single paid wave-acceptance run).

## 6. Proposed design

### 6.0 Considered alternatives — why state-channel storage and not BaseStore

CLAUDE.md §"LangGraph primitives — search docs before rolling custom" requires that any non-trivial orchestration design cite the native LangGraph primitive it adopts (or explicitly justify rolling custom). For "where do we store 100KB+ of produced text artifacts", LangGraph offers two persistence layers, and they are not interchangeable:

| Layer | Scope | API | Lifecycle | Native primitive |
|---|---|---|---|---|
| **State channels (checkpointer)** | per-thread; serialised on every superstep | `TypedDict` fields with reducers; read via `state["compose"][...]`; persisted by `SqliteSaver` / equivalent | Tied to thread-id. Cleared with thread. | `langgraph.checkpoint.sqlite.SqliteSaver` + `CachePolicy` cache rows |
| **BaseStore** | cross-thread; namespaced key-value store with optional embedding index | `store.put(ns, key, val)` / `store.search(ns, query=...)`; sync or async via `runtime.store` | Independent of threads; survives thread deletion. | `langgraph.store.memory.InMemoryStore` (dev), `PostgresStore` (prod) |

Live docs (read 2026-05-10): <https://docs.langchain.com/oss/python/langgraph/persistence>. The page's framing is unambiguous — BaseStore exists to retain information **across threads**, e.g. user-profile memories shared between conversations. State channels are the per-thread primitive.

**Why state channels (the choice this spec makes):**

1. Our use case is **single-thread per fixture run.** A canonical-fixture replay starts a thread, walks the graph, and terminates. We never need to share an artifact body across threads — each replay is self-contained. BaseStore's distinguishing feature (cross-thread sharing) is wasted on us.
2. **Cache-key fingerprinting.** Cache keys for downstream nodes need to fingerprint the upstream artifact body. With state channels, the body is already in the state dict the node receives — `string_fingerprint(state["compose"]["design"]["design_md"])` is a pure function of the input. With BaseStore, the node would have to either (a) fetch the body inside `key_func` (now `key_func` performs I/O, defeating its determinism contract), or (b) fingerprint the *store key* and hope the underlying value never mutates (we'd be back to the file-fingerprint failure mode, just with a different backend).
3. **Replay determinism.** `SqliteCache` rows already roundtrip via `JsonPlusSerializer`. Adding a parallel BaseStore introduces a second persistence layer that must also roundtrip, also be committed to the fixture, and also be respected by the replay machinery (`tests/_helpers/replay_dispatch.py`). Two committed binary blobs per fixture instead of one — strictly worse for the review surface.
4. **No native cache-replay story.** `CachePolicy` caches the node's return-value channel writes. Side effects to BaseStore performed inside a node body are not part of those writes; on a cache hit, the side effect is not replayed (same failure mode we have today with disk writes — just moved one layer). Making the BaseStore write the *return value* (so the cache replays it) collapses BaseStore back into a verbose state channel.

**When BaseStore would be the right call** (and is not, today):

- If we ever need cross-fixture artifact sharing (e.g. "the design tokens from episode A seed episode B"), BaseStore's namespacing is purpose-built for it. Today we don't.
- If `JsonPlusSerializer` roundtrip on >1 MB strings becomes a bottleneck (§11 sizing budget says we're well under that — total Phase 4 state delta ~100–300 KB), spilling specific large bodies to BaseStore while leaving keys in state is a defensible escape hatch. Today the budget is fine.
- **If the §7 pre-migration spike fails** (structured-output extraction proves unreliable for large bodies on the current model tier), BaseStore becomes the fallback architecture: producer nodes call `runtime.store.aput((slug, "compose"), "scene-<id>.html", body)` from their post-dispatch hook (still reading the body from the disk file the sub-agent's `Write` tool created — disk stays the producer-to-store-write bridge), the cache row stores a content-hash key, and downstream nodes fetch via `runtime.store.aget(...)`. This preserves the FS-source-of-truth pattern HOM-134 settled on while still committing all artifact bodies to one canonical persistence layer (the BaseStore SQLite file) instead of scattered `compositions/*.html`. The kill-switch in §7 makes this concrete.

This section is the explicit "checked $URL — chose primitive X over primitive Y because Z" satisfying CLAUDE.md's search-docs-first rule. Doc URLs cited above; primitive chosen: state channels via existing `SqliteCache` row content (no new persistence layer introduced).

### 6.1 State schema additions

`graph/src/edit_episode_graph/state.py` gains the following fields on `ComposeState` and its child types (`DesignState`, `ExpansionState`, `CaptionsState`, `AssembleState`, plus a new `PersistState` if not already present and a new `SceneState`). The path-bearing fields stay during migration (§10 dual-write window) and are deleted in the cutover PR.

```python
class SceneState(TypedDict, total=False):
    scene_id: str
    html: str  # full Pattern A scene fragment as authored

class DesignState(TypedDict, total=False):
    design_md: str  # markdown body
    # legacy fields retained until cutover

class ExpansionState(TypedDict, total=False):
    expanded_prompt: str

class CaptionsState(TypedDict, total=False):
    html: str  # captions block as injected into root composition

class AssembleState(TypedDict, total=False):
    index_html: str  # full root composition HTML post-assembly

class PersistState(TypedDict, total=False):
    session_block: str  # markdown block appended to project.md

class ComposeState(TypedDict, total=False):
    scenes: dict[str, SceneState]
    design: DesignState
    expansion: ExpansionState
    captions: CaptionsState
    assemble: AssembleState
    persist: PersistState
```

A schema-loosening migration test (per CLAUDE.md §"Conditional (4) Schema migration test") verifies that the pre-migration shape (no body fields, only `*_path` echoes) still parses — so the existing fixture cache.db rows survive parsing while we wire up new producers.

### 6.2 Node return-type changes

Each producer node stops emitting metadata-only deltas and returns the artifact body in state. The brief is rewritten to instruct the sub-agent to *return* HTML/markdown via structured output rather than `Write` it. `LLMNode.allowed_tools` drops `Write` for these nodes; the structured-output schema gains a single body field (e.g. `html: str` for scene/captions, `markdown: str` for design/expansion/persist).

| Node | Today | Tomorrow |
|---|---|---|
| `p4_design_system` | `result_key="design"`; brief renders `design_md_path`; sub-agent `Write`s `DESIGN.md`. | Returns `{"compose": {"design": {"design_md": "..."}}}`. Brief drops `design_md_path` and instructs structured return. |
| `p4_prompt_expansion` | `result_key="expansion"`; sub-agent `Write`s `.hyperframes/expanded-prompt.md`. | Returns `{"compose": {"expansion": {"expanded_prompt": "..."}}}`. |
| `p4_beat` (per `Send`) | `result_key="_beat_unused"` (placeholder); sub-agent `Write`s `compositions/<scene_id>.html`. | Returns `{"compose": {"scenes": {scene_id: {"html": "..."}}}}`. The `Send` payload still carries `scene_id`; the merge into `compose.scenes` uses a dict reducer so parallel beats compose correctly. |
| `p4_captions_layer` | `result_key="_captions_unused"`; sub-agent `Write`s captions block to disk. | Returns `{"compose": {"captions": {"html": "..."}}}`. |
| `p4_assemble_index` | Reads scene HTML and captions back from disk (`p4_assemble_index.py:588`, `:604`, `:611`); returns `assembled_at` + `beat_names` only. | Reads `compose.scenes[*].html`, `compose.captions.html`, the scaffold tokens (already in state via `p4_scaffold`) directly from state. Returns `{"compose": {"assemble": {"index_html": "...", "assembled_at": ..., "beat_names": [...]}}}`. The `assemble_html` helper is already pure — only its inputs and return shape change. |
| `p4_persist_session` | `result_key="persist"`; sub-agent appends Session block to `project.md`. | Returns `{"compose": {"persist": {"session_block": "..."}}}`. The materializer appends to disk. |

Fan-out merge for `compose.scenes`: today there is no merge problem because each `Send` writes a unique file. After migration, parallel beats need a merging reducer. Specified and tested in Step A (`_scenes_merge`, sorted-by-key dict union; see §10 Step A for the reducer body and unit tests). Verified canon — `langgraph.graph.message.add_messages` is the textbook example; a dict-merge analogue is a few lines.

### 6.3 The single materializer

```python
# graph/src/edit_episode_graph/nodes/p4_materialize_disk.py
def p4_materialize_disk_node(state: dict) -> dict:
    """Pure side-effect node. Reads compose.* from state and atomic-writes
    every produced artifact to disk. Idempotent — content-hash compares
    before overwriting. Cache-keyed on stable_fingerprint of the entire
    material set; skips when nothing changed.
    """
    paths = EpisodePaths(state["slug"])
    compose = state["compose"]

    # Atomic writes (write-temp, fsync, rename) for every body field.
    _atomic_write(paths.design_md_path,        compose["design"]["design_md"])
    _atomic_write(paths.expanded_prompt_path,  compose["expansion"]["expanded_prompt"])
    for scene_id, scene in compose["scenes"].items():
        _atomic_write(paths.scene_html_path(scene_id), scene["html"])
    if compose.get("captions", {}).get("html"):
        _atomic_write(paths.captions_block_path, compose["captions"]["html"])
    _atomic_write(paths.index_html_path, compose["assemble"]["index_html"])
    _append_session_block(paths.project_md_path, compose["persist"]["session_block"])

    return {"compose": {"materialize": {"materialized_at": _now()}}}
```

Cache policy: `make_key` (deterministic, no LLM tier) keyed on `compose` body hashes — sha256 of each artifact body, joined. Skips re-writing when hashes match the previous run. Wired at the end of the chain just before `studio_launch`.

The materializer is *not* responsible for `final.mp4` (Phase 3, ffmpeg subprocess), `transcripts/final.json` (Phase 3, ElevenLabs Scribe), or any binary artifact. It writes only the text artifacts that LLM creative nodes produce.

### 6.4 Cache keys collapse

Today `p4_plan` (and most Phase 4 LLM nodes) read `compose.design_md_path` and `compose.expanded_prompt_path` off disk via `_caching.file_fingerprint`. Tomorrow they read `state["compose"]["design"]["design_md"]` and `state["compose"]["expansion"]["expanded_prompt"]` (strings) and pass those into `make_llm_key`'s `extras=` tuple as sha256-of-string.

Concretely, `_caching.py::make_llm_key` gains a small helper `string_fingerprint(s: str) -> str` (sha256 hexdigest), and the per-node `_cache_key` constructions move from:

```python
files=[state["compose"]["design_md_path"], state["compose"]["expanded_prompt_path"], ...]
```

to:

```python
files=[paths.transcripts_final_json_path]  # genuinely on-disk inputs only
extras=(
    string_fingerprint(state["compose"]["design"]["design_md"]),
    string_fingerprint(state["compose"]["expansion"]["expanded_prompt"]),
    ...
)
```

For Phase 4 LLM nodes, `files=` shrinks toward `[]` or to `[transcripts.final_json_path]` only. The HOM-195 epic's whole motivation — "remove worktree-bound absolute paths from state-derived cache keys" — disappears for these nodes by construction. EpisodePaths still resolves disk paths inside the materializer and at Studio-render time; it no longer leaks into cache keys for upstream creative nodes.

### 6.5 Fixture shape

```
tests/fixtures/episodes/canonical-portrait-talking-head/
  raw.mp4              # immutable input
  intent.yaml          # immutable input
  cache.db             # entire reproducible artifact bundle (binary, canonical)
  recordings/*.json    # human-readable diff surface, regenerable from cache.db
```

That is the entire fixture. No `hyperframes/compositions/*.html`. No `index.html`. No `DESIGN.md`. No `expanded-prompt.md`. Those bodies live in `cache.db` cells.

The `hyperframes/` directory under the fixture episode becomes gitignored. When a replay test wants to materialise the composition for Playwright, it dispatches `p4_materialize_disk_node` against the cached state into a tmpdir (or into the gitignored fixture `hyperframes/` dir on the operator's machine).

### 6.6 Commit protocol

Single-file commits to `cache.db` plus the JSON dump under `recordings/`. PR diff =

- binary `cache.db` (opaque; reviewer trusts the recording mode);
- text `recordings/*.json` (the actual review surface — human-readable, sorted-keys, normalised whitespace per HOM-182);
- brief snapshots when briefs changed.

The "PR also accidentally re-recorded the wrong episode" failure mode (HOM-181, HOM-189) becomes structurally impossible: any wrong-episode recording is visible in `recordings/p3_pre_scan.json` (transcript-derived) and `recordings/p4_design_system.json` (palette/voice/topic-derived) on `git diff` before the operator opens the PR.

## 7. Which incidents this prevents — and which it does not

Restating §1's honest scoping with concrete mechanisms. Three buckets:

**Defused cleanly (3 of 7):**

1. **HOM-189 (worktree-bound paths):** no path strings in state for Phase 4 artifacts at all. Worktree-invariant by construction. `EpisodePaths` resolves at materialiser time, after replay has already validated state.
2. **HOM-195 family (`EpisodePaths` echoes leaking into cache keys):** subsumed for Phase 4 — the whole motivation ("remove worktree-bound absolute paths from state-derived cache keys") disappears for these nodes by construction. Phase 3 retains `EpisodePaths` for genuine on-disk binary inputs; that's correct usage.
3. **HOM-216 (cache vs disk drift on scene HTML):** the on-disk `compositions/*.html` no longer exists in the committed fixture after D2. The cache contains a canonical 3-beat plan plus three scene HTMLs; the materializer regenerates disk from cache. The `e014830` 4-beat HTML residue is deleted with the rest of `tests/fixtures/.../hyperframes/compositions/`.

**Defused partially (1 of 7):**

4. **HOM-181 (wrong source episode, silent skip):** the dominant root cause was `requires_fixture_cache` treating "file present" as "cache valid" — that's a test-harness predicate bug fixed independently of artifact sourcing. State-first reduces blast radius (a re-record-against-the-wrong-episode mistake would surface a different transcript / palette / strategy in `recordings/*.json` on `git diff` before the operator opens the PR), but the silent-skip itself is unrelated to where artifact bodies live.

**Not defused (3 of 7) — orthogonal classes; complementary fixes needed:**

5. **HOM-154 `dffe526` (brief-churn re-record):** legitimate `_CACHE_VERSION` bump on `p4_strategy` invalidated cache rows. Re-record cost is paid LLM dispatch on the bumped node + downstream. State-first changes nothing about *whether* the dispatch happens. It does shrink *recovery cost*: post-bump, the materializer regenerates disk artifacts at $0 from the new cache rows, no cascade of stale `compositions/*.html` to commit. But the dollar cost of the bump is unchanged. **Complementary fix:** none in this spec; treat as orthogonal. Long-term mitigations belong to a separate ticket on brief-stability discipline (e.g. brief-snapshot review gating bumps).
6. **HOM-154 `752056f` (gate-shape change re-record):** identical mechanism — `gate_animation_map_classify`'s output schema mutated, cache rows obsoleted, paid re-record. Same orthogonality as 5. **Complementary fix:** §12 Risks & rollback notes the brief-snapshot review surface does NOT today cover `output_schema` mutations — a gate-shape change can land without anyone reading the schema diff. Adding `output_schema` to the snapshot surface is a separate, small ticket.
7. **HOM-227 (filed against stale `state*.json`):** operator habit, not architecture. State-first does shrink the surface (one `cache.db` to `sqlite3`-interrogate instead of a sprawl of state files), but inventing a stale state.json from a failed run is a failure of pre-filing verification, fixed by memory `feedback_verify_fixture_state_before_filing_tickets`. **Complementary fix:** none in this spec; the memory entry is the canonical fix.

**Net:** state-first is a real architectural improvement for the artifact-sourcing class. It is not a silver bullet for the schema-evolution or process-discipline classes. The first draft of this spec claimed otherwise; this revision walks that back.

## 8. HOM-216 disposition under the new model

- The 3-beat plan in committed `cache.db` is authoritative — it is what was actually recorded, and reproduces the assemble step deterministically.
- The 4-beat HTML on disk is residue from a different attempted run with no provenance in any cached state.
- Migration cutover (§10 step D) deletes `tests/fixtures/.../hyperframes/compositions/`, `tests/fixtures/.../hyperframes/index.html`, `tests/fixtures/.../edit/DESIGN.md`, `tests/fixtures/.../edit/.hyperframes/expanded-prompt.md`, etc. The materializer regenerates the tree.
- Playwright runs in HOM-216 turn green against the regenerated 3-beat tree; the test changes scope from "verify our committed scene HTML matches snapshots" to "verify materializer output of canonical fixture matches snapshots". Fewer moving parts.
- No re-record. No paid LLM. HOM-216 becomes a one-day cleanup task once the migration lands.

## 9. What NOT to do

1. **"Re-record again with a 4-beat plan to match the disk."** Same de-sync next time anyone touches `p4_plan`. Treats the incident as a content bug; it is an architecture bug.
2. **"Add `compositions/*.html` to the fixture commit and require all bodies in lockstep."** Adds a new commit-protocol invariant. Two-source-of-truth problems cannot be solved by adding sources of truth — only by removing them.
3. **"Add sha256 of `compositions/` into cache key."** Fingerprint chasing — same class as HOM-195 / HOM-225 / HOM-229. Today's `EpisodePaths` migration already proved this approach is whack-a-mole; adding more files to keys grows the surface.
4. **"Use git-LFS for the HTML."** Solves storage, not correctness. The committed disk artifact still drifts from cache.
5. **"Replay re-runs the LLM if disk is missing."** Re-introduces non-determinism. Defeats the $0 promise of replay mode (CLAUDE.md §"Testing infra — fixture replay").
6. **"Make `p4_beat` return both path and content."** Three sources of truth (cache row, file path, file body). Worse than today.
7. **"Amend HOM-216 to commit four scene HTMLs."** Same as 2. Even if it greens HOM-216 today, the next brief change re-opens the same drift.

## 10. Migration plan

Estimated ~10–15 PR-days plus one paid wave-acceptance run. Each PR keeps both the old disk-write side effect *and* the new state-return value during the migration window so the tree stays green; the cutover is split across two PRs (D1 read-switch and D2 strip-and-delete) — see Sequencing safety.

### Step 0 — Pre-migration spike (HARD GATE, ~$10 budget, 1 day)

**This step gates the entire migration. If acceptance fails, the rest of step A onward does not start and the team pivots to BaseStore (§6.0 fallback path).**

Reason: HOM-134 (`p4_captions_layer.py:172-180`, `p4_beat.py:174 output_schema=None`) is documented prior evidence that for a large-body creative node, the dispatched sub-agent emits prose ("Wrote captions.html (...)") rather than a JSON object containing the body, and the `_schema_extract.py` JSON-from-fenced-code-block extractor raises `SchemaValidationError`. The prior decision retreated to FS-source-of-truth; this spec proposes reversing it. We must prove the reversal works on the current model tier before sinking ~10 PR-days into it.

**Scope:** `p4_beat` only. Single beat. Single brief revision. No topology changes. No materializer.

**Status 2026-05-10:** spike executed (HOM-243 / PR #136), 6/6 PASS (1 pilot + 5 acceptance), 0 `SchemaValidationError`, 0 retries, 0 truncation, 0 JSON-escape corruption. `html_chars ∈ [5524, 7238]` on `claude-opus-4-7`. Step A clear to start. Re-trigger this gate if a downstream node downgrades to a smaller tier (Haiku/Sonnet) or if the brief mutates structurally.

**Procedure:**

1. Branch off `main`. Add a Pydantic `BeatBody(BaseModel): html: str` schema. Edit `p4_beat.py:174` to `output_schema=BeatBody`, drop `Write` from `allowed_tools`, swap `result_key="_beat_unused"` → `result_key="scenes"` (or per-`Send` write into `compose.scenes[scene_id]`).
2. Edit `briefs/p4_beat.j2` to drop the "write to `<scene_html_path>`" instruction; replace with "return the scene HTML body as the `html` field of your structured response. Do not call the `Write` tool; it is not in your allowed_tools list. Your response must be a single fenced JSON block matching the schema." Cite the canonical `~/.agents/skills/hyperframes/SKILL.md` paths unchanged.
3. Run `HOMESTUDIO_TEST_MODE=record-on-miss pytest tests/test_graph_replay.py::test_p4_beat_smoke -k <one-beat>` five times against the canonical fixture. Record extraction success/failure for each attempt. Each successful attempt costs ~$1.50 — total budget cap $10.

**Acceptance:**

- 5/5 attempts must produce a `BeatBody` with `len(html) > 5_000` and (after a quick `npx hyperframes lint`-style sanity check) no truncation / no JSON-escape corruption.
- 0 `SchemaValidationError` retries observed across the 5 runs (`backends/_router.py` retry counter must stay at 0).

**On failure** (any attempt below acceptance):

- File the spike's transcripts as evidence.
- Pivot the rest of this spec to the §6.0 BaseStore fallback path: producer nodes keep `Write` in `allowed_tools`, post-dispatch hook reads the file and `runtime.store.aput`s it under namespace `(slug, "compose")`, downstream nodes fetch via `runtime.store.aget`, fixture commits one BaseStore SQLite file alongside `cache.db`. Step A's schema additions still apply (just with content-hash keys instead of full bodies); steps B–G's brief edits and topology stay materially the same.
- Either path proceeds; the failure does NOT kill the epic, only one of the two backing strategies.

**On success:** spike PR lands as Step 0; step A starts immediately.

### Step A — State schema additions + `compose.scenes` reducer (1 PR, ~1 day)

Add `compose.scenes`, `compose.design.design_md`, `compose.expansion.expanded_prompt`, `compose.captions.html`, `compose.index_html`, `compose.persist.session_block`, `compose.materialize` to `graph/src/edit_episode_graph/state.py`. All new fields `total=False`. No node touches them yet. Schema-migration test asserts old shape still parses.

**HOM-231 implementation note (2026-05-10):** `compose.index_html` was placed flat under `ComposeState`, not nested under `compose.assemble.*` as originally written. Rationale: only `p4_assemble_index` produces it, no sibling assemble-body fields exist, and the existing `compose.assemble.*` namespace holds metadata (`assembled_at`, `beat_names`) not bodies. Future migration to nested form is mechanical if a sibling appears. The §11 sizing table still references `compose.assemble.index_html` for prose continuity, but the schema key is `compose.index_html`.

**Cross-cutting infrastructure landed in this same PR (moved here from step B's `p4_beat` sub-PR):**

`compose.scenes` is `Annotated[dict[str, SceneState], _scenes_merge]` where `_scenes_merge(left, right)` is a deterministic dict-union reducer:

```python
def _scenes_merge(left: dict, right: dict) -> dict:
    """Union-merge two scenes dicts. On conflict (same scene_id from two
    parallel Sends) the right-hand value wins — last-Send-write semantics
    matching LangGraph's standard channel-write order. Output dict is
    sorted by scene_id so downstream content-hash fingerprints are
    iteration-order independent."""
    merged = dict(left)
    merged.update(right)
    return {k: merged[k] for k in sorted(merged)}
```

The sorted-by-key output is load-bearing for the materializer's cache key (§6.3) — Python dict iteration is insertion-ordered, and parallel `Send` completion order is non-deterministic, so an unsorted union would produce different cache keys for the same scene set. The reducer is the only place we control this; getting it right in step A means every subsequent step inherits a stable fingerprint.

**Unit tests in this PR (target file `tests/test_state_reducers.py`):**

- `test_scenes_merge_union` — disjoint dicts merge to union.
- `test_scenes_merge_conflict_right_wins` — same key, right-hand value wins.
- `test_scenes_merge_sort_stable` — `_scenes_merge({"b":1, "a":2}, {"c":3})` and `_scenes_merge({"c":3}, {"b":1, "a":2})` return dicts with the same `list(d.keys()) == ["a", "b", "c"]`.
- `test_scenes_merge_fingerprint_invariant` — `sha256(json.dumps(left|right, sort_keys=True))` is invariant under reducer-input reordering.

Without this PR landing the reducer + tests *first*, `p4_beat`'s step-B PR would have to ship the cross-cutting reducer alongside its node-specific changes, hiding the topology contract inside a node-scoped review.

### Step B — Convert each creative node from disk-write to state-return (~6 PRs, ~1 day each)

Six independent, sequential PRs; each:

- **Consumers of `compose.scenes` must read from the new top-level `state['scenes']` channel, not `state['compose']['scenes']`** (see HOM-234 amendment below — nested `Annotated` reducers do not fire; the channel was promoted to `GraphState.scenes`). Any future `p4_assemble_index` / `p4_captions_layer` rewire that consumes per-scene fragment bodies MUST read the top-level channel; reading the deprecated nested key returns stale data because no reducer ever fired there.

1. Bumps `_CACHE_VERSION` for the node.
2. Edits the brief (`briefs/<node>.j2`) to drop the "write to `<path>`" instruction and require structured return (`html: str` or `markdown: str`).
3. Updates `LLMNode` config: drops `Write` from `allowed_tools`, swaps the placeholder `result_key="_*_unused"` for a real key, defines an `output_schema` Pydantic model with the body field.
4. Adds dual-write: the node still writes the body to disk (using the body it received from the LLM, not via the `Write` tool) so downstream disk-readers (today's `p4_assemble_index.py:588` etc.) keep working.
5. Updates the brief snapshot, fingerprint registry, and replay smoke (per CLAUDE.md §"Definition of done for LLM-node tickets").

Order: `p4_design_system` → `p4_prompt_expansion` → `p4_beat` (the `_scenes_merge` reducer landed in Step A; this PR only wires `p4_beat`'s per-`Send` writes into the top-level `scenes` channel — promoted out of `ComposeState.scenes` by the HOM-234 amendment below) → `p4_captions_layer` → `p4_assemble_index` (rewires inputs from state, but keeps writing to disk) → `p4_persist_session`.

**Amendment — HOM-234 pre-check (2026-05-15).** Step A wired the `scenes` reducer at `ComposeState.scenes` (nested inside the `compose: Annotated[..., dict_merge]` channel). The HOM-234 pre-check (`tests/test_compose_scenes_fanout.py`) empirically proved that LangGraph reducers do NOT walk nested `Annotated` channels — only the top-level reducer fires, and the outer `dict_merge` ran shallow `{**left, **right}` over whole `scenes` dicts, so the second parallel `Send` from `p4_beat` clobbered the first. The fix landed in the HOM-234 PR: `scenes` was promoted to a TOP-LEVEL channel on `GraphState` (`scenes: Annotated[dict[str, SceneState], _scenes_merge]`). The deprecated `ComposeState.scenes` slot remains on the schema for forward-compat parsing of pre-HOM-234 checkpoints, but new producers (Step B `p4_beat` onward) write to `state["scenes"][scene_id]`, not `state["compose"]["scenes"][scene_id]`. Downstream consumers in later Step-B PRs (`p4_assemble_index`, `p4_captions_layer` inputs, etc.) and the Step D1 read-switch must read from the top-level channel.

After Step B all six creative nodes return body strings in state *and* still write to disk. The fixture cache.db's bodies are now populated (after one re-record per node, but each is replayable at $0 once recorded).

**Step B progress (landed PRs):** B1 `p4_design_system` (HOM-232, PR #138) · B2 `p4_prompt_expansion` (HOM-233, PR #139) · B3 `p4_beat` (HOM-234, PR #140) · B4 `p4_captions_layer` (HOM-235) — sub-agent returns `CaptionsOutput.html`; orchestrator dual-writes to `EpisodePaths(slug).captions_block_path`.

### Step C — Add `p4_materialize_disk_node` as no-op (1 PR, ~1 day)

New node module `nodes/p4_materialize_disk.py`. Wired into `graph.py` between `p4_persist_session` and `studio_launch` (or per `_routing.py`'s decision tree). Initially a no-op: reads `compose.*.html` / `compose.*.markdown` from state and asserts they exist; does not write. Cache policy: `make_key` keyed on body hashes.

This step gives reviewers a chance to validate the materializer's read shape against the state schema before any disk writes are routed through it.

### Step D1 — Read-switch (1 PR, ~1 day; one-week soak before D2)

The first half of the cutover. Goal: every consumer reads state, but disk dual-writes stay (committed fixture artifacts stay committed). Reversible.

1. Activate atomic writes in `p4_materialize_disk_node` (it now produces disk artifacts in addition to the producers' dual-writes — temporarily redundant, intentional).
2. `p4_assemble_index` switches its read of scene/captions HTML from `read_text` (`p4_assemble_index.py:588`, `:604`) to `state["compose"]["scenes"][sid]["html"]` / `state["compose"]["captions"]["html"]`. The disk reads stay as fallback inside an `if state.get(...)` guard with a logged warning ("falling back to disk read"); after the soak window any warning logs trigger investigation, not a green tree.
3. Add `tests/_helpers/materialize_into_tmpdir.py` for the Playwright tests so they exercise the materializer-regenerated tree, not the committed disk tree.
4. HOM-216 Playwright snapshots turn green here against the materializer-regenerated tree (the committed `compositions/*.html` are still on disk, but the test path no longer reads them).

**Soak window (~1 week, calendar time):** all production runs, all developer replay runs, all Studio sessions exercise the read-switch path. Operators watch for `compose.*` state-read fallback warnings, in-flight thread checkpoints failing to deserialise (the schema-loosening test from §6.1 should prevent this, but in-flight observability beats hope), and any HOM-216-shaped Playwright regression. Rollback is `git revert <D1>` and re-record nothing — disk artifacts are still committed and authoritative.

### Step D2 — Strip dual-writes + delete committed artifacts (1 PR — only irreversible commit)

After the D1 soak window with no fallback warnings observed:

1. Strip dual-writes from each producer node (the `Write` tool fallback added in step B). Producers now return state only.
2. Strip the disk-read fallback guards in `p4_assemble_index` (added in D1 step 2). State reads only.
3. `git rm -r tests/fixtures/episodes/canonical-portrait-talking-head/hyperframes/` and `tests/fixtures/episodes/canonical-portrait-talking-head/edit/{DESIGN.md,.hyperframes/}`. Add the entries to `.gitignore`.
4. Verify the replay smoke + Playwright still green after the `git rm` (materializer regenerates everything from cache.db on demand).

This PR is the irreversible point. All preceding PRs are partial migrations that keep the tree green; D1 is reversible by revert; D2 deletes the disk artifacts from history (still recoverable from git history, but `git rm` plus a fresh `git gc` after a few months removes them from clones — the `cache.db` becomes the only source of truth).

**Why split?** A single-PR cutover combined the breaking schema change, the consumer-read-switch, and the artifact deletion into one commit. If any one of those landed buggy (most likely candidate: in-flight checkpoint compatibility — a thread paused mid-Phase-4 in Studio at D-1 timestamp resumes after D and tries to read `state["compose"]["scenes"]` against a dict-merge reducer that didn't exist in its checkpoint), the revert had to undo all three. D1/D2 split gives a real soak window for the in-flight class without coupling it to artifact deletion.

### Step E — Decommission EpisodePaths reads from Phase 4 cache keys (1 PR, ~½ day)

Remove `compose.design_md_path`, `compose.expanded_prompt_path`, `compose.captions_block_path` from `state.py` (they are now legacy echoes only). Update `_cache_key` builders in `p4_plan`, `p4_beat`, `p4_captions_layer`, `p4_assemble_index`, `p4_persist_session` to use `string_fingerprint(state[...]["body"])` extras instead of `file_fingerprint(EpisodePaths(...).<path>)` files.

`p4_scaffold` and `p4_catalog_scan` are unaffected (no body inputs). Phase 3 nodes are unaffected.

### Step F — Wave acceptance (one paid run, ~$8–12)

`HOMESTUDIO_TEST_MODE=record pytest tests/test_graph_replay.py` against the canonical fixture under the new architecture. Records a fresh `cache.db` from scratch on production tier. Eyeballs `recordings/*.json` for sanity. Commits the new cache.db + JSON dump.

Subsequent re-records on brief / schema bumps remain `$0 → $cost-of-bumped-node-only` via `record-on-miss`.

### Step G — Cleanup (1 PR)

- Retire `_paths.project_root()` workarounds in places where they are now load-bearing only for legacy-echo fields (TBD during step E).
- Update CLAUDE.md §"Studio replay (operator runbook)" to drop `--allow-blocking` (Phase 4 cache keys no longer issue synchronous file reads during graph draw — the file reads were `_caching.file_fingerprint` calls on `compose.design_md_path` etc., which step E removed).
- Update CLAUDE.md §"Definition of done for LLM-node tickets" item 5 (fingerprint invalidation): the registry's `mutation_fn` for creative nodes shifts from "edit upstream artifact file" to "mutate upstream state body string."
- Update CLAUDE.md §"Worktree data-dir resolution": the warning still applies (Phase 3 binary artifacts), but Phase 4 worktree-binding is no longer a category.

### Sequencing safety

Step 0 is a hard gate; on failure the migration pivots to BaseStore (§6.0). Steps A–C are independent partial PRs that always keep the tree green. Step D1 (read-switch, dual-write retained) ships behind a code-review gate verifying all six producers have shipped their state-return PRs; D1 is fully revertible. After a one-week soak with no fallback warnings, D2 (strip dual-writes, `git rm` artifacts) ships as the irreversible commit. Step E ships after D2 when the `compose.*_path` legacy-echo fields are no longer read anywhere. Step F is operator-driven; step G is opportunistic cleanup.

If step D1 is reverted mid-rollout, Steps A–C continue working (the dual-write fallback keeps disk populated, and the materializer's writes are content-hash-idempotent against the producers' writes). If step D2 is reverted, the deleted fixture artifacts must be restored from `cache.db` via the materializer before the tree turns green again — this is by design, the irreversibility marker.

## 10b. Atomic-record protocol — complementary fix for partial-commit drift

This section addresses incidents 1 (HOM-181) and 7 (HOM-216) at a different layer than state-first. Even after the state-first migration lands, the *recording* step (operator runs `record-on-miss`) produces two artefacts that must be committed together: `cache.db` (binary) and `recordings/*.json` (human-readable). A partial commit — `cache.db` updated but `recordings/*.json` stale, or vice versa — reproduces the HOM-216 failure shape one layer up. State-first does not prevent this; the operator's `git add` is the failure point.

**Proposed (future sub-issue, number TBD; NOT to be filed as part of this spec — HOM-243 is the spike PR #136):**

A `scripts/record_fixture.py` wrapper plus an opt-in `pre-commit` hook:

1. Wrapper invocation: `python scripts/record_fixture.py <slug> [<node>...]`. Internally runs `HOMESTUDIO_TEST_MODE=record-on-miss pytest tests/test_graph_replay.py::<filter>`, then immediately runs `python -m tests.dump_recordings <slug>` to regenerate the JSON dump from the just-updated `cache.db`.
2. Validation step: re-loads the regenerated JSON and re-encodes via the same `JsonPlusSerializer` to verify roundtrip stability before allowing `git add`.
3. Atomic stage: only after validation passes does the wrapper run `git add tests/fixtures/episodes/<slug>/cache.db tests/fixtures/episodes/<slug>/recordings/`. If validation fails, the wrapper exits non-zero and refuses to stage.
4. Optional pre-commit hook (project-local `.pre-commit-config.yaml`): if any file under `tests/fixtures/episodes/<slug>/cache.db` is staged but no corresponding `recordings/<node>.json` is staged (or vice versa), block the commit with a message pointing to the wrapper.

The hook is opt-in (we don't impose pre-commit on every contributor), but the wrapper becomes the documented happy path in `tests/README.md`.

**Why this is complementary to state-first, not redundant:** state-first stops the cache and disk from drifting at *replay time* (the materializer is the only writer; cache is the only source). The atomic-record protocol stops the cache and the JSON dump from drifting at *commit time* (the wrapper is the only stager; both are produced from the same `cache.db`). Two different commits, two different drift surfaces, two different fixes.

This is left as a sub-issue candidate (HOM-243) and not blocked into the state-first epic — implementable independently, in any order. Mentioned here so the design intent is recorded; do NOT create the ticket as part of this spec's PR (that's a separate scoping decision).

## 12. Risks & rollback

Each risk lists the failure mode (one line), the indicator that would tell us it's manifesting, and the cheapest revert path.

### 12.1 Structured-output extraction fragility for 30 KB HTML strings

**Failure mode:** sub-agent emits prose ("Wrote scene-hook.html (...)") instead of a JSON object containing the body; `_schema_extract.py` raises `SchemaValidationError`; `_router.py` retries until backend exhaustion; paid LLM calls burn at the failure rate.

**Indicator:** any `SchemaValidationError` for a creative node in the `record-on-miss` smoke logs during step 0 or step B PRs. The §7 spike's acceptance bar (5/5, 0 retries) is the explicit gate.

**Rollback:** abandon structured-output for large bodies; pivot to §6.0 BaseStore fallback (producers keep `Write`, post-dispatch hook reads file → `runtime.store.aput`). Specs A onward survive the pivot — only the brief edits and `output_schema` declarations change. Cheapest revert: spike PR (Step 0) is freestanding; on failure no main-tree code changed.

### 12.2 In-flight checkpoint compatibility during D1 → D2 transition

**Failure mode:** a thread paused mid-Phase-4 in Studio (e.g. at the `strategy_confirmed_interrupt` HITL) at D1-1 timestamp resumes after D2 has shipped. The resumed thread's checkpoint contains the old schema (no `compose.scenes.html`, no dict-merge reducer); reading from the new state shape fails or silently returns empty.

**Indicator:** `compose.*` state-read fallback warning logs from D1's guarded fallback paths during the soak window. If the warnings fire, D2 does not ship until the in-flight thread is drained or its checkpoint manually migrated.

**Rollback:** D2 ships the irreversible commit only after one calendar week of zero fallback warnings. If D2 ships and an in-flight thread breaks, the cheapest revert is `git revert <D2>` plus a manual `cache.db → disk` materialiser run for the affected fixture; the thread restarts from the last successful checkpoint.

### 12.3 Materializer cache-key non-determinism (dict iteration order)

**Failure mode:** the materializer's cache key is "sha256 of all body fields concatenated." Python dict iteration order matches insertion order, but parallel `Send` completion order is non-deterministic. Two equivalent state inputs produce different cache keys depending on which `Send` finished first → cache misses where it should hit → re-runs the materializer against identical inputs.

**Indicator:** materializer cache hit-rate < 100 % on consecutive replay runs against the same fixture (verifiable via `__metadata__.cached: true` count in Studio trace).

**Mitigation (in §6.0 reducer + Step A unit tests):** the `_scenes_merge` reducer sorts its output by key, and the materializer's cache-key construction MUST iterate `sorted(state["compose"]["scenes"].items())` and concatenate body bytes in deterministic order. Step A's `test_scenes_merge_fingerprint_invariant` test pins this contract.

**Rollback:** if the test catches a regression post-merge, the fix is local to the materializer's `key_func` and `_scenes_merge` — no graph topology change, no schema migration. Sub-1-hour fix.

### 12.4 Brief-snapshot tests don't cover `output_schema` mutations

**Failure mode:** a creative node's `output_schema` field changes from `BeatBody` to `BeatBodyV2` (added field, renamed field). The Jinja brief is unchanged; `tests/snapshots/briefs/<node>.txt` is unchanged; brief-snapshot review passes. But the cache-key fingerprint changes (`make_llm_key`'s `NodeConfig` includes schema-derived bits via `tier`/`model`/etc but NOT `output_schema` directly), or worse, doesn't change and rows that *should* invalidate stay cached against the old shape — exactly HOM-154 `752056f`'s mechanism.

**Indicator:** a creative-node PR ships an `output_schema` change with no `_CACHE_VERSION` bump and no fingerprint-registry entry. Currently no automated check catches this.

**Mitigation:** out of scope for this spec, but flag in §12 so a follow-up ticket extends `tests/test_brief_snapshots.py` to also snapshot the `output_schema.model_json_schema()` output per node. Trivial — Pydantic emits canonical JSON Schema. Sub-half-day implementation.

**Rollback:** if a state-first node lands with this shape-drift latent, the symptom is the same as HOM-154 `752056f`: paid re-record on next iteration. Cost ~$5–10 per missed bump.

## 11. Sizing budget

The state envelope grows per Phase 4 episode by:

| Field | Typical size |
|---|---|
| `compose.design.design_md` | 2–5 KB |
| `compose.expansion.expanded_prompt` | 3–8 KB |
| `compose.scenes[*].html` × 3–5 scenes | 20–40 KB each → 60–200 KB total |
| `compose.captions.html` | 2–10 KB |
| `compose.assemble.index_html` | 30–80 KB (full root composition incl. tokens, shim, nested fragments) |
| `compose.persist.session_block` | 1–3 KB |

Total Phase 4 state delta: ~100–300 KB per episode.

Three sizing checks:

1. **`JsonPlusSerializer` roundtrip on multi-line nested HTML/CSS/JS.** The serializer is JSON with type-tag extensions for non-JSON-native types (datetime, set, Path, etc.); plain UTF-8 strings roundtrip trivially regardless of internal characters. Verified against `langgraph.checkpoint.serde.jsonplus` source — strings go through `json.dumps(s, ensure_ascii=False)`.
2. **`SqliteCache` row size.** SQLite has a default `SQLITE_MAX_LENGTH` of 1 GB. A 300 KB blob is unremarkable. WAL throughput on writes of this size is sub-millisecond on a modern SSD.
3. **Checkpointer (`SqliteSaver`) roundtrip cost.** The checkpointer serialises the *entire* state on every superstep. At ~300 KB per checkpoint × ~25 supersteps in a Phase 4 run = ~7.5 MB of cumulative writes per thread. A 30-day fixture-replay session producing ~40 threads = ~300 MB of `checkpoints.sqlite`. Empirically tolerable; if growth becomes painful we add a thread-rotation policy (out of scope here).

The pre-migration state is ~50–100 KB per episode (mostly transcript and EDL JSON). Post-migration is 3–5× larger but still well under the byte-budget threshold where checkpoint replay becomes user-perceptibly slow.

## 13. Open questions

1. **Will the LLM sub-agent reliably emit a single `html: str` Pydantic field?** Today the `Write` tool surface is forgiving — the sub-agent can write any string of any length. A structured-output schema with a single `html: str` field is stricter: malformed JSON in the response, or schema drift between brief and Pydantic model, will surface as a parser error rather than a silently-truncated file. Mitigation: keep the body field unconstrained (no length limit, no regex), and wrap the call in the existing retry-on-`SchemaValidationError` machinery already present in `_llm.py`. Open: do we need a structured-output "raw HTML" mode that bypasses JSON entirely for the body field? (Probably not — Anthropic's tool-use response format already handles long string fields.)
2. **`compose.scenes` reducer correctness under `Send` fan-out.** Five parallel `Send`s each emit a partial dict `{scene_id: {"html": "..."}}`. The reducer must merge into a union dict, *not* overwrite. LangGraph's `add_messages` is the canonical reference; a generic dict-merge channel is a few lines but needs a smoke test under the real `Send` path before step B's `p4_beat` PR lands.
3. **Migration of in-flight runs.** A run started under the old schema and resumed after a partial migration would see new state fields it does not know how to read. Mitigation: the `total=False` schema makes both old and new shapes valid; the dual-write window (Step B) means producers populate both old and new fields. Acceptable.
4. **Materializer cache hit on `index.html` body change but no scene body change.** If `p4_assemble_index` runs and produces a different `index_html` (e.g. tokens changed), the materializer's cache key (sha256 of all body fields) misses — correct. If only the materializer's *brief* / version changes, the cache misses — correct. Edge case: what if the operator manually edits a file under `<edit_dir>/` between Studio runs, expecting the materializer to detect and overwrite? Current design says: it won't, because the cache key fingerprints state, not disk. This is a deliberate trade — the materializer is "state to disk", not "state to disk with disk-as-secondary-truth". Documented in the materializer's docstring; if user demand surfaces, add a content-hash check at write time as a follow-up.
5. **Wave-acceptance recording cost.** ~$8–12 once at step F. Subsequent re-records (on brief / schema bumps that affect the canonical fixture) are scoped to the bumped node + downstream via `record-on-miss`, mirroring the current model.
6. **Breaking-change announcement.** The cutover (step D) `git rm`s committed fixture files. Any open feature branch that touched those files merges with conflicts. Plan: announce in the M-wave kickoff retro, freeze fixture-touching PRs for the cutover day, land step D first thing in the morning, unfreeze.

## 14. Acceptance criteria for the epic

- All six creative Phase 4 nodes return body strings in state. No production node calls the `Write` tool for canonical text artifacts.
- `p4_materialize_disk_node` is the only Phase 4 writer to disk for text artifacts. Its cache policy uses `make_key` keyed on body content hashes.
- `tests/fixtures/episodes/canonical-portrait-talking-head/` contains exactly four entries: `raw.mp4`, `intent.yaml`, `cache.db`, `recordings/`.
- Replay smoke `pytest tests/test_graph_replay.py` runs at $0 against the post-cutover cache.db; every Phase 4 node hits.
- HOM-216 Playwright snapshots green against materializer-regenerated tree.
- `compose.design_md_path` / `compose.expanded_prompt_path` / `compose.captions_block_path` removed from `state.py`. No Phase 4 cache key uses `file_fingerprint`.
- CLAUDE.md sections updated per Step G.
- One paid wave-acceptance run lands the new fixture; no follow-on re-records required for unrelated PRs.

## 15. References

- Current state schema: `graph/src/edit_episode_graph/state.py:165-235` (`ComposeState`, `DesignState`, `ExpansionState`, `CaptionsState`, `AssembleState`).
- Producer call sites: `graph/src/edit_episode_graph/nodes/p4_design_system.py:128-180`, `p4_prompt_expansion.py:142`, `p4_beat.py:169-194`, `p4_captions_layer.py:187-189`, `p4_assemble_index.py:588-638`, `p4_persist_session.py:209-211`.
- Cache mechanism: spec `2026-05-06-langgraph-node-caching-design.md` (HOM-132 epic) — unchanged in mechanism, narrowed in surface.
- Fixture-replay model: spec `2026-05-08-testing-infra-fixture-replay-design.md` (HOM-179 epic), CLAUDE.md §"Testing infra — fixture replay", §"Definition of done for LLM-node tickets".
- Replay-dispatch carve-out: `tests/_helpers/replay_dispatch.py:115-127` (`_decode_channel_writes`), `:246-247` (`loads_typed` reconstruction); CLAUDE.md §"Exception — fixture-replay test inspection".
- Memory:
  - `feedback_verify_fixture_state_before_filing_tickets` (HOM-227 retro)
  - `feedback_fixture_prewarm_project_root` (HOM-189)
  - `feedback_langgraph_native_primitives` (CachePolicy / SqliteCache canon)
  - `feedback_fixture_replay_dod` (per-ticket DoD)
- Prior incidents (Linear): HOM-181, HOM-189, HOM-154, HOM-203, HOM-195 / HOM-222 / HOM-223 / HOM-224 / HOM-225 / HOM-226 / HOM-229, HOM-227 (cancelled), HOM-216 (current).
- LangGraph references: `langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer`, `langgraph.cache.sqlite.SqliteCache`, `langgraph.types.CachePolicy`. Docs: <https://docs.langchain.com/oss/python/langgraph/graph-api>, <https://langchain-ai.github.io/langgraph/reference/types/>.

## 16. CLAUDE.md sections to amend after this epic lands (informational; do not edit now)

- **§"Idempotency"** — clarify that Phase 4 cache keys fingerprint state-string bodies, not on-disk paths. The §"LLM cache keys include routing-config fingerprint" paragraph remains correct in mechanism but its example (`p3_strategy.timeout_s 120 → 300`) stays as-is; add a sibling paragraph noting that creative-node `extras=` now contains body sha256s.
- **§"Worktree data-dir resolution"** — narrow to "Phase 3 binary artifacts" scope. Phase 4 is no longer worktree-bound.
- **§"Studio replay (operator runbook)"** — drop the `--allow-blocking` requirement once step E lands (no synchronous file reads during graph draw for Phase 4 nodes). The `HOMESTUDIO_PROJECT_ROOT` requirement remains, since Phase 3 still uses it.
- **§"Definition of done for LLM-node tickets"** — item 5 (fingerprint invalidation) registry entries shift from "edit upstream artifact file" mutations to "mutate upstream state body string" mutations. Update the helper's signature to accept state-string mutations naturally.
- **§"Testing infra — fixture replay"** — update the reviewer-expectations bulleted list: the cache.db diff and JSON dump are still the review surfaces, but the fixture directory listing shrinks (no `hyperframes/`, no `edit/DESIGN.md`, no `edit/.hyperframes/`).
- **§"Exception — fixture-replay test inspection"** — the carve-out for `replay_dispatch.py` remains, but the "go through `compiled.invoke`" failure mode argument weakens once cache keys no longer fingerprint test-machine paths. Re-evaluate at step G whether the helper can be retired in favour of the runtime path.

End of spec.
