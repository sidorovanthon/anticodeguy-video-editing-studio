"""gate_animation_map_classify — cheap-tier LLM fix-or-justify classifier (HOM-156).

Reads the gate_animation_map record's ``pending_justifiable`` list and
dispatches a cheap-tier LLM helper that classifies each paced-fast /
paced-slow flag as either ``justify`` (legitimate creative choice — pass)
or ``fix`` (dictation mismatch — redispatch).

Per CLAUDE.md §"Idempotency" + spec
``docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md``:
the LLM dispatch lives in its own graph node so LangGraph's
``cache_policy=`` mechanism applies — re-running the gate cluster
on identical inputs produces zero LLM dispatches. (S1 review fix:
the prior in-gate-body dispatch had ``CACHE_POLICY`` defined but
unreachable — ``SqliteCache`` only fires on whole graph nodes.)

Brief: ``briefs/gate_animation_map_classify.j2`` — references canon
paths, never embeds canon (CLAUDE.md §"Decomposition via
brief-references-canon").

Output: appends a fresh ``gate:animation_map`` record (iteration N+1)
to ``state.gate_results`` with merged classifier decisions:

  * ``violations`` — original always-fix list **plus** flags the
    classifier marked ``fix`` (with the model's reason inlined).
  * ``justifications`` — the ``justify`` decisions, one entry per
    accepted pace flag (Studio reads this for operator visibility).
  * ``passed`` — ``True`` iff merged ``violations`` is empty.

The router (``route_after_animation_map_classify``) reads the new
record and routes accordingly: pass → ``gate_snapshot``;
fail+iter<3 → ``p4_redispatch_beat``; fail+iter≥3 →
``halt_llm_boundary``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langgraph.types import CachePolicy
from pydantic import BaseModel, ConfigDict, Field

from .._caching import make_llm_key, stable_fingerprint
from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
_CACHE_VERSION = 1


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
    compose = state.get("compose") or {}
    hf_dir = compose.get("hyperframes_dir")
    if hf_dir:
        return Path(hf_dir)
    episode_dir = state.get("episode_dir")
    if episode_dir:
        return Path(episode_dir) / "hyperframes"
    return None


def _animation_map_path(state: dict) -> Path | None:
    hf_dir = _hf_dir(state)
    if hf_dir is None:
        return None
    return hf_dir / _OUT_SUBDIR / _OUT_FILE


def _design_md_path(state: dict) -> str:
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


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
    """Most recent gate:animation_map record (the one carrying pending_justifiable)."""
    for record in reversed(state.get("gate_results") or []):
        if record.get("gate") == "gate:animation_map":
            return record
    return None


def _pending_justifiable(state: dict) -> list[dict]:
    record = _latest_animation_map_record(state)
    if not record:
        return []
    return list(record.get("pending_justifiable") or [])


def _render_ctx(state: dict) -> dict:
    anim_path = _animation_map_path(state)
    flagged = _pending_justifiable(state)
    return {
        "animation_map_json_path": str(anim_path) if anim_path else "",
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
      - pending_justifiable fingerprint (``extras=``) — the classifier's
        actual input set, gated by the gate record's pending list.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"gate_animation_map_classify cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    anim_path = _animation_map_path(state)
    compose = state.get("compose") or {}
    return make_llm_key(
        node="gate_animation_map_classify",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            str(anim_path) if anim_path else None,
            compose.get("design_md_path"),
        ],
        extras=(
            stable_fingerprint(_plan_beats(state)),
            stable_fingerprint(_pending_justifiable(state)),
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


def _violation_for(flagged: dict, reason: str) -> str:
    return (
        f"{flagged['flag']} flag on {flagged['selector']} "
        f"(duration {flagged['duration']}s) — fix per LLM classifier: {reason}"
    )


def _iteration(state: dict) -> int:
    prior = [r for r in (state.get("gate_results") or []) if r.get("gate") == "gate:animation_map"]
    return len(prior) + 1


def gate_animation_map_classify_node(state: dict, *, router: BackendRouter | None = None) -> dict:
    """Classify pending pace flags, append a follow-up gate record."""
    record = _latest_animation_map_record(state)
    flagged_input = list((record or {}).get("pending_justifiable") or [])
    base_violations = list((record or {}).get("violations") or [])
    extras: dict = {}
    for k in ("helper_path", "fallback_helper_used"):
        if record and k in record:
            extras[k] = record[k]

    if not flagged_input:
        # Defensive: router should not send us here. Emit a passing record so
        # the router sees a clean state and advances.
        passing_record = {
            "gate": "gate:animation_map",
            "passed": not base_violations,
            "violations": base_violations,
            "iteration": _iteration(state),
            "timestamp": _now(),
            **extras,
        }
        return {"gate_results": [passing_record]}

    node = _build_node()
    try:
        update = node(state, router=router)
    except Exception as exc:  # AllBackendsExhausted etc. — gate must not raise.
        # Surface dispatch failure as a redispatch-routing decision: every
        # pending flag becomes a fix-violation, classifier failure noted.
        violations = list(base_violations)
        violations.append(
            f"animation-map classify dispatch failed: {type(exc).__name__}: {exc}"
        )
        for flagged in flagged_input:
            violations.append(
                f"{flagged['flag']} flag on {flagged['selector']} "
                f"(duration {flagged['duration']}s) — classifier unavailable; "
                "treat as fix until classifier is re-runnable"
            )
        fail_record = {
            "gate": "gate:animation_map",
            "passed": False,
            "violations": violations,
            "iteration": _iteration(state),
            "timestamp": _now(),
            **extras,
        }
        return {"gate_results": [fail_record]}

    compose_update = update.get("compose") or {}
    payload = compose_update.get("classify_decisions") or {}
    flags_out = payload.get("flags") if isinstance(payload, dict) else None

    violations = list(base_violations)
    justifications: list[dict] = []
    decisions_by_id: dict[str, _FlagDecision] = {}

    if isinstance(flags_out, list):
        for entry in flags_out:
            if not isinstance(entry, dict):
                continue
            try:
                d = _FlagDecision.model_validate(entry)
            except Exception:
                continue
            decisions_by_id[d.flag_id] = d
    else:
        # Output_schema validation failed and the router fell through to raw text,
        # OR the payload missed the `flags` key. Treat as classifier failure.
        preview = ""
        if isinstance(payload, dict) and "raw_text" in payload:
            preview = (payload.get("raw_text") or "")[:300]
        violations.append(
            "animation-map classifier returned unstructured / malformed output"
            + (f"; first 300 chars: {preview!r}" if preview else "")
        )

    for flagged in flagged_input:
        d = decisions_by_id.get(flagged["flag_id"])
        if d is None:
            violations.append(
                f"{flagged['flag']} flag on {flagged['selector']} "
                f"(duration {flagged['duration']}s) — classifier returned no "
                f"decision for flag_id={flagged['flag_id']!r}"
            )
            continue
        if d.decision == "fix":
            violations.append(_violation_for(flagged, d.reason))
        else:
            justifications.append({
                "flag_id": flagged["flag_id"],
                "selector": flagged["selector"],
                "flag": flagged["flag"],
                "duration": flagged["duration"],
                "reason": d.reason,
            })

    follow_up = {
        "gate": "gate:animation_map",
        "passed": not violations,
        "violations": violations,
        "iteration": _iteration(state),
        "timestamp": _now(),
        **extras,
    }
    if justifications:
        follow_up["justifications"] = justifications

    # Drop the noisy LLMNode result_key from the compose namespace — the
    # gate_results record carries the only signal downstream nodes consume.
    update["gate_results"] = [follow_up]
    if isinstance(compose_update, dict):
        compose_update.pop("classify_decisions", None)
    return update
