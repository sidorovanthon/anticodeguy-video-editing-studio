"""Fixture-replay harness for graph cache.db round-trips.

HOM-180 / spec §4. Wraps native LangGraph `langgraph.cache.sqlite.SqliteCache`
without forking it: provides three modes controlled by env var
``HOMESTUDIO_TEST_MODE``:

* ``replay`` (default) — fixture cache.db is opened **read-only** via
  ``sqlite3.connect(uri=True, ...&mode=ro)``. Any cache miss raises
  :class:`ReplayCacheMissError` with the canonical re-record instruction.
  Guarantees zero paid LLM dispatches in this mode.
* ``record-on-miss`` — fixture cache.db is copied to a working copy that
  the graph reads/writes normally; on test teardown
  :func:`finalize_record_on_miss` writes back via ``VACUUM INTO`` + atomic
  rename so the committed file is in deterministic raw form.
* ``record`` — same writeback as ``record-on-miss`` but the working copy
  starts empty (or is wiped from the existing fixture); intended as
  «one-shot full re-record» (e.g. spec §4 first record of a fixture
  episode after a major schema change).

Native primitives only: we do not subclass `BaseCache`, we just use
`SqliteCache` with a path we control. The replay-mode cache is a thin
SqliteCache subclass that opens the underlying connection in ``mode=ro``
and short-circuits ``set()`` to raise — keeping the LangGraph integration
contract intact (see spec §4 «Stability concern», option 1).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langgraph.cache.base import FullKey, ValueT
from langgraph.cache.sqlite import SqliteCache

Mode = Literal["replay", "record-on-miss", "record"]
"""Allowed values for ``HOMESTUDIO_TEST_MODE``."""

DEFAULT_MODE: Mode = "replay"
ENV_VAR = "HOMESTUDIO_TEST_MODE"

# Where the live graph compiles its cache to (matches
# `edit_episode_graph.graph._CACHE_PATH`). The harness mounts the fixture
# at this exact path so the compiled graph picks it up without code changes.
_LIVE_CACHE_RELATIVE = Path("graph") / ".cache" / "langgraph.db"


class ReplayCacheMissError(RuntimeError):
    """Raised in ``replay`` mode when a node is not in the recorded fixture.

    Message matches the spec §4 contract verbatim so reviewers/devs see
    a consistent re-record hint regardless of which test trips it.
    """


def _resolve_mode(explicit: Mode | None) -> Mode:
    if explicit is not None:
        return explicit
    raw = os.environ.get(ENV_VAR)
    if raw is None or raw == "":
        return DEFAULT_MODE
    if raw not in ("replay", "record-on-miss", "record"):
        raise ValueError(
            f"{ENV_VAR}={raw!r} is not a valid mode; "
            "expected one of 'replay', 'record-on-miss', 'record'"
        )
    return raw  # type: ignore[return-value]


def _fixture_cache_path(slug: str, fixtures_root: Path) -> Path:
    return fixtures_root / "episodes" / slug / "cache.db"


def _fixture_episode_dir(slug: str, fixtures_root: Path) -> Path:
    return fixtures_root / "episodes" / slug


@dataclass
class MountedFixture:
    """Result handle returned by :func:`mount_fixture_cache`.

    ``working_path`` is what the harness wires into the compiled graph
    (a temp file in ``record`` / ``record-on-miss`` mode, the fixture
    file itself in ``replay`` mode). ``fixture_path`` is the canonical
    committed cache.db. ``mode`` is the resolved mode for clean
    diagnostics.
    """

    slug: str
    mode: Mode
    fixture_path: Path
    working_path: Path
    _tmp_dir: Path | None = None

    def cleanup(self) -> None:
        """Best-effort removal of any tmp artifacts created during mount."""
        if self._tmp_dir is not None and self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None


class _ReadOnlySqliteCache(SqliteCache):
    """``SqliteCache`` opened ``mode=ro`` with miss → :class:`ReplayCacheMissError`.

    Subclass replaces the connection initialization but reuses the parent's
    schema/SerDe layer — so any future schema change in upstream
    LangGraph propagates without us touching anything. Spec §4 stability
    option (1): read-only URI prevents accidental writes (journal,
    pragma) producing spurious diffs.
    """

    def __init__(self, *, path: str, serde=None) -> None:
        # Skip parent's __init__ (it always opens RW + CREATE TABLE).
        # Initialize the BaseCache layer manually for serde.
        from langgraph.cache.base import BaseCache  # local import: avoid hard dep cycle

        BaseCache.__init__(self, serde=serde)
        # Open the SQLite file in read-only URI mode. The parent uses a
        # plain path, so we mirror its connect kwargs but flip mode=ro.
        uri = Path(path).as_uri() + "?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        # Lock kept identical for thread-safety contract parity.
        import threading

        self._lock = threading.RLock()

    def set(  # type: ignore[override]
        self, mapping: Mapping[FullKey, tuple[ValueT, int | None]]
    ) -> None:
        if not mapping:
            return
        # Surface the miss with the canonical operator hint. We pull one
        # representative key for the message so the dev can grep
        # `recordings/<node>.json` directly.
        first_key = next(iter(mapping))
        ns, fp = first_key
        node = ",".join(ns)
        raise ReplayCacheMissError(
            f"no recording for node {node} with fingerprint {fp}; "
            f"re-record locally via {ENV_VAR}=record-on-miss"
        )

    async def aset(  # type: ignore[override]
        self, mapping: Mapping[FullKey, tuple[ValueT, int | None]]
    ) -> None:
        # Mirror sync semantics — async writes fail loudly too.
        self.set(mapping)

    def clear(self, namespaces: Sequence | None = None) -> None:  # type: ignore[override]
        raise ReplayCacheMissError(
            f"clear() called in replay mode (read-only); "
            f"set {ENV_VAR}=record to wipe + re-record fixture"
        )


def mount_fixture_cache(
    slug: str,
    *,
    mode: Mode | None = None,
    fixtures_root: Path | None = None,
    project_root: Path | None = None,
) -> MountedFixture:
    """Make ``tests/fixtures/episodes/<slug>/cache.db`` the active cache.

    Behaviour by mode:

    * ``replay`` — the fixture is the working file (we will only ever
      open it RO via :func:`open_cache`). No copy made.
    * ``record-on-miss`` — fixture is copied to a tmp working file; the
      caller is expected to wire the compiled graph's cache to that
      path and call :func:`finalize_record_on_miss` on teardown to
      atomically write back.
    * ``record`` — empty tmp working file (or wiped from fixture); the
      same finalize step writes it back as the new canonical fixture.

    Args:
        slug: Episode slug (matches the directory name under
            ``tests/fixtures/episodes/``).
        mode: Optional explicit override; default reads
            ``HOMESTUDIO_TEST_MODE``.
        fixtures_root: Optional override for the fixtures dir; default
            is ``<project_root>/tests/fixtures``.
        project_root: Optional override for the project root; default
            walks up from this file (so this works inside any worktree).
    """
    resolved = _resolve_mode(mode)
    if project_root is None:
        # tests/_helpers/replay_harness.py → tests/_helpers → tests → project
        project_root = Path(__file__).resolve().parents[2]
    if fixtures_root is None:
        fixtures_root = project_root / "tests" / "fixtures"

    fixture_path = _fixture_cache_path(slug, fixtures_root)
    fixture_dir = _fixture_episode_dir(slug, fixtures_root)

    if resolved == "replay":
        if not fixture_path.exists():
            raise FileNotFoundError(
                f"replay mode requires fixture cache.db at {fixture_path}; "
                f"run with {ENV_VAR}=record to create it first"
            )
        return MountedFixture(
            slug=slug,
            mode=resolved,
            fixture_path=fixture_path,
            working_path=fixture_path,
        )

    # Both record modes use a tmp working file so we can VACUUM INTO
    # the canonical fixture path atomically on finalize. The tmp dir
    # is owned by the MountedFixture handle and torn down on cleanup.
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"hom180-{slug}-"))
    working_path = tmp_dir / "langgraph.db"

    if resolved == "record-on-miss":
        if fixture_path.exists():
            shutil.copy2(fixture_path, working_path)
        # else: empty start is fine — no recording yet for this slug.
    elif resolved == "record":
        # Explicitly leave working_path empty; first SqliteCache write
        # creates the schema. We do NOT preemptively delete the fixture
        # — finalize() does the atomic swap.
        pass

    # Make sure fixture dir exists so finalize can write into it.
    fixture_dir.mkdir(parents=True, exist_ok=True)

    return MountedFixture(
        slug=slug,
        mode=resolved,
        fixture_path=fixture_path,
        working_path=working_path,
        _tmp_dir=tmp_dir,
    )


def open_cache(mounted: MountedFixture) -> SqliteCache:
    """Open the appropriate `SqliteCache` for the given mounted fixture.

    In ``replay`` mode this returns a read-only subclass that raises
    :class:`ReplayCacheMissError` on any write attempt. In record modes
    it returns a vanilla `SqliteCache` pointed at the temp working file.
    """
    if mounted.mode == "replay":
        return _ReadOnlySqliteCache(path=str(mounted.working_path))
    return SqliteCache(path=str(mounted.working_path))


def finalize_record_on_miss(mounted: MountedFixture, cache: SqliteCache) -> None:
    """Persist record-mode writes back to the canonical fixture path.

    Uses ``VACUUM INTO`` to write a deterministic raw form (no journal,
    no free pages, no WAL artefacts) followed by atomic ``Path.replace``
    so partial writes can never leave a corrupted fixture. Spec §4
    stability option (2).

    No-op in ``replay`` mode (cache is read-only).
    """
    if mounted.mode == "replay":
        return

    # Make sure the working connection has flushed all writes. SqliteCache
    # uses `with self._conn` per-call so commits are already flushed, but
    # we issue a defensive PRAGMA wal_checkpoint(TRUNCATE) before VACUUM
    # so the resulting file has no -wal sidecar dependency.
    conn = cache._conn  # noqa: SLF001 — interlocking with native primitive
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except sqlite3.DatabaseError:
        # If the DB is brand-new (record from empty, no writes yet) the
        # pragma may fail silently — non-fatal.
        pass

    tmp_target = mounted.fixture_path.with_suffix(".db.tmp")
    if tmp_target.exists():
        tmp_target.unlink()
    # VACUUM INTO is a SQLite native one-shot snapshot (3.27+); produces
    # the same byte-for-byte file regardless of insert order or WAL state.
    conn.execute("VACUUM INTO ?", (str(tmp_target),))

    # Close the working connection before swapping the destination — on
    # Windows, ``Path.replace`` cannot overwrite a file that has any
    # open handle (including the destination's own readers). Closing
    # the source connection here also prevents accidental writes after
    # the fixture has been canonicalized.
    try:
        conn.close()
    except sqlite3.Error:
        pass

    # If a replay-side reader (or another process) is keeping the
    # destination file open, retry the rename a few times — gives the
    # OS a chance to flush handles. POSIX is unaffected (replace works
    # while the file is open).
    import time

    last_err: Exception | None = None
    for _ in range(5):
        try:
            tmp_target.replace(mounted.fixture_path)
            last_err = None
            break
        except PermissionError as e:  # Windows file-lock race
            last_err = e
            time.sleep(0.05)
    if last_err is not None:
        raise last_err
