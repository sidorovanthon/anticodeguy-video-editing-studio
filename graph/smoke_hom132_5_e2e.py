"""HOM-132.5 smoke — full-chain E2E cache validation on a real fixture.

Stitches all 18 cached nodes (P3 LLM, P3 deterministic, P4 LLM, P4
deterministic) into a single compiled graph wired to a single SqliteCache,
points the state at a real fixture episode's on-disk artifacts so cache
keys fingerprint real files, and validates the three resume scenarios from
spec §2:

  1. **Forward continuation (cold → warm).** Run 1 cold → all 18 nodes
     execute, none cached. Run 2 identical → all 18 cache-hit, zero LLM /
     subprocess invocation.
  2. **Targeted re-do.** Edit ``DESIGN.md`` content between Run 2 and
     Run 3 → only nodes that fingerprint design_md (`p4_prompt_expansion`,
     `p4_plan`, `p4_beat`, `p4_captions_layer`) invalidate; upstream P3 +
     `p4_design_system` stay cached (they don't list design_md in
     ``files=``); downstream `p4_persist_session` stays cached (keys on
     index_html_path).
  3. **Crash recovery.** Identical to Run 2 — once everything is cached,
     re-submitting from any starting point cache-hits the whole chain
     (this is what "resume from failing node, no upstream re-execution"
     reduces to once `p3_self_eval` etc. are mid-chain cache hits).

Cost: $0. Every node body short-circuits via its own skipped-state
early-return (no `episode_dir`, `edit.edl.skipped=True`,
`compose.plan.beats=[]`); the cache wrapper still applies — that's the
whole point. Real fixture paths are referenced for content-fingerprinting
only, not opened by node bodies.

Wall-time output is the deliverable for the HOM-132.5 PR Test plan
(spec §9 row HOM-132.5: "manual; cold-vs-warm timing in PR body").

Run from worktree's `graph/` dir:

    .venv/Scripts/python smoke_hom132_5_e2e.py [<fixture-slug>]

Default fixture: ``2026-05-05-desktop-software-licensing-it-turns-out-is``
— the most-complete episode in `episodes/` (Phase 3 + Phase 4 artifacts
present). Override via positional CLI arg if you check in another fixture.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure `edit_episode_graph` is importable when run as a script.
_GRAPH_SRC = Path(__file__).resolve().parent / "src"
if str(_GRAPH_SRC) not in sys.path:
    sys.path.insert(0, str(_GRAPH_SRC))

from langgraph.cache.sqlite import SqliteCache  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402

# All 18 cached nodes — 5 P3 LLM + 5 P4 LLM + 8 deterministic (one of which,
# p4_design_system, was the HOM-132.1 pilot and wasn't in the §6 deterministic
# row but IS cached). Imported with their CACHE_POLICY values.
from edit_episode_graph.nodes.glue_remap_transcript import (  # noqa: E402
    CACHE_POLICY as glue_remap_cache_policy,
    glue_remap_transcript_node,
)
from edit_episode_graph.nodes.isolate_audio import (  # noqa: E402
    CACHE_POLICY as isolate_audio_cache_policy,
    isolate_audio_node,
)
from edit_episode_graph.nodes.p3_edl_select import (  # noqa: E402
    CACHE_POLICY as p3_edl_select_cache_policy,
    p3_edl_select_node,
)
from edit_episode_graph.nodes.p3_inventory import (  # noqa: E402
    CACHE_POLICY as p3_inventory_cache_policy,
    p3_inventory_node,
)
from edit_episode_graph.nodes.p3_persist_session import (  # noqa: E402
    CACHE_POLICY as p3_persist_session_cache_policy,
    p3_persist_session_node,
)
from edit_episode_graph.nodes.p3_pre_scan import (  # noqa: E402
    CACHE_POLICY as p3_pre_scan_cache_policy,
    p3_pre_scan_node,
)
from edit_episode_graph.nodes.p3_render_segments import (  # noqa: E402
    CACHE_POLICY as p3_render_segments_cache_policy,
    p3_render_segments_node,
)
from edit_episode_graph.nodes.p3_self_eval import (  # noqa: E402
    CACHE_POLICY as p3_self_eval_cache_policy,
    p3_self_eval_node,
)
from edit_episode_graph.nodes.p3_strategy import (  # noqa: E402
    CACHE_POLICY as p3_strategy_cache_policy,
    p3_strategy_node,
)
from edit_episode_graph.nodes.p4_assemble_index import (  # noqa: E402
    CACHE_POLICY as p4_assemble_index_cache_policy,
    p4_assemble_index_node,
)
from edit_episode_graph.nodes.p4_beat import (  # noqa: E402
    CACHE_POLICY as p4_beat_cache_policy,
    p4_beat_node,
)
from edit_episode_graph.nodes.p4_captions_layer import (  # noqa: E402
    CACHE_POLICY as p4_captions_layer_cache_policy,
    p4_captions_layer_node,
)
from edit_episode_graph.nodes.p4_catalog_scan import (  # noqa: E402
    CACHE_POLICY as p4_catalog_scan_cache_policy,
    p4_catalog_scan_node,
)
from edit_episode_graph.nodes.p4_design_system import (  # noqa: E402
    CACHE_POLICY as p4_design_system_cache_policy,
    p4_design_system_node,
)
from edit_episode_graph.nodes.p4_persist_session import (  # noqa: E402
    CACHE_POLICY as p4_persist_session_cache_policy,
    p4_persist_session_node,
)
from edit_episode_graph.nodes.p4_plan import (  # noqa: E402
    CACHE_POLICY as p4_plan_cache_policy,
    p4_plan_node,
)
from edit_episode_graph.nodes.p4_prompt_expansion import (  # noqa: E402
    CACHE_POLICY as p4_prompt_expansion_cache_policy,
    p4_prompt_expansion_node,
)
from edit_episode_graph.nodes.p4_scaffold import (  # noqa: E402
    CACHE_POLICY as p4_scaffold_cache_policy,
    p4_scaffold_node,
)
from edit_episode_graph.state import GraphState  # noqa: E402


# Topology order — matches graph.py production wiring (entry-to-exit linear
# projection of the v1 topology). Pretty-printing only; the chain is built
# below in this exact sequence.
_CHAIN: list[tuple[str, object, object]] = [
    ("isolate_audio", isolate_audio_node, isolate_audio_cache_policy),
    ("p3_inventory", p3_inventory_node, p3_inventory_cache_policy),
    ("p3_pre_scan", p3_pre_scan_node, p3_pre_scan_cache_policy),
    ("p3_strategy", p3_strategy_node, p3_strategy_cache_policy),
    ("p3_edl_select", p3_edl_select_node, p3_edl_select_cache_policy),
    ("p3_render_segments", p3_render_segments_node, p3_render_segments_cache_policy),
    ("p3_self_eval", p3_self_eval_node, p3_self_eval_cache_policy),
    ("p3_persist_session", p3_persist_session_node, p3_persist_session_cache_policy),
    ("glue_remap_transcript", glue_remap_transcript_node, glue_remap_cache_policy),
    ("p4_scaffold", p4_scaffold_node, p4_scaffold_cache_policy),
    ("p4_design_system", p4_design_system_node, p4_design_system_cache_policy),
    ("p4_prompt_expansion", p4_prompt_expansion_node, p4_prompt_expansion_cache_policy),
    ("p4_plan", p4_plan_node, p4_plan_cache_policy),
    ("p4_catalog_scan", p4_catalog_scan_node, p4_catalog_scan_cache_policy),
    ("p4_captions_layer", p4_captions_layer_node, p4_captions_layer_cache_policy),
    ("p4_beat", p4_beat_node, p4_beat_cache_policy),
    ("p4_assemble_index", p4_assemble_index_node, p4_assemble_index_cache_policy),
    ("p4_persist_session", p4_persist_session_node, p4_persist_session_cache_policy),
]


def _build_chain(cache_db: Path):
    g = StateGraph(GraphState)
    for name, fn, policy in _CHAIN:
        g.add_node(name, fn, cache_policy=policy)
    g.add_edge(START, _CHAIN[0][0])
    for (a, _, _), (b, _, _) in zip(_CHAIN, _CHAIN[1:]):
        g.add_edge(a, b)
    g.add_edge(_CHAIN[-1][0], END)
    return g.compile(cache=SqliteCache(path=str(cache_db)))


def _state(*, slug: str, episode_dir: Path, design_md: Path, raw_mp4: Path) -> dict:
    """Skip-state across all 18 nodes, with real on-disk paths for fingerprinting.

    `episode_dir` IS set (non-empty) so `isolate_audio`'s `_cmd` factory
    can build a command — it's invoked before body skip checks. The
    mocked subprocess returns a canned cached=True payload, so no
    ElevenLabs call fires. Every other node short-circuits via
    "<episode_dir>/edit/takes_packed.md missing" or analogous path-not-found
    checks; the cache wrapper still computes the key from this state,
    including content-fingerprints of `raw_mp4` and `design_md`.
    """
    return {
        "slug": slug,
        "episode_dir": str(episode_dir),
        "pickup": {
            "raw_path": str(raw_mp4),
            "script_path": str(episode_dir / "script.txt"),
        },
        "audio": {"wav_path": str(episode_dir / "audio" / "raw.cleaned.wav")},
        "transcripts": {
            "raw_json_path": str(episode_dir / "edit" / "transcripts" / "raw.json"),
            "takes_packed_path": str(episode_dir / "edit" / "takes_packed.md"),
            "final_json_path": str(episode_dir / "edit" / "transcripts" / "final.json"),
        },
        "edit": {
            "pre_scan": {"slips": []},
            "strategy": {},
            "edl": {
                "skipped": True,
                "ranges": [],
                "edl_path": str(episode_dir / "edit" / "edl.json"),
            },
            "render": {"skipped": True},
            "eval": {},
            "final_mp4_path": str(episode_dir / "edit" / "final.mp4"),
        },
        "compose": {
            "hyperframes_dir": "",  # p4_scaffold / p4_prompt_expansion early-return
            "design_md_path": str(design_md),
            "expanded_prompt_path": "",
            "captions_block_path": "",
            "style_request": "",
            "plan": {"beats": []},  # p4_dispatch_beats / p4_assemble_index skip
            "design": {},
            "assemble": {},
        },
        "_beat_dispatch": {"scene_id": "hook", "plan_beat": {}},
        "gate_results": [],
        "strategy_revisions": [],
        "phase_feedback": {},
        "errors": [],
        "notices": [],
    }


_CHAIN_NAMES = tuple(name for name, _, _ in _CHAIN)


_ISOLATE_STDOUT = (
    '{"cached": true, "api_called": false, '
    '"wav_path": "/fake/clean.wav", "reason": "smoke"}'
)


def _mock_subprocess_run(*args, **kwargs):
    """Mock for `_deterministic.subprocess.run` (covers `isolate_audio` etc.)."""
    rv = MagicMock()
    rv.returncode = 0
    rv.stdout = _ISOLATE_STDOUT
    rv.stderr = ""
    return rv


def _run(graph, state: dict, label: str) -> tuple[dict[str, bool], float]:
    print(f"\n--- {label} ---")
    seen: dict[str, bool] = {}
    t0 = time.perf_counter()
    with patch(
        "edit_episode_graph.nodes._deterministic.subprocess.run",
        side_effect=_mock_subprocess_run,
    ):
        for event in graph.stream(state, stream_mode="updates"):
            meta = event.get("__metadata__") or {}
            cached_flag = bool(meta.get("cached"))
            for n in event.keys():
                if n == "__metadata__":
                    continue
                if n in _CHAIN_NAMES:
                    seen[n] = seen.get(n, False) or cached_flag
            node_keys = [k for k in event.keys() if k != "__metadata__"]
            print(f"  {' / '.join(node_keys):<40s} cached={cached_flag}")
    elapsed = time.perf_counter() - t0
    print(f"  → wall: {elapsed*1000:.1f} ms")
    return seen, elapsed


def _resolve_fixture(slug: str) -> Path:
    """Find ``episodes/<slug>``. Walks up from CWD and from the script
    directory so the smoke runs equally well from a worktree (where
    `episodes/` is gitignored and lives only in the main repo) or from
    the main repo. Override via positional CLI arg.
    """
    candidates = []
    seen: set[Path] = set()
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for p in [start, *start.parents]:
            if p in seen:
                continue
            seen.add(p)
            cand = p / "episodes" / slug
            if cand.is_dir():
                return cand
            candidates.append(str(cand))
    print(
        f"SMOKE FAIL: fixture episode '{slug}' not found. Tried:\n  "
        + "\n  ".join(candidates[:6])
        + "\nPass a valid slug as argv[1] or check episodes/.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "2026-05-05-desktop-software-licensing-it-turns-out-is"
    fixture = _resolve_fixture(slug)
    print(f"Fixture: {fixture}")

    raw_mp4 = fixture / "raw.mp4"
    fixture_design_md = fixture / "hyperframes" / "DESIGN.md"
    if not fixture_design_md.is_file() or not raw_mp4.is_file():
        print(
            f"SMOKE FAIL: fixture missing required artifacts "
            f"(raw.mp4 / hyperframes/DESIGN.md). Pick a more complete episode.",
            file=sys.stderr,
        )
        return 2

    # Work in a tempdir so the smoke is hermetic — copy the few files whose
    # content the cache keys fingerprint, mutate copies for the invalidation
    # run. Keeps the real fixture untouched.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        td_p = Path(td)
        cache_db = td_p / "smoke_hom132_5.db"
        # Stage a sandbox episode dir — empty inner files are fine, every
        # node body's `<episode_dir>/.../<artifact> missing` skip triggers.
        # `isolate_audio._cmd` only requires `episode_dir` itself to exist
        # in state (it doesn't stat the dir).
        staged_episode = td_p / "ep" / slug
        staged_episode.mkdir(parents=True)
        # raw.mp4 sentinel — content-fingerprinted by isolate_audio's key.
        raw_mp4 = staged_episode / "raw.mp4"
        shutil.copyfile(fixture / "raw.mp4", raw_mp4) if (fixture / "raw.mp4").exists() else raw_mp4.write_bytes(b"sentinel")
        # DESIGN.md sentinel — content-fingerprinted by the four design-dependent
        # P4 nodes. Seed from real fixture so fingerprint reflects production-shaped content.
        design_md = td_p / "DESIGN.md"
        shutil.copyfile(fixture_design_md, design_md)

        graph = _build_chain(cache_db)

        # ─── Run 1: cold ───
        cold, t_cold = _run(
            graph,
            _state(slug=slug, episode_dir=staged_episode, design_md=design_md, raw_mp4=raw_mp4),
            "Run 1 (cold) — empty cache db, all 18 nodes execute",
        )
        cold_hits = [n for n in _CHAIN_NAMES if cold.get(n)]
        if cold_hits:
            print(
                f"SMOKE FAIL: Run 1 reported cached=True for {cold_hits} "
                "(cache should be empty)",
                file=sys.stderr,
            )
            return 1
        if not all(n in cold for n in _CHAIN_NAMES):
            missing = [n for n in _CHAIN_NAMES if n not in cold]
            print(
                f"SMOKE FAIL: Run 1 missing events for {missing} — chain wiring broken",
                file=sys.stderr,
            )
            return 1

        # ─── Run 2: warm ───
        warm, t_warm = _run(
            graph,
            _state(slug=slug, episode_dir=staged_episode, design_md=design_md, raw_mp4=raw_mp4),
            "Run 2 (warm) — identical state, all 18 nodes cache-hit",
        )
        warm_misses = [n for n in _CHAIN_NAMES if not warm.get(n)]
        if warm_misses:
            print(
                f"SMOKE FAIL: Run 2 did NOT cache-hit for {warm_misses} — "
                "CachePolicy/SqliteCache wiring broken on those nodes",
                file=sys.stderr,
            )
            return 1

        # ─── Run 3: targeted re-do via DESIGN.md edit ───
        design_md.write_text("# mutated palette — HOM-132.5 invalidation probe\n", encoding="utf-8")
        edited, t_edit = _run(
            graph,
            _state(slug=slug, episode_dir=staged_episode, design_md=design_md, raw_mp4=raw_mp4),
            "Run 3 (after DESIGN.md edit) — design-dependent nodes invalidate",
        )
        # Per spec §6: design_md is in `files=` for p4_prompt_expansion, p4_plan,
        # p4_beat, p4_captions_layer. p4_design_system PRODUCES design.md, doesn't
        # depend on it. Persist + assemble key on different files. Everything else
        # upstream is P3 — design_md isn't in their `files=`.
        design_dependent = (
            "p4_prompt_expansion",
            "p4_plan",
            "p4_beat",
            "p4_captions_layer",
        )
        stuck = [n for n in design_dependent if edited.get(n)]
        if stuck:
            print(
                f"SMOKE FAIL: Run 3 cache-hit on design-dependent nodes "
                f"{stuck} after DESIGN.md edit — invalidation broken",
                file=sys.stderr,
            )
            return 1
        # Upstream P3 + design_system + persist + assemble should all stay cached.
        upstream_cached = (
            "isolate_audio",
            "p3_inventory",
            "p3_pre_scan",
            "p3_strategy",
            "p3_edl_select",
            "p3_render_segments",
            "p3_self_eval",
            "p3_persist_session",
            "glue_remap_transcript",
            "p4_scaffold",
            "p4_design_system",
            "p4_catalog_scan",
            "p4_assemble_index",
            "p4_persist_session",
        )
        leaked_misses = [n for n in upstream_cached if not edited.get(n)]
        if leaked_misses:
            print(
                f"SMOKE FAIL: Run 3 cache-missed {leaked_misses} — "
                "they should NOT depend on DESIGN.md content (spec §6 violation)",
                file=sys.stderr,
            )
            return 1

    # ─── Wall-time summary ───
    print("\n──────── HOM-132.5 cold-vs-warm timing ────────")
    print(f"  Run 1 (cold,         18 nodes execute):  {t_cold*1000:8.1f} ms")
    print(f"  Run 2 (warm,         18 nodes cache-hit): {t_warm*1000:8.1f} ms")
    print(f"  Run 3 (post-edit,  4 nodes re-execute):  {t_edit*1000:8.1f} ms")
    if t_cold > 0:
        print(f"  Speedup cold→warm:                          {t_cold/t_warm:5.2f}×")
    print(
        "\n[OK] smoke_hom132_5_e2e PASS — full 18-node cached chain validates "
        "all three resume scenarios (forward continuation, targeted re-do, "
        "crash recovery) on real fixture artifacts."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
