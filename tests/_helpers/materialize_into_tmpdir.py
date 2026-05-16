"""Materialize a fixture episode into an isolated tmpdir at $0 spend.

HOM-255 / Step D1 of HOM-230 (state-first artifacts).

Purpose
-------

Tests that need a physical materialized HyperFrames tree (Playwright
snapshot smokes, ``npx hyperframes preview`` smokes, byte-equality
regression tests) historically read the committed
``tests/fixtures/episodes/<slug>/hyperframes/`` tree directly. HOM-239
(Step D2) will ``git rm`` that tree once D1 lands, because the
materializer regenerates it from state. Until D2 ships, the committed
tree is still on disk and MUST NOT be mutated by tests.

This helper builds an isolated project root under ``tmpdir`` and runs
:func:`p4_materialize_disk_node` against it — same writes the
production graph would do, but pointed at scratch space. The committed
fixture is read-only. After D2, this helper becomes the only path for
tests to see a materialized tree.

State reconstruction
--------------------

The materializer reads body fields from ``state`` (DESIGN.md body,
expanded-prompt body, index.html body, scene HTML bodies, optional
captions HTML, optional session block). Post HOM-241 the canonical
fixture cache.db carries those body strings directly (Step F re-record
under the post-Step-B+C+D1 architecture); ``_reconstruct_state`` reads
them from the decoded cache rows and uses them verbatim.

The helper also retains a per-field disk fallback — only consulted when
state is missing or empty for a given body field — so legacy
pre-Step-B cache.db files committed for historical diff inspection
remain usable. State always wins over disk: if cache.db has a non-empty
body for a field, the disk copy (if any) is ignored.

Native primitive contract
-------------------------

This helper does NOT call ``compiled.invoke`` / ``runs.create`` for state
reconstruction — CLAUDE.md §"Exception — fixture-replay test inspection"
applies here: going through the runtime would re-evaluate cache
fingerprints against the test machine's file paths under ``tmpdir``,
guaranteeing a silent cache miss → real LLM dispatch inside what
claimed to be a $0 replay smoke. State is reconstructed by direct
SQLite + ``JsonPlusSerializer`` decode plus disk reads of the committed
fixture's text artifacts.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Iterator


@contextlib.contextmanager
def _project_root_env(value: str) -> Iterator[None]:
    """Temporarily override ``HOMESTUDIO_PROJECT_ROOT``."""
    key = "HOMESTUDIO_PROJECT_ROOT"
    prior = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prior


def _decode_cache_rows(cache_db: Path) -> dict[str, list[dict[str, Any]]]:
    """Decode every cache row in ``cache_db``, grouped by node name.

    Each entry is a flattened ``{channel_name: value}`` dict; same shape
    used by :func:`tests._helpers.replay_dispatch.dispatch_node`. Pure
    SQLite + ``JsonPlusSerializer`` — never invokes the graph runtime.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    uri = cache_db.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        rows = conn.execute(
            "SELECT ns, encoding, val FROM cache ORDER BY ns, key"
        ).fetchall()
    finally:
        conn.close()

    by_node: dict[str, list[dict[str, Any]]] = {}
    for ns, enc, val in rows:
        # ns format: "__pregel_ns_writes,<dotted_callable>,<node_name>"
        parts = ns.split(",")
        if not parts:
            continue
        node_name = parts[-1]
        try:
            decoded = serde.loads_typed((enc, val))
        except Exception:
            continue
        flat: dict[str, Any] = {}
        try:
            for entry in decoded:
                if not entry or len(entry) < 2:
                    continue
                flat[str(entry[0])] = entry[1]
        except TypeError:
            continue
        by_node.setdefault(node_name, []).append(flat)
    return by_node


def _deep_merge(left: dict, right: dict) -> dict:
    """Recursive dict union (right wins on scalar conflicts).

    Mirrors LangGraph's default channel-merge behaviour for nested
    ``compose`` writes — top-level ``compose`` is a last-wins channel,
    but each producer writes a sub-tree that should accumulate, so we
    do a deep merge ourselves over the cache rows.
    """
    out = dict(left)
    for k, v in right.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _reconstruct_state(slug: str, source_episode_dir: Path) -> dict:
    """Reconstruct the state needed by ``p4_materialize_disk_node``.

    Reads:
      * The fixture cache.db for whatever channel writes are recorded.
      * The on-disk artifacts under ``source_episode_dir`` for body
        strings missing from the cache (see module docstring rationale).

    The result is a ``dict`` whose shape matches what the materializer
    reads at production time: top-level ``slug`` + ``scenes`` channels,
    nested ``compose.{design,expansion,captions,persist}`` sub-trees,
    ``compose.index_html`` top-level string.
    """
    cache_db = source_episode_dir / "cache.db"

    # Start from the cache rows (gives us llm_runs, gate metadata, the
    # `compose.*` skeleton with paths, etc.).
    state: dict = {"slug": slug, "compose": {}, "scenes": {}}
    if cache_db.is_file():
        by_node = _decode_cache_rows(cache_db)
        # Merge `compose` writes across all nodes.
        for entries in by_node.values():
            for flat in entries:
                compose_write = flat.get("compose")
                if isinstance(compose_write, dict):
                    state["compose"] = _deep_merge(state["compose"], compose_write)
                scenes_write = flat.get("scenes")
                if isinstance(scenes_write, dict):
                    state["scenes"].update(scenes_write)

    # Drop materializer's own previous output if recorded — we want a
    # fresh run, not a replay.
    state.get("compose", {}).pop("materialize", None)
    # Strip transient `compose._beat_unused` (pre-HOM-234 artifact —
    # confuses nothing but adds noise to state).
    state.get("compose", {}).pop("_beat_unused", None)

    # Post HOM-241: cache.db now carries body strings in state (Step B/C/D1
    # producers dual-wrote them; Step F re-recorded under the new
    # architecture). State is authoritative; disk fallback survives only
    # to keep the helper usable on legacy pre-Step-B cache.db files (any
    # historical PR that pinned an older fixture for diff inspection).
    compose = state.setdefault("compose", {})
    hf_dir = source_episode_dir / "hyperframes"
    edit_dir = source_episode_dir / "edit"

    def _state_first_string(current: str | None, disk_path: Path) -> str | None:
        if isinstance(current, str) and current:
            return current
        if disk_path.is_file():
            return disk_path.read_text(encoding="utf-8")
        return None

    design = compose.setdefault("design", {})
    val = _state_first_string(design.get("design_md"), hf_dir / "DESIGN.md")
    if val is not None:
        design["design_md"] = val

    expansion = compose.setdefault("expansion", {})
    val = _state_first_string(
        expansion.get("expanded_prompt"),
        hf_dir / ".hyperframes" / "expanded-prompt.md",
    )
    if val is not None:
        expansion["expanded_prompt"] = val

    val = _state_first_string(compose.get("index_html"), hf_dir / "index.html")
    if val is not None:
        compose["index_html"] = val

    captions = compose.setdefault("captions", {})
    val = _state_first_string(captions.get("html"), hf_dir / "captions.html")
    if val is not None:
        captions["html"] = val

    persist = compose.setdefault("persist", {})
    # project.md substring-skip in the materializer means re-appending the
    # full file content is idempotent on a copied project.md and produces
    # a byte-identical file on an empty tmpdir.
    val = _state_first_string(persist.get("session_block"), edit_dir / "project.md")
    if val is not None:
        persist["session_block"] = val

    # Scenes: state-first, with per-scene disk fallback for any scene_id
    # the cache.db didn't record (legacy fixtures only).
    compositions_dir = hf_dir / "compositions"
    if compositions_dir.is_dir():
        for scene_html in sorted(compositions_dir.glob("*.html")):
            scene_id = scene_html.stem
            existing = state["scenes"].get(scene_id) or {}
            if not isinstance(existing.get("html"), str) or not existing.get("html"):
                state["scenes"][scene_id] = {
                    **existing,
                    "html": scene_html.read_text(encoding="utf-8"),
                }

    return state


def materialize_into_tmpdir(
    slug: str,
    *,
    source_episode_dir: Path,
    tmpdir: Path,
) -> Path:
    """Materialize ``slug`` from ``source_episode_dir`` into ``tmpdir``.

    Args:
        slug: Fixture episode slug.
        source_episode_dir: Path to the committed fixture episode dir
            (``tests/fixtures/episodes/<slug>``). Not mutated.
        tmpdir: Scratch root (pytest's ``tmp_path`` or any temp dir).
            The helper builds ``<tmpdir>/episodes/<slug>/`` and pins
            ``HOMESTUDIO_PROJECT_ROOT=<tmpdir>`` for the materializer
            call.

    Returns:
        Path to ``<tmpdir>/episodes/<slug>/hyperframes`` — the
        directory containing the materialized HyperFrames tree.
    """
    tmpdir = Path(tmpdir).resolve()
    source_episode_dir = Path(source_episode_dir).resolve()

    target_episode_dir = tmpdir / "episodes" / slug
    target_episode_dir.mkdir(parents=True, exist_ok=True)
    (target_episode_dir / "edit").mkdir(parents=True, exist_ok=True)
    (target_episode_dir / "hyperframes").mkdir(parents=True, exist_ok=True)

    # Copy small read-side ancillaries the materializer doesn't write
    # but downstream tooling (preview, `npx hyperframes`) may expect.
    # Skip silently if absent — cache.db is what matters for state.
    for relpath in ("intent.yaml", "raw.mp4"):
        src = source_episode_dir / relpath
        if src.is_file():
            shutil.copy2(src, target_episode_dir / relpath)

    state = _reconstruct_state(slug, source_episode_dir)

    # The materializer resolves paths via `EpisodePaths(slug)` →
    # `project_root() / "episodes" / slug / ...`. Pin `project_root()`
    # at `tmpdir` for the duration of the call.
    from edit_episode_graph.nodes.p4_materialize_disk import (
        p4_materialize_disk_node,
    )

    with _project_root_env(str(tmpdir)):
        p4_materialize_disk_node(state)

    return target_episode_dir / "hyperframes"
