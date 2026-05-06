"""HOM-132.4 smoke — deterministic heavy nodes cache-hit on warm re-run.

Verifies the seven nodes wired in this PR — `isolate_audio`,
`p3_inventory`, `p3_render_segments`, `glue_remap_transcript`,
`p4_scaffold`, `p4_catalog_scan`, `p4_assemble_index` — carry a working
`cache_policy=` and that warm re-runs short-circuit before the heavy
subprocess they normally spawn (ffmpeg, ElevenLabs Scribe, npx hyperframes,
transcribe_batch, pack_transcripts).

Three layers of assertion (in this order):

1. **Per-node `key_func` stability.** Each node's `_cache_key` is callable
   with a minimal dict-state and returns the same string twice — a quick
   sanity check that key_funcs don't accidentally embed transient values
   (timestamps, counters, mutable dict iteration order).

2. **Chain cache-hit smoke (`isolate_audio` + naturally-skipping nodes).**
   Builds a 3-node chain — `isolate_audio` (subprocess mocked),
   `p3_render_segments` (state-driven skip via `edl.skipped=True`),
   `p4_assemble_index` (state-driven skip via empty `compose.plan.beats`).
   Run 1 (cold): `subprocess.run` is called for `isolate_audio` (the
   ElevenLabs-credit-spending invocation we want to cache). Run 2 (warm):
   `__metadata__.cached==True` for all three nodes; **`subprocess.run`
   is NOT called at all** — the primary cost-saving claim of HOM-132.

3. **Cache invalidation on input change.** Editing `pickup.raw_path`
   content between runs forces `isolate_audio` to cache-miss again
   (proves the key actually fingerprints the file rather than just
   the path string).

Cost: $0 — all subprocess calls are mocked.

Run from the worktree:

    .venv/Scripts/python graph/smoke_hom132_4_deterministic.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure `edit_episode_graph` is importable when run as a script.
_GRAPH_SRC = Path(__file__).resolve().parent / "src"
if str(_GRAPH_SRC) not in sys.path:
    sys.path.insert(0, str(_GRAPH_SRC))

from langgraph.cache.sqlite import SqliteCache  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402

from edit_episode_graph.nodes.glue_remap_transcript import (  # noqa: E402
    CACHE_POLICY as glue_remap_cache_policy,
    _cache_key as glue_remap_key,
)
from edit_episode_graph.nodes.isolate_audio import (  # noqa: E402
    CACHE_POLICY as isolate_audio_cache_policy,
    _cache_key as isolate_audio_key,
    isolate_audio_node,
)
from edit_episode_graph.nodes.p3_inventory import (  # noqa: E402
    CACHE_POLICY as p3_inventory_cache_policy,
    _cache_key as p3_inventory_key,
)
from edit_episode_graph.nodes.p3_render_segments import (  # noqa: E402
    CACHE_POLICY as p3_render_segments_cache_policy,
    _cache_key as p3_render_segments_key,
    p3_render_segments_node,
)
from edit_episode_graph.nodes.p4_assemble_index import (  # noqa: E402
    CACHE_POLICY as p4_assemble_index_cache_policy,
    _cache_key as p4_assemble_index_key,
    p4_assemble_index_node,
)
from edit_episode_graph.nodes.p4_catalog_scan import (  # noqa: E402
    CACHE_POLICY as p4_catalog_scan_cache_policy,
    _cache_key as p4_catalog_scan_key,
)
from edit_episode_graph.nodes.p4_scaffold import (  # noqa: E402
    CACHE_POLICY as p4_scaffold_cache_policy,
    _cache_key as p4_scaffold_key,
)
from edit_episode_graph.state import GraphState  # noqa: E402


def _check_key_func_stable() -> int:
    """Layer 1: every key_func must be deterministic for a given state."""
    print("--- Layer 1: per-node key_func stability ---")
    state: dict = {
        "slug": "hom132-4-smoke",
        "episode_dir": "/tmp/episodes/hom132-4-smoke",
        "pickup": {"raw_path": "/tmp/inbox/foo.mp4"},
        "audio": {"wav_path": "/tmp/audio/foo.wav"},
        "transcripts": {
            "raw_json_path": "/tmp/transcripts/raw.json",
            "takes_packed_path": "/tmp/edit/takes_packed.md",
        },
        "edit": {"edl": {"edl_path": "/tmp/edit/edl.json"}},
        "compose": {
            "index_html_path": "/tmp/hf/index.html",
            "captions_block_path": "/tmp/hf/captions.html",
            "plan": {"beats": [{"beat": "hook", "duration_s": 1.0}]},
        },
    }
    pairs = [
        ("isolate_audio", isolate_audio_key),
        ("p3_inventory", p3_inventory_key),
        ("p3_render_segments", p3_render_segments_key),
        ("glue_remap_transcript", glue_remap_key),
        ("p4_scaffold", p4_scaffold_key),
        ("p4_catalog_scan", p4_catalog_scan_key),
        ("p4_assemble_index", p4_assemble_index_key),
    ]
    for name, fn in pairs:
        k1 = fn(state)
        k2 = fn(state)
        if k1 != k2:
            print(
                f"SMOKE FAIL: {name} key_func not stable: {k1!r} != {k2!r}",
                file=sys.stderr,
            )
            return 1
        if not isinstance(k1, str) or not k1:
            print(f"SMOKE FAIL: {name} key_func returned non-string {k1!r}", file=sys.stderr)
            return 1
        print(f"  {name}: stable -> {k1[:80]}...")

    # Empty/missing slug must not crash key_func (LangGraph introspects via
    # `compiled.get_graph()` with __unbound__ state).
    bare: dict = {"slug": "", "pickup": {}, "audio": {}, "transcripts": {}, "edit": {}, "compose": {}}
    for name, fn in pairs:
        try:
            fn(bare)
        except Exception as exc:
            print(
                f"SMOKE FAIL: {name} key_func raised on bare state: {exc!r}",
                file=sys.stderr,
            )
            return 1
    print("  all key_funcs accept bare/__unbound__ state without crashing")
    return 0


_ISOLATE_STDOUT = json.dumps(
    {"cached": True, "api_called": False, "wav_path": "/fake/clean.wav", "reason": None}
)


def _mock_subprocess_run(*args, **kwargs):
    """Mock that returns a canned isolate_audio stdout for all calls.

    We only spawn `isolate_audio`'s subprocess in this chain (the other
    two chain nodes skip without subprocessing), so a single canned
    response works.
    """
    rv = MagicMock()
    rv.returncode = 0
    rv.stdout = _ISOLATE_STDOUT
    rv.stderr = ""
    return rv


def _build_chain(cache_db: Path):
    g = StateGraph(GraphState)
    g.add_node(
        "isolate_audio", isolate_audio_node, cache_policy=isolate_audio_cache_policy
    )
    g.add_node(
        "p3_render_segments",
        p3_render_segments_node,
        cache_policy=p3_render_segments_cache_policy,
    )
    g.add_node(
        "p4_assemble_index",
        p4_assemble_index_node,
        cache_policy=p4_assemble_index_cache_policy,
    )
    g.add_edge(START, "isolate_audio")
    g.add_edge("isolate_audio", "p3_render_segments")
    g.add_edge("p3_render_segments", "p4_assemble_index")
    g.add_edge("p4_assemble_index", END)
    return g.compile(cache=SqliteCache(path=str(cache_db)))


_CHAIN_NODES = ("isolate_audio", "p3_render_segments", "p4_assemble_index")


def _state_for_chain(raw_path: str, episode_dir: str) -> dict:
    """State that drives `p3_render_segments` and `p4_assemble_index` to
    return their state-driven skip dicts (both write a `skipped=True`
    namespace, which IS cacheable). `isolate_audio` is the only node that
    actually reaches its (mocked) subprocess.
    """
    return {
        "slug": "hom132-4-smoke",
        "episode_dir": episode_dir,
        "pickup": {"raw_path": raw_path},
        # p3_render_segments: edl.skipped=True → returns skip dict immediately.
        "edit": {"edl": {"skipped": True, "skip_reason": "smoke"}},
        # p4_assemble_index: empty plan.beats → returns skip dict immediately.
        "compose": {"plan": {"beats": []}},
    }


def _run(graph, state: dict, label: str) -> tuple[dict[str, bool], list]:
    print(f"\n--- {label} ---")
    seen_cached: dict[str, bool] = {}
    events = []
    for event in graph.stream(state, stream_mode="updates"):
        events.append(event)
        meta = event.get("__metadata__") or {}
        cached_flag = bool(meta.get("cached"))
        for n in event.keys():
            if n == "__metadata__":
                continue
            if n in _CHAIN_NODES:
                seen_cached[n] = seen_cached.get(n, False) or cached_flag
        node_keys = [k for k in event.keys() if k != "__metadata__"]
        print(f"  event: nodes={node_keys} cached={cached_flag}")
    return seen_cached, events


def _check_chain_cache_hit() -> int:
    """Layer 2 + 3: chain cache-hit + invalidation on input change."""
    print("\n--- Layer 2: chain cache-hit on warm re-run ---")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        td_p = Path(td)
        cache_db = td_p / "smoke_cache.db"
        episode_dir = td_p / "episode"
        episode_dir.mkdir()
        raw = td_p / "inbox" / "foo.mp4"
        raw.parent.mkdir()
        raw.write_bytes(b"raw video v1")

        graph = _build_chain(cache_db)
        state = _state_for_chain(str(raw), str(episode_dir))

        # Run 1 (cold): mock subprocess.run; isolate_audio's subprocess
        # MUST be called.
        with patch(
            "edit_episode_graph.nodes._deterministic.subprocess.run",
            side_effect=_mock_subprocess_run,
        ) as run_cold:
            cold, _ = _run(graph, state, "Run 1 (cold) — isolate_audio subprocess fires")
        cold_calls = run_cold.call_count
        print(f"  cold subprocess.run calls: {cold_calls}")
        if cold_calls < 1:
            print(
                "SMOKE FAIL: cold run did not invoke isolate_audio's subprocess "
                "(mock unhooked or chain wiring broken)",
                file=sys.stderr,
            )
            return 1
        for n in _CHAIN_NODES:
            if cold.get(n):
                print(
                    f"SMOKE FAIL: Run 1 reported cached=True for {n} (cache should be empty)",
                    file=sys.stderr,
                )
                return 1

        # Run 2 (warm): identical state. subprocess.run MUST NOT be called
        # at all — every node cache-hits before its body.
        with patch(
            "edit_episode_graph.nodes._deterministic.subprocess.run",
            side_effect=_mock_subprocess_run,
        ) as run_warm:
            warm, _ = _run(graph, state, "Run 2 (warm) — zero subprocess calls expected")
        warm_calls = run_warm.call_count
        print(f"  warm subprocess.run calls: {warm_calls}")
        if warm_calls != 0:
            print(
                f"SMOKE FAIL: Run 2 invoked subprocess.run {warm_calls}× — "
                "isolate_audio cache did not short-circuit; ElevenLabs credits "
                "would be re-spent on real run",
                file=sys.stderr,
            )
            return 1
        for n in _CHAIN_NODES:
            if not warm.get(n):
                print(
                    f"SMOKE FAIL: Run 2 did NOT cache-hit for {n}",
                    file=sys.stderr,
                )
                return 1

        # Run 3: edit raw.mp4 content → isolate_audio key changes → cache miss.
        print("\n--- Layer 3: invalidation on raw video edit ---")
        raw.write_bytes(b"raw video v2 (edited)")
        with patch(
            "edit_episode_graph.nodes._deterministic.subprocess.run",
            side_effect=_mock_subprocess_run,
        ) as run_edit:
            edit_seen, _ = _run(graph, state, "Run 3 (after raw edit) — isolate_audio re-runs")
        if edit_seen.get("isolate_audio"):
            print(
                "SMOKE FAIL: Run 3 cache-hit isolate_audio after raw video edit — "
                "content fingerprint not honoured",
                file=sys.stderr,
            )
            return 1
        if run_edit.call_count < 1:
            print(
                "SMOKE FAIL: Run 3 did not re-spawn isolate_audio subprocess after raw edit",
                file=sys.stderr,
            )
            return 1
        # Downstream skipping nodes don't depend on raw_path, so they
        # should still cache-hit.
        for n in ("p3_render_segments", "p4_assemble_index"):
            if not edit_seen.get(n):
                print(
                    f"SMOKE FAIL: Run 3 cache-missed {n} — its key did not change "
                    "(only raw video did, which it does not depend on)",
                    file=sys.stderr,
                )
                return 1

    return 0


def main() -> int:
    if _check_key_func_stable() != 0:
        return 1
    if _check_chain_cache_hit() != 0:
        return 1
    print(
        "\n[OK] smoke_hom132_4_deterministic PASS — all 7 deterministic nodes "
        "expose stable cache keys; chain warm re-run fires ZERO subprocess "
        "calls (isolate_audio Scribe credits preserved); raw-video edit "
        "invalidates isolate_audio while leaving downstream cached."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
