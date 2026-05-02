"""CodexBackend — `codex exec "<task>" --model <id> --json`.

Spec §7.2. ChatGPT subscription auth.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel

from ._schema_extract import extract_structured
from ._stream_parsers import parse_codex_json
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
    "cheap": "gpt-5-mini",
    "smart": "gpt-5",
}

_AUTH_SIGNALS = ("not authenticated", "codex login", "unauthorized", "session expired")
_RATE_SIGNALS = ("rate limit", "quota", "too many requests")


class CodexBackend:
    name = "codex"
    capabilities = BackendCapabilities(
        name="codex", has_tools=True, supports_streaming=False, max_concurrent=2,
    )

    def __init__(self, executable: str | None = None):
        self._executable = executable or shutil.which("codex") or "codex"

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
        cmd = [self._executable, "exec", task, "--model", model, "--json"]
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise BackendTimeout(f"codex exceeded {timeout_s}s") from e
        wall = time.monotonic() - t0
        stderr_lc = (result.stderr or "").lower()
        if result.returncode != 0:
            if any(sig in stderr_lc for sig in _AUTH_SIGNALS):
                raise AuthError(result.stderr.strip() or "codex auth failed")
            if any(sig in stderr_lc for sig in _RATE_SIGNALS):
                raise RateLimitError(result.stderr.strip() or "codex rate limited")
            raise RuntimeError(f"codex exit {result.returncode}: {result.stderr.strip()}")

        parsed = parse_codex_json(result.stdout)
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
