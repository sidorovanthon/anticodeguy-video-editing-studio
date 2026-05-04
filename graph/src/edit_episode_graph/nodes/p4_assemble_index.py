"""p4_assemble_index node — assemble root composition from beats + captions block.

Deterministic class-1 node. Reads:
  - `compose.beats[]`              — per-beat artifacts produced by the beat
    fan-out (future ticket); each entry has `name` and `html_path`.
  - `compose.captions_block_path`  — captions block produced by the captions
    node (future ticket); inlined alongside beats.
  - `compose.index_html_path`      — root index.html produced by `p4_scaffold`
    (we patch in place rather than rewriting from scratch so the scaffold's
    viewport, video+audio pair, and transcript wiring all carry through).

Writes the patched root index.html. State delta updates the path (no-op if
unchanged) and records the assembled beat names for observability.

Canon (`~/.agents/skills/hyperframes/SKILL.md` §"Composition Structure"):
the root composition is a STANDALONE composition — its `data-composition-id`
div sits directly in `<body>`, NOT wrapped in `<template>`. Sub-comp loading
via `<template>` + `data-composition-src` would be the canonical way to
reference each beat as its own composition, but HF 0.4.41's loader produces
black renders / 0 elements with that pattern (memory
`feedback_hf_subcomp_loader_data_composition_src`,
`feedback_hf_compositions_cli_template_zero_elements`, upstream #589).
Until #589 lands, beats are inlined directly into the root composition
body — the canon is honored at the root level, the workaround is the
inline-instead-of-sub-comp choice for beat content.

Skips when beats are missing (the future fan-out node hasn't populated
state yet) — emits a `compose.assemble.skipped=True` delta with a reason
so `halt_llm_boundary` can surface why nothing was assembled.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


_BEAT_INJECTION_MARKER = "<!-- p4_assemble_index: beats -->"
_CAPTIONS_INJECTION_MARKER = "<!-- p4_assemble_index: captions -->"
_END_INJECTION_MARKER = "<!-- p4_assemble_index: end -->"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {
        "errors": [
            {"node": "p4_assemble_index", "message": message, "timestamp": _now()},
        ]
    }


def _skip(reason: str) -> dict:
    return {
        "compose": {
            "assemble": {"skipped": True, "skip_reason": reason},
        },
    }


def _strip_existing_injection(html: str) -> str:
    """Remove a previously-injected beats/captions block so re-runs are idempotent.

    Two cases handled:
      1. Complete injection (begin + end markers) — the normal happy path.
         Strip everything from begin to end, inclusive.
      2. Partial injection (begin marker, no end marker) — possible if a
         prior `write_text` was interrupted mid-write. We can't recover the
         pre-injection content, but we CAN clear from the begin marker to
         end-of-string so a fresh injection isn't doubled up. (Atomic
         replace on the full write avoids creating this state in the first
         place; this is belt-and-suspenders.)
    """
    complete = re.compile(
        re.escape(_BEAT_INJECTION_MARKER)
        + r".*?"
        + re.escape(_END_INJECTION_MARKER),
        flags=re.DOTALL,
    )
    cleaned = complete.sub("", html)
    if _BEAT_INJECTION_MARKER in cleaned:
        # Partial / unterminated injection — drop from the begin marker to EOF.
        cleaned = cleaned.split(_BEAT_INJECTION_MARKER, 1)[0]
    return cleaned


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically via tmp + os.replace.

    Prevents the partial-injection state described in `_strip_existing_injection`:
    on crash mid-write, the original file is preserved untouched rather than
    left half-written.
    """
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def assemble_html(
    *,
    root_html: str,
    beat_html_fragments: list[tuple[str, str]],
    captions_html: str | None,
) -> str:
    """Inject beat fragments + optional captions block before `</body>`.

    Pure function so unit tests can drive it without touching disk.

    Args:
        root_html: scaffolded index.html as written by p4_scaffold.
        beat_html_fragments: list of (beat_name, html_fragment) pairs. Each
            fragment is inlined as-is; the caller is responsible for it
            being a valid `data-composition-id` block (or its inner content).
        captions_html: optional captions block HTML; injected after beats.

    Returns:
        Patched HTML string.
    """
    cleaned = _strip_existing_injection(root_html)
    pieces = [_BEAT_INJECTION_MARKER]
    for name, fragment in beat_html_fragments:
        pieces.append(f"<!-- beat: {name} -->")
        pieces.append(fragment.strip())
    if captions_html:
        pieces.append(_CAPTIONS_INJECTION_MARKER)
        pieces.append(captions_html.strip())
    pieces.append(_END_INJECTION_MARKER)
    injection = "\n".join(pieces) + "\n"

    if "</body>" in cleaned:
        return cleaned.replace("</body>", injection + "</body>", 1)
    # No </body> — append at end. (Scaffolded index.html always has one,
    # but this keeps the function total for tests / hand-edited inputs.)
    return cleaned + injection


def p4_assemble_index_node(state):
    compose = state.get("compose") or {}
    beats = compose.get("beats") or []
    if not beats:
        return _skip("no beats in state (per-beat fan-out has not run)")

    index_html_path = compose.get("index_html_path")
    if not index_html_path:
        return _error("compose.index_html_path missing (p4_scaffold must run first)")
    index_path = Path(index_html_path)
    if not index_path.is_file():
        return _error(f"root index.html not found at {index_path}")

    fragments: list[tuple[str, str]] = []
    for beat in beats:
        if not isinstance(beat, dict):
            return _error(f"unexpected beat entry type: {type(beat).__name__}")
        name = beat.get("name") or "unnamed"
        beat_html_path = beat.get("html_path")
        if not beat_html_path:
            return _error(f"beat {name!r} missing html_path")
        bp = Path(beat_html_path)
        if not bp.is_file():
            return _error(f"beat {name!r} html_path does not exist: {bp}")
        fragments.append((name, bp.read_text(encoding="utf-8")))

    captions_html: str | None = None
    captions_path_str = compose.get("captions_block_path")
    if captions_path_str:
        cp = Path(captions_path_str)
        if not cp.is_file():
            return _error(f"captions block path does not exist: {cp}")
        captions_html = cp.read_text(encoding="utf-8")

    root_html = index_path.read_text(encoding="utf-8")
    patched = assemble_html(
        root_html=root_html,
        beat_html_fragments=fragments,
        captions_html=captions_html,
    )
    if patched != root_html:
        _atomic_write_text(index_path, patched)

    return {
        "compose": {
            "index_html_path": str(index_path),
            "assemble": {
                "assembled_at": _now(),
                "beat_names": [name for name, _ in fragments],
                "captions_included": captions_html is not None,
            },
        },
    }
