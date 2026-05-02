"""LLMBackend Protocol — the single contract every backend implements.

Spec §7.1. Nodes never import a concrete backend; they go through
`BackendRouter.invoke(node_requirements, task, ...)`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ._types import (
    BackendCapabilities,
    InvokeResult,
    NodeRequirements,
    Tier,
)


@runtime_checkable
class LLMBackend(Protocol):
    name: str
    capabilities: BackendCapabilities

    def supports(self, req: NodeRequirements) -> bool: ...

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
    ) -> InvokeResult: ...


__all__ = ["LLMBackend"]
