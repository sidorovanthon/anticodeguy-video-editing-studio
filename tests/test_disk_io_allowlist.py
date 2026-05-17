"""Lint rule: structurally enforce the state-first artifact invariant (HOM-283).

Walks every ``.py`` under ``graph/src/edit_episode_graph/{nodes,gates}/`` with
``ast`` and flags any direct disk-I/O call site that is not (a) inside a
whole-file allowlisted module or (b) suppressed by a same-line
``# disk-io-allow: <reason>`` comment.

Pre-HOM-277 we accumulated 4-5 latent disk-vs-state contract violations that
only surfaced on the next fresh-tier prewarm weeks later. The invariant +
fresh-tier-gate (see CLAUDE.md §"Definition of done") prevents recurrence.

Flagged forms:

- Attribute call on any expression: ``.read_text``, ``.write_text``,
  ``.read_bytes``, ``.write_bytes``, ``.is_file``, ``.is_dir``, ``.exists``,
  ``.iterdir``, ``.mkdir``, ``.unlink``, ``.glob``.
- Bare-name call: ``open(...)``.

Whole-file allowlist — files where disk I/O is the *intended* purpose, or
which predate the state-first refactor and have a documented reason:

- ``nodes/p4_materialize_disk.py`` — canonical disk writer (HOM-239).
- ``nodes/_paths.py`` — pure path helpers (no I/O today, kept for future).
- ``nodes/preflight_canon.py`` — bare-repro sidecar persists its own state.
- ``nodes/_llm.py`` — brief template loader.
- ``gates/_base.py`` — CLI binary discovery (``shutil.which`` + sanity).
- Phase 3 nodes: ``p3_*.py``, ``glue_remap_transcript.py``,
  ``rehydrate_skip_phase3.py``, ``pickup.py``, ``isolate_audio.py`` — Phase
  3 reads/writes ``edit/*`` artifacts on disk by design (video-use canon).
- Class D / routing: ``_routing.py``, ``halt_llm_boundary.py`` — routing
  inspects disk-presence to decide phase entry.
- Runtime side-channel: ``studio_launch.py`` — Studio PID + log files.

Per-line escape: add ``# disk-io-allow: <reason>`` on the same line as the
call. One suppression per finding; the rationale ends up in `git blame` and
is read by reviewers.
"""
from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
NODES_DIR = REPO_ROOT / "graph" / "src" / "edit_episode_graph" / "nodes"
GATES_DIR = REPO_ROOT / "graph" / "src" / "edit_episode_graph" / "gates"

DISALLOWED_ATTRS = frozenset({
    "read_text",
    "write_text",
    "read_bytes",
    "write_bytes",
    "is_file",
    "is_dir",
    "exists",
    "iterdir",
    "mkdir",
    "unlink",
    "glob",
})
DISALLOWED_NAMES = frozenset({"open"})

# Whole-file allowlist (relative to NODES_DIR / GATES_DIR).
ALLOWLIST_NODES = frozenset({
    "p4_materialize_disk.py",
    "_paths.py",
    "preflight_canon.py",
    "_llm.py",
    # Phase 3 cluster — disk-bound by video-use canon.
    "p3_pre_scan.py",
    "p3_inventory.py",
    "p3_strategy.py",
    "p3_edl_select.py",
    "p3_render_segments.py",
    "p3_self_eval.py",
    "p3_persist_session.py",
    "p3_review_interrupt.py",
    "strategy_confirmed_interrupt.py",
    "edl_failure_interrupt.py",
    "eval_failure_interrupt.py",
    "glue_remap_transcript.py",
    "rehydrate_skip_phase3.py",
    "pickup.py",
    "isolate_audio.py",
    # Class D / routing.
    "_routing.py",
    "halt_llm_boundary.py",
    # Runtime side-channels.
    "studio_launch.py",
    # Class B canonical tmpdir staging (HOM-281) — by-design materialization
    # of an HF project to disk so puppeteer-driven CLIs can fetch sibling
    # assets by relative URL.
    "_materialize_tmpdir.py",
})

ALLOWLIST_GATES = frozenset({
    "_base.py",
})

ALLOW_COMMENT = "disk-io-allow"


class _DiskIOVisitor(ast.NodeVisitor):
    """AST visitor that flags disk-I/O call sites.

    Place the ``# disk-io-allow:`` comment on the same source line as the
    call's *start* (the receiver), not the method-name line — ``ast.Call.lineno``
    points at the receiver in chained expressions.
    """

    def __init__(self, source_lines: list[str]) -> None:
        self.source_lines = source_lines
        self.findings: list[tuple[int, str]] = []

    def _line_suppressed(self, lineno: int) -> bool:
        """Return True iff the source line carries a ``# disk-io-allow`` comment.

        Keyed on ``ast.Call.lineno``, which points at the call's *start* (the
        receiver in chained expressions). For multi-line chained calls, put the
        suppression comment on the receiver's line, not the method-name line.
        """
        if lineno < 1 or lineno > len(self.source_lines):
            return False
        line = self.source_lines[lineno - 1]
        # Comment text after `#`; tolerate `# disk-io-allow:` or
        # `# disk-io-allow <reason>`.
        hash_idx = line.find("#")
        if hash_idx < 0:
            return False
        return ALLOW_COMMENT in line[hash_idx:]

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 (ast API)
        func = node.func
        call_label: str | None = None
        if isinstance(func, ast.Attribute) and func.attr in DISALLOWED_ATTRS:
            call_label = f".{func.attr}"
        elif isinstance(func, ast.Name) and func.id in DISALLOWED_NAMES:
            call_label = func.id
        if call_label is not None and not self._line_suppressed(node.lineno):
            self.findings.append((node.lineno, call_label))
        self.generic_visit(node)


def _scan_file(path: pathlib.Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _DiskIOVisitor(source.splitlines())
    visitor.visit(tree)
    rel = path.relative_to(REPO_ROOT).as_posix()
    return [
        f"{rel}:{lineno}: disallowed disk I/O {call}"
        for lineno, call in visitor.findings
    ]


def test_disk_io_allowlist() -> None:
    """Fail if a non-allowlisted node/gate adds an un-suppressed disk-I/O call."""
    violations: list[str] = []
    for path in sorted(NODES_DIR.glob("*.py")):
        if path.name in ALLOWLIST_NODES:
            continue
        violations.extend(_scan_file(path))
    for path in sorted(GATES_DIR.glob("*.py")):
        if path.name in ALLOWLIST_GATES:
            continue
        violations.extend(_scan_file(path))

    assert not violations, (
        "Disallowed disk I/O in non-allowlisted node/gate. Either move the call "
        "to a state-channel hand-off, add a per-line `# disk-io-allow: <reason>` "
        "comment, or extend the whole-file allowlist in "
        "`tests/test_disk_io_allowlist.py` with a reviewer-justified rationale. "
        "Findings:\n  " + "\n  ".join(violations)
    )


def _scan_source(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    visitor = _DiskIOVisitor(source.splitlines())
    visitor.visit(tree)
    return visitor.findings


def test_visitor_self_test_negative_cases() -> None:
    """Guard against silent regressions in `_DiskIOVisitor` detection."""
    # 1. Bare Path(...).read_text() — must be reported.
    findings = _scan_source("import pathlib\npathlib.Path('x').read_text()\n")
    assert findings and findings[0][1] == ".read_text", findings

    # 2. Same call with a same-line `# disk-io-allow: <reason>` — suppressed.
    findings = _scan_source(
        "import pathlib\n"
        "pathlib.Path('x').read_text()  # disk-io-allow: test fixture\n"
    )
    assert findings == [], findings

    # 3. Bare-name `open(...)` — must be reported.
    findings = _scan_source("open('x')\n")
    assert findings and findings[0][1] == "open", findings
