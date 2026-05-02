from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._types import AuthError, NodeRequirements, RateLimitError
from edit_episode_graph.backends.codex import CodexBackend


class _R(BaseModel):
    slips: list[dict]


def _fake(stdout="", stderr="", rc=0):
    return lambda cmd, **kw: SimpleNamespace(stdout=stdout, stderr=stderr, returncode=rc)


def test_invoke_parses(fixtures_dir, monkeypatch):
    raw = (fixtures_dir / "codex_json_ok.json").read_text(encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _fake(stdout=raw))
    b = CodexBackend()
    res = b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=30, output_schema=_R)
    assert res.backend_used == "codex"
    assert res.model_used == "gpt-5-mini"
    assert res.structured is not None


def test_command_shape(monkeypatch, fixtures_dir):
    raw = (fixtures_dir / "codex_json_ok.json").read_text(encoding="utf-8")
    captured = {}

    def fake(cmd, **kw):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout=raw, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake)
    b = CodexBackend()
    b.invoke("hi", tier="smart", cwd=Path.cwd(), timeout_s=30, output_schema=None)
    cmd_str = " ".join(captured["cmd"])
    assert "exec" in cmd_str
    assert "--json" in cmd_str
    assert "gpt-5" in cmd_str


def test_auth_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake(stderr="please run `codex login`", rc=1))
    b = CodexBackend()
    with pytest.raises(AuthError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake(stderr="rate limit hit", rc=1))
    b = CodexBackend()
    with pytest.raises(RateLimitError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_supports():
    assert CodexBackend().supports(NodeRequirements(tier="cheap", needs_tools=True, backends=["codex"]))
