"""Schema for p3_persist_session output.

The dispatched sub-agent appends a Session block to `<edit>/project.md`
following the canon §"Memory" format. The node returns the path it wrote
to and the session number it chose; the file mutation itself happens
agent-side via the Edit/Write tool.
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
