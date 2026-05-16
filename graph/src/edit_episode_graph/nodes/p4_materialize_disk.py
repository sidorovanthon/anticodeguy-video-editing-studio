"""p4_materialize_disk — single deterministic writer for Phase 4 text artifacts.

Step C of HOM-230 (state-first artifacts). NO-OP shipping mode: reads the
body fields populated by Step-B producers from state and asserts they are
present where required. Does NOT yet write files — producers still
dual-write to disk during the migration window. Step D1 activates atomic
writes here and strips the dual-writes from producers.

Cache policy: keyed on sha256 of every consumed body field (deterministic,
no LLM tier). Same state → same key → cache hit. Body change in any
producer → key miss → re-run. Per spec §11 risk
("Materializer cache key non-determinism") the scenes channel is iterated
via ``sorted(state["scenes"].items())`` so parallel ``Send`` completion
order from ``p4_beat`` does not produce different keys for the same
scene set. Mirrors ``_scenes_merge``'s sorted output (state.py).

Spec: docs/superpowers/specs/2026-05-10-state-first-artifacts.md §6.3,
§"Step C — Add `p4_materialize_disk_node` as no-op".
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import CachePolicy

from .._caching import make_key, stable_fingerprint

# Bump on schema/contract change (HOM-132 spec §8). v1: initial no-op
# release (Step C). v2 will land with Step D1 when atomic disk writes
# turn on — at which point ``files_written`` becomes meaningful and the
# fingerprint scope may expand.
_CACHE_VERSION = 1


# Mandatory body fields the materializer asserts and (in Step D1) writes.
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
    """No-op (Step C) deterministic writer.

    Reads the Step-B body fields, asserts the mandatory ones are
    present, and records a ``materialized_at`` timestamp. Does NOT
    touch disk — Step D1 activates atomic writes.
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

    # Mandatory presence checks. Raise a clear RuntimeError naming the
    # missing field — the operator should never see this in normal
    # flow because all three producers run upstream on the happy path;
    # a miss means a producer regressed its body-string contract or
    # the materializer is wired in the wrong topology position.
    for path, name in _MANDATORY:
        value = _pluck(state, path)
        if not isinstance(value, str) or not value:
            raise RuntimeError(
                f"p4_materialize_disk: required body field {name!r} missing "
                "or empty in state — producer must populate before "
                "materializer runs"
            )
    # `scenes` is a dict channel — assert non-empty separately. Empty
    # scenes is a real failure (no beats made it through fan-out) and
    # nothing for Step D1 to write into compositions/.
    scenes = state.get("scenes") or {}
    if not scenes:
        raise RuntimeError(
            "p4_materialize_disk: required body field 'scenes' missing or "
            "empty — p4_beat fan-out produced no scene fragments"
        )

    return {
        "compose": {
            "materialize": {
                "materialized_at": _now(),
                # Step D1 will populate this list during atomic writes.
                # Empty list at Step C makes the transition diff-only.
                "files_written": [],
            },
        },
    }
