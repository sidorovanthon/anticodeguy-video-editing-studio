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
    BackendCLIError,
    BackendTimeout,
    InvokeResult,
    NodeRequirements,
    RateLimitError,
    Tier,
)

# Three-tier mapping (HOM-115). Naming follows model-line ordering rather than the
# original two-tier shorthand so adding a new node is a single decision: pick
# `cheap` for mechanical / tool-loop work where retry is cheap, `smart` for
# general reasoning, `expensive` for highest-stakes creative judgment.
#
# - cheap     → Haiku 4.5: structured-write nodes, smoke / mechanical loops.
# - smart     → Sonnet 4.6: general reasoning, EDL-style numeric precision work.
# - expensive → Opus 4.7  : creative direction (design system, prompt expansion,
#                            plan, beat composition) — opt-in per memory
#                            `feedback_creative_nodes_flagship_tier` (creative
#                            LLM nodes must NOT degrade to cheaper tiers; HOM-154
#                            retro showed cheap-tier output triggered redispatch
#                            loops costing more than one successful Opus run).
_MODEL_BY_TIER: dict[str, str] = {
    "cheap": "claude-haiku-4-5-20251001",
    "smart": "claude-sonnet-4-6",
    "expensive": "claude-opus-4-7",
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
        # HOM-275: Pipe the brief via stdin instead of passing it as a positional
        # argv. Windows `CreateProcessW` caps the full command line at ~32k chars
        # and rejects oversize argv with `[WinError 206] The filename or extension
        # is too long`. State-first Phase 4 briefs (p4_plan, p4_dispatch_beats)
        # inline DESIGN.md + EDL + transcript and routinely exceed this. The
        # claude CLI accepts the prompt on stdin when `-p`/`--print` is used
        # without a positional prompt (verified via `claude --help`:
        # `-p, --print` is a flag, prompt is a separate positional arg; default
        # `--input-format text` reads stdin). Linux/macOS argv limit is ~2 MB so
        # the bug only surfaces on Windows, but the stdin path is portable.
        cmd = [
            self._executable,
            "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--model", model,
        ]
        if allowed_tools == []:
            cmd += ["--tools", ""]
        elif allowed_tools:
            cmd += ["--allowed-tools", ",".join(allowed_tools)]

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                input=task,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=str(cwd),
                timeout=timeout_s,
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
            raise BackendCLIError(returncode=result.returncode, stderr=result.stderr or "")

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
