"""Pure parsers for CLI stdout shapes.

These are the ONLY place that knows the exact wire format of each CLI's JSON
output. Backends call them and treat the result uniformly. Garbage / partial
lines are skipped silently — CLIs occasionally emit progress noise that isn't
load-bearing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ._types import ToolCall


@dataclass
class ParsedStream:
    assistant_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int | None = None
    tokens_out: int | None = None
    model_used: str = ""


def parse_claude_stream_json(stdout: str) -> ParsedStream:
    """Parse `claude -p --output-format stream-json` stdout."""
    out = ParsedStream(assistant_text="")
    pending_tools: dict[str, ToolCall] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        otype = obj.get("type")
        if otype == "system" and obj.get("subtype") == "init":
            out.model_used = obj.get("model", out.model_used)
        elif otype == "assistant":
            for block in (obj.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    tc = ToolCall(
                        name=block.get("name", ""),
                        input=block.get("input") or {},
                        output_preview="",
                    )
                    pending_tools[block.get("id", "")] = tc
                    out.tool_calls.append(tc)
        elif otype == "user":
            for block in (obj.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_result":
                    tc = pending_tools.get(block.get("tool_use_id", ""))
                    if tc is not None:
                        content = block.get("content") or ""
                        if isinstance(content, list):
                            content = " ".join(str(c) for c in content)
                        idx = out.tool_calls.index(tc)
                        out.tool_calls[idx] = ToolCall(
                            name=tc.name,
                            input=tc.input,
                            output_preview=str(content)[:200],
                        )
        elif otype == "result":
            out.assistant_text = obj.get("result", out.assistant_text) or ""
            usage = obj.get("usage") or {}
            out.tokens_in = usage.get("input_tokens")
            out.tokens_out = usage.get("output_tokens")
            if "model" in obj:
                out.model_used = obj["model"]
    return out


def parse_codex_json(stdout: str) -> ParsedStream:
    """Parse `codex exec --json` stdout (single JSON envelope)."""
    obj = json.loads(stdout)
    out = ParsedStream(
        assistant_text="",
        model_used=obj.get("model", ""),
    )
    usage = obj.get("usage") or {}
    out.tokens_in = usage.get("input_tokens")
    out.tokens_out = usage.get("output_tokens")
    pending_tools: dict[str, ToolCall] = {}
    for msg in obj.get("messages") or []:
        role = msg.get("role")
        if role == "assistant":
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                try:
                    inp = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    inp = {"_raw": fn.get("arguments", "")}
                call = ToolCall(name=fn.get("name", ""), input=inp, output_preview="")
                pending_tools[tc.get("id", "")] = call
                out.tool_calls.append(call)
            content = msg.get("content")
            if isinstance(content, str) and content:
                out.assistant_text = content
        elif role == "tool":
            tc = pending_tools.get(msg.get("tool_call_id", ""))
            if tc is not None:
                idx = out.tool_calls.index(tc)
                out.tool_calls[idx] = ToolCall(
                    name=tc.name,
                    input=tc.input,
                    output_preview=str(msg.get("content", ""))[:200],
                )
    return out
