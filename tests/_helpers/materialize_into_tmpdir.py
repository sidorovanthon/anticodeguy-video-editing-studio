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
captions HTML, optional session block). The committed fixture
``cache.db`` predates the Step-B body-in-state work (HOM-232..237):
recorded ``compose`` channel writes carry path references but NOT the
body strings (they were written to disk by Step-B producers' dual-writes
and only later flowed into state). To bridge the gap until the operator
re-records the fixture under post-Step-B code, this helper reads bodies
from the committed on-disk artifacts (``DESIGN.md``,
``.hyperframes/expanded-prompt.md``, ``compositions/<scene>.html``,
``captions.html``, ``index.html``, ``edit/project.md``) and the recorded
cache.db rows for any structured metadata. The materializer then
regenerates the tree byte-for-byte under ``tmpdir`` — proving the
write-logic is correct under self-consistency. Once a post-Step-B
fixture cache.db lands, the body-from-disk fallback can be removed and
state-reconstruction becomes pure cache.db replay.

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

    hf_dir = source_episode_dir / "hyperframes"
    edit_dir = source_episode_dir / "edit"

    # --- Body strings from on-disk artifacts (fallback for pre-Step-B
    # cache.db; once the operator re-records, these reads become
    # redundant — the cache will already carry the bodies).
    compose = state.setdefault("compose", {})

    design_md = hf_dir / "DESIGN.md"
    if design_md.is_file():
        compose.setdefault("design", {})["design_md"] = design_md.read_text(
            encoding="utf-8"
        )

    expanded_prompt = hf_dir / ".hyperframes" / "expanded-prompt.md"
    if expanded_prompt.is_file():
        compose.setdefault("expansion", {})["expanded_prompt"] = (
            expanded_prompt.read_text(encoding="utf-8")
        )

    index_html = hf_dir / "index.html"
    if index_html.is_file():
        compose["index_html"] = index_html.read_text(encoding="utf-8")

    captions = hf_dir / "captions.html"
    if captions.is_file():
        compose.setdefault("captions", {})["html"] = captions.read_text(
            encoding="utf-8"
        )

    project_md = edit_dir / "project.md"
    if project_md.is_file():
        # Use the entire project.md content as the "session block" —
        # the materializer's substring-skip means re-appending it onto a
        # freshly-copied project.md is a no-op write. For an empty
        # tmpdir (no copy) it produces a project.md byte-identical to
        # the source.
        compose.setdefault("persist", {})["session_block"] = project_md.read_text(
            encoding="utf-8"
        )

    # Scenes: read every `compositions/*.html` and populate the
    # top-level `scenes` channel.
    compositions_dir = hf_dir / "compositions"
    if compositions_dir.is_dir():
        for scene_html in sorted(compositions_dir.glob("*.html")):
            scene_id = scene_html.stem
            state["scenes"][scene_id] = {"html": scene_html.read_text(encoding="utf-8")}

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
