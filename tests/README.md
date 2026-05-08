# Orchestrator tests

**See also:**
- Spec: [`docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`](../docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md) — three-layer pyramid (L0 / L1 / L2), recording mechanism, fixture choice.
- DoD: [`CLAUDE.md` §"Definition of done for LLM-node tickets"](../CLAUDE.md) and §"Testing infra — fixture replay" — the rules every LLM-node PR must satisfy + reviewer checklist.

Layout:

```
tests/
  _helpers/replay_harness.py   # HOM-180: fixture-replay cache harness
  conftest.py                  # exposes `replay_mode` pytest fixture
  fixtures/
    episodes/<slug>/cache.db   # prewarmed LangGraph SqliteCache, committed
    episodes/<slug>/recordings # human-readable JSON dump per node (later)
  test_replay_harness.py       # unit tests for the harness itself
  test_graph_replay.py         # graph-replay smoke (HOM-180 placeholder, fills in over M6)
  test_*.py                    # pre-existing pickup / scaffold / etc. tests
```

## Modes — `HOMESTUDIO_TEST_MODE`

The harness wraps native LangGraph `langgraph.cache.sqlite.SqliteCache`
(spec `docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md` §4).
One env var picks the behaviour:

| Mode             | Default? | Cache file opened                                   | LLM cost   |
| ---------------- | -------- | --------------------------------------------------- | ---------- |
| `replay`         | yes      | fixture cache.db, `sqlite3 mode=ro`                 | $0 (fails on miss) |
| `record-on-miss` | local dev | tmp working copy seeded from fixture; misses run real | pay-as-you-go |
| `record`         | wave acceptance | tmp working copy starts empty; full re-record     | full real run |

Cache misses in `replay` raise:

```
ReplayCacheMissError: no recording for node X with fingerprint Y;
re-record locally via HOMESTUDIO_TEST_MODE=record-on-miss
```

That message is the canonical operator hint — do not paraphrase it
elsewhere.

## Running

```powershell
# default replay (no env var, no API key needed):
python -m pytest tests/

# local dev: real LLM dispatch on cache miss, persists back to fixture cache.db
$env:HOMESTUDIO_TEST_MODE = "record-on-miss"
python -m pytest tests/test_graph_replay.py

# wave acceptance: full re-record from scratch (paid)
$env:HOMESTUDIO_TEST_MODE = "record"
python -m pytest tests/test_graph_replay.py
```

## Recording a fresh fixture

After M6 wave work or a node schema bump:

1. Set `HOMESTUDIO_TEST_MODE=record-on-miss` (or `record` for a clean wipe).
2. Run the relevant `pytest tests/test_graph_replay.py::test_<node>_smoke`.
3. The harness writes the working cache.db back to
   `tests/fixtures/episodes/<slug>/cache.db` via SQLite `VACUUM INTO` +
   atomic rename — deterministic raw form, no WAL artefacts, no journal
   leftover, no spurious diff.
4. `git diff tests/fixtures/episodes/<slug>/cache.db` will show the
   updated binary; commit it together with the brief / schema change
   in the same PR.
5. Reviewer agent inspects the diff plus (later) the human-readable
   `recordings/<node>.json` companion dump.

## How it plugs into the compiled graph

Production code lives in `graph/src/edit_episode_graph/graph.py::build_graph`,
which calls `compile(cache=SqliteCache(path=...))`. The harness yields a
`MountedFixture` whose `working_path` you can pass straight to that
constructor — no production-side change needed. See
`test_replay_harness_smoke` for a minimal example.

## Canonical fixture episode

`tests/fixtures/episodes/canonical-portrait-talking-head/` (HOM-181)
holds the single canonical portrait talking-head clip used by the
fixture-replay layer. See its
[README](fixtures/episodes/canonical-portrait-talking-head/README.md)
for the source segment, ffmpeg command, and the prewarm command.

`cache.db` **is committed** (PR #102, HOM-181 prewarm follow-up — 71
recorded entries across 17 nodes, ~156 KB). The fixture is the
deterministic, $0 surface every replay-mode test reads from. If you
need to refresh it after a brief / schema change, see
[Recording a fresh fixture](#recording-a-fresh-fixture) above and the
[Studio replay](#studio-replay-operator-runbook) runbook below.

## Studio replay (operator runbook)

To pick up the recorded fixture episode in `langgraph dev` Studio and
walk it through the full graph at $0 spend:

```powershell
copy tests\fixtures\episodes\canonical-portrait-talking-head\cache.db graph\.cache\langgraph.db
$env:HOMESTUDIO_PROJECT_ROOT = "$PWD\tests\fixtures"
cd graph
.venv\Scripts\langgraph.exe dev --allow-blocking --no-browser
# In the Studio UI: POST a run with slug = canonical-portrait-talking-head
# Resume both interrupts with payload {"resume":"approved"}
```

- **`--allow-blocking`** is required: `_caching.py::file_fingerprint`
  performs synchronous file I/O during graph draw (cache key
  resolution). Without the flag, `langgraph dev` aborts on the first
  sync read.
- **`HOMESTUDIO_PROJECT_ROOT`** is mandatory — points
  `_paths.project_root()` at `tests/fixtures` so the graph reads
  `episodes/<slug>/` from the committed fixture tree rather than the
  gitignored production `episodes/`. Without it, Studio sees an empty
  episode folder and the run halts on pickup.
- **Two HITL interrupts** fire on the recorded happy path:
  `strategy_confirmed_interrupt` (after `p3_strategy`) and
  `p3_review_interrupt` (after `p3_persist_session`). Resume each with
  `{"resume":"approved"}` to advance.
- **HF render is NOT in the graph** — HOM-78 (`p4_final_render`) is
  future work. After the graph terminates at `p4_assemble_index` → gate
  cluster → `p4_persist_session` → `studio_launch`, run
  `npx hyperframes render` manually inside
  `tests/fixtures/episodes/canonical-portrait-talking-head/hyperframes/`.
  Don't conflate "graph terminated" with "pipeline complete".

## Dumping recordings to JSON for review (HOM-182)

`cache.db` is the canonical fixture, but binary — PR diffs are
unreadable. The `tests/dump_recordings.py` CLI walks the SQLite rows
through the same serde the cache uses (`JsonPlusSerializer`), groups
by node, and writes one canonically-sorted JSON file per node into
`tests/fixtures/episodes/<slug>/recordings/`.

```powershell
# Dump explicitly:
python -m tests.dump_recordings <slug>

# Or via pytest (auto on session finish):
python -m pytest --dump-recordings=<slug>

# Auto-fires on a record-on-miss session if --dump-recordings is set:
$env:HOMESTUDIO_TEST_MODE = "record-on-miss"
python -m pytest tests/test_graph_replay.py --dump-recordings=<slug>
```

Per-node JSON shape:

```json
{
  "node": "p3_strategy",
  "namespace": "__pregel_ns_writes,edit_episode_graph.nodes.p3_strategy.p3_strategy_node,p3_strategy",
  "fingerprint": "p3_strategy|v3|<slug>|<file-hashes>|cfg:<sha>",
  "channel_writes": { ... decoded payload ... },
  "recorded_at": null,
  "recording_meta": {"encoding": "msgpack", "value_bytes": 1234}
}
```

Filenames are `<node_name>.json` per spec §4 — the canonical node name
extracted from the SQLite `ns` cell (last comma-segment of LangGraph's
pregel-namespaced cache key). The full `ns` lives inside each record
under `namespace` so pregel-write provenance is preserved without
overrunning Windows MAX_PATH (260) under nested worktree paths.

If a node has multiple recordings (different fingerprints, e.g.
`p4_beat` fan-out shards) they appear as a sorted list; otherwise the
file holds the bare object.

**Field provenance** (full notes in `tests/dump_recordings.py`
docstring):

- `node`: canonical node name — last comma-segment of the SQLite `ns`
  cell. For LLM nodes `ns` is
  `__pregel_ns_writes,<full_module_path>.<wrapper>,<node_name>`.
- `namespace`: raw `ns` cell verbatim, retained in-record so reviewers
  don't lose pregel-write context when the filename is shortened.
- `fingerprint`: live SQLite `key` column; what `make_llm_key` produces
  (a stable identifier; brief / schema / tier bumps flip it).
- `channel_writes`: `serde.loads_typed` of the stored blob; non-JSON
  natives (datetimes, bytes, Pydantic models) are coerced to readable
  strings — for genuinely opaque values you get
  `"<binary blob N bytes>"` so the diff still surfaces a delta.
- `recorded_at`: `null` for the common no-TTL case (LangGraph's
  `SqliteCache` doesn't store absolute set-time; only TTL expiry); use
  the JSON file mtime as the fallback for review.
- `recording_meta.model` / `tier` from the spec are **not** in the
  output — that info is part of the cache *key* (one-way `cfg:<sha>`),
  not the cached value. Reviewers spot model / tier shifts via a
  fingerprint diff.

The dump opens `cache.db` read-only (URI `mode=ro`) so a dump cannot
mutate the canonical fixture. Round-trip-stable: re-running the dump
on the same content produces byte-for-byte identical JSON
(`test_round_trip_identical_bytes`).

## Brief snapshot tests (HOM-183)

L0 layer of the testing pyramid (spec §3): every creative LLM brief
under `graph/src/edit_episode_graph/briefs/` is rendered through the
production Jinja env (`edit_episode_graph.nodes._llm._BRIEF_ENV`) with
a stable fixture context, and the output is pinned to
`tests/snapshots/briefs/<node>.txt`.

Coverage at the time of HOM-183:

- `p3_strategy`, `p3_edl_select`
- `p4_design_system`, `p4_prompt_expansion`, `p4_plan`, `p4_beat`,
  `p4_captions_layer`

```powershell
# Default — assert every brief matches its snapshot
python -m pytest tests/test_brief_snapshots.py

# Intentional brief change — overwrite the snapshot, then commit
python -m pytest tests/test_brief_snapshots.py --update-snapshots
```

The fixture render contexts live in
`tests/_helpers/brief_render_contexts.py`. They use deterministic
placeholder values (`slug = "snapshot-fixture"`,
`episode_dir = "/tmp/snapshot-fixture/episode"`, etc.) so the
snapshots are stable across operators and platforms.

**Reviewer rule:** a snapshot diff in a PR is a flag to verify the
canon-references-not-embeds rule (CLAUDE.md §"Decomposition via
brief-references-canon" item 1). Briefs cite SKILL.md by path; they
do NOT pre-paraphrase canon. If a diff shows the brief growing new
prose that looks like it came out of a SKILL.md section, push back.

When canonical paths or section names move upstream, the snapshot diff
shows up first — that's by design. Update the brief, re-run with
`--update-snapshots`, and commit both files together so the diff is
self-evident.

## Fingerprint invalidation tests (HOM-184)

L0 layer (spec §3 «Fingerprint invalidation assertion»). Asserts the
three creative-node cache-key invariants without spending a cent:

1. **Brief / schema bump** — `_CACHE_VERSION` increment flips the key.
2. **Routing-config bump** — `make_llm_key`'s HOM-157 `cfg:<sha>` extra
   reflects `graph/config.yaml` changes (tier / model / timeout /
   backend_preference).
3. **Upstream artifact edit** — content-hash of every `files=` entry
   actually feeds the key (`file_fingerprint` content-hashes, not
   mtime-cheats).

```powershell
python -m pytest tests/test_fingerprint_invalidation.py
```

The helper lives in `tests/_helpers/fingerprint_assertions.py`. Adding
a new creative node? Register it in `_NODE_REGISTRY` with a
``base_state`` factory and a ``primary_artifact_pointer`` and the three
parametrised tests automatically cover it.

For one-off custom mutations, call `assert_fingerprint_changes_when`
directly with your own `mutation_fn(state)`. Coverage at the time of
HOM-184: `p3_strategy`, `p4_design_system`, `p4_beat` — extend as new
creative nodes land.

## Migrated `smoke_hom*.py` (HOM-184)

The legacy `graph/smoke_hom*.py` scripts were per-ticket Haiku-tier
real-CLI smokes. Under the new fixture-replay model (spec §6 DoD
migration) they live in `tests/test_graph_replay.py` and run at $0
against the recorded fixture cache:

| Old smoke | Migrated to | Status |
| --- | --- | --- |
| `smoke_hom107.py` Case 1 (topology) | `test_phase3_topology` | green |
| `smoke_hom107.py` Case 2 (Haiku p3_edl_select) | `test_p3_edl_select_smoke` | green (HOM-186) |
| `smoke_hom107.py` Case 3 (gate eval) | covered by `graph/tests/test_edl_ok_gate.py` | n/a |
| `smoke_hom118.py` (Opus p4_design_system) | `test_p4_design_system_smoke` | green (HOM-186) |
| `smoke_hom119.py` (Haiku p4_prompt_expansion) | `test_p4_prompt_expansion_smoke` | green (HOM-186) |
| `smoke_hom127.py` Case 1 (gate-cluster topology) | `test_post_assemble_gate_cluster_topology` | green |
| `smoke_hom127.py` Case 2 (gate invocations against fixture) | covered by `graph/tests/test_*_gate.py` | n/a |
| `smoke_hom127.py` Case 3 (halt notice) | `test_halt_notice_surfaces_gate_cluster_failure` | green |
| `smoke_hom163.py` (gate_results_reducer) | `test_gate_results_reducer_through_runtime` | green |
| `smoke_hom165.py` (Haiku p4_beat anti-patterns) | `test_p4_beat_smoke` | green (HOM-186) |
| other `smoke_hom*.py` | superseded by L0 + L1 layers | deleted |

The replay-mode smokes carry a `requires_fixture_cache` `skipif` mark
that fires when `tests/fixtures/episodes/canonical-portrait-talking-head/cache.db`
is missing. With cache.db committed (PR #102), the smokes run by
default — every replay served at $0 via
`tests._helpers.replay_dispatch.dispatch_node` (HOM-186). No `pytest`
flag is needed.

## Spec / canon links

- Spec: `docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`
- Native primitive: `langgraph.cache.sqlite.SqliteCache`
- LLM-key fingerprinting: `make_llm_key` in
  `graph/src/edit_episode_graph/_caching.py` (HOM-157 — config tier
  goes into the cache key)
- CLAUDE.md §"LangGraph primitives — search docs first"
