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


def test_node_errors_when_episode_dir_missing():
    update = p4_catalog_scan_node({})
    assert update["errors"][0]["node"] == "p4_catalog_scan"
    assert "episode_dir" in update["errors"][0]["message"]


def test_node_errors_when_hyperframes_dir_missing(tmp_path):
    update = p4_catalog_scan_node({"episode_dir": str(tmp_path)})
    assert update["errors"][0]["node"] == "p4_catalog_scan"
    assert "hyperframes/" in update["errors"][0]["message"]
