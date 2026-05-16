"""p4_materialize_disk — single deterministic writer for Phase 4 text artifacts.

Step D1 of HOM-230 (state-first artifacts). Reads body fields populated
by Step-B producers from state, asserts mandatory presence, then
atomically writes each artifact to the canonical on-disk location via
``_atomic_write`` (overwrite via temp-file + ``os.replace``) or, for
``project.md``, ``_append_session_block`` (substring-skip + fsynced
append). Producers continue to dual-write during D1 — Step D2 (HOM-239)
strips the dual-writes and ``git rm``s the committed fixture artifacts.

Atomicity contract: every validation (mandatory bodies + per-scene
``html`` presence) runs to completion BEFORE any byte hits disk. A
malformed state raises ``RuntimeError`` without leaving a partial tree.

Idempotency contract:
  * ``_atomic_write`` skips when ``path.exists()`` and content is byte-
    identical to ``content``. Returns ``False`` on skip, ``True`` on
    actual write. Skips are NOT recorded in ``files_written``.
  * ``_append_session_block`` skips when ``block`` is already a substring
    of the existing file content — the persist producer's dual-write
    during D1 will have inserted it once already, and re-running the
    materializer must not duplicate it.

Cache policy: keyed on sha256 of every consumed body field (deterministic,
no LLM tier). Same state → same key → cache hit. Body change in any
producer → key miss → re-run. Per spec §11 risk
("Materializer cache key non-determinism") the scenes channel is iterated
via ``sorted(state["scenes"].items())`` so parallel ``Send`` completion
order from ``p4_beat`` does not produce different keys for the same
scene set. Mirrors ``_scenes_merge``'s sorted output (state.py).

Spec: docs/superpowers/specs/2026-05-10-state-first-artifacts.md §6.3,
§"Step D — Cutover" §"Step D1".
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import CachePolicy

from .._caching import make_key, stable_fingerprint
from .._paths import EpisodePaths

# Bump on schema/contract change (HOM-132 spec §8). v1: initial no-op
# release (Step C, HOM-238). v2 (HOM-255 / Step D1): atomic disk writes
# activated; files_written populated.
_CACHE_VERSION = 2


# Mandatory body fields the materializer asserts and writes.
# Each entry is (state-path-tuple, human-name for error messages).
_MANDATORY: tuple[tuple[tuple[str, ...], str], ...] = (
    (("compose", "design", "design_md"), "compose.design.design_md"),
    (("compose", "expansion", "expanded_prompt"), "compose.expansion.expanded_prompt"),
    (("compose", "index_html"), "compose.index_html"),
)


def _pluck(state: dict, path: tuple[str, ...]):
    cur: object = state
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _body_set(state: dict) -> dict:
    """Gather every body string consumed by the materializer.

    Returns a dict that ``stable_fingerprint`` hashes deterministically —
    `sort_keys=True` plus the sorted-by-key ``scenes`` iteration makes
    the result independent of Python dict insertion order and parallel
    ``Send`` completion order from the ``p4_beat`` fan-out.
    """
    compose = state.get("compose") or {}
    design = compose.get("design") or {}
    expansion = compose.get("expansion") or {}
    captions = compose.get("captions") or {}
    persist = compose.get("persist") or {}
    # Top-level `scenes` channel (HOM-234), NOT `compose.scenes` —
    # nested Annotated channels do not fire their reducer. The spec
    # mandates sorted iteration here for cache-key determinism (§11).
    scenes = state.get("scenes") or {}
    scenes_sorted = {
        scene_id: (scene.get("html") if isinstance(scene, dict) else None)
        for scene_id, scene in sorted(scenes.items())
    }
    body: dict = {
        "design_md": design.get("design_md"),
        "expanded_prompt": expansion.get("expanded_prompt"),
        "index_html": compose.get("index_html"),
        "scenes": scenes_sorted,
    }
    # Optional bodies — only included when present, because both
    # producers can legitimately skip (captions on transcript absence;
    # persist on assemble skip). Including them as ``None`` would
    # entangle the cache key with the absence-vs-present distinction
    # post-hoc; omission keeps the key stable across legitimate skips.
    captions_html = captions.get("html")
    if captions_html is not None:
        body["captions_html"] = captions_html
    session_block = persist.get("session_block")
    if session_block is not None:
        body["session_block"] = session_block
    return body


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_materialize_disk cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    return make_key(
        node="p4_materialize_disk",
        version=_CACHE_VERSION,
        slug=slug,
        files=[],
        extras=(stable_fingerprint(_body_set(state)),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, content: str) -> bool:
    """Atomically write ``content`` to ``path``; idempotent on byte-match.

    Returns ``True`` if a write happened, ``False`` if the file already
    contained byte-identical ``content`` (idempotent skip — no temp file
    created, no mtime touched).

    Mechanics:
      * Idempotency: read existing content with UTF-8 decoding; compare.
      * Write: ``<path>.tmp`` is opened in text mode with ``newline=""``
        so no Windows CRLF surprise; ``fh.flush()`` + ``os.fsync(fh.fileno())``
        guarantees bytes are on the platter; ``os.replace`` performs the
        atomic rename (Windows-compatible).
      * On exception during the temp-write phase, the temp file is
        unlinked (best-effort) so no ``*.tmp`` artifacts are left
        behind to confuse the next run.

    Encoding: UTF-8, no BOM, LF line endings preserved.
    """
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            existing = None
        if existing == content:
            return False

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        # Clean up the orphaned temp file so a future run does not see
        # a stale ``*.tmp`` lingering. Suppress secondary errors during
        # cleanup — the original exception is what callers need.
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
    return True


def _append_session_block(path: Path, block: str) -> bool:
    """Append ``block`` to ``path`` with substring-skip idempotency.

    Returns ``True`` on actual append, ``False`` when ``block`` is
    already a substring of the existing file content (skip — the
    persist producer's dual-write during D1 inserted it, or a prior
    materializer run did).

    Mechanics:
      * Idempotency: substring check on existing content. Cheap, no
        normalization — matches the persist producer's write byte-for-byte.
      * Separator: if the file exists and is non-empty, insert ``\\n``
        when its last byte isn't a newline, then a blank line ``\\n``
        before the block (mirrors persist producer's ``sep`` logic).
      * fsync the append handle before close so the new block is
        durable on the platter before the materializer returns.
    """
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            existing = ""
        if block in existing:
            return False

    path.parent.mkdir(parents=True, exist_ok=True)
    sep = ""
    if existing:
        sep = "\n" if not existing.endswith("\n") else ""
        sep += "\n"
    with path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(sep + block)
        fh.flush()
        os.fsync(fh.fileno())
    return True


def _upstream_skipped(compose: dict) -> tuple[bool, str | None]:
    """Return (True, reason) when an upstream step the materializer
    depends on has skipped. Mirrors the producers' skip-propagation
    pattern so the materializer behaves consistently along skip paths
    (no spurious RuntimeError from a state that legitimately has no
    body to materialize).
    """
    for sub in ("assemble", "design", "expansion"):
        section = compose.get(sub) or {}
        if section.get("skipped"):
            return True, (
                f"upstream {sub} skipped: "
                f"{section.get('skip_reason') or 'no reason given'}"
            )
    return False, None


def p4_materialize_disk_node(state: dict) -> dict:
    """Atomic single-writer for Phase 4 text artifacts (Step D1).

    Validates mandatory body presence, then atomically writes each
    artifact to its canonical on-disk path resolved via
    ``EpisodePaths(state["slug"])``. Returns ``materialized_at`` (ISO
    timestamp) plus ``files_written`` (absolute paths of files whose
    write actually changed content; idempotent skips are NOT listed).
    """
    compose = state.get("compose") or {}
    skipped, skip_reason = _upstream_skipped(compose)
    if skipped:
        return {
            "compose": {
                "materialize": {
                    "skipped": True,
                    "skip_reason": skip_reason,
                },
            },
        }

    # ----- Validation phase (no disk I/O yet — atomicity property) ---
    # Raise BEFORE any write so a malformed state can never leave a
    # partial tree on disk.
    for path, name in _MANDATORY:
        value = _pluck(state, path)
        if not isinstance(value, str) or not value:
            raise RuntimeError(
                f"p4_materialize_disk: required body field {name!r} missing "
                "or empty in state — producer must populate before "
                "materializer runs"
            )
    scenes = state.get("scenes") or {}
    if not scenes:
        raise RuntimeError(
            "p4_materialize_disk: required body field 'scenes' missing or "
            "empty — p4_beat fan-out produced no scene fragments"
        )
    # Per-scene validation — every scene must carry a non-empty `html`
    # body. If any scene is malformed, fail BEFORE writing any file
    # (atomicity property).
    for scene_id, scene in sorted(scenes.items()):
        if not isinstance(scene, dict):
            raise RuntimeError(
                f"p4_materialize_disk: scene {scene_id!r} is not a dict "
                f"(got {type(scene).__name__}) — p4_beat regressed its "
                "fan-out output shape"
            )
        body = scene.get("html")
        if not isinstance(body, str) or not body:
            raise RuntimeError(
                f"p4_materialize_disk: scene {scene_id!r} missing non-empty "
                "'html' body — p4_beat fan-out produced an incomplete scene"
            )

    # ----- Write phase --------------------------------------------------
    slug = state.get("slug")
    if not isinstance(slug, str) or not slug:
        raise RuntimeError(
            "p4_materialize_disk: state['slug'] missing or empty — cannot "
            "resolve target paths via EpisodePaths"
        )
    paths = EpisodePaths(slug)

    files_written: list[str] = []

    design_md = _pluck(state, ("compose", "design", "design_md"))
    if _atomic_write(paths.design_md_path, design_md):
        files_written.append(str(paths.design_md_path))

    expanded_prompt = _pluck(state, ("compose", "expansion", "expanded_prompt"))
    if _atomic_write(paths.expanded_prompt_path, expanded_prompt):
        files_written.append(str(paths.expanded_prompt_path))

    for scene_id, scene in sorted(scenes.items()):
        scene_html = scene["html"]  # validated above
        target = paths.beat_fragment_path(scene_id)
        if _atomic_write(target, scene_html):
            files_written.append(str(target))

    captions_html = (compose.get("captions") or {}).get("html")
    if isinstance(captions_html, str) and captions_html:
        if _atomic_write(paths.captions_block_path, captions_html):
            files_written.append(str(paths.captions_block_path))

    index_html = _pluck(state, ("compose", "index_html"))
    if _atomic_write(paths.index_html_path, index_html):
        files_written.append(str(paths.index_html_path))

    session_block = (compose.get("persist") or {}).get("session_block")
    if isinstance(session_block, str) and session_block:
        project_md = paths.edit_dir / "project.md"
        if _append_session_block(project_md, session_block):
            files_written.append(str(project_md))

    return {
        "compose": {
            "materialize": {
                "materialized_at": _now(),
                "files_written": files_written,
            },
        },
    }
