"""Graph state schema.

v0 shipped one namespace: `pickup`.
v1 adds `audio`, `transcripts`, `compose` plus the append-only `notices`
top-level list — see spec §5.2 for the full progression.

Reducer choice rationale (spec §5.1):
- `dict_merge` for phase namespaces. Multiple nodes may eventually write into
  the same namespace; shallow merge preserves siblings without per-node
  awareness of the full namespace shape.
- `operator.add` for `errors` and `notices` (append-only).
- Last-write-wins (default) for identity fields (`slug`, `episode_dir`).
"""

from operator import add
from typing import Annotated, TypedDict


def dict_merge(left: dict | None, right: dict | None) -> dict:
    """Shallow dict merge. Right wins on key collisions; missing inputs treated as {}."""
    out = dict(left or {})
    out.update(right or {})
    return out


class PickupState(TypedDict, total=False):
    raw_path: str | None
    script_path: str | None
    resumed: bool
    idle: bool
    warning: str | None


class AudioState(TypedDict, total=False):
    cached: bool
    api_called: bool
    wav_path: str | None
    reason: str | None


class TranscriptsState(TypedDict, total=False):
    raw_json_path: str | None
    final_json_path: str | None
    edl_hash: str | None


class ComposeState(TypedDict, total=False):
    hyperframes_dir: str | None
    index_html_path: str | None


class GraphError(TypedDict):
    node: str
    message: str
    timestamp: str


class GraphState(TypedDict, total=False):
    slug: str
    episode_dir: str
    pickup: Annotated[PickupState, dict_merge]
    audio: Annotated[AudioState, dict_merge]
    transcripts: Annotated[TranscriptsState, dict_merge]
    compose: Annotated[ComposeState, dict_merge]
    errors: Annotated[list[GraphError], add]
    notices: Annotated[list[str], add]
