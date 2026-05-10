# State-first artifacts — single-source-of-truth for graph node outputs

**Date:** 2026-05-10
**Status:** Proposed (awaiting user review)
**Linear:** Epic placeholder `HOM-NEW-state-first-artifacts` (sub-issues to be created on approval — see §10).
**Scope:** Make graph node return values the source of truth for produced artifacts (DESIGN.md, expanded-prompt.md, beat-scene HTML, captions HTML, root index.html, project.md session blocks). Side effects to disk move to a single dedicated terminal materializer node. Eliminates the entire class of "cache stores metadata about a write that may or may not still exist on disk" bugs that produced the seven incidents catalogued in §2.

---

## 1. Problem

Re-running the graph on an already-recorded fixture cache should be deterministic at $0 cost (CLAUDE.md §"Testing infra — fixture replay"; spec `2026-05-08-testing-infra-fixture-replay-design.md` §3 L1). It is not, in a way that has produced seven distinct incidents over three weeks. Each incident was diagnosed and fixed on its own terms; none of the fixes addressed the underlying class. HOM-216 is the seventh instance and made the pattern legible: committed `cache.db` carries a 3-beat plan (hook / thesis / payoff), the working tree carries a 4-beat plan (hook / problem / pivot / payoff), and the two are claimed to be "the canonical fixture." Neither shape is recoverable from the other, because the cache stores `assemble.assembled_at` and a list of beat names (`p4_assemble_index.py:630-638`), not the HTML bodies of the scenes themselves.

The seven incidents are not seven bugs. They are seven facets of one architectural mistake: **graph nodes write large produced artifacts to disk as side effects, while their LangGraph cache row stores only a small metadata delta about that write.** A `CachePolicy` cache hit rehydrates the metadata delta into state — it does not replay the side effect. Disk and cache drift become the steady state, and every PR keeps surfacing one more way they drift.

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

Fan-out merge for `compose.scenes`: today there is no merge problem because each `Send` writes a unique file. After migration, parallel beats need a merging reducer. Use a `TypedDict` with an `Annotated[dict, _scenes_merge]` reducer (or equivalent dict-merge channel) so `compose.scenes` is the union of partial dicts emitted by each `Send`. Verified canon — `langgraph.graph.message.add_messages` is the textbook example; a dict-merge analogue is a few lines.

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

## 7. Why this prevents each of the seven incidents recurring

1. **HOM-181 (wrong source episode):** cached state carries literal HTML and EDL bodies. Pointing at the wrong `raw.mp4` would change the transcript, the strategy, the EDL, the design — every JSON dump diff visibly. Caught by `git diff` before commit.
2. **HOM-189 (worktree-bound paths):** no path strings in state for Phase 4 artifacts at all. Worktree-invariant by construction. EpisodePaths resolves at materialiser time, after replay has already validated state.
3. **HOM-154 brief refreshes:** legitimate `_CACHE_VERSION` bumps still happen. But a re-record after a semantic-neutral brief change is now $0: only the bumped node and its downstream dependents re-execute (mechanism unchanged). Today, post-bump disk and cache drift between any pair of nodes; tomorrow, post-bump cache contains the new bodies and the materializer regenerates disk from cache.
4. **HOM-203 gate-shape change:** same as 3.
5. **HOM-195 EpisodePaths:** subsumed for Phase 4. Phase 3 retains EpisodePaths for genuine on-disk inputs; that's correct usage.
6. **HOM-227 ("what is fixture state"):** answered by `sqlite3 cache.db "SELECT count(*), node FROM cache GROUP BY node"`. Operator never needs a stale `state*.json` to reason about it.
7. **HOM-216:** the on-disk `compositions/*.html` no longer exists in the committed fixture. The cache contains a canonical 3-beat plan plus three scene HTMLs. The materializer regenerates disk from cache. The `e014830` 4-beat HTML residue is deleted with the rest of `tests/fixtures/.../hyperframes/compositions/`.

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

Estimated ~10–15 PR-days plus one paid wave-acceptance run. Each PR keeps both the old disk-write side effect *and* the new state-return value during the migration window so the tree stays green; the cutover (step D) is the only breaking commit.

### Step A — State schema additions (1 PR, ~½ day)

Add `compose.scenes`, `compose.design.design_md`, `compose.expansion.expanded_prompt`, `compose.captions.html`, `compose.assemble.index_html`, `compose.persist.session_block`, `compose.materialize` to `graph/src/edit_episode_graph/state.py`. All new fields `total=False`. No node touches them yet. Schema-migration test asserts old shape still parses.

### Step B — Convert each creative node from disk-write to state-return (~6 PRs, ~1 day each)

Six independent, sequential PRs; each:

1. Bumps `_CACHE_VERSION` for the node.
2. Edits the brief (`briefs/<node>.j2`) to drop the "write to `<path>`" instruction and require structured return (`html: str` or `markdown: str`).
3. Updates `LLMNode` config: drops `Write` from `allowed_tools`, swaps the placeholder `result_key="_*_unused"` for a real key, defines an `output_schema` Pydantic model with the body field.
4. Adds dual-write: the node still writes the body to disk (using the body it received from the LLM, not via the `Write` tool) so downstream disk-readers (today's `p4_assemble_index.py:588` etc.) keep working.
5. Updates the brief snapshot, fingerprint registry, and replay smoke (per CLAUDE.md §"Definition of done for LLM-node tickets").

Order: `p4_design_system` → `p4_prompt_expansion` → `p4_beat` (and the reducer for `compose.scenes`) → `p4_captions_layer` → `p4_assemble_index` (rewires inputs from state, but keeps writing to disk) → `p4_persist_session`.

After Step B all six creative nodes return body strings in state *and* still write to disk. The fixture cache.db's bodies are now populated (after one re-record per node, but each is replayable at $0 once recorded).

### Step C — Add `p4_materialize_disk_node` as no-op (1 PR, ~1 day)

New node module `nodes/p4_materialize_disk.py`. Wired into `graph.py` between `p4_persist_session` and `studio_launch` (or per `_routing.py`'s decision tree). Initially a no-op: reads `compose.*.html` / `compose.*.markdown` from state and asserts they exist; does not write. Cache policy: `make_key` keyed on body hashes.

This step gives reviewers a chance to validate the materializer's read shape against the state schema before any disk writes are routed through it.

### Step D — Cutover (1 PR — only breaking commit)

1. Activate atomic writes in `p4_materialize_disk_node`.
2. Strip dual-writes from each producer node (the `Write` tool fallback added in Step B). Producers now return state only.
3. `p4_assemble_index` switches its read of scene/captions HTML from `read_text` (`p4_assemble_index.py:588`, `:604`) to `state["compose"]["scenes"][sid]["html"]` / `state["compose"]["captions"]["html"]`.
4. `git rm -r tests/fixtures/episodes/canonical-portrait-talking-head/hyperframes/` and `tests/fixtures/episodes/canonical-portrait-talking-head/edit/`. Add the entries to `.gitignore`.
5. Add `tests/_helpers/materialize_into_tmpdir.py` for the Playwright tests.
6. HOM-216 turns green here.

This PR is the irreversible point. All preceding PRs are partial migrations that keep the tree green.

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

Steps A–C are independent partial PRs that always keep the tree green. Step D is the single breaking commit and ships behind a code-review gate that explicitly verifies all six producers have shipped their state-return PRs. Step E ships after D when the `compose.*_path` legacy-echo fields are no longer read anywhere. Step F is operator-driven; step G is opportunistic cleanup.

If step D is reverted mid-rollout, Steps A–C continue working (the dual-write fallback keeps disk populated, and the no-op materializer is harmless).

## 11. Sizing — does state stay under the JSON-plus serializer's comfort zone?

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

## 12. Open questions

1. **Will the LLM sub-agent reliably emit a single `html: str` Pydantic field?** Today the `Write` tool surface is forgiving — the sub-agent can write any string of any length. A structured-output schema with a single `html: str` field is stricter: malformed JSON in the response, or schema drift between brief and Pydantic model, will surface as a parser error rather than a silently-truncated file. Mitigation: keep the body field unconstrained (no length limit, no regex), and wrap the call in the existing retry-on-`SchemaValidationError` machinery already present in `_llm.py`. Open: do we need a structured-output "raw HTML" mode that bypasses JSON entirely for the body field? (Probably not — Anthropic's tool-use response format already handles long string fields.)
2. **`compose.scenes` reducer correctness under `Send` fan-out.** Five parallel `Send`s each emit a partial dict `{scene_id: {"html": "..."}}`. The reducer must merge into a union dict, *not* overwrite. LangGraph's `add_messages` is the canonical reference; a generic dict-merge channel is a few lines but needs a smoke test under the real `Send` path before step B's `p4_beat` PR lands.
3. **Migration of in-flight runs.** A run started under the old schema and resumed after a partial migration would see new state fields it does not know how to read. Mitigation: the `total=False` schema makes both old and new shapes valid; the dual-write window (Step B) means producers populate both old and new fields. Acceptable.
4. **Materializer cache hit on `index.html` body change but no scene body change.** If `p4_assemble_index` runs and produces a different `index_html` (e.g. tokens changed), the materializer's cache key (sha256 of all body fields) misses — correct. If only the materializer's *brief* / version changes, the cache misses — correct. Edge case: what if the operator manually edits a file under `<edit_dir>/` between Studio runs, expecting the materializer to detect and overwrite? Current design says: it won't, because the cache key fingerprints state, not disk. This is a deliberate trade — the materializer is "state to disk", not "state to disk with disk-as-secondary-truth". Documented in the materializer's docstring; if user demand surfaces, add a content-hash check at write time as a follow-up.
5. **Wave-acceptance recording cost.** ~$8–12 once at step F. Subsequent re-records (on brief / schema bumps that affect the canonical fixture) are scoped to the bumped node + downstream via `record-on-miss`, mirroring the current model.
6. **Breaking-change announcement.** The cutover (step D) `git rm`s committed fixture files. Any open feature branch that touched those files merges with conflicts. Plan: announce in the M-wave kickoff retro, freeze fixture-touching PRs for the cutover day, land step D first thing in the morning, unfreeze.

## 13. Acceptance criteria for the epic

- All six creative Phase 4 nodes return body strings in state. No production node calls the `Write` tool for canonical text artifacts.
- `p4_materialize_disk_node` is the only Phase 4 writer to disk for text artifacts. Its cache policy uses `make_key` keyed on body content hashes.
- `tests/fixtures/episodes/canonical-portrait-talking-head/` contains exactly four entries: `raw.mp4`, `intent.yaml`, `cache.db`, `recordings/`.
- Replay smoke `pytest tests/test_graph_replay.py` runs at $0 against the post-cutover cache.db; every Phase 4 node hits.
- HOM-216 Playwright snapshots green against materializer-regenerated tree.
- `compose.design_md_path` / `compose.expanded_prompt_path` / `compose.captions_block_path` removed from `state.py`. No Phase 4 cache key uses `file_fingerprint`.
- CLAUDE.md sections updated per Step G.
- One paid wave-acceptance run lands the new fixture; no follow-on re-records required for unrelated PRs.

## 14. References

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

## 15. CLAUDE.md sections to amend after this epic lands (informational; do not edit now)

- **§"Idempotency"** — clarify that Phase 4 cache keys fingerprint state-string bodies, not on-disk paths. The §"LLM cache keys include routing-config fingerprint" paragraph remains correct in mechanism but its example (`p3_strategy.timeout_s 120 → 300`) stays as-is; add a sibling paragraph noting that creative-node `extras=` now contains body sha256s.
- **§"Worktree data-dir resolution"** — narrow to "Phase 3 binary artifacts" scope. Phase 4 is no longer worktree-bound.
- **§"Studio replay (operator runbook)"** — drop the `--allow-blocking` requirement once step E lands (no synchronous file reads during graph draw for Phase 4 nodes). The `HOMESTUDIO_PROJECT_ROOT` requirement remains, since Phase 3 still uses it.
- **§"Definition of done for LLM-node tickets"** — item 5 (fingerprint invalidation) registry entries shift from "edit upstream artifact file" mutations to "mutate upstream state body string" mutations. Update the helper's signature to accept state-string mutations naturally.
- **§"Testing infra — fixture replay"** — update the reviewer-expectations bulleted list: the cache.db diff and JSON dump are still the review surfaces, but the fixture directory listing shrinks (no `hyperframes/`, no `edit/DESIGN.md`, no `edit/.hyperframes/`).
- **§"Exception — fixture-replay test inspection"** — the carve-out for `replay_dispatch.py` remains, but the "go through `compiled.invoke`" failure mode argument weakens once cache keys no longer fingerprint test-machine paths. Re-evaluate at step G whether the helper can be retired in favour of the runtime path.

End of spec.
