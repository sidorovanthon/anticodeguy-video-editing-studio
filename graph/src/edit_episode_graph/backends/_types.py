"""Backend-layer shared types and exception taxonomy.

All backends speak the same language to nodes via these primitives. Adding a
new field here is a breaking change for every backend implementation — keep
the surface narrow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Tier = Literal["cheap", "smart"]


@dataclass(frozen=True)
class BackendCapabilities:
    name: str
    has_tools: bool
    supports_streaming: bool
    max_concurrent: int


@dataclass(frozen=True)
class NodeRequirements:
    tier: Tier
    needs_tools: bool
    backends: list[str]   # preference order; empty = router default

    def satisfied_by(self, caps: BackendCapabilities) -> bool:
        if self.needs_tools and not caps.has_tools:
            return False
        return True


@dataclass
class ToolCall:
    name: str
    input: dict[str, Any]
    output_preview: str   # truncated; full output is in stream log


@dataclass
class InvokeResult:
    raw_text: str
    structured: Any | None
    tokens_in: int | None
    tokens_out: int | None
    wall_time_s: float
    model_used: str
    backend_used: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class BackendError(Exception):
    """Base for all backend-layer errors."""


class AuthError(BackendError):
    """CLI reports unauthenticated / expired session."""


class RateLimitError(BackendError):
    """CLI reports rate-limit / quota exhausted."""


class BackendTimeout(BackendError):
    """Subprocess exceeded `timeout_s`."""


class BackendCLIError(BackendError):
    """Backend CLI exited non-zero with no recognized auth/rate signal in stderr."""

    def __init__(self, returncode: int, stderr: str):
        super().__init__(f"backend CLI exit {returncode}: {stderr.strip()[:200]}")
        self.returncode = returncode
        self.stderr = stderr


class SchemaValidationError(BackendError):
    """Final assistant text could not be parsed into the requested Pydantic schema."""

    def __init__(self, message: str, raw_text: str):
        super().__init__(message)
        self.raw_text = raw_text


class AllBackendsExhausted(BackendError):
    """Router tried every backend in the preference list and none succeeded."""

    def __init__(self, attempts: list[dict[str, Any]]):
        # Embed a compact summary of attempts directly in the exception message
        # so it surfaces in checkpoint task.error and `langgraph_api.worker`
        # error logs without needing the per-run stream-events replay (which
        # is unavailable once the run has terminated).
        summary_parts = []
        for i, a in enumerate(attempts):
            piece = f"#{i + 1} backend={a.get('backend')} reason={a.get('reason')} exc={a.get('exc_type')}"
            msg = (a.get("message") or "")[:120]
            if msg:
                piece += f" msg={msg!r}"
            stderr = (a.get("stderr_preview") or "")[:120]
            if stderr:
                piece += f" stderr={stderr!r}"
            rc = a.get("returncode")
            if rc is not None:
                piece += f" rc={rc}"
            summary_parts.append(piece)
        summary = " | ".join(summary_parts) if summary_parts else "(no attempts)"
        super().__init__(
            f"All backends exhausted across {len(attempts)} attempt(s): {summary}"
        )
        self.attempts = attempts
