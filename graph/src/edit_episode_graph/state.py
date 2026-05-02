"""Graph state schema.

v0 ships a single namespace: `pickup`. Future versions add `audio`, `transcripts`,
`edit`, `compose`, `review`, etc. — see spec §5.2 for the full progression.
"""

from operator import add
from typing import Annotated, TypedDict


class PickupState(TypedDict, total=False):
    raw_path: str | None
    script_path: str | None
    resumed: bool
    idle: bool
    warning: str | None


class GraphError(TypedDict):
    node: str
    message: str
    timestamp: str


class GraphState(TypedDict, total=False):
    slug: str
    episode_dir: str
    pickup: PickupState
    errors: Annotated[list[GraphError], add]
