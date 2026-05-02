from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends._types import (
    AllBackendsExhausted,
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
)


class _Schema(BaseModel):
    n: int


class _StubBackend:
    def __init__(self, name: str, behavior):
        self.name = name
        self.capabilities = BackendCapabilities(name, has_tools=True, supports_streaming=True, max_concurrent=2)
        self._behavior = behavior     # callable(call_idx) -> raises or returns InvokeResult
        self.calls = 0

    def supports(self, req): return True

    def invoke(self, task, *, tier, cwd, timeout_s, output_schema, allowed_tools=None, model_override=None):
        self.calls += 1
        return self._behavior(self.calls)


def _ok():
    return InvokeResult(raw_text="{\"n\":1}", structured=_Schema(n=1), tokens_in=1,
                        tokens_out=1, wall_time_s=0.01, model_used="m", backend_used="x", tool_calls=[])


def test_first_backend_succeeds():
    a = _StubBackend("a", lambda i: _ok())
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "task", cwd=Path.cwd(), timeout_s=10, output_schema=_Schema)
    assert res.backend_used in ("x",)
    assert a.calls == 1 and b.calls == 0
    assert len(attempts) == 1 and attempts[0]["success"] is True


def test_auth_fail_advances_to_next_backend():
    def auth_fail(_): raise AuthError("nope")
    a = _StubBackend("a", auth_fail)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 1 and b.calls == 1
    assert attempts[0]["reason"] == "auth"
    assert attempts[1]["success"] is True


def test_schema_validation_retries_same_backend(monkeypatch):
    states = iter([
        SchemaValidationError("bad", "raw1"),
        SchemaValidationError("bad", "raw2"),
        _ok(),
    ])

    def behavior(_):
        nxt = next(states)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    a = _StubBackend("a", behavior)
    r = BackendRouter([a], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 3
    assert sum(1 for at in attempts if at.get("reason") == "schema") == 2


def test_schema_validation_exhausts_to_next(monkeypatch):
    a = _StubBackend("a", lambda i: (_ for _ in ()).throw(SchemaValidationError("bad", "r")))
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, _ = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                      "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 3 and b.calls == 1


def test_rate_limit_retries_once_then_advances(monkeypatch):
    sleeps = []
    monkeypatch.setattr("edit_episode_graph.backends._router.time.sleep", lambda s: sleeps.append(s))

    states = iter([RateLimitError("nope"), RateLimitError("still"), _ok()])

    def behavior(_):
        nxt = next(states)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    a = _StubBackend("a", behavior)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 2  # initial + one retry after sleep
    assert b.calls == 1
    assert sleeps == [30]


def test_timeout_advances():
    def boom(_): raise BackendTimeout("slow")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert attempts[0]["reason"] == "timeout"


def test_all_exhausted_raises():
    def boom(_): raise AuthError("x")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", boom)
    r = BackendRouter([a, b], BackendSemaphores({}))
    with pytest.raises(AllBackendsExhausted):
        r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                 "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)


def test_unsupported_backend_skipped():
    class _NoTools(_StubBackend):
        def __init__(self):
            super().__init__("a", lambda i: _ok())
            self.capabilities = BackendCapabilities("a", has_tools=False, supports_streaming=True, max_concurrent=1)
        def supports(self, req): return not req.needs_tools

    a = _NoTools()
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 0 and b.calls == 1
