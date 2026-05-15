"""Graph state schema.

v0 shipped one namespace: `pickup`.
v1 adds `audio`, `transcripts`, `compose` plus the append-only `notices`
top-level list — see spec §5.2 for the full progression.

Reducer choice rationale (spec §5.1):
- `dict_merge` for phase namespaces. Multiple nodes may eventually write into
  the same namespace; shallow merge preserves siblings without per-node
  awareness of the full namespace shape.
- `operator.add` for `errors` and `notices` (append-only).
- `gate_results_reducer` for `gate_results` — additive by default with
  sentinel-based clear/replace semantics for `update_state`-driven rewind
  (HOM-163).
- Last-write-wins (default) for identity fields (`slug`, `episode_dir`).

HOM-223 — P3 absolute-path keys removed from state writes. P3 nodes now
derive paths via `EpisodePaths(slug)` at use-site. Old recordings carrying
the deprecated keys still parse cleanly because `TypedDict` is a runtime
`dict`: extra keys are ignored on read but never emitted by post-HOM-223
writers. Removed keys (writer in parens):
* `TranscriptsState.raw_json_path` (`glue_remap_transcript`)
* `TranscriptsState.final_json_path` (`glue_remap_transcript`)
* `TranscriptsState.takes_packed_path` (`p3_inventory`)
* `TranscriptsState.raw_json_paths` (`p3_inventory`)
* `InventoryState.source_dir` / `transcript_json_paths` /
  `takes_packed_path` (`p3_inventory`)
* `PreScanState.source_path` (`p3_pre_scan`)
* `StrategyState.source_path` (`p3_strategy` / `rehydrate_skip_phase3`)
* `EdlState.source_path` / `edl_path` (`p3_edl_select`)
* `RenderState.final_mp4` / `clips_dir` (`p3_render_segments`)
* `EvalState.final_mp4_path` (`p3_self_eval`)
* `PersistState.persisted_at` (`p3_persist_session`) — repurposed to a
  boolean-ish ISO timestamp upstream by p4_persist_session; kept on the
  schema so existing callers continue to type-check, but p3 no longer
  writes a path-shaped value. p4 ownership is Sub-3 territory.

The keys remain typed on the schema below for forward-compat parsing of
already-recorded fixtures (cache.db rows). New code MUST NOT write them.

HOM-224 — P4 absolute-path keys removed from state writes. P4 nodes now
derive paths via `EpisodePaths(slug)` at use-site (mirrors the p3
migration). Old recordings carrying these keys still parse cleanly. Removed
keys (writer in parens):
* `ComposeState.hyperframes_dir` (`p4_scaffold`)
* `ComposeState.index_html_path` (`p4_scaffold` / `p4_assemble_index`)
* `ComposeState.design_md_path` (`p4_design_system`)
* `DesignState.design_md_path` (`p4_design_system` — structured-output
  echo no longer mirrored up to the top-level `compose.design_md_path`;
  the schema field stays so the LLM may still emit it, but the node body
  does not promote it into state)
* `ComposeState.expanded_prompt_path` (`p4_prompt_expansion`)
* `ExpansionState.expanded_prompt_path` — same shape as design above
* `ComposeState.captions_block_path` (`p4_captions_layer`)
* `CaptionsState.captions_block_path` (`p4_captions_layer`)
* `AssembleState.index_html_path` (`p4_assemble_index`) — `assembled_at`
  ISO timestamp is the success signal; the path was redundant with
  `compose.index_html_path` and EpisodePaths
* `PersistState.persisted_at` (`p4_persist_session`) — same str|None slot
  as p3, semantics shift from absolute path → ISO timestamp

The keys remain typed on the schema below for forward-compat parsing.

HOM-231 (Step A of HOM-230 state-first artifacts epic) — body-string fields
added to the compose namespace alongside the existing `*_path` keys. New
fields under ``compose``: ``scenes`` (dict[scene_id -> {html}], wired through
the deterministic ``_scenes_merge`` reducer), ``index_html`` (top-level —
intentionally NOT nested under ``compose.assemble`` per the HOM-231 ticket;
the spec's §10 Step A wrote ``compose.assemble.index_html`` but the Linear
ticket simplified to a flat key to avoid premature nesting; flatness is fine
because the only producer is ``p4_assemble_index`` and there are no sibling
assemble-body fields). Body fields on existing sub-namespaces:
``design.design_md``, ``expansion.expanded_prompt``, ``captions.html``,
``persist.session_block``. Plus ``materialize`` placeholder for HOM-230
Step C. All new fields are ``total=False`` and additive — no existing
``*_path`` field is removed; coexistence is intentional and Step E removes
the path keys.
"""

from operator import add
from typing import Annotated, TypedDict


def dict_merge(left: dict | None, right: dict | None) -> dict:
    """Shallow dict merge. Right wins on key collisions; missing inputs treated as {}."""
    out = dict(left or {})
    out.update(right or {})
    return out


def _scenes_merge(left: dict | None, right: dict | None) -> dict:
    """Union-merge two scenes dicts. On conflict (same scene_id from two
    parallel Sends) the right-hand value wins — last-Send-write semantics
    matching LangGraph's standard channel-write order. Output dict is
    sorted by scene_id so downstream content-hash fingerprints are
    iteration-order independent.

    Used as the reducer for the top-level ``GraphState.scenes`` channel
    (HOM-234). The HOM-231 nested annotation on ``ComposeState.scenes``
    was rendered non-functional by LangGraph's reducer semantics — only
    top-level ``Annotated`` channels fire their reducer, nested
    ``Annotated`` types inside another ``Annotated`` channel are
    ignored. The HOM-234 pre-check (``tests/test_compose_scenes_fanout``)
    empirically pinned this; the channel was promoted from
    ``compose.scenes`` to the top-level ``scenes`` on ``GraphState``. The
    sorted-by-key output is load-bearing for the future materializer's
    cache key (spec §6.3) — Python dict iteration is insertion-ordered,
    and parallel ``Send`` completion order is non-deterministic, so an
    unsorted union would produce different cache keys for the same scene
    set. Spec source-of-truth:
    ``docs/superpowers/specs/2026-05-10-state-first-artifacts.md`` §10
    Step A.
    """
    merged = dict(left or {})
    merged.update(right or {})
    return {k: merged[k] for k in sorted(merged)}


def gate_results_reducer(
    left: list | None, right: list | dict | None
) -> list:
    """Reducer for ``gate_results`` with clear-on-replay semantics (HOM-163).

    Default behavior is **additive append** — preserves backward compatibility
    with all existing gate nodes that emit ``{"gate_results": [record]}``.

    Two sentinel shapes are recognised when ``right`` is a ``dict``:

    * ``{"_replace": True, "items": [...]}`` — replace the entire list with
       ``items`` (or ``[]`` if absent). Functionally equivalent to LangGraph's
       native :class:`langgraph.types.Overwrite`, but kept here for symmetry
       with ``_clear_gate``: ``Overwrite`` only intercepts a binary-aggregate
       reducer, so once we install a custom reducer the framework no longer
       routes ``Overwrite`` for this channel — we have to provide the
       full-replace path ourselves.
    * ``{"_clear_gate": "<gate_name>"}`` — drop every existing record whose
       ``gate`` field equals ``<gate_name>``. No-op if no records match.
       Operators use this from
       ``client.threads.update_state(values=..., as_node=...)`` to rewind out
       of a stuck gate-failure cluster without losing unrelated history
       (lint failures, eval_ok failures, etc. recorded by other gates).

    Anything else (a plain ``list``, a single-record ``dict`` without
    sentinel keys) is appended.

    Refs:
        * Ticket: HOM-163 (M5 cleanup, M6 acceptance dependency).
        * LangGraph reducers concept page:
          https://langchain-ai.github.io/langgraph/concepts/low_level/
        * Native overwrite primitive verified present in
          ``langgraph.types.Overwrite`` (LangGraph 0.x). It only handles full
          replace and only via ``BinaryOperatorAggregate``; the ``_clear_gate``
          filter requires reading the existing list, so we keep one custom
          reducer that handles both replace and selective filter.
    """
    base = list(left or [])
    if right is None:
        return base
    if isinstance(right, dict):
        if right.get("_replace") is True:
            return list(right.get("items") or [])
        if "_clear_gate" in right:
            gate = right["_clear_gate"]
            return [
                r for r in base
                if not (isinstance(r, dict) and r.get("gate") == gate)
            ]
        # Plain single-record dict (no sentinel keys) — defensive append.
        # Not the canonical writer shape (writers emit `[record]`), but
        # historically a single-dict update would have been list-add'd
        # via Python's list.__add__([dict]) semantics; keep that intact.
        return base + [right]
    # list / tuple / other iterable of records → append.
    return base + list(right)


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
    # HOM-231 (Step A): body string returned by p4_design_system. Coexists
    # with `design_md_path` during the migration; Step E drops the path.
    design_md: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class ExpansionState(TypedDict, total=False):
    expanded_prompt_path: str | None
    # HOM-231 (Step A): body string returned by p4_prompt_expansion.
    expanded_prompt: str | None
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
    # HOM-231 (Step A): body string returned by p4_captions_layer.
    html: str | None
    cached: bool
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class SceneState(TypedDict, total=False):
    """Per-scene fragment body returned by p4_beat (HOM-231).

    Populated under ``compose.scenes[<scene_id>]`` via the ``_scenes_merge``
    reducer. Step B wires `p4_beat`'s structured-output writes into this
    channel; Step A only ships the schema.
    """
    html: str


class MaterializeState(TypedDict, total=False):
    """Placeholder for HOM-230 Step C ``p4_materialize_disk_node`` outputs.

    No fields required at Step A — the materializer's output shape is
    finalized in its own PR. Schema slot reserved here so the topology
    test for the future node has somewhere to land state without a
    second schema-migration round.
    """
    materialized_at: str | None
    files_written: list[str]


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
    # HOM-231 (Step A): Session-block markdown body returned by
    # p4_persist_session (and, on the Phase-3 side, p3_persist_session if
    # it is later migrated). The disk append into <edit>/project.md
    # remains the authoritative artifact during the migration window.
    session_block: str | None
    raw_text: str | None
    skipped: bool
    skip_reason: str | None


class ComposeState(TypedDict, total=False):
    hyperframes_dir: str | None
    index_html_path: str | None
    # HOM-231 (Step A): assembled top-level index.html body returned by
    # p4_assemble_index. Top-level under compose (NOT nested under
    # `compose.assemble`) per the Linear ticket — flatness is fine because
    # the only producer is p4_assemble_index and there are no sibling
    # assemble-body fields. Spec §10 Step A originally wrote
    # `compose.assemble.index_html`; ticket simplified to flat.
    index_html: str | None
    design: DesignState
    design_md_path: str | None
    style_request: str | None
    expansion: ExpansionState
    expanded_prompt_path: str | None
    catalog: CatalogReport
    # HOM-231 (Step A): per-scene fragment bodies, keyed by scene_id.
    # DEPRECATED location — HOM-234 pre-check (2026-05-15) proved
    # LangGraph reducers do NOT walk nested ``Annotated`` channels:
    # two parallel ``Send``s into ``compose.scenes`` clobbered each
    # other because only the outer ``compose: Annotated[..., dict_merge]``
    # reducer fired at the top level (shallow `{**left, **right}` over
    # whole `scenes` dicts, last Send wins). ``scenes`` was promoted to a
    # top-level channel on ``GraphState`` so ``_scenes_merge`` actually
    # runs over the parallel fan-out from ``p4_beat``. This field stays
    # on ``ComposeState`` only so already-recorded checkpoints carrying
    # the deprecated nested key still parse cleanly; new code MUST write
    # to ``GraphState.scenes`` (top-level). See
    # ``tests/test_compose_scenes_fanout.py`` for the empirical pin and
    # ``docs/superpowers/specs/2026-05-10-state-first-artifacts.md`` §10
    # Step B for the spec amendment.
    scenes: dict[str, SceneState]
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
    # HOM-231 (Step A): placeholder slot for p4_materialize_disk_node
    # outputs (HOM-230 Step C). Empty in Step A.
    materialize: MaterializeState


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
    target_fps: int | None
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
    # HOM-234: per-scene fragment bodies from the p4_beat fan-out. Top-level
    # rather than nested under ``compose`` because LangGraph reducers do NOT
    # walk nested ``Annotated`` channels — two parallel ``Send``s writing
    # into ``compose.scenes`` clobber each other under the outer
    # ``dict_merge``. Promoting ``scenes`` to a top-level channel routes the
    # parallel writes through ``_scenes_merge`` (union + sorted-by-key for
    # deterministic content-hash fingerprints, spec §6.3). Empirical pin:
    # ``tests/test_compose_scenes_fanout.py``. Spec amendment:
    # ``docs/superpowers/specs/2026-05-10-state-first-artifacts.md`` §10
    # Step B. Step E (HOM-230 epic close) keeps this channel; the
    # deprecated ``ComposeState.scenes`` field stays only for forward-compat
    # parsing of pre-HOM-234 checkpoints.
    scenes: Annotated[dict[str, SceneState], _scenes_merge]
    edit: Annotated[EditState, dict_merge]
    preflight: Annotated[PreflightState, dict_merge]
    errors: Annotated[list[GraphError], add]
    notices: Annotated[list[str], add]
    llm_runs: Annotated[list[LLMRunRecord], add]
    gate_results: Annotated[list[GateResult], gate_results_reducer]
    # Append-only operator feedback collected by strategy_confirmed_interrupt
    # when the resume payload is a revision rather than approval. p3_strategy
    # reads this list on each re-entry to refine the strategy. Top-level so
    # it survives strategy regeneration via dict_merge on `edit`.
    strategy_revisions: Annotated[list[str], add]
