from edit_episode_graph.backends._stream_parsers import (
    parse_claude_stream_json,
    parse_codex_json,
)


def test_parse_claude_stream_json(fixtures_dir):
    raw = (fixtures_dir / "claude_stream_ok.jsonl").read_text(encoding="utf-8")
    parsed = parse_claude_stream_json(raw)
    assert "slips" in parsed.assistant_text
    assert parsed.tokens_in == 120
    assert parsed.tokens_out == 40
    assert parsed.model_used == "claude-sonnet-4-6"
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "Read"
    assert parsed.tool_calls[0].input == {"file_path": "/tmp/takes_packed.md"}


def test_parse_codex_json(fixtures_dir):
    raw = (fixtures_dir / "codex_json_ok.json").read_text(encoding="utf-8")
    parsed = parse_codex_json(raw)
    assert "slips" in parsed.assistant_text
    assert parsed.tokens_in == 100
    assert parsed.tokens_out == 30
    assert parsed.model_used == "gpt-5-mini"
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "Read"


def test_claude_stream_garbage_lines_skipped():
    raw = "not-json\n" + '{"type":"result","subtype":"success","session_id":"x","model":"claude-sonnet-4-6","usage":{"input_tokens":1,"output_tokens":1},"result":"hi"}\n'
    parsed = parse_claude_stream_json(raw)
    assert parsed.assistant_text == "hi"
