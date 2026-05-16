"""ClaudeCodeBackend stdin regression (HOM-275-equivalent).

The Windows `CreateProcessW` API rejects argv whose combined length exceeds
~32k characters with `[WinError 206] The filename or extension is too long`.
State-first Phase 4 briefs (p4_plan, p4_dispatch_beats) inline DESIGN.md,
EDL, and transcript bodies and routinely cross that line, so we must pipe
the prompt to the claude CLI via stdin rather than embed it in argv.

These tests assert the wire shape, not the LLM behaviour:

  * the brief NEVER appears as a positional argv element,
  * the brief IS passed through `subprocess.run(..., input=...)`,
  * no single argv element exceeds a sanity cap (catches accidental regressions
    where the brief or some other large blob gets spliced into the command).

Linux/macOS argv limit is ~2 MB so the bug only surfaces on Windows, but
the stdin path is portable and is what the official Anthropic agent SDK uses.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from edit_episode_graph.backends.claude import ClaudeCodeBackend


def _stub_subprocess_run(monkeypatch, captured: dict, stdout: str = "") -> None:
    """Replace subprocess.run with a recorder that stashes args + kwargs."""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)


# A "minimum viable" stream-json transcript that parse_claude_stream_json
# accepts. Mirrors graph/tests/fixtures/claude_stream_ok.jsonl but avoids
# pulling the fixtures fixture into this file.
_OK_STREAM = (
    '{"type":"system","subtype":"init","session_id":"s","model":"claude-sonnet-4-6"}\n'
    '{"type":"assistant","message":{"content":[{"type":"text","text":"ok"}]}}\n'
    '{"type":"result","subtype":"success","model":"claude-sonnet-4-6",'
    '"usage":{"input_tokens":1,"output_tokens":1},"result":"ok"}\n'
)


def test_brief_passed_via_stdin_not_argv(monkeypatch):
    """The brief must travel through stdin (kwarg `input`), never as an argv element."""
    captured: dict = {}
    _stub_subprocess_run(monkeypatch, captured, stdout=_OK_STREAM)

    brief = "BRIEF-MARKER-" + ("x" * 40_000)  # >40k chars; well past WinError 206 cliff
    b = ClaudeCodeBackend()
    b.invoke(brief, tier="cheap", cwd=Path.cwd(), timeout_s=30, output_schema=None)

    cmd = captured["cmd"]
    kwargs = captured["kwargs"]

    # Brief travels via stdin.
    assert kwargs.get("input") == brief, "brief must be passed to subprocess.run via input=..."

    # And NOT via argv — no element of cmd is or contains the brief.
    for i, element in enumerate(cmd):
        assert element != brief, f"cmd[{i}] equals the full brief — argv leak"
        assert "BRIEF-MARKER-" not in element, (
            f"cmd[{i}]={element!r} contains the brief marker — partial argv leak"
        )

    # Sanity cap: no argv element should be remotely large. Catches regressions
    # where some other inline blob (transcript, DESIGN.md, etc.) gets spliced
    # into cmd by future "convenience" changes. 1000 chars is far above the
    # longest legitimate flag value (model name, comma-joined tools list).
    for i, element in enumerate(cmd):
        assert len(element) <= 1000, f"cmd[{i}] is {len(element)} chars — argv bloat regression"


def test_invocation_passes_utf8_encoding(monkeypatch):
    """Stdin path must use explicit UTF-8 encoding (Windows default is locale)."""
    captured: dict = {}
    _stub_subprocess_run(monkeypatch, captured, stdout=_OK_STREAM)

    b = ClaudeCodeBackend()
    b.invoke("привет — non-ASCII", tier="cheap", cwd=Path.cwd(), timeout_s=30, output_schema=None)

    kwargs = captured["kwargs"]
    assert kwargs.get("encoding") == "utf-8"
    assert kwargs.get("text") is True
    assert kwargs.get("capture_output") is True


def test_p_flag_is_bare_no_positional_prompt(monkeypatch):
    """`-p`/`--print` is a flag with NO positional value. The prompt comes from stdin.

    Per `claude --help`: `-p, --print` is a boolean flag; the prompt is a separate
    positional argument. Omitting the positional makes the CLI read from stdin
    (default `--input-format text`).
    """
    captured: dict = {}
    _stub_subprocess_run(monkeypatch, captured, stdout=_OK_STREAM)

    b = ClaudeCodeBackend()
    b.invoke("hello", tier="cheap", cwd=Path.cwd(), timeout_s=30, output_schema=None)

    cmd = captured["cmd"]
    # `-p` is present.
    assert "-p" in cmd
    # And the element immediately following `-p` is a flag (starts with `--`),
    # not a positional prompt value.
    p_idx = cmd.index("-p")
    assert p_idx + 1 < len(cmd), "cmd ends right after -p — missing follow-on flags"
    next_token = cmd[p_idx + 1]
    assert next_token.startswith("--"), (
        f"-p must be a bare flag; next argv element is {next_token!r}, "
        "which looks like a positional prompt value (argv-prompt regression)"
    )
