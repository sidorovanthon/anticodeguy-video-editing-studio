"""Schema for p4_persist_session output.

Mirrors `schemas.p3_persist_session.PersistSessionResult`. Both Phase 3 and
Phase 4 persist runs append `## Session N — <date>` blocks to the same
`<edit>/project.md` file; session numbering is monotonic across the file
regardless of which phase wrote the block.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersistSessionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_at: str = Field(
        min_length=1,
        description="Absolute path to the project.md file that was appended to.",
    )
    session_n: int = Field(
        ge=1,
        description="Session number used in the appended `## Session N — <date>` heading.",
    )
