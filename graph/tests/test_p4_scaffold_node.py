"""Unit tests for p4_scaffold node — HOM-280 body-into-state cutover.

The full subprocess (npx hyperframes init) is not exercised here — that's
covered by `scripts/scaffold_hyperframes.py`'s own integration tests and
by the fixture-replay smoke. This module pins the body-hoist contract
(`compose.scaffold.index_html` populated from the disk file post-
subprocess) and the cache-key invariants.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from edit_episode_graph.nodes import p4_scaffold as p4_scaffold_mod
from edit_episode_graph.nodes.p4_scaffold import p4_scaffold_node


def _fake_run(stdout: str, returncode: int = 0):
    """Build a CompletedProcess-like stub."""

    class _R:
        def __init__(self):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    return _R()


def test_node_hoists_index_html_body_into_state(tmp_path, monkeypatch):
    """HOM-280 acceptance: after the subprocess returns, the body of
    `<hf>/index.html` lives at `compose.scaffold.index_html`."""
    slug = "test-slug"
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    hf_dir = tmp_path / "episodes" / slug / "hyperframes"
    hf_dir.mkdir(parents=True)
    body = "<!doctype html><html><body>scaffolded</body></html>"
    (hf_dir / "index.html").write_text(body, encoding="utf-8")

    with patch.object(
        p4_scaffold_mod,
        "subprocess",
        autospec=True,
    ) as fake_sub:
        fake_sub.run.return_value = _fake_run(
            json.dumps({"hyperframes_dir": str(hf_dir)})
        )
        update = p4_scaffold_node({"slug": slug, "episode_dir": str(tmp_path / "episodes" / slug)})

    assert "errors" not in update, update.get("errors")
    scaffold = update["compose"]["scaffold"]
    assert scaffold["index_html"] == body
    assert scaffold["scaffolded_at"].startswith("20")  # ISO timestamp
    assert any("scaffold complete" in n for n in update["notices"])


def test_node_errors_when_index_html_unreadable(tmp_path, monkeypatch):
    """If the subprocess succeeds but the file is missing (shouldn't
    happen in practice; defensive), the node surfaces a clear error
    rather than silently emitting an empty body."""
    slug = "test-slug-missing"
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    hf_dir = tmp_path / "episodes" / slug / "hyperframes"
    hf_dir.mkdir(parents=True)
    # Note: NO index.html written.

    with patch.object(
        p4_scaffold_mod,
        "subprocess",
        autospec=True,
    ) as fake_sub:
        fake_sub.run.return_value = _fake_run(
            json.dumps({"hyperframes_dir": str(hf_dir)})
        )
        update = p4_scaffold_node({"slug": slug, "episode_dir": str(tmp_path / "episodes" / slug)})

    assert "errors" in update
    msg = update["errors"][0]["message"]
    assert "failed to read" in msg.lower() or "no such file" in msg.lower()


def test_node_propagates_subprocess_failure(tmp_path, monkeypatch):
    """A non-zero subprocess exit surfaces as a graph error with combined
    stdout/stderr, no body hoist attempted."""
    slug = "test-slug-fail"
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))

    class _R:
        returncode = 1
        stdout = "boom out"
        stderr = "boom err"

    with patch.object(
        p4_scaffold_mod,
        "subprocess",
        autospec=True,
    ) as fake_sub:
        fake_sub.run.return_value = _R()
        update = p4_scaffold_node({"slug": slug, "episode_dir": str(tmp_path / "episodes" / slug)})

    assert "errors" in update
    assert "compose" not in update or "scaffold" not in update.get("compose", {})
    msg = update["errors"][0]["message"]
    assert "boom" in msg


# HOM-280 fingerprint invariants live under `tests/test_fingerprint_invalidation.py`
# (root tests/ tree, alongside the `tests/_helpers/fingerprint_assertions.py`
# registry they consume). p4_scaffold is a deterministic node (make_key) —
# same exemption from CREATIVE_NODES as gate_animation_map.
