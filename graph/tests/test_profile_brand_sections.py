"""Verbatim snapshot tests for profile/brand markdown sections (HOM-114).

Loads each registered profile/brand anchor from the REAL shipped layers
(`profiles/talking-head-portrait`, `brand/anticodeguy`) and asserts the block
matches a committed snapshot. Regenerate intentionally (after editing a
house-style.md / brand.md heading or body) with:

    HOMESTUDIO_UPDATE_SNAPSHOTS=1 graph/.venv/Scripts/python.exe -m pytest \
        graph/tests/test_profile_brand_sections.py

then commit the snapshot diff in the same PR.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from edit_episode_graph import _canon_loader as cl
from edit_episode_graph._paths import repo_root

_SNAP_DIR = Path(__file__).parent / "snapshots" / "sections"
_PROFILE_ID = "talking-head-portrait"
_BRAND_ID = "anticodeguy"


def _profile_dir() -> Path:
    return repo_root() / "profiles" / _PROFILE_ID


def _brand_dir() -> Path:
    return repo_root() / "brand" / _BRAND_ID


def _cases():
    out = []
    for node, refs in cl.NODE_PROFILE_ANCHORS.items():
        for ref in refs:
            out.append(("profile", _PROFILE_ID, ref))
    for node, refs in cl.NODE_BRAND_ANCHORS.items():
        for ref in refs:
            out.append(("brand", _BRAND_ID, ref))
    seen, deduped = set(), []
    for layer, lid, ref in out:
        ident = (layer, lid, ref.key)
        if ident not in seen:
            seen.add(ident)
            deduped.append((layer, lid, ref))
    return deduped


@pytest.mark.parametrize(
    "layer,lid,ref",
    _cases(),
    ids=[f"{layer}-{lid}-{ref.key}" for layer, lid, ref in _cases()],
)
def test_section_snapshot(layer, lid, ref):
    layer_dir = _profile_dir() if layer == "profile" else _brand_dir()
    block = cl.load_section(
        layer_dir / ref.rel_path, ref.anchor, item=ref.item,
        min_anchor_text=cl._MIN_SECTION_ANCHOR_TEXT,
        source_label=f"{layer}:{lid}",
    )
    assert block.strip(), f"{layer}:{lid}:{ref.key} resolved empty"
    assert block.startswith(ref.anchor)

    snap = _SNAP_DIR / f"{layer}__{lid}__{ref.key}.md"
    if os.environ.get("HOMESTUDIO_UPDATE_SNAPSHOTS") == "1":
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(block, encoding="utf-8")
    assert snap.is_file(), f"missing snapshot {snap} (run with HOMESTUDIO_UPDATE_SNAPSHOTS=1)"
    assert block == snap.read_text(encoding="utf-8"), f"section drift vs {snap.name}"


def test_verify_profile_brand_anchors_resolves_shipped_layers():
    cl.verify_profile_brand_anchors()
