"""Unit tests for p4_persist_session node and brief contract."""

from __future__ import annotations

from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_persist_session as node_module
from edit_episode_graph.nodes.p4_persist_session import (
    _phase4_gate_records,
    p4_persist_session_node,
)
from edit_episode_graph.schemas.p4_persist_session import PersistSessionOutput


def _ok_state(tmp_path, **overrides):
    # HOM-224: identity-only state — paths derive via `EpisodePaths(slug)`.
    # Tests must pin `HOMESTUDIO_PROJECT_ROOT=tmp_path` (via monkeypatch in
    # the calling test) so `EpisodePaths("demo")` resolves under tmp_path.
    # We pre-seed DESIGN.md / expanded-prompt.md / captions.html on disk so
    # the brief render context picks up their slug-derived locations.
    slug = "demo"
    episode_dir = tmp_path / "episodes" / slug
    hf_dir = episode_dir / "hyperframes"
    state_dir = hf_dir / ".hyperframes"
    hf_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    (hf_dir / "DESIGN.md").write_text("# DESIGN", encoding="utf-8")
    (state_dir / "expanded-prompt.md").write_text("# expanded", encoding="utf-8")
    (hf_dir / "captions.html").write_text("<div>captions</div>", encoding="utf-8")
    base = {
        "slug": slug,
        "compose": {
            "plan": {
                "beats": [
                    {"id": "b1", "title": "Hook", "duration_s": 3.0},
                    {"id": "b2", "title": "Reveal", "duration_s": 4.5},
                ],
            },
            "assemble": {
                # HOM-224: `index_html_path` write removed; `assembled_at`
                # is now an ISO timestamp.
                "assembled_at": "2026-05-10T12:00:00+00:00",
            },
            "beats": [
                {"beat_id": "b1", "scene_path": "compositions/b1.html", "status": "rendered"},
            ],
            # HOM-282: captions surfaced in the brief only when
            # `compose.captions.html` is populated in state (state-first
            # presence check; the disk file alone is no longer sufficient).
            "captions": {"html": "<div>captions</div>"},
        },
        "gate_results": [
            {"gate": "gate:design_ok", "passed": True},
            {"gate": "gate:plan_ok", "passed": True},
            {"gate": "gate:eval_ok", "passed": True},  # phase 3 — must NOT leak into phase 4 brief
        ],
    }
    base.update(overrides)
    return base


def _stub_router_returning(persisted_at: str, session_n: int) -> MagicMock:
    session_block = (
        f"## Session {session_n} — 2026-05-10\n\n"
        "- Phase 4 / HF composition session (stub).\n"
    )
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text=(
                f'{{"session_block":"{session_block!r}",'
                f'"persisted_at":"{persisted_at}","session_n":{session_n}}}'
            ),
            structured=PersistSessionOutput(
                session_block=session_block,
                persisted_at=persisted_at,
                session_n=session_n,
            ),
            tokens_in=180,
            tokens_out=24,
            wall_time_s=1.1,
            model_used="claude-haiku-4-5-20251001",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-haiku-4-5-20251001",
          "tokens_in": 180, "tokens_out": 24, "wall_time_s": 1.1, "ts": "now"}],
    )
    return router


def test_skips_when_no_slug():
    """HOM-224: identity is `slug`, not `episode_dir`."""
    update = p4_persist_session_node({}, router=MagicMock())
    assert update["compose"]["persist"]["skipped"] is True
    assert "slug" in update["compose"]["persist"]["skip_reason"]


def test_skips_when_assemble_skipped():
    state = {
        "slug": "demo",
        "compose": {"assemble": {"skipped": True, "skip_reason": "no scenes"}},
    }
    update = p4_persist_session_node(state, router=MagicMock())
    assert update["compose"]["persist"]["skipped"] is True
    assert "assemble skipped" in update["compose"]["persist"]["skip_reason"]


def test_skips_when_no_assembled_index():
    state = {
        "slug": "demo",
        "compose": {"assemble": {}},
    }
    update = p4_persist_session_node(state, router=MagicMock())
    assert update["compose"]["persist"]["skipped"] is True
    assert "assembled" in update["compose"]["persist"]["skip_reason"]


def test_phase4_gate_filter_excludes_phase3_records():
    state = {
        "gate_results": [
            {"gate": "gate:edl_ok", "passed": True},
            {"gate": "gate:eval_ok", "passed": True},
            {"gate": "gate:plan_ok", "passed": True},
            {"gate": "gate:static_guard", "passed": True},
        ]
    }
    gates = _phase4_gate_records(state)
    names = {g["gate"] for g in gates}
    assert names == {"gate:plan_ok", "gate:static_guard"}


def test_runs_with_tools_and_embeds_phase4_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    target = "2026-05-10T12:00:00+00:00"  # HOM-224: ISO timestamp, not path
    router = _stub_router_returning(target, 2)
    state = _ok_state(tmp_path)

    update = p4_persist_session_node(state, router=router)

    assert update["compose"]["persist"]["session_n"] == 2
    # HOM-224: `persisted_at` is an ISO 8601 timestamp (runtime overwrite),
    # not a filesystem path. Validate the shape (parseable by `datetime`).
    from datetime import datetime
    persisted_at = update["compose"]["persist"]["persisted_at"]
    datetime.fromisoformat(persisted_at)  # raises if not ISO 8601
    assert update["compose"]["session_persisted"] is True
    assert update["llm_runs"][0]["node"] == "p4_persist_session"

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "cheap"
    assert req.needs_tools is True
    assert kwargs["allowed_tools"] == ["Read"]
    # Phase 4 inputs must appear in the rendered brief.
    assert "DESIGN.md" in task
    assert "expanded-prompt.md" in task
    assert "Hook" in task and "Reveal" in task
    assert "captions.html" in task
    assert "index.html" in task
    # Phase 3 gate must NOT leak into the rendered task.
    assert "gate:eval_ok" not in task
    # Phase 4 gates that exist in state must appear.
    assert "gate:design_ok" in task
    assert "gate:plan_ok" in task


def test_idempotent_increments_session_n_on_re_run(tmp_path, monkeypatch):
    """Re-running with a higher session_n response simulates the agent
    finding existing blocks in project.md and incrementing N. The node
    itself never overwrites — it just records what the agent reported."""
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    target = "2026-05-10T12:00:00+00:00"
    state = _ok_state(tmp_path)

    update1 = p4_persist_session_node(state, router=_stub_router_returning(target, 1))
    assert update1["compose"]["persist"]["session_n"] == 1

    update2 = p4_persist_session_node(state, router=_stub_router_returning(target, 2))
    assert update2["compose"]["persist"]["session_n"] == 2
    # HOM-224: `persisted_at` is overwritten with a fresh ISO 8601 timestamp
    # at runtime — successive runs produce different values (the
    # observation, "when", not the location, "where"). Both must parse
    # as ISO 8601.
    from datetime import datetime
    datetime.fromisoformat(update1["compose"]["persist"]["persisted_at"])
    datetime.fromisoformat(update2["compose"]["persist"]["persisted_at"])


def test_brief_references_canon_memory_section():
    brief = node_module._load_brief("p4_persist_session")
    assert "~/.claude/skills/video-use/SKILL.md" in brief
    assert '§"Memory' in brief
    assert "Return JSON only" in brief or '"persisted_at"' in brief


def test_brief_does_not_embed_canon_field_names():
    """Brief references canon, does not embed canonical bullet field names
    (`Strategy:`, `Decisions:`, `Reasoning log:`, `Outstanding:`). The
    sub-agent reads canon at call time."""
    brief = node_module._load_brief("p4_persist_session")
    forbidden = ["Decisions:", "Reasoning log:", "Outstanding:"]
    for marker in forbidden:
        assert marker not in brief, f"brief embeds canonical field marker: {marker}"


def test_brief_marks_phase4_distinct_from_phase3():
    """Both phases share project.md; the block must self-identify as Phase 4
    so a future reader (and the next session-numbering scan) can tell them
    apart even though the heading shape is identical."""
    brief = node_module._load_brief("p4_persist_session")
    assert "Phase 4" in brief


def test_render_ctx_reads_project_md_body_from_state_not_disk(tmp_path, monkeypatch):
    """HOM-282: `_render_ctx` inlines the prior project.md body from
    `state.session.project_md` (populated by `p4_materialize_disk_node`
    post-append), NOT from a disk read.

    Pin a project root where the on-disk project.md contains DIFFERENT
    bytes than the state channel — the brief must reflect the state
    body, proving the disk path is no longer load-bearing.
    """
    from edit_episode_graph.nodes.p4_persist_session import _render_ctx

    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    state = _ok_state(tmp_path)
    # Write a misleading body to disk to prove the function does NOT
    # read it.
    edit_dir = tmp_path / "episodes" / state["slug"] / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)
    (edit_dir / "project.md").write_text("# WRONG — disk read would pick this up\n", encoding="utf-8")

    canonical_body = "# project.md\n\n## Session 1 — 2026-05-10\n- ...\n"
    state["session"] = {"project_md": canonical_body}

    ctx = _render_ctx(state)
    assert ctx["project_md_body"] == canonical_body
    # Path is still surfaced for the brief's debug reference, but the
    # body is the state value, not the disk value.
    assert "project.md" in ctx["project_md_path"]


def test_render_ctx_empty_project_md_body_on_fresh_thread(tmp_path, monkeypatch):
    """HOM-282: with no `state.session` channel populated, the brief
    body is the empty string (sub-agent then knows N = 1).
    """
    from edit_episode_graph.nodes.p4_persist_session import _render_ctx

    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    state = _ok_state(tmp_path)
    # Even if a stale project.md exists on disk, no state channel = empty body.
    edit_dir = tmp_path / "episodes" / state["slug"] / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)
    (edit_dir / "project.md").write_text("# stale disk\n", encoding="utf-8")

    ctx = _render_ctx(state)
    assert ctx["project_md_body"] == ""


def test_render_ctx_captions_path_reads_from_state_not_disk(tmp_path, monkeypatch):
    """HOM-282 (Class A leftover): `captions_block_path` is surfaced
    only when `compose.captions.html` is populated in state, NOT based
    on a disk `is_file()` probe."""
    from edit_episode_graph.nodes.p4_persist_session import _render_ctx

    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    state = _ok_state(tmp_path)
    # The _ok_state fixture writes captions.html to disk; HOM-282 must
    # ignore the disk file and read state.
    state["compose"].pop("captions", None)
    ctx = _render_ctx(state)
    assert ctx["captions_block_path"] == "", (
        "without compose.captions.html in state, captions_block_path must be empty "
        "even though captions.html exists on disk (HOM-282 Class A)"
    )

    # Now populate state — path appears.
    state["compose"]["captions"] = {"html": "<div/>"}
    ctx = _render_ctx(state)
    assert ctx["captions_block_path"].endswith("captions.html"), (
        "with compose.captions.html populated, captions_block_path must surface"
    )
