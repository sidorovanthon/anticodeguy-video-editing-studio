"""ClaudeCodeBackend tests — subprocess is monkey-patched.

We verify: command shape, stdout parsing, schema extraction, exception
mapping for stderr signals (auth, rate limit, timeout). No real CLI is
invoked.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._types import (
    AuthError,
    BackendTimeout,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
)
from edit_episode_graph.backends.claude import ClaudeCodeBackend


class _Slip(BaseModel):
    quote: str
    take_index: int | None = None
    reason: str


class _Report(BaseModel):
    slips: list[_Slip]


def _make_subprocess_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)
    return fake_run


def test_invoke_parses_structured(monkeypatch, fixtures_dir):
    raw = (fixtures_dir / "claude_stream_ok.jsonl").read_text(encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _make_subprocess_run(stdout=raw))
    b = ClaudeCodeBackend()
    res = b.invoke(
        "do thing",
        tier="cheap",
        cwd=Path.cwd(),
        timeout_s=60,
        output_schema=_Report,
    )
    assert res.backend_used == "claude"
    assert res.model_used == "claude-sonnet-4-6"
    assert isinstance(res.structured, _Report)
    assert res.structured.slips[0].quote == "hello world"
    assert len(res.tool_calls) == 1


def test_invoke_command_shape(monkeypatch, fixtures_dir):
    raw = (fixtures_dir / "claude_stream_ok.jsonl").read_text(encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(stdout=raw, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    b = ClaudeCodeBackend()
    b.invoke("hello", tier="smart", cwd=Path.cwd(), timeout_s=30, output_schema=None)

    cmd = captured["cmd"]
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    assert "-p" in cmd_str
    assert "stream-json" in cmd_str
    assert "claude-opus-4-7" in cmd_str   # smart tier
    assert captured["kwargs"]["timeout"] == 30


def test_auth_failure_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        _make_subprocess_run(stderr="Error: not authenticated. Run `claude login`.", returncode=1),
    )
    b = ClaudeCodeBackend()
    with pytest.raises(AuthError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_rate_limit_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        _make_subprocess_run(stderr="Error: rate limit reached, retry in 60s.", returncode=1),
    )
    b = ClaudeCodeBackend()
    with pytest.raises(RateLimitError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=None)


def test_timeout_raises(monkeypatch):
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))
    monkeypatch.setattr(subprocess, "run", boom)
    b = ClaudeCodeBackend()
    with pytest.raises(BackendTimeout):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=1, output_schema=None)


def test_schema_failure_raises(monkeypatch):
    bad = '{"type":"result","subtype":"success","model":"claude-sonnet-4-6","usage":{"input_tokens":1,"output_tokens":1},"result":"no json here"}\n'
    monkeypatch.setattr(subprocess, "run", _make_subprocess_run(stdout=bad))
    b = ClaudeCodeBackend()
    with pytest.raises(SchemaValidationError):
        b.invoke("x", tier="cheap", cwd=Path.cwd(), timeout_s=10, output_schema=_Report)


def test_supports_requires_tools_capability():
    b = ClaudeCodeBackend()
    assert b.supports(NodeRequirements(tier="cheap", needs_tools=True, backends=["claude"]))
    assert b.supports(NodeRequirements(tier="cheap", needs_tools=False, backends=[]))
