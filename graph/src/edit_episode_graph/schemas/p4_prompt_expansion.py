"""Schema for p4_prompt_expansion output.

The dispatched sub-agent runs hyperframes canon §"Step 2: Prompt expansion"
(`references/prompt-expansion.md`) and returns the per-scene production
spec body in the `expanded_prompt` field. The orchestrator dual-writes
the body to `.hyperframes/expanded-prompt.md` so today's downstream
disk-readers (`p4_plan`, `p4_beats`) keep working until Step D2 of the
HOM-230 epic strips the dual-write.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExpandedPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expanded_prompt_path: str = Field(
        min_length=1,
        description="Absolute path to the `.hyperframes/expanded-prompt.md` the orchestrator "
                    "writes to disk (derived from slug via `EpisodePaths`; echoed for gate "
                    "convenience). Step E (HOM-230 epic) removes this field once disk-readers "
                    "are gone.",
    )
    expanded_prompt: str = Field(
        min_length=1,
        description="Full `.hyperframes/expanded-prompt.md` body — the six required output "
                    "sections + per-scene specs per "
                    "`~/.agents/skills/hyperframes/references/prompt-expansion.md` and "
                    "`references/beat-direction.md`. HOM-233: returned in state (state-first "
                    "artifacts, Step B of HOM-230). Orchestrator dual-writes to "
                    "`expanded_prompt_path` for today's disk-readers; Step D2 strips that "
                    "dual-write.",
    )
