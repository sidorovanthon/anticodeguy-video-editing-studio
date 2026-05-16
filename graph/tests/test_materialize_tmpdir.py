"""Unit tests for ``edit_episode_graph.nodes._materialize_tmpdir``.

HOM-281. Pins the shared body-bytes producer + transient tmpdir helper
contract: every state-channel artifact lands in the tmpdir, scaffold
ancillaries are copied from the canonical hf_dir, the in-run cache
returns the same path for the same fingerprint, and a state mutation
invalidates the cache.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.nodes._compose_materialization import (
    compose_bodies,
    upstream_skipped,
    validate_state,
)
from edit_episode_graph.nodes._materialize_tmpdir import (
    _ANCILLARY_RELPATHS,
    _clear_cache_for_tests,
    materialize_into_tmpdir,
    materialize_scaffold_tmpdir,
)


def _happy_state(slug: str = "demo") -> dict:
    return {
        "slug": slug,
        "compose": {
            "design": {"design_md": "# DESIGN\nbody"},
            "expansion": {"expanded_prompt": "# expanded\nbody"},
            "index_html": "<!doctype html><html><body>scenes here</body></html>",
            "captions": {"html": "<div class='captions'>cap</div>"},
            "scaffold": {"index_html": "<!doctype html><html></html>"},
        },
        "scenes": {
            "b1": {"html": "<section id='b1'>hook</section>"},
            "b2": {"html": "<section id='b2'>reveal</section>"},
        },
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the module-level tmpdir cache between tests."""
    _clear_cache_for_tests()
    yield
    _clear_cache_for_tests()


@pytest.fixture
def isolated_project_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    # Pre-create the canonical hf_dir and seed scaffold ancillary files
    # the way p4_scaffold would.
    hf_dir = tmp_path / "episodes" / "demo" / "hyperframes"
    hf_dir.mkdir(parents=True, exist_ok=True)
    (hf_dir / "package.json").write_text("{\"name\":\"demo\"}", encoding="utf-8")
    (hf_dir / "hyperframes.json").write_text("{}", encoding="utf-8")
    (hf_dir / "transcript.json").write_text("[]", encoding="utf-8")
    (hf_dir / "AGENTS.md").write_text("# agents", encoding="utf-8")
    (hf_dir / "CLAUDE.md").write_text("# claude", encoding="utf-8")
    (hf_dir / "final.mp4").write_bytes(b"\x00\x01")
    return tmp_path


# ---------------------------------------------------------------------------
# _compose_materialization
# ---------------------------------------------------------------------------


def test_compose_bodies_returns_every_state_artifact():
    bodies = compose_bodies(_happy_state())
    assert bodies["DESIGN.md"] == "# DESIGN\nbody"
    assert bodies[".hyperframes/expanded-prompt.md"] == "# expanded\nbody"
    assert bodies["index.html"].startswith("<!doctype html>")
    assert bodies["captions.html"].startswith("<div")
    assert bodies["compositions/b1.html"] == "<section id='b1'>hook</section>"
    assert bodies["compositions/b2.html"] == "<section id='b2'>reveal</section>"


def test_compose_bodies_omits_captions_when_absent():
    state = _happy_state()
    state["compose"]["captions"] = {}
    bodies = compose_bodies(state)
    assert "captions.html" not in bodies


def test_validate_state_raises_on_missing_design_md():
    state = _happy_state()
    state["compose"]["design"]["design_md"] = ""
    with pytest.raises(RuntimeError, match="design_md"):
        validate_state(state)


def test_validate_state_raises_on_empty_scenes():
    state = _happy_state()
    state["scenes"] = {}
    with pytest.raises(RuntimeError, match="scenes"):
        validate_state(state)


def test_upstream_skipped_detects_assemble_skip():
    state = _happy_state()
    state["compose"]["assemble"] = {"skipped": True, "skip_reason": "no beats"}
    skipped, reason = upstream_skipped(state["compose"])
    assert skipped
    assert "no beats" in reason


# ---------------------------------------------------------------------------
# materialize_into_tmpdir
# ---------------------------------------------------------------------------


def test_materialize_writes_all_bodies_to_tmpdir(isolated_project_root):
    state = _happy_state()
    target = materialize_into_tmpdir(state, slug="demo")
    assert target.is_dir()
    assert (target / "DESIGN.md").read_text(encoding="utf-8") == "# DESIGN\nbody"
    assert (target / ".hyperframes" / "expanded-prompt.md").is_file()
    assert (target / "index.html").read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (target / "captions.html").is_file()
    assert (target / "compositions" / "b1.html").is_file()
    assert (target / "compositions" / "b2.html").is_file()


def test_materialize_copies_ancillary_from_canonical_hf_dir(isolated_project_root):
    target = materialize_into_tmpdir(_happy_state(), slug="demo")
    for rel in _ANCILLARY_RELPATHS:
        if rel == "meta.json":
            # not seeded in this fixture
            continue
        src = isolated_project_root / "episodes" / "demo" / "hyperframes" / rel
        dst = target / rel
        if src.is_file():
            assert dst.is_file(), f"ancillary {rel} not copied"
            assert dst.read_bytes() == src.read_bytes()


def test_materialize_skips_missing_ancillary(isolated_project_root):
    # No final.mp4 present.
    (isolated_project_root / "episodes" / "demo" / "hyperframes" / "final.mp4").unlink()
    target = materialize_into_tmpdir(_happy_state(), slug="demo")
    assert not (target / "final.mp4").exists()
    # Other ancillaries still copied.
    assert (target / "package.json").is_file()


def test_materialize_falls_back_to_state_slug(isolated_project_root):
    state = _happy_state()
    # Don't pass slug=, force fallback to state["slug"].
    target = materialize_into_tmpdir(state)
    assert (target / "index.html").is_file()


def test_materialize_raises_without_slug(isolated_project_root):
    state = _happy_state()
    state.pop("slug")
    with pytest.raises(RuntimeError, match="slug"):
        materialize_into_tmpdir(state)


def test_materialize_raises_when_upstream_skipped(isolated_project_root):
    state = _happy_state()
    state["compose"]["assemble"] = {"skipped": True, "skip_reason": "no beats"}
    with pytest.raises(RuntimeError, match="cannot materialize a skipped run"):
        materialize_into_tmpdir(state, slug="demo")


def test_materialize_propagates_validation_failure(isolated_project_root):
    state = _happy_state()
    state["compose"]["design"]["design_md"] = ""
    with pytest.raises(RuntimeError, match="design_md"):
        materialize_into_tmpdir(state, slug="demo")


# ---------------------------------------------------------------------------
# In-run cache behaviour
# ---------------------------------------------------------------------------


def test_cache_returns_same_dir_for_identical_state(isolated_project_root):
    state = _happy_state()
    a = materialize_into_tmpdir(state, slug="demo")
    b = materialize_into_tmpdir(state, slug="demo")
    assert a == b
    # The dir should not have been rewritten between calls (proven by
    # path equality — the helper would have created a fresh
    # ``tempfile.mkdtemp`` if the cache had missed).


def test_cache_invalidates_when_state_changes(isolated_project_root):
    state = _happy_state()
    first = materialize_into_tmpdir(state, slug="demo")
    state["compose"]["index_html"] = "<!doctype html><html><body>new</body></html>"
    second = materialize_into_tmpdir(state, slug="demo")
    assert first != second
    assert (second / "index.html").read_text(encoding="utf-8").endswith("new</body></html>")


def test_cache_invalidates_when_ancillary_changes(isolated_project_root):
    """Ancillary fingerprint mixes size+mtime — rewriting a scaffold file
    must produce a different tmpdir on the next call."""
    import time
    state = _happy_state()
    first = materialize_into_tmpdir(state, slug="demo")
    # Touch package.json to change mtime and content.
    pkg = isolated_project_root / "episodes" / "demo" / "hyperframes" / "package.json"
    time.sleep(0.01)
    pkg.write_text("{\"name\":\"demo\",\"version\":\"1\"}", encoding="utf-8")
    second = materialize_into_tmpdir(state, slug="demo")
    assert first != second


# ---------------------------------------------------------------------------
# materialize_scaffold_tmpdir (partial — used by p4_catalog_scan)
# ---------------------------------------------------------------------------


def test_scaffold_variant_works_without_phase4_bodies(isolated_project_root):
    """At p4_catalog_scan time, only scaffold has run; DESIGN/expansion/
    scenes are absent. The scaffold variant must succeed anyway and
    copy ancillaries from disk."""
    state = {
        "slug": "demo",
        "compose": {
            "scaffold": {"index_html": "<!doctype html><html></html>"},
        },
    }
    target = materialize_scaffold_tmpdir(state, slug="demo")
    assert target.is_dir()
    assert (target / "index.html").is_file()
    assert (target / "package.json").is_file()
    # Phase-4 artifacts must NOT appear in a scaffold-mode dir.
    assert not (target / "DESIGN.md").exists()
    assert not (target / "compositions").exists()


def test_scaffold_variant_distinct_cache_from_full_variant(isolated_project_root):
    """Same slug, both variants called — must return distinct dirs."""
    state = _happy_state()
    full = materialize_into_tmpdir(state, slug="demo")
    scaffold = materialize_scaffold_tmpdir(state, slug="demo")
    assert full != scaffold
    # And scaffold doesn't have phase-4 artifacts even though state did.
    assert not (scaffold / "DESIGN.md").exists()


def test_scaffold_variant_raises_without_slug(isolated_project_root):
    with pytest.raises(RuntimeError, match="slug"):
        materialize_scaffold_tmpdir({})
