"""Brief snapshot helpers (HOM-183, spec §3 L0).

Renders an LLM node's Jinja brief through the production
``edit_episode_graph.nodes._llm._BRIEF_ENV`` environment and compares
the result against a committed text snapshot. PR diffs become the
review surface for canon-citation drift, accidental section drops, or
canon paraphrase smuggling — see CLAUDE.md §"Decomposition via
brief-references-canon".

Two flavours of comparison:

* ``assert_brief_snapshot`` — pytest-assertion form. On mismatch raises
  ``AssertionError`` with a unified diff. With pytest's
  ``--update-snapshots`` flag (registered in :mod:`tests.conftest`),
  silently overwrites the snapshot instead.
* ``render_brief`` — plain rendering, no I/O. Used by both the
  assertion helper and any future test that wants to inspect rendered
  output directly.

Snapshot files live at ``tests/snapshots/briefs/<node>.txt``. The file
encoding is UTF-8 LF; whatever the production Jinja env emits is what
gets pinned (``keep_trailing_newline=True`` is mirrored — same as
``_BRIEF_ENV``).
"""

from __future__ import annotations

import difflib
from pathlib import Path

# Reuse the *production* Jinja environment so any future change to it
# (custom filters, globals, autoescape) flows into the snapshots
# automatically — no separate fidelity to maintain.
from edit_episode_graph.nodes._llm import _BRIEF_ENV, _load_brief

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "tests" / "snapshots" / "briefs"


def _snapshot_path(node_name: str, snapshot_dir: Path | None = None) -> Path:
    return (snapshot_dir or SNAPSHOT_DIR) / f"{node_name}.txt"


def render_brief(node_name: str, context: dict) -> str:
    """Render ``briefs/<node_name>.j2`` with ``context`` via the prod env.

    Mirrors :meth:`edit_episode_graph.nodes._llm.LLMNode._invoke_with`
    (``_BRIEF_ENV.from_string(template).render(**ctx)``) so the bytes
    we snapshot are identical to what a real dispatch would produce.
    """
    template_text = _load_brief(node_name)
    return _BRIEF_ENV.from_string(template_text).render(**context)


def _update_requested(config) -> bool:
    """Read pytest's ``--update-snapshots`` flag if present.

    The option is registered conditionally in :mod:`tests.conftest`;
    if a non-pytest caller imports this module it will pass ``None``
    and we treat that as "do not update".
    """
    if config is None:
        return False
    try:
        return bool(config.getoption("--update-snapshots"))
    except (ValueError, AttributeError):
        return False


def assert_brief_snapshot(
    node_name: str,
    rendered: str,
    *,
    pytestconfig=None,
    snapshot_dir: Path | None = None,
) -> None:
    """Compare ``rendered`` to the on-disk snapshot.

    On mismatch raises ``AssertionError`` with a unified diff suitable
    for pytest's diff renderer. When ``--update-snapshots`` is set,
    overwrites the file and returns silently. Snapshot files are
    written/read as UTF-8 LF text.
    """
    path = _snapshot_path(node_name, snapshot_dir)

    if _update_requested(pytestconfig):
        path.parent.mkdir(parents=True, exist_ok=True)
        # newline="" preserves whatever the renderer emitted (Jinja env
        # uses keep_trailing_newline=True; templates use LF). Combined
        # with explicit utf-8 this guarantees stable round-trip on
        # Windows (no implicit CRLF translation).
        path.write_text(rendered, encoding="utf-8", newline="")
        return

    if not path.exists():
        raise AssertionError(
            f"snapshot missing for node {node_name!r} at {path}; "
            "run pytest with --update-snapshots to create it"
        )

    expected = path.read_text(encoding="utf-8")
    if expected == rendered:
        return

    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile=f"snapshot:{node_name}.txt",
            tofile=f"rendered:{node_name}",
            n=3,
        )
    )
    raise AssertionError(
        f"brief snapshot mismatch for node {node_name!r}.\n"
        f"To accept the new output, re-run with --update-snapshots.\n"
        f"Reviewer note: a snapshot diff is a flag to verify the "
        f"canon-references-not-embeds rule (CLAUDE.md §\"Decomposition "
        f"via brief-references-canon\") was not violated.\n\n"
        f"{diff}"
    )
