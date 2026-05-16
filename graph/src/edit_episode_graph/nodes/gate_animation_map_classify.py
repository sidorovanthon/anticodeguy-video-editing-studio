"""gate_animation_map_classify — cheap-tier LLM advisory classifier (HOM-156, HOM-204).

Reads the gate_animation_map record's ``advisory_findings.pending_classify``
list and dispatches a cheap-tier LLM helper that annotates each
paced-fast / paced-slow flag with a per-flag decision (``justify`` /
``fix``) and reason. **Output is advisory metadata** — it never affects
routing.

Per CLAUDE.md §"Idempotency" + spec
``docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md``:
the LLM dispatch lives in its own graph node so LangGraph's
``cache_policy=`` mechanism applies — re-running the gate cluster
on identical inputs produces zero LLM dispatches.

Brief: ``briefs/gate_animation_map_classify.j2`` — references canon
paths, never embeds canon (CLAUDE.md §"Decomposition via
brief-references-canon").

HOM-204 demotion (parent HOM-203): four clean ``hyperframes`` skill
sessions never invoked ``animation-map.mjs`` at all — canon treats it
as optional QA tooling, not a blocking gate. We keep the classifier
because its per-flag justifications are operator-readable signal in
Studio, but its decisions are advisory: classifier output merges into
``advisory_findings.pending_classify`` (each entry gains
``decision`` + ``reason`` keys) and the router always advances to
``gate_snapshot``.

Output: appends a fresh ``gate:animation_map`` record to
``state.gate_results`` with:

  * ``passed`` — preserved from the upstream gate record (advisory
    routing — successful helper run is always ``True``; infra
    failures don't reach this node).
  * ``violations`` — preserved as-is (gate base contract; carries
    upstream infra failures only, ``[]`` on the happy path).
  * ``advisory_findings`` — same three-key shape as the upstream
    record, with ``pending_classify`` entries annotated per-flag.
  * ``classifier_status`` — ``"ok"`` on a successful dispatch,
    ``"failed: <reason>"`` on dispatch / schema failure. The router
    does not read this; it's operator-facing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langgraph.types import CachePolicy
from pydantic import BaseModel, ConfigDict, Field

from .._caching import make_llm_key, stable_fingerprint
from .._paths import EpisodePaths
from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v1 = HOM-156 — initial cheap-tier extraction from gate body.
# v2 = HOM-204 — output shape change: classifier decisions merge into
#      ``advisory_findings.pending_classify`` (was: into ``violations`` /
#      ``justifications``). Reads upstream input from
#      ``advisory_findings.pending_classify`` (was: ``pending_justifiable``).
# v3 = HOM-206 — brief rewrite: drop "this task is canon" misclaim;
#      reframe classifier output as advisory orchestrator-house QA (canon
#      treats animation-map as optional QA tooling, not a mandate); allow
#      partial output (no length-parity requirement). Brief content is
#      part of the LLM dispatch's effective input — bump invalidates
#      stale recorded classifications under the old framing.
# v4 = HOM-225 — cache key + render ctx derive `hf_dir` / `design_md_path`
#      via `EpisodePaths(slug)` rather than reading deprecated
#      `compose.hyperframes_dir` / `compose.design_md_path` echoes (which
#      no p4 node writes after HOM-224). Without this bump, DESIGN.md
#      edits silently fail to invalidate the classifier cache on fresh
#      runs because the legacy slot is `None`.
# v5 = HOM-282 — brief input set migrated: `animation-map.json` is no
#      longer Read from disk by the sub-agent; the parsed report is
#      inlined via the upstream gate record's
#      `animation_map_report` extras (Class C fold-in). The cache key
#      still fingerprints `animation_map_json_path` via `files=` so
#      content changes invalidate as before — but the brief no longer
#      depends on the file being present at dispatch time. Bump
#      invalidates so recordings made under v4 (which assumed `Read`
#      tool calls on the file) are not replayed under the new brief.
_CACHE_VERSION = 5


# ---------------------------------------------------------------------------
# Output schema — Literal types for clean validation (review nit).
# ---------------------------------------------------------------------------


class _FlagDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str = Field(min_length=1, description="Stable id from flagged_tweens input.")
    decision: Literal["justify", "fix"] = Field(
        description="`justify` if intentional creative choice; `fix` otherwise.",
    )
    reason: str = Field(
        min_length=1,
        description="One sentence citing the beat label and energy/mood that justifies, "
                    "or the specific mismatch that requires a fix.",
    )


class _ClassifyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flags: list[_FlagDecision] = Field(
        description="One decision per flagged tween, in the same order as the input.",
    )


# ---------------------------------------------------------------------------
# Render context + cache-key helpers.
# ---------------------------------------------------------------------------


# Path layout mirrored from gates.animation_map (kept local so this node has
# no import cycle through the gate module — both reference the same canonical
# location under the HF project).
_OUT_SUBDIR = Path(".hyperframes/anim-map")
_OUT_FILE = "animation-map.json"


def _hf_dir(state: dict) -> Path | None:
    """HOM-225: derive via `EpisodePaths(slug)` — identity-only state.

    Returns ``None`` only when slug itself is missing (pre-pickup state).
    The legacy ``compose.hyperframes_dir`` / ``state["episode_dir"]``
    chain is gone — those keys are no longer written by any p4 node
    after HOM-224.
    """
    slug = state.get("slug")
    if not slug:
        return None
    return EpisodePaths(slug).hyperframes_dir


def _animation_map_path(state: dict) -> Path | None:
    hf_dir = _hf_dir(state)
    if hf_dir is None:
        return None
    return hf_dir / _OUT_SUBDIR / _OUT_FILE


def _design_md_path(state: dict) -> str:
    """HOM-225: derive via `EpisodePaths(slug)` — identity-only state.

    Returns ``""`` only when slug itself is missing. The legacy
    ``compose.design_md_path`` / ``compose.design.design_md_path`` chain
    is gone — no p4 node writes those keys after HOM-224.
    """
    slug = state.get("slug")
    if not slug:
        return ""
    return str(EpisodePaths(slug).design_md_path)


def _plan_beats(state: dict) -> list[dict]:
    plan = (state.get("compose") or {}).get("plan") or {}
    beats = plan.get("beats") or []
    out: list[dict] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        out.append({
            "beat": b.get("beat"),
            "concept": b.get("concept"),
            "mood": b.get("mood"),
            "energy": b.get("energy"),
            "duration_s": b.get("duration_s"),
        })
    return out


def _latest_animation_map_record(state: dict) -> dict | None:
    """Most recent gate:animation_map record (the one carrying advisory_findings)."""
    for record in reversed(state.get("gate_results") or []):
        if record.get("gate") == "gate:animation_map":
            return record
    return None


def _pending_classify(state: dict) -> list[dict]:
    """Read pending pace-flags from the latest gate record (HOM-204 shape)."""
    record = _latest_animation_map_record(state)
    if not record:
        return []
    advisory = record.get("advisory_findings") or {}
    return list(advisory.get("pending_classify") or [])


def _animation_map_report(state: dict) -> dict | None:
    """HOM-282 (Class C fold-in): prefer the parsed report hoisted into
    the upstream gate record's ``extras`` over the on-disk JSON file.

    The deterministic gate (``gates/animation_map.py``) parses
    ``animation-map.json`` once and stashes the result under
    ``gate_results[-1].animation_map_report``. Reading it from state
    here keeps the classifier's brief input fully state-fed — the disk
    file becomes a debug artifact, not control flow.
    """
    record = _latest_animation_map_record(state)
    if not record:
        return None
    report = record.get("animation_map_report")
    return report if isinstance(report, dict) else None


def _render_ctx(state: dict) -> dict:
    anim_path = _animation_map_path(state)
    flagged = _pending_classify(state)
    report = _animation_map_report(state)
    return {
        # Path retained for brief context only (operator-facing debug
        # reference — the agent must NOT re-Read it; the body is
        # inlined via ``animation_map_json``).
        "animation_map_json_path": str(anim_path) if anim_path else "",
        # HOM-282 (Class C fold-in): inline the parsed helper output
        # in the brief so the sub-agent does not Read the JSON file.
        "animation_map_json": json.dumps(report or {}, ensure_ascii=False),
        "design_md_path": _design_md_path(state),
        "plan_beats_json": json.dumps(_plan_beats(state), ensure_ascii=False),
        "flagged_tweens_json": json.dumps(flagged, ensure_ascii=False),
    }


def _cache_key(state, *_args, **_kwargs):
    """Cache key for the LLM classifier.

    HOM-157: ``make_llm_key`` auto-prepends a ``cfg:<sha>`` extra so a
    ``graph/config.yaml`` bump on this node invalidates without manual cache
    wipe. We additionally bake in:
      - the animation-map.json content hash (``files=``) — different flags
        ⇒ different decision space.
      - DESIGN.md content hash (``files=``) — different visual identity
        ⇒ different justification surface.
      - plan beats fingerprint (``extras=``) — beats live in-memory on
        ``state.compose.plan``, not on disk.
      - pending_classify fingerprint (``extras=``) — the classifier's
        actual input set, gated by the gate record's pending list
        (HOM-204 shape: ``advisory_findings.pending_classify``).
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"gate_animation_map_classify cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    anim_path = _animation_map_path(state)
    design_md = _design_md_path(state)
    return make_llm_key(
        node="gate_animation_map_classify",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            str(anim_path) if anim_path else None,
            design_md or None,
        ],
        extras=(
            stable_fingerprint(_plan_beats(state)),
            stable_fingerprint(_pending_classify(state)),
        ),
    )


# Exposed for `graph.py` cache wiring AND for tests/_helpers/fingerprint_assertions.py.
CACHE_POLICY = CachePolicy(key_func=_cache_key)


# ---------------------------------------------------------------------------
# Node body.
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_node() -> LLMNode:
    return LLMNode(
        name="gate_animation_map_classify",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("gate_animation_map_classify"),
        output_schema=_ClassifyOutput,
        result_namespace="compose",
        result_key="classify_decisions",
        timeout_s=120,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def _iteration(state: dict) -> int:
    prior = [r for r in (state.get("gate_results") or []) if r.get("gate") == "gate:animation_map"]
    return len(prior) + 1


def _annotated_pending(
    flagged_input: list[dict],
    decisions_by_id: dict[str, "_FlagDecision"],
    fallback_reason: str | None,
) -> list[dict]:
    """Return pending_classify entries annotated with the classifier's
    per-flag decisions (or a fallback if classifier failed).

    Output is always advisory (HOM-204) — even ``decision="fix"`` does
    not affect routing. Each entry preserves its original keys
    (``flag_id``, ``selector``, ``flag``, ``duration``, ``index``) and
    gains ``decision`` + ``reason``.
    """
    out: list[dict] = []
    for flagged in flagged_input:
        entry = dict(flagged)
        d = decisions_by_id.get(flagged.get("flag_id"))
        if d is not None:
            entry["decision"] = d.decision
            entry["reason"] = d.reason
        else:
            entry["decision"] = "fix"
            entry["reason"] = fallback_reason or (
                "classifier returned no decision for this flag; "
                "treating as advisory fix until the classifier is re-runnable"
            )
        out.append(entry)
    return out


def gate_animation_map_classify_node(state: dict, *, router: BackendRouter | None = None) -> dict:
    """Annotate pending pace flags with advisory decisions (HOM-204).

    Always emits a follow-up ``gate:animation_map`` record. The record's
    ``passed`` is preserved from the upstream gate record (advisory:
    successful helper run is always ``True``). Routing always advances
    to ``gate_snapshot`` regardless of what the classifier said — the
    decisions are operator-facing metadata.
    """
    record = _latest_animation_map_record(state)
    upstream_advisory = (record or {}).get("advisory_findings") or {}
    flagged_input = list(upstream_advisory.get("pending_classify") or [])
    upstream_violations = list((record or {}).get("violations") or [])
    upstream_passed = bool((record or {}).get("passed", True))

    extras: dict = {}
    for k in ("helper_path", "fallback_helper_used"):
        if record and k in record:
            extras[k] = record[k]

    # Always-fix and dead-zones come straight through unchanged.
    base_advisory = {
        "always_fix": list(upstream_advisory.get("always_fix") or []),
        "dead_zones": list(upstream_advisory.get("dead_zones") or []),
        "pending_classify": [],  # filled in below
    }

    if not flagged_input:
        # Defensive: router should not send us here, but be safe — emit a
        # passing-through record so the router sees a clean state.
        passthrough_record = {
            "gate": "gate:animation_map",
            "passed": upstream_passed,
            "violations": upstream_violations,
            "advisory_findings": {**base_advisory, "pending_classify": []},
            "classifier_status": "skipped: no pending_classify entries",
            "iteration": _iteration(state),
            "timestamp": _now(),
            **extras,
        }
        return {"gate_results": [passthrough_record]}

    node = _build_node()
    try:
        update = node(state, router=router)
    except Exception as exc:  # AllBackendsExhausted etc. — gate must not raise.
        annotated = _annotated_pending(
            flagged_input,
            decisions_by_id={},
            fallback_reason=(
                f"classifier dispatch failed ({type(exc).__name__}: {exc}); "
                "advisory only — no routing impact"
            ),
        )
        fail_record = {
            "gate": "gate:animation_map",
            "passed": upstream_passed,
            "violations": upstream_violations,
            "advisory_findings": {**base_advisory, "pending_classify": annotated},
            "classifier_status": f"failed: {type(exc).__name__}: {exc}",
            "iteration": _iteration(state),
            "timestamp": _now(),
            **extras,
        }
        return {"gate_results": [fail_record]}

    compose_update = update.get("compose") or {}
    payload = compose_update.get("classify_decisions") or {}
    flags_out = payload.get("flags") if isinstance(payload, dict) else None

    decisions_by_id: dict[str, _FlagDecision] = {}
    classifier_status = "ok"

    if isinstance(flags_out, list):
        for entry in flags_out:
            if not isinstance(entry, dict):
                continue
            try:
                d = _FlagDecision.model_validate(entry)
            except Exception:
                continue
            decisions_by_id[d.flag_id] = d
        if not decisions_by_id:
            classifier_status = "failed: classifier returned no valid decisions"
    else:
        # Output_schema validation failed and the router fell through to raw text,
        # OR the payload missed the `flags` key.
        preview = ""
        if isinstance(payload, dict) and "raw_text" in payload:
            preview = (payload.get("raw_text") or "")[:300]
        classifier_status = (
            "failed: classifier returned unstructured / malformed output"
            + (f"; first 300 chars: {preview!r}" if preview else "")
        )

    fallback_reason = None
    if classifier_status != "ok":
        fallback_reason = (
            f"classifier output unusable ({classifier_status}); "
            "advisory only — no routing impact"
        )

    annotated = _annotated_pending(
        flagged_input,
        decisions_by_id=decisions_by_id,
        fallback_reason=fallback_reason,
    )

    follow_up = {
        "gate": "gate:animation_map",
        "passed": upstream_passed,
        "violations": upstream_violations,
        "advisory_findings": {**base_advisory, "pending_classify": annotated},
        "classifier_status": classifier_status,
        "iteration": _iteration(state),
        "timestamp": _now(),
        **extras,
    }

    # Drop the noisy LLMNode result_key from the compose namespace — the
    # gate_results record carries the only signal downstream nodes consume.
    update["gate_results"] = [follow_up]
    if isinstance(compose_update, dict):
        compose_update.pop("classify_decisions", None)
    return update
