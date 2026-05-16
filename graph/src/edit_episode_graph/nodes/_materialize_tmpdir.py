"""Materialize an HF project into a fresh tmpdir for puppeteer-driven CLIs.

HOM-281. Six Class B sites call ``npx hyperframes <cmd>`` (lint / validate /
inspect / snapshot / catalog / animation-map) with ``cwd=<hf_dir>`` and need
a real project directory on disk with ``package.json``, ``index.html``,
``compositions/*.html``, transcripts, and the ancillary scaffold-produced
files (``hyperframes.json``, ``AGENTS.md``, ``CLAUDE.md``, ``final.mp4``).
Piping bodies via stdin is not viable for puppeteer — the headless browser
fetches sibling assets by relative URL, which only works if they sit next
to ``index.html`` on disk.

Per the HOM-230 state-first cutover, the canonical ``<episode>/hyperframes/``
tree is no longer the source of truth — the producer nodes emit body
strings into state, and ``p4_materialize_disk_node`` (the single
deterministic disk writer) renders them to the canonical location. The
gates and CLI-callers in this file render the SAME bodies to a transient
tmpdir instead, so they can run BEFORE materialization to disk is
necessary (or in fact, run without materializing to the canonical dir at
all when only a CLI invocation needs the tree).

Lifecycle decisions
-------------------

WHERE: tmpdir lives under ``tempfile.gettempdir()`` with a stable prefix
``hf-materialize-<slug>-`` so an operator can locate / inspect it if a
CLI subprocess hangs or fails. Not under ``graph/.cache/`` — that's
LangGraph's persistent cache surface and conflating ephemeral CLI
scratch with cache state would muddy the "wipe cache.db to force
re-execution" escape hatch.

WHEN: cleaned via :mod:`atexit` registration for any tmpdir created in
this process. Within a single graph-run (or a ``langgraph dev`` session
that processes multiple slugs back-to-back) the per-fingerprint cache
keeps the dir hot so the post-assemble gate cluster shares one tmpdir
across all six gates. The OS tmp-reaper is the long-tail safety net for
crashes that bypass atexit.

HOW (in-run cache): module-level dict keyed on
``(slug, hash(bodies-plus-ancillary-state))``. A second call with the
same key returns the cached path. A call with a different fingerprint
creates a NEW dir; the previous dir for that slug is unlinked from
the cache (and unlinked from disk via atexit on process exit). The
"different-fingerprint dir on disk until process exit" leak is bounded —
worst case is N back-to-back assemble retries within one graph-run,
which is bounded by gate-max-iterations.

WHAT we copy: state-channel bodies via ``compose_bodies`` PLUS a small
set of scaffold-produced ancillary files (``package.json``,
``hyperframes.json``, ``transcript.json``, ``AGENTS.md``, ``CLAUDE.md``,
``meta.json``, ``final.mp4``) read from the canonical
``EpisodePaths(slug).hyperframes_dir`` if they exist. These files are
written by ``p4_scaffold`` (a subprocess that writes to disk directly and
is not state-mirrored — HOM-280 only hoisted ``index.html``); copying
them keeps the tmpdir self-sufficient for the CLI subprocess.

What we do NOT copy: ``node_modules/``. The CLI subprocesses use
``npx hyperframes`` which resolves the hyperframes binary against the
ambient global / user-level npm cache; the headless Chrome puppeteer
ships inside the hyperframes package. Smoke-tested empirically on the
canonical fixture — none of the six CLIs we drive require a populated
``node_modules/`` next to ``index.html`` (puppeteer's browser binary is
discovered via the package's own install layout, not the project's).
If a future CLI needs project-local node_modules we revisit.

Hyperframes does write small artifacts (``snapshot`` PNGs, ``animation-map``
JSON) under the cwd it runs in — those land in the tmpdir, which is
exactly the isolation property we want. The gates that need to read
those artifacts (``snapshot`` for PNG sizing, ``animation_map`` for the
JSON) read them from the tmpdir, not the canonical hf_dir.

Native primitive note (CLAUDE.md §"LangGraph primitives"): there is no
LangGraph-level "per-run scratch dir" primitive. The closest is
``Runtime.context`` (graph-level mutable state outside channels), but
that's intended for resource handles (DB connections, HTTP clients),
not filesystem dirs that need fingerprint-keyed reuse + atexit cleanup.
Rolling a module-level cache + atexit is the conservative choice here.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Iterable

from .._paths import EpisodePaths
from ._compose_materialization import compose_bodies, upstream_skipped


# Ancillary files copied from the canonical hf_dir into the tmpdir when
# present. These are produced by ``p4_scaffold`` (a subprocess writer
# whose outputs are NOT state-mirrored) plus the transcript landed by
# the Phase-3 → Phase-4 hand-off. Missing files are silently skipped —
# a fresh-from-pickup state may legitimately have none of these yet
# (the materializer is then called before scaffold has run, which is
# itself an error but is signalled by the missing index.html body
# from ``compose_bodies`` rather than from this ancillary copy).
_ANCILLARY_RELPATHS: tuple[str, ...] = (
    "package.json",
    "hyperframes.json",
    "transcript.json",
    "AGENTS.md",
    "CLAUDE.md",
    "meta.json",
    "final.mp4",
)


# Module-level in-run cache: key -> tmpdir path. Per-process, protected by
# a lock because the production graph runs nodes concurrently via
# LangGraph's threadpool executor (gates fan-in after the assemble cluster
# but the executor can still call ``materialize_into_tmpdir`` from
# overlapping threads). The cache is a write-once-per-key map so the lock
# only serializes the create step, not the read.
_TMPDIRS_LOCK = threading.Lock()
_TMPDIRS: dict[str, Path] = {}
_ATEXIT_REGISTERED = False


def _register_atexit_once() -> None:
    """Register the cleanup hook exactly once per process."""
    global _ATEXIT_REGISTERED
    if _ATEXIT_REGISTERED:
        return
    atexit.register(_cleanup_all)
    _ATEXIT_REGISTERED = True


def _cleanup_all() -> None:
    """Best-effort recursive-rm of every tmpdir we created.

    Suppresses errors — atexit runs during interpreter teardown and any
    filesystem error here would obscure the real shutdown error. The OS
    tmp-reaper is the long-tail safety net.
    """
    with _TMPDIRS_LOCK:
        dirs = list(_TMPDIRS.values())
        _TMPDIRS.clear()
    for path in dirs:
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


def _fingerprint(state: dict, slug: str, bodies: dict[str, str], ancillary: Iterable[Path]) -> str:
    """Stable fingerprint of (slug, body bytes, ancillary file mtimes+sizes).

    Bodies are hashed by content (their actual bytes drive what lands in
    the tmpdir). Ancillary files are fingerprinted by (relpath, size,
    mtime_ns) — we don't want to read multi-MB ``final.mp4`` into memory
    just to key the cache. mtime + size is a sufficient proxy for
    "scaffold reran and the ancillary changed".

    Includes a tiny version byte so a future contract change (more
    bodies, different copy set) auto-invalidates without an explicit
    cache flush.
    """
    h = hashlib.sha256()
    h.update(b"v1\x00")
    h.update(slug.encode("utf-8"))
    h.update(b"\x00bodies\x00")
    for relpath in sorted(bodies):
        h.update(relpath.encode("utf-8"))
        h.update(b"\x00")
        h.update(bodies[relpath].encode("utf-8"))
        h.update(b"\x00")
    h.update(b"\x00ancillary\x00")
    for path in sorted(ancillary, key=lambda p: p.name):
        try:
            stat = path.stat()
        except OSError:
            continue
        h.update(path.name.encode("utf-8"))
        h.update(f"\x00{stat.st_size}\x00{stat.st_mtime_ns}\x00".encode("utf-8"))
    return h.hexdigest()


def _ancillary_sources(slug: str) -> list[Path]:
    """Existing ancillary files under the canonical hf_dir for ``slug``."""
    hf_dir = EpisodePaths(slug).hyperframes_dir
    return [hf_dir / rel for rel in _ANCILLARY_RELPATHS if (hf_dir / rel).is_file()]


def _write_bodies(target: Path, bodies: dict[str, str]) -> None:
    """Write every (relpath → body) into ``target`` with parents created.

    No atomic temp-rename dance — the tmpdir is private to the run and
    visible to no other reader until ``materialize_into_tmpdir`` returns.
    UTF-8, ``newline=""`` so Windows does not surprise us with CRLF.
    """
    for relpath, body in bodies.items():
        dest = target / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8", newline="") as fh:
            fh.write(body)


def _copy_ancillary(target: Path, sources: Iterable[Path]) -> None:
    """Copy each ancillary file from its canonical hf_dir location into ``target``."""
    for src in sources:
        shutil.copy2(src, target / src.name)


def materialize_into_tmpdir(state: dict, *, slug: str | None = None) -> Path:
    """Render the in-state HF project into a fresh tmpdir; return the dir.

    The tmpdir is a self-contained HyperFrames project root suitable as
    ``cwd`` for ``npx hyperframes <cmd>``: it carries the assembled
    ``index.html``, scene fragments under ``compositions/``, the
    DESIGN.md / expanded-prompt / captions text artifacts, plus the
    scaffold-produced ancillaries (``package.json``, ``hyperframes.json``,
    ``transcript.json``, etc.) read from the canonical hf_dir.

    Subsequent calls within the same process with identical state return
    the same tmpdir (in-run cache keyed on body+ancillary fingerprint).
    A state change invalidates the cache entry for that slug and a fresh
    tmpdir is created.

    Args:
        state: Phase-4 graph state. Must carry the body fields populated
            by the producer nodes (``compose.design.design_md``,
            ``compose.expansion.expanded_prompt``, ``compose.index_html``,
            ``scenes[*].html``).
        slug: Episode slug. Falls back to ``state["slug"]`` if omitted;
            raises ``RuntimeError`` if both are absent.

    Returns:
        Path to the materialized tmpdir (the HF project root). Caller
        passes this as the subprocess cwd.

    Raises:
        RuntimeError: when ``slug`` cannot be resolved or when
            :func:`compose_bodies` validation fails. On upstream-skip
            this returns no value — callers should not be reaching the
            tmpdir helper on a skipped run.
    """
    if slug is None:
        slug = state.get("slug")
    if not isinstance(slug, str) or not slug:
        raise RuntimeError(
            "materialize_into_tmpdir: slug missing — pass slug= explicitly "
            "or populate state['slug']"
        )

    compose = state.get("compose") or {}
    skipped, skip_reason = upstream_skipped(compose)
    if skipped:
        raise RuntimeError(
            f"materialize_into_tmpdir: cannot materialize a skipped run "
            f"({skip_reason}) — caller should short-circuit before "
            "invoking the tmpdir helper"
        )

    bodies = compose_bodies(state)
    ancillary_sources = _ancillary_sources(slug)
    fp = _fingerprint(state, slug, bodies, ancillary_sources)
    cache_key = f"{slug}::{fp}"

    with _TMPDIRS_LOCK:
        cached = _TMPDIRS.get(cache_key)
        if cached is not None and cached.is_dir():
            return cached

        # Evict any prior tmpdir registered under this slug with a different
        # fingerprint. Disk cleanup is best-effort — atexit catches what
        # we miss here.
        stale_keys = [k for k in _TMPDIRS if k.startswith(f"{slug}::") and k != cache_key]
        for k in stale_keys:
            stale_path = _TMPDIRS.pop(k, None)
            if stale_path is not None:
                shutil.rmtree(stale_path, ignore_errors=True)

        _register_atexit_once()
        target = Path(tempfile.mkdtemp(prefix=f"hf-materialize-{slug}-"))
        try:
            _write_bodies(target, bodies)
            _copy_ancillary(target, ancillary_sources)
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise
        _TMPDIRS[cache_key] = target
        return target


def materialize_scaffold_tmpdir(state: dict, *, slug: str | None = None) -> Path:
    """Render a minimal scaffold-only HF project into a fresh tmpdir.

    Variant of :func:`materialize_into_tmpdir` for callers that run
    BEFORE the Phase-4 producer chain has populated state-channel bodies
    (``p4_catalog_scan`` is the canonical caller — it runs immediately
    after ``gate_plan_ok`` so design / expansion / beats / captions are
    all absent from state at that point). Only the scaffold's
    ``index.html`` body (hoisted into ``compose.scaffold.index_html`` by
    HOM-280) plus the on-disk scaffold ancillaries (``package.json``,
    ``hyperframes.json``, ``transcript.json``, ``AGENTS.md``,
    ``CLAUDE.md``, ``final.mp4``) are materialized.

    Skips :func:`compose_bodies` validation entirely — by design this
    helper runs against an incomplete state. The returned tmpdir is
    sufficient for ``npx hyperframes catalog`` (which only requires
    "a directory with an HF project shape exists" — the catalog itself
    reads from the global registry) but is NOT sufficient for the
    full-project CLIs (``lint`` / ``validate`` / ``inspect`` / ``snapshot``
    / ``animation-map``); those callers MUST use :func:`materialize_into_tmpdir`.

    The in-run cache is shared with :func:`materialize_into_tmpdir` —
    a scaffold-mode call uses a distinct fingerprint (no body bytes) so
    it never collides with the full-project cache entry for the same
    slug, and a later full-project call gets its own dir.
    """
    if slug is None:
        slug = state.get("slug")
    if not isinstance(slug, str) or not slug:
        raise RuntimeError(
            "materialize_scaffold_tmpdir: slug missing — pass slug= "
            "explicitly or populate state['slug']"
        )

    compose = state.get("compose") or {}
    scaffold = compose.get("scaffold") or {}
    scaffold_index_html = scaffold.get("index_html")
    bodies: dict[str, str] = {}
    if isinstance(scaffold_index_html, str) and scaffold_index_html:
        bodies["index.html"] = scaffold_index_html

    ancillary_sources = _ancillary_sources(slug)
    fp = _fingerprint(state, slug, bodies, ancillary_sources)
    cache_key = f"{slug}::scaffold::{fp}"

    with _TMPDIRS_LOCK:
        cached = _TMPDIRS.get(cache_key)
        if cached is not None and cached.is_dir():
            return cached

        _register_atexit_once()
        target = Path(tempfile.mkdtemp(prefix=f"hf-scaffold-{slug}-"))
        try:
            _write_bodies(target, bodies)
            _copy_ancillary(target, ancillary_sources)
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise
        _TMPDIRS[cache_key] = target
        return target


def _clear_cache_for_tests() -> None:
    """Test-only hook: drop every cached tmpdir.

    The production graph never calls this; it exists so the unit tests
    can prove the cache works without leaking state across test cases.
    """
    with _TMPDIRS_LOCK:
        dirs = list(_TMPDIRS.values())
        _TMPDIRS.clear()
    for path in dirs:
        shutil.rmtree(path, ignore_errors=True)
