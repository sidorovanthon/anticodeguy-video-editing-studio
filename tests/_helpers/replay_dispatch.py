"""Per-node dispatch helper for fixture-replay smokes (HOM-186 Part B).

Provides :func:`dispatch_node`, which dispatches a single LLM-node-under-test
against the committed fixture ``cache.db`` and returns the recorded channel
writes — guaranteed $0 spend, no LLM API calls.

Native primitive contract
-------------------------

CLAUDE.md §"LangGraph primitives — search docs first" calls out
``client.threads.update_state(thread_id, values=…, as_node="<previous_node>")``
+ ``client.runs.create(thread_id, assistant_id, input=None)`` as the
canonical *production* mid-graph dispatch primitive — used to skip
already-completed phases in a real run on a paid tier. The in-process
equivalents are ``compiled.update_state(...)`` + ``compiled.invoke(None, cfg)``.

For *fixture-replay tests* the relevant native primitive is the one we
already wrap: ``langgraph.cache.sqlite.SqliteCache`` paired with each
node's ``CachePolicy(key_func=…)`` (HOM-132 / spec
``2026-05-06-langgraph-node-caching-design.md`` §6). The cache layer is
the deterministic, $0 surface; ``update_state`` is irrelevant when the
goal is "replay one recorded node and prove no LLM dispatch occurred".
Going through ``compiled.invoke`` would route through the full graph
runtime, recompute every cache key against current in-memory + on-disk
state, and on the slightest fingerprint drift (recording-time strategy
file vs current strategy file content) issue a real LLM call before
``cache.set`` ever raises — defeating the $0 guarantee.

This helper therefore queries the cache directly through ``SqliteCache``'s
own serde (``JsonPlusSerializer``) — the same path Pregel uses for hits.
It does NOT import ``_build_node`` and call it (which would also bypass
the cache); it does NOT run the production graph (which on fingerprint
drift will call the LLM before the cache layer can intervene). The
mounted fixture cache is opened read-only, queried for any recording
under the node's pregel namespace, and the recorded ``channel_writes``
deque is decoded and returned. Cache-hit telemetry is accumulated so
smokes can assert ``hits >= 1`` — i.e. the recording was found and
served without spending a cent.

Refs:
  - https://langchain-ai.github.io/langgraph/concepts/persistence/#caching
  - https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.CachePolicy
  - Spec ``docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`` §3 L1
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from tests._helpers.replay_harness import (
    Mode,
    ReplayCacheMissError,
    mount_fixture_cache,
)


# ---------------------------------------------------------------------------
# Predecessor map. Documents the *production* graph topology for each
# replayable node — what node would precede it on the happy path. Tests can
# read this to assert the helper's wiring stays in lockstep with
# ``edit_episode_graph.graph.build_graph_uncompiled``. The map is also the
# canonical place to extend coverage when new creative nodes land.
# ---------------------------------------------------------------------------

_PREDECESSORS: dict[str, str] = {
    "p3_edl_select": "strategy_confirmed_interrupt",
    "p4_design_system": "p4_scaffold",
    "p4_prompt_expansion": "gate_design_ok",
    # HOM-235: captions layer sits between `p4_catalog_scan` and
    # `p4_dispatch_beats` on the happy path.
    "p4_captions_layer": "p4_catalog_scan",
    # `p4_beat` is fan-out via Send from `p4_dispatch_beats`; the closest
    # deterministic predecessor on the happy path is `p4_captions_layer`.
    "p4_beat": "p4_captions_layer",
    # HOM-156 (review S1): cheap-tier classifier in the post-assemble cluster.
    # Predecessor is the deterministic `gate_animation_map` whose record
    # carries `advisory_findings.pending_classify` (HOM-204 shape) — the
    # list the classifier annotates with per-flag decisions.
    "gate_animation_map_classify": "gate_animation_map",
}


# ---------------------------------------------------------------------------
# Dispatch result.
# ---------------------------------------------------------------------------


@dataclass
class DispatchResult:
    """Outcome of a :func:`dispatch_node` call.

    ``cache_hits`` is the number of recorded entries served for the target
    node's pregel namespace. ``llm_dispatches`` is always 0 — by design
    this helper never calls an LLM. ``final_state`` carries the decoded
    ``channel_writes`` deque from the served recording (a list of
    ``[channel_name, value]`` pairs, matching the cache wire format).
    """

    node: str
    predecessor: str
    cache_hits: int
    llm_dispatches: int = 0
    fingerprints: list[str] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)

    @property
    def all_hits(self) -> bool:
        return self.cache_hits >= 1 and self.llm_dispatches == 0


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------


def _decode_channel_writes(encoding: str, raw: bytes) -> Any:
    """Decode a stored ``channel_writes`` blob via the cache's own serde.

    LangGraph's ``SqliteCache`` stores values via
    ``langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer.dumps_typed``
    and reads them back via ``loads_typed``. Importing the serde directly
    keeps decoding aligned with whatever upstream changes — no manual
    msgpack handling.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    return serde.loads_typed((encoding, raw))


def _flatten_channel_writes(decoded: Any) -> dict[str, Any]:
    """Project a ``channel_writes`` deque into a state-shaped dict.

    The cached blob shape is ``deque([[channel_name, value], ...])`` —
    the same wire format Pregel emits when a node returns a state delta.
    For diagnostic / state-shape inspection in tests we collapse it into
    ``{channel: value}``; collisions (a node writing the same channel
    twice) keep the last value, matching Pregel's reducer semantics for
    last-write-wins channels.
    """
    out: dict[str, Any] = {}
    try:
        for entry in decoded:
            # entries are [channel_name, value]; tolerate tuples too.
            if not entry or len(entry) < 2:
                continue
            ch, val = entry[0], entry[1]
            out[str(ch)] = val
    except TypeError:
        # Decoded value isn't iterable (defensive — should never happen
        # for valid cache rows). Surface the raw value under a sentinel
        # key so the caller still sees something useful.
        out["__raw__"] = decoded
    return out


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def dispatch_node(
    node_name: str,
    slug: str,
    *,
    state_overrides: dict | None = None,
    mode: Mode = "replay",
) -> DispatchResult:
    """Replay a recorded node from the committed fixture cache.

    Runs entirely against the SQLite-backed fixture cache — no production
    graph runtime invocation, no LLM dispatch under any circumstances.
    Asserts at least one recorded entry exists for ``node_name`` under
    the canonical pregel namespace pattern; returns the decoded
    ``channel_writes`` for the first recording.

    Args:
        node_name: Cache-policy'd node to replay (must appear in
            :data:`_PREDECESSORS`). The predecessor mapping is verified
            for documentation parity with the production graph topology.
        slug: Fixture episode slug — used to locate the committed
            ``tests/fixtures/episodes/<slug>/cache.db``.
        state_overrides: Reserved for future symmetry with full graph
            dispatch; currently unused (no state seeding occurs because
            no graph is run). Pass-through preserves the signature shape
            documented in HOM-186.
        mode: HOMESTUDIO_TEST_MODE override; defaults to ``replay``. Any
            of the supported modes works since the helper only reads the
            cache.

    Returns:
        :class:`DispatchResult` with telemetry. ``llm_dispatches`` is
        always 0 — the dispatch never reaches a node body. Tests assert
        ``result.all_hits`` to verify $0 spend.

    Raises:
        KeyError: ``node_name`` missing from :data:`_PREDECESSORS`.
        ReplayCacheMissError: no recording found for the node in the
            fixture cache (replay mode contract: surface miss as the
            canonical error type so test diagnostics stay consistent).
    """
    if node_name not in _PREDECESSORS:
        raise KeyError(
            f"dispatch_node: no predecessor mapping for {node_name!r}; "
            f"add an entry to tests/_helpers/replay_dispatch._PREDECESSORS"
        )
    predecessor = _PREDECESSORS[node_name]

    # state_overrides is reserved (see docstring); silence linters without
    # constraining the signature.
    _ = state_overrides

    mounted = mount_fixture_cache(slug, mode=mode)
    try:
        # Open RO ourselves — `open_cache` would return the read-only
        # SqliteCache subclass which doesn't expose direct row access. A
        # raw `mode=ro` connection is the clean path; matches harness's
        # spec §4 stability option (1).
        from pathlib import Path

        uri = Path(mounted.working_path).as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        try:
            ns_pattern = f"%,{node_name}"
            rows = conn.execute(
                "SELECT ns, key, encoding, val FROM cache "
                "WHERE ns LIKE ? ORDER BY key",
                (ns_pattern,),
            ).fetchall()
        finally:
            conn.close()
    finally:
        mounted.cleanup()

    if not rows:
        raise ReplayCacheMissError(
            f"no recording for node {node_name!r} in fixture cache.db; "
            f"re-record locally via HOMESTUDIO_TEST_MODE=record-on-miss "
            f"or HOMESTUDIO_TEST_MODE=record"
        )

    fingerprints = [key for _ns, key, _enc, _val in rows]
    # First recording wins for the returned `final_state` — additional
    # entries (gate-retry redispatches etc.) are surfaced via
    # `fingerprints` so callers can inspect the full set if needed.
    _ns, _key, encoding, raw = rows[0]
    decoded = _decode_channel_writes(encoding, raw)
    final_state = _flatten_channel_writes(decoded)

    return DispatchResult(
        node=node_name,
        predecessor=predecessor,
        cache_hits=len(rows),
        llm_dispatches=0,
        fingerprints=fingerprints,
        final_state=final_state,
    )
