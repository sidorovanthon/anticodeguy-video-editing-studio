from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends._types import (
    AllBackendsExhausted,
    AuthError,
    BackendCLIError,
    BackendCapabilities,
    BackendError,
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
    assert attempts[0]["exc_type"] == "AuthError"
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


def test_programmer_error_propagates_not_failed_over():
    """AttributeError / TypeError from a parser regression must surface, not burn attempts."""
    def boom(_): raise AttributeError("'NoneType' object has no attribute 'foo'")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    with pytest.raises(AttributeError):
        r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                 "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 1 and b.calls == 0


def test_backend_cli_error_records_returncode_and_stderr_preview():
    long_stderr = "x" * 500
    def boom(_): raise BackendCLIError(returncode=42, stderr=long_stderr)
    a = _StubBackend("a", boom)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert attempts[0]["reason"] == "cli_error"
    assert attempts[0]["returncode"] == 42
    assert attempts[0]["stderr_preview"] == "x" * 200
    assert attempts[0]["exc_type"] == "BackendCLIError"
    assert b.calls == 1


def test_other_backend_error_records_exc_type():
    """Unmapped BackendError subclass falls under 'other' but records exc_type."""
    class WeirdBackendError(BackendError):
        pass
    def boom(_): raise WeirdBackendError("something odd")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert attempts[0]["reason"] == "other"
    assert attempts[0]["exc_type"] == "WeirdBackendError"


def test_oserror_caught_as_other():
    """OSError (e.g. subprocess spawn failure) is classified, not propagated."""
    def boom(_): raise OSError("no such executable")
    a = _StubBackend("a", boom)
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert attempts[0]["reason"] == "other"
    assert attempts[0]["exc_type"] == "OSError"
    assert b.calls == 1


def test_unsupported_backend_skipped():
    class _NoTools(_StubBackend):
        def __init__(self):
            super().__init__("a", lambda i: _ok())
            self.capabilities = BackendCapabilities("a", has_tools=False, supports_streaming=True, max_concurrent=1)
        def supports(self, req): return not req.needs_tools

    a = _NoTools()
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["a", "b"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 0 and b.calls == 1
    # Per spec §7.4: unsupported attempts must be recorded with reason=unsupported
    # so telemetry surfaces *why* a preferred backend was skipped (not just success rates).
    assert attempts[0] == {"backend": "a", "success": False, "reason": "unsupported",
                           "ts": attempts[0]["ts"]}
    assert attempts[1]["backend"] == "b" and attempts[1]["success"] is True


def test_empty_preference_falls_back_to_all_registered_backends():
    """req.backends=[] (or None) → router uses every registered backend in
    insertion order. Guards against future refactors that might treat empty
    list as 'none allowed'."""
    a = _StubBackend("a", lambda i: (_ for _ in ()).throw(AuthError("nope")))
    b = _StubBackend("b", lambda i: _ok())
    r = BackendRouter([a, b], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, []),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert a.calls == 1 and b.calls == 1
    assert [at["backend"] for at in attempts] == ["a", "b"]


def test_unknown_backend_in_preference_recorded_as_unsupported():
    """Preference may name a backend the router doesn't know about (e.g.
    config.yaml has a typo). Should be recorded, not crash."""
    a = _StubBackend("a", lambda i: _ok())
    r = BackendRouter([a], BackendSemaphores({}))
    res, attempts = r.invoke(NodeRequirements("cheap", True, ["nonexistent", "a"]),
                             "t", cwd=Path.cwd(), timeout_s=5, output_schema=_Schema)
    assert attempts[0]["backend"] == "nonexistent"
    assert attempts[0]["reason"] == "unsupported"
    assert attempts[1]["backend"] == "a" and attempts[1]["success"] is True
