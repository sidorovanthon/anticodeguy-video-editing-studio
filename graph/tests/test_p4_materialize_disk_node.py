"""Unit tests for the p4_materialize_disk atomic writer.

Step D1 of HOM-230 (HOM-255): the materializer reads body fields from
state, asserts mandatory presence + per-scene html, then atomically
writes each artifact to the canonical EpisodePaths target. ``DESIGN.md``,
``.hyperframes/expanded-prompt.md``, ``compositions/<scene>.html``,
``captions.html``, ``index.html`` go through ``_atomic_write``
(write-temp + fsync + os.replace, idempotent on byte-match);
``edit/project.md`` goes through ``_append_session_block`` (substring-
skip + fsynced append).

These tests pin the read shape, cache-key determinism, atomicity (no
partial writes on malformed input), and idempotency (no double writes /
duplicate appends on re-run).

Spec: docs/superpowers/specs/2026-05-10-state-first-artifacts.md §6.3,
§"Step D1".
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from edit_episode_graph.nodes.p4_materialize_disk import (
    _append_session_block,
    _atomic_write,
    _cache_key,
    p4_materialize_disk_node,
)


def _happy_state(*, with_captions: bool = True, with_persist: bool = True) -> dict:
    state = {
        "slug": "demo",
        "compose": {
            "design": {"design_md": "# DESIGN\nbody"},
            "expansion": {"expanded_prompt": "# expanded\nbody"},
            "index_html": "<!doctype html><html><body>scenes here</body></html>",
            "captions": {},
            "persist": {},
        },
        "scenes": {
            "b1": {"html": "<section id='b1'>hook</section>"},
            "b2": {"html": "<section id='b2'>reveal</section>"},
        },
    }
    if with_captions:
        state["compose"]["captions"]["html"] = "<div class='captions'>...</div>"
    if with_persist:
        state["compose"]["persist"]["session_block"] = "## Session 1 — 2026-05-16\n\n- ...\n"
    return state


@pytest.fixture
def isolated_project_root(tmp_path, monkeypatch):
    """Pin EpisodePaths(...) under ``tmp_path`` for the duration of the test."""
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return tmp_path


# --- _atomic_write helpers -------------------------------------------------


def test_atomic_write_creates_file(tmp_path):
    target = tmp_path / "sub" / "a.txt"
    assert _atomic_write(target, "hello") is True
    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_idempotent_when_content_matches(tmp_path):
    target = tmp_path / "a.txt"
    assert _atomic_write(target, "hello") is True
    mtime_before = target.stat().st_mtime_ns
    # Sleep is unnecessary — idempotent skip never touches the file at
    # all, so mtime must be byte-identical regardless of granularity.
    assert _atomic_write(target, "hello") is False
    assert target.stat().st_mtime_ns == mtime_before
    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_overwrites_when_content_differs(tmp_path):
    target = tmp_path / "a.txt"
    _atomic_write(target, "v1")
    assert _atomic_write(target, "v2") is True
    assert target.read_text(encoding="utf-8") == "v2"


def test_atomic_write_no_partial_on_simulated_failure(tmp_path, monkeypatch):
    target = tmp_path / "a.txt"

    def boom(_src, _dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="simulated replace failure"):
        _atomic_write(target, "v1")
    # No `*.tmp` left behind (cleanup ran in the except handler).
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"tmp file not cleaned up: {leftovers}"
    # Final target either doesn't exist or wasn't created.
    assert not target.exists(), (
        "target file should not exist after a failed atomic write"
    )


# --- _append_session_block helpers ----------------------------------------


def test_append_session_block_skips_when_block_present(tmp_path):
    project_md = tmp_path / "project.md"
    block = "## Session 5 — 2026-05-16\n\nDecisions: ...\n"
    project_md.write_text(f"existing top\n\n{block}\nmore stuff\n", encoding="utf-8")
    mtime_before = project_md.stat().st_mtime_ns
    assert _append_session_block(project_md, block) is False
    assert project_md.stat().st_mtime_ns == mtime_before


def test_append_session_block_appends_when_missing(tmp_path):
    project_md = tmp_path / "project.md"
    block = "## Session 1 — 2026-05-16\n\nfresh\n"
    # Empty file path → no existing content, no separator.
    assert _append_session_block(project_md, block) is True
    assert project_md.read_text(encoding="utf-8") == block


def test_append_session_block_inserts_blank_line_separator(tmp_path):
    project_md = tmp_path / "project.md"
    project_md.write_text("prior content", encoding="utf-8")  # no trailing newline
    block = "## Session 2\n\nbody\n"
    assert _append_session_block(project_md, block) is True
    contents = project_md.read_text(encoding="utf-8")
    # Existing content with no trailing newline → newline + blank-line + block.
    assert contents == "prior content\n\n" + block


# --- happy path ------------------------------------------------------------


def test_happy_path_returns_materialized_at_timestamp(isolated_project_root):
    """Mandatory bodies present → materialized_at ISO timestamp +
    populated files_written. Atomic writes land under EpisodePaths."""
    update = p4_materialize_disk_node(_happy_state())
    materialize = update["compose"]["materialize"]
    datetime.fromisoformat(materialize["materialized_at"])
    assert "skipped" not in materialize
    files_written = materialize["files_written"]
    # 1 DESIGN.md + 1 expanded-prompt + 2 scenes + 1 captions + 1 index +
    # 1 project.md = 7 writes on the first run.
    assert len(files_written) == 7, f"expected 7 writes, got {files_written}"
    for f in files_written:
        assert Path(f).is_file(), f"materializer reported {f} written but file is missing"


def test_happy_path_with_optional_bodies_absent(isolated_project_root):
    """captions.html and persist.session_block are optional — both
    producers can legitimately skip. Materializer must succeed."""
    state = _happy_state(with_captions=False, with_persist=False)
    update = p4_materialize_disk_node(state)
    materialize = update["compose"]["materialize"]
    datetime.fromisoformat(materialize["materialized_at"])
    # 1 DESIGN.md + 1 expanded-prompt + 2 scenes + 1 index = 5 writes.
    assert len(materialize["files_written"]) == 5


def test_materialize_disk_writes_full_tree(isolated_project_root):
    """Happy-path call lands every artifact at its EpisodePaths target."""
    from edit_episode_graph._paths import EpisodePaths

    state = _happy_state()
    p4_materialize_disk_node(state)
    paths = EpisodePaths(state["slug"])

    assert paths.design_md_path.read_text(encoding="utf-8") == "# DESIGN\nbody"
    assert paths.expanded_prompt_path.read_text(encoding="utf-8") == "# expanded\nbody"
    assert paths.beat_fragment_path("b1").read_text(encoding="utf-8") == (
        "<section id='b1'>hook</section>"
    )
    assert paths.beat_fragment_path("b2").read_text(encoding="utf-8") == (
        "<section id='b2'>reveal</section>"
    )
    assert paths.captions_block_path.read_text(encoding="utf-8") == (
        "<div class='captions'>...</div>"
    )
    assert paths.index_html_path.read_text(encoding="utf-8") == (
        "<!doctype html><html><body>scenes here</body></html>"
    )
    project_md = paths.edit_dir / "project.md"
    assert project_md.read_text(encoding="utf-8") == (
        "## Session 1 — 2026-05-16\n\n- ...\n"
    )


def test_materialize_disk_idempotent_second_call(isolated_project_root):
    """Second call against the same state writes nothing (every file
    already matches on-disk content); session_block is a substring of
    existing project.md, so it's skipped too."""
    state = _happy_state()
    first = p4_materialize_disk_node(state)
    assert first["compose"]["materialize"]["files_written"], (
        "first call should write files"
    )
    second = p4_materialize_disk_node(state)
    files_written = second["compose"]["materialize"]["files_written"]
    assert files_written == [], (
        f"second call should be a pure no-op; got {files_written}"
    )


# --- atomicity --------------------------------------------------------------


def test_materialize_disk_atomicity_on_malformed_scene(isolated_project_root):
    """A scene without `html` raises RuntimeError BEFORE any file is
    written — validation runs to completion first."""
    from edit_episode_graph._paths import EpisodePaths

    state = _happy_state()
    state["scenes"]["b3"] = {}  # malformed — no `html`
    with pytest.raises(RuntimeError, match="b3"):
        p4_materialize_disk_node(state)
    paths = EpisodePaths(state["slug"])
    # None of the artifacts should have been written.
    leaked = []
    for p in (
        paths.design_md_path,
        paths.expanded_prompt_path,
        paths.beat_fragment_path("b1"),
        paths.beat_fragment_path("b2"),
        paths.captions_block_path,
        paths.index_html_path,
    ):
        if p.exists():
            leaked.append(str(p))
    assert leaked == [], (
        f"atomicity violation — partial writes after validation error: {leaked}"
    )


# --- mandatory missing ----------------------------------------------------


@pytest.mark.parametrize(
    "drop_path,field_name",
    [
        (("compose", "design", "design_md"), "compose.design.design_md"),
        (("compose", "expansion", "expanded_prompt"),
         "compose.expansion.expanded_prompt"),
        (("compose", "index_html"), "compose.index_html"),
    ],
)
def test_raises_on_missing_mandatory_field(drop_path, field_name):
    state = _happy_state()
    cur = state
    for k in drop_path[:-1]:
        cur = cur[k]
    cur.pop(drop_path[-1], None)
    with pytest.raises(RuntimeError) as exc:
        p4_materialize_disk_node(state)
    assert field_name in str(exc.value)


def test_raises_on_empty_scenes():
    state = _happy_state()
    state["scenes"] = {}
    with pytest.raises(RuntimeError) as exc:
        p4_materialize_disk_node(state)
    assert "scenes" in str(exc.value)


# --- skip propagation -----------------------------------------------------


@pytest.mark.parametrize(
    "skip_section,skip_reason_text",
    [
        ("assemble", "no scenes"),
        ("design", "design upstream broke"),
        ("expansion", "no DESIGN.md"),
    ],
)
def test_propagates_upstream_skip(skip_section, skip_reason_text):
    """Any upstream skip (assemble / design / expansion) → materializer
    returns its own skip block. No RuntimeError; no materialized_at."""
    state = {
        "slug": "demo",
        "compose": {
            skip_section: {"skipped": True, "skip_reason": skip_reason_text},
        },
    }
    update = p4_materialize_disk_node(state)
    materialize = update["compose"]["materialize"]
    assert materialize["skipped"] is True
    assert skip_section in materialize["skip_reason"]
    assert skip_reason_text in materialize["skip_reason"]
    assert "materialized_at" not in materialize


# --- cache-key determinism (spec §11 risk pin) ----------------------------


def test_cache_key_is_scene_order_independent():
    """Parallel ``Send`` completion order from p4_beat is
    non-deterministic; the materializer's cache key must hash scenes via
    sorted-by-key iteration so two state shapes that differ ONLY in
    scenes dict insertion order produce the same key. Spec §11 risk
    "Materializer cache key non-determinism"."""
    state_a = _happy_state()
    state_a["scenes"] = {
        "b1": {"html": "<section id='b1'>x</section>"},
        "b2": {"html": "<section id='b2'>y</section>"},
        "b3": {"html": "<section id='b3'>z</section>"},
    }
    state_b = _happy_state()
    state_b["scenes"] = {
        "b3": {"html": "<section id='b3'>z</section>"},
        "b1": {"html": "<section id='b1'>x</section>"},
        "b2": {"html": "<section id='b2'>y</section>"},
    }
    assert _cache_key(state_a) == _cache_key(state_b)


def test_cache_key_changes_when_scene_body_changes():
    state_a = _happy_state()
    state_b = _happy_state()
    state_b["scenes"]["b1"] = {"html": "<section id='b1'>DIFFERENT</section>"}
    assert _cache_key(state_a) != _cache_key(state_b)


def test_cache_key_changes_when_optional_body_appears():
    without = _happy_state(with_captions=False)
    with_caps = _happy_state(with_captions=True)
    assert _cache_key(without) != _cache_key(with_caps)
