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
    raw_json_paths: list[str]
    takes_packed_path: str | None


class ComposeState(TypedDict, total=False):
    hyperframes_dir: str | None
    index_html_path: str | None


class PreScanState(TypedDict, total=False):
    slips: list[dict]
    source_path: str | None
    skipped: bool
    skip_reason: str | None


class StrategyState(TypedDict, total=False):
    shape: str
    takes: list[str]
    grade: str
    pacing: str
    length_estimate_s: float
    source_path: str | None
    skipped: bool
    skip_reason: str | None


class InventoryState(TypedDict, total=False):
    sources: list[dict]
    source_dir: str | None
    transcript_json_paths: list[str]
    takes_packed_path: str | None


class EdlState(TypedDict, total=False):
    version: int
    sources: dict[str, str]
    ranges: list[dict]
    grade: str
    overlays: list[dict]
    total_duration_s: float
    source_path: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class RenderState(TypedDict, total=False):
    final_mp4: str | None
    clips_dir: str | None
    duration_s: float | None
    expected_duration_s: float | None
    delta_ms: int | None
    n_segments: int | None
    cached: bool
    skipped: bool
    skip_reason: str | None


class EvalState(TypedDict, total=False):
    issues: list[dict]
    passed: bool
    final_mp4_path: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class EditState(TypedDict, total=False):
    inventory: InventoryState
    pre_scan: PreScanState
    strategy: StrategyState
    edl: EdlState
    render: RenderState
    eval: EvalState


class GateResult(TypedDict, total=False):
    gate: str
    passed: bool
    violations: list[str]
    iteration: int
    timestamp: str


class LLMRunRecord(TypedDict, total=False):
    node: str
    backend: str
    model: str
    tier: str
    success: bool
    reason: str | None
    wall_time_s: float | None
    tokens_in: int | None
    tokens_out: int | None
    timestamp: str


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
    edit: Annotated[EditState, dict_merge]
    errors: Annotated[list[GraphError], add]
    notices: Annotated[list[str], add]
    llm_runs: Annotated[list[LLMRunRecord], add]
    gate_results: Annotated[list[GateResult], add]
