# Orchestrator tests

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

`cache.db` is **not** in the repo at this stage — it is populated by a
one-shot real-tier prewarm the user runs in a follow-up step after the
fixture scaffold lands. Until then, `replay`-mode tests against this
slug will (correctly) fail with `FileNotFoundError: replay mode
requires fixture cache.db at .../cache.db`.

## Spec / canon links

- Spec: `docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`
- Native primitive: `langgraph.cache.sqlite.SqliteCache`
- LLM-key fingerprinting: `make_llm_key` in
  `graph/src/edit_episode_graph/_caching.py` (HOM-157 — config tier
  goes into the cache key)
- CLAUDE.md §"LangGraph primitives — search docs first"
