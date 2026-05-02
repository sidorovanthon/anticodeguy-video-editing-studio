"""ClaudeCodeBackend — `claude -p "<task>" --output-format stream-json --model <id>`.

Spec §7.2. Subscription auth only.

Windows note (§7.7 + memory `feedback_bundled_helper_path.md`): `claude.exe`
on Windows is a `.cmd` shim. We resolve it via `shutil.which("claude")` which
returns the absolute path the OS will actually exec; Python's subprocess can
launch a `.cmd` from an absolute path without `shell=True` on modern Windows
Python (3.11+).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel

from ._schema_extract import extract_structured
from ._stream_parsers import parse_claude_stream_json
from ._types import (
    AuthError,
    BackendCapabilities,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    Tier,
)

_MODEL_BY_TIER: dict[str, str] = {
    "cheap": "claude-sonnet-4-6",
    "smart": "claude-opus-4-7",
}

_AUTH_SIGNALS = ("not authenticated", "claude login", "unauthorized", "auth", "session expired")
_RATE_SIGNALS = ("rate limit", "quota", "too many requests")


class ClaudeCodeBackend:
    name = "claude"
    capabilities = BackendCapabilities(
        name="claude", has_tools=True, supports_streaming=True, max_concurrent=2,
    )

    def __init__(self, executable: str | None = None):
        self._executable = executable or shutil.which("claude") or "claude"

    def supports(self, req: NodeRequirements) -> bool:
        return self.capabilities.has_tools or not req.needs_tools

    def invoke(
        self,
        task: str,
        *,
        tier: Tier,
        cwd: Path,
        timeout_s: int,
        output_schema: type[BaseModel] | None,
        allowed_tools: list[str] | None = None,
        model_override: str | None = None,
    ) -> InvokeResult:
        model = model_override or _MODEL_BY_TIER[tier]
        cmd = [
            self._executable,
            "-p", task,
            "--output-format", "stream-json",
            "--verbose",
            "--model", model,
        ]
        if allowed_tools:
            cmd += ["--allowed-tools", ",".join(allowed_tools)]

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise BackendTimeout(f"claude exceeded {timeout_s}s") from e
        wall = time.monotonic() - t0

        stderr_lc = (result.stderr or "").lower()
        if result.returncode != 0:
            if any(sig in stderr_lc for sig in _AUTH_SIGNALS):
                raise AuthError(result.stderr.strip() or "claude auth failed")
            if any(sig in stderr_lc for sig in _RATE_SIGNALS):
                raise RateLimitError(result.stderr.strip() or "claude rate limited")
            # generic non-zero — surface as auth-or-other; let router retry
            raise RuntimeError(f"claude exit {result.returncode}: {result.stderr.strip()}")

        parsed = parse_claude_stream_json(result.stdout)
        structured = None
        if output_schema is not None:
            structured = extract_structured(parsed.assistant_text, output_schema)

        return InvokeResult(
            raw_text=parsed.assistant_text,
            structured=structured,
            tokens_in=parsed.tokens_in,
            tokens_out=parsed.tokens_out,
            wall_time_s=wall,
            model_used=parsed.model_used or model,
            backend_used=self.name,
            tool_calls=parsed.tool_calls,
        )
