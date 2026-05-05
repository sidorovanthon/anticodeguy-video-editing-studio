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


class DesignState(TypedDict, total=False):
    style_name: str
    palette: list[dict]
    typography: list[dict]
    refs: list[dict]
    alternatives: list[dict]
    anti_patterns: list[str]
    beat_visual_mapping: list[dict]
    design_md_path: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class ExpansionState(TypedDict, total=False):
    expanded_prompt_path: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class CatalogReport(TypedDict, total=False):
    blocks: list[dict]
    components: list[dict]
    fetched_at: str


class BeatArtifact(TypedDict, total=False):
    name: str
    html_path: str
    duration_s: float


class CaptionsState(TypedDict, total=False):
    captions_block_path: str | None
    cached: bool
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class AssembleState(TypedDict, total=False):
    assembled_at: str
    beat_names: list[str]
    captions_included: bool
    skipped: bool
    skip_reason: str | None


# PersistState is shared by EditState (Phase 3) and ComposeState (Phase 4);
# defined here so ComposeState can reference it without a forward decl.
class PersistState(TypedDict, total=False):
    persisted_at: str | None
    session_n: int | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class ComposeState(TypedDict, total=False):
    hyperframes_dir: str | None
    index_html_path: str | None
    design: DesignState
    design_md_path: str | None
    style_request: str | None
    expansion: ExpansionState
    expanded_prompt_path: str | None
    catalog: CatalogReport
    # DEPRECATED — `compose.beats` is no longer populated by any node. The
    # per-beat fan-out (HOM-133/134) writes scene fragments to
    # `<hyperframes_dir>/compositions/<scene_id>.html` directly, and
    # `p4_assemble_index` reads them from disk in `compose.plan.beats[]`
    # order (FS source-of-truth, no state echo). Kept on the schema only
    # so existing checkpoints with the field don't fail validation;
    # mechanical removal is tracked separately. Spec:
    # `2026-05-04-hom-122-p4-beats-fan-out-design.md` §"State changes".
    beats: list[BeatArtifact]
    captions: CaptionsState
    captions_block_path: str | None
    assemble: AssembleState
    # p4_persist_session (HOM-126): Phase 4 Session block appended to
    # <edit>/project.md. Shape mirrors EditState.persist; same PersistState
    # type. `session_persisted` is set true on a structured success.
    persist: PersistState
    session_persisted: bool
    # studio_launch (HOM-125): backgrounded `hyperframes preview` server.
    studio_pid: int | None
    preview_log_path: str | None
    preview_port: int | None
    studio_launched_at: str | None
    studio_reused: bool


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
    # HR 11 — set by strategy_confirmed_interrupt after operator approval.
    approved: bool
    approval_payload: object


class InventoryState(TypedDict, total=False):
    sources: list[dict]
    source_dir: str | None
    transcript_json_paths: list[str]
    takes_packed_path: str | None


class FailureResumeState(TypedDict, total=False):
    """Operator's resume payload after a HITL gate-failure interrupt (HOM-130).

    `action` is whatever the operator passed to `Command(resume=...)` —
    typed `object` because Studio resumes are free-form (None / str / dict).
    Routing inspects this via `_routing._is_abort` to decide retry vs halt.
    """
    action: object
    iteration_at_suspend: int | None
    resumed_at: str | None


class EdlState(TypedDict, total=False):
    version: int
    sources: dict[str, str]
    ranges: list[dict]
    grade: str
    overlays: list[dict]
    total_duration_s: float
    source_path: str | None
    edl_path: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None
    failure_resume: FailureResumeState


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
    failure_resume: FailureResumeState


class EditState(TypedDict, total=False):
    inventory: InventoryState
    pre_scan: PreScanState
    strategy: StrategyState
    edl: EdlState
    render: RenderState
    eval: EvalState
    persist: PersistState


class BugCheck(TypedDict, total=False):
    bug_slug: str
    # "still_broken" | "no_longer_reproducible" | "inconclusive" | "fresh" | "missing_script"
    status: str
    last_verified: str | None
    repro_exit_code: int | None
    duration_s: float | None
    message: str | None


class PreflightState(TypedDict, total=False):
    checked: list[BugCheck]
    state_path: str | None


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
    preflight: Annotated[PreflightState, dict_merge]
    errors: Annotated[list[GraphError], add]
    notices: Annotated[list[str], add]
    llm_runs: Annotated[list[LLMRunRecord], add]
    gate_results: Annotated[list[GateResult], add]
    # Append-only operator feedback collected by strategy_confirmed_interrupt
    # when the resume payload is a revision rather than approval. p3_strategy
    # reads this list on each re-entry to refine the strategy. Top-level so
    # it survives strategy regeneration via dict_merge on `edit`.
    strategy_revisions: Annotated[list[str], add]
