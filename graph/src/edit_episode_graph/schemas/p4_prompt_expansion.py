"""Schema for p4_prompt_expansion output.

The dispatched sub-agent runs hyperframes canon §"Step 2: Prompt expansion"
(`references/prompt-expansion.md`) and writes a per-scene production spec
to `.hyperframes/expanded-prompt.md` in the project directory. The structured
return value is intentionally minimal — the file on disk is the artifact.
We surface the path back into state so downstream nodes (`p4_plan`,
`p4_beats`) can read the expansion at call time.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExpandedPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expanded_prompt_path: str = Field(
        min_length=1,
        description="Absolute path to the `.hyperframes/expanded-prompt.md` the sub-agent wrote.",
    )
