"""Unit tests for p4_catalog_scan node — parser + missing-input branches.

The subprocess invocation itself is exercised by `smoke_hom121.py`
(real `npx hyperframes catalog --json`); these tests cover everything
that doesn't require spawning the CLI.
"""

from __future__ import annotations

import json

from edit_episode_graph.nodes.p4_catalog_scan import (
    p4_catalog_scan_node,
    parse_catalog_stdout,
)


def test_parse_splits_blocks_and_components():
    payload = json.dumps([
        {"name": "data-chart", "type": "block", "title": "Data Chart"},
        {"name": "grain", "type": "component", "title": "Grain Overlay"},
        {"name": "outro", "type": "block", "title": "Logo Outro"},
    ])
    report = parse_catalog_stdout(payload)
    assert [b["name"] for b in report["blocks"]] == ["data-chart", "outro"]
    assert [c["name"] for c in report["components"]] == ["grain"]
    assert "fetched_at" in report


def test_parse_ignores_unknown_types():
    payload = json.dumps([
        {"name": "x", "type": "block"},
        {"name": "y", "type": "future-category"},
        "not-a-dict",
    ])
    report = parse_catalog_stdout(payload)
    assert [b["name"] for b in report["blocks"]] == ["x"]
    assert report["components"] == []


def test_parse_rejects_non_array():
    import pytest
    with pytest.raises(ValueError):
        parse_catalog_stdout('{"blocks": []}')


def test_node_errors_when_slug_missing():
    """HOM-281: slug is now load-bearing — the node derives the
    subprocess cwd via ``materialize_scaffold_tmpdir(state, slug=...)``,
    which requires the slug. Previously the node looked up
    ``state['episode_dir']`` directly."""
    update = p4_catalog_scan_node({})
    assert update["errors"][0]["node"] == "p4_catalog_scan"
    assert "slug" in update["errors"][0]["message"]


def test_node_errors_when_materializer_raises(monkeypatch):
    """HOM-281: a materializer failure (e.g. scaffold ancillary read
    error) surfaces as a node error rather than crashing the run."""

    def boom(state, slug=None):
        raise RuntimeError("scaffold dir missing under episodes/demo")

    monkeypatch.setattr(
        "edit_episode_graph.nodes.p4_catalog_scan.materialize_scaffold_tmpdir",
        boom,
    )
    update = p4_catalog_scan_node({"slug": "demo"})
    assert update["errors"][0]["node"] == "p4_catalog_scan"
    assert "materialize_scaffold_tmpdir failed" in update["errors"][0]["message"]
