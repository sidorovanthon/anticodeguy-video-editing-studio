from edit_episode_graph.backends._types import (
    AllBackendsExhausted,
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    SchemaValidationError,
    ToolCall,
)


def test_capabilities_defaults():
    caps = BackendCapabilities(name="claude", has_tools=True, supports_streaming=True, max_concurrent=2)
    assert caps.name == "claude" and caps.max_concurrent == 2


def test_node_requirements_supports():
    req = NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"])
    caps = BackendCapabilities(name="claude", has_tools=True, supports_streaming=True, max_concurrent=2)
    assert req.satisfied_by(caps) is True
    no_tools = BackendCapabilities(name="x", has_tools=False, supports_streaming=False, max_concurrent=1)
    assert req.satisfied_by(no_tools) is False


def test_invoke_result_round_trip():
    r = InvokeResult(
        raw_text="hi",
        structured=None,
        tokens_in=10,
        tokens_out=2,
        wall_time_s=0.5,
        model_used="claude-sonnet-4-6",
        backend_used="claude",
        tool_calls=[ToolCall(name="Read", input={"path": "/x"}, output_preview="...")],
    )
    assert r.tool_calls[0].name == "Read"


def test_exception_hierarchy():
    assert issubclass(AuthError, Exception)
    assert issubclass(RateLimitError, Exception)
    assert issubclass(SchemaValidationError, Exception)
    assert issubclass(BackendTimeout, Exception)
    assert issubclass(AllBackendsExhausted, Exception)
