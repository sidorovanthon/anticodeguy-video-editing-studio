"""Shared body-bytes-per-relative-path producer for the Phase-4 materializers.

HOM-281. Both ``p4_materialize_disk_node`` (atomic write to the canonical
``<episode>/hyperframes/`` tree) and ``materialize_into_tmpdir`` (transient
write to a fresh scratch dir for puppeteer-driven CLI subprocesses) consume
the same state-channel body inputs and produce the same per-relpath byte
contents. This module is that producer.

Returned mapping
----------------

``compose_bodies(state) -> dict[str, str]``

Keys are forward-slash relative paths under the HF project root (e.g.
``"index.html"``, ``"DESIGN.md"``, ``".hyperframes/expanded-prompt.md"``,
``"compositions/<scene_id>.html"``, ``"captions.html"``). Values are the
UTF-8 text bodies the producers wrote into ``state``. Optional bodies
(``captions.html``, scene fragments when ``scenes`` is empty) are simply
absent from the dict, never present-as-``None``.

The ``edit/project.md`` append (a sibling of ``hyperframes/``) is NOT part
of this mapping — it is an append-with-substring-skip operation, not a
"write these bytes to this path" operation, so it lives in
``p4_materialize_disk_node`` directly. The tmpdir helper does not need
it: ``project.md`` is consumed by the operator, not by any puppeteer CLI.

Validation contract
-------------------

``compose_bodies`` raises ``RuntimeError`` BEFORE returning if any mandatory
body field is missing or empty (same shape and error messages as the
pre-extraction validation in ``p4_materialize_disk_node``). The atomicity
contract of the canonical disk writer relies on validate-before-write —
keeping validation in the shared producer preserves that property for both
callers and keeps the failure surface identical.

Scene iteration order
---------------------

Per spec §11 the ``scenes`` channel is iterated via ``sorted(...)`` so the
output mapping is deterministic regardless of ``p4_beat`` ``Send`` fan-out
completion order. This matches the iteration in ``p4_materialize_disk``'s
``_body_set`` (used for cache-key hashing) so the producer and consumer
agree on order.
"""

from __future__ import annotations

from typing import Iterable


# Mandatory body fields. Each entry is (state-path-tuple, human-name for error
# messages). Mirrors `p4_materialize_disk._MANDATORY` — kept in lockstep here
# because the validation phase is shared.
_MANDATORY: tuple[tuple[tuple[str, ...], str], ...] = (
    (("compose", "design", "design_md"), "compose.design.design_md"),
    (("compose", "expansion", "expanded_prompt"), "compose.expansion.expanded_prompt"),
    (("compose", "index_html"), "compose.index_html"),
)


def _pluck(state: dict, path: Iterable[str]):
    cur: object = state
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def upstream_skipped(compose: dict) -> tuple[bool, str | None]:
    """Return ``(True, reason)`` when an upstream Phase-4 step skipped.

    Mirrors the producers' skip-propagation pattern: the materializer
    legitimately has nothing to write when an upstream producer signaled
    a skip, and should propagate the skip rather than raise on absent
    bodies. Shared between the disk writer and tmpdir helper so both
    behave consistently on skip paths.
    """
    for sub in ("assemble", "design", "expansion"):
        section = compose.get(sub) or {}
        if section.get("skipped"):
            return True, (
                f"upstream {sub} skipped: "
                f"{section.get('skip_reason') or 'no reason given'}"
            )
    return False, None


def validate_state(state: dict) -> None:
    """Raise ``RuntimeError`` if any mandatory body field is missing or empty.

    Pre-write validation: callers run this BEFORE any disk I/O so a
    malformed state can never leave a partial materialized tree on disk
    (atomicity contract of ``p4_materialize_disk``; the tmpdir helper
    benefits from the same property).

    Skip-path callers should call :func:`upstream_skipped` first and
    short-circuit if it returns True; this validator assumes no upstream
    skip.
    """
    for path, name in _MANDATORY:
        value = _pluck(state, path)
        if not isinstance(value, str) or not value:
            raise RuntimeError(
                f"materialize: required body field {name!r} missing or "
                "empty in state — producer must populate before "
                "materializer runs"
            )
    scenes = state.get("scenes") or {}
    if not scenes:
        raise RuntimeError(
            "materialize: required body field 'scenes' missing or empty — "
            "p4_beat fan-out produced no scene fragments"
        )
    for scene_id, scene in sorted(scenes.items()):
        if not isinstance(scene, dict):
            raise RuntimeError(
                f"materialize: scene {scene_id!r} is not a dict "
                f"(got {type(scene).__name__}) — p4_beat regressed its "
                "fan-out output shape"
            )
        body = scene.get("html")
        if not isinstance(body, str) or not body:
            raise RuntimeError(
                f"materialize: scene {scene_id!r} missing non-empty 'html' "
                "body — p4_beat fan-out produced an incomplete scene"
            )


def compose_bodies(state: dict) -> dict[str, str]:
    """Return ``{relpath: body}`` for every state-channel artifact.

    Relpaths are forward-slash, rooted at the HF project (so
    ``"index.html"``, ``"compositions/<scene_id>.html"``, etc.). Bodies
    are UTF-8 strings — callers encode + write per their atomicity needs.

    Raises ``RuntimeError`` via :func:`validate_state` if a mandatory body
    is missing. Optional bodies (``captions.html``, etc.) are omitted from
    the result when absent.
    """
    validate_state(state)

    compose = state.get("compose") or {}
    out: dict[str, str] = {
        "DESIGN.md": _pluck(state, ("compose", "design", "design_md")),
        ".hyperframes/expanded-prompt.md": _pluck(
            state, ("compose", "expansion", "expanded_prompt")
        ),
        "index.html": _pluck(state, ("compose", "index_html")),
    }
    scenes = state.get("scenes") or {}
    for scene_id, scene in sorted(scenes.items()):
        out[f"compositions/{scene_id}.html"] = scene["html"]
    captions_html = (compose.get("captions") or {}).get("html")
    if isinstance(captions_html, str) and captions_html:
        out["captions.html"] = captions_html
    return out
