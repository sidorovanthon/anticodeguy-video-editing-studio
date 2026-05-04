"""gate:plan_ok — validates the CompositionPlan produced by p4_plan.

Per spec §4.3 / canon hyperframes SKILL.md §"Step 3: Plan":
  - Plan parseable and not skipped upstream.
  - ≥3 beats. Multi-scene compositions need at least three to carry a
    narrative arc; the schema also enforces this — re-asserted at the
    gate so a schema regression never silently weakens enforcement.
  - Every interior beat boundary has an explicit transition with a
    canonical mechanism (`css` / `shader` / `final-fade` per memory
    `feedback_translucent_transitions`). `final-fade` is only valid as
    the terminal exit on the last beat (canon `references/transitions.md`
    §"Animation Rules" — exit animations BANNED except final scene).
  - Per beat: `catalog_or_custom` set with non-empty `justification`
    (orchestrator-house catalog-scan gate per memory
    `feedback_hf_catalog_orchestrator_gate`).
  - Beat coverage: every EDL beat has a matching `beats[].beat` entry,
    in EDL order. An unmapped or out-of-order beat means downstream beat
    sub-agents will mis-route the EDL ranges.
"""

from __future__ import annotations

from ._base import Gate

_VALID_MECHANISMS = {"css", "shader", "final-fade"}


def _edl_beats(state: dict) -> list[str]:
    edl = (state.get("edit") or {}).get("edl") or {}
    ranges = edl.get("ranges") or []
    seen: list[str] = []
    for r in ranges:
        beat = r.get("beat")
        if beat and beat not in seen:
            seen.append(beat)
    return seen


class PlanOkGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:plan_ok")

    def checks(self, state: dict) -> list[str]:
        violations: list[str] = []
        plan = (state.get("compose") or {}).get("plan") or {}

        if plan.get("skipped"):
            return [f"plan skipped upstream: {plan.get('skip_reason')}"]
        if "raw_text" in plan and "beats" not in plan:
            return ["plan unparseable (raw_text only — schema validation failed upstream)"]

        beats = plan.get("beats") or []
        if len(beats) < 3:
            violations.append(f"beats has {len(beats)} entries; need ≥ 3 for multi-scene narrative")

        # Per-beat catalog-vs-custom justification — orchestrator-house gate.
        for i, beat in enumerate(beats):
            if not isinstance(beat, dict):
                continue
            cat = beat.get("catalog_or_custom")
            just = (beat.get("justification") or "").strip()
            if cat not in {"catalog", "custom"}:
                violations.append(
                    f"beats[{i}] ({beat.get('beat')!r}) catalog_or_custom={cat!r}; "
                    "must be 'catalog' or 'custom'"
                )
            if not just:
                violations.append(
                    f"beats[{i}] ({beat.get('beat')!r}) missing justification — required by "
                    "orchestrator catalog-scan gate"
                )

        transitions = plan.get("transitions") or []
        beat_labels = [b.get("beat") for b in beats if isinstance(b, dict)]

        # Interior boundary coverage: for n beats there are n-1 interior
        # boundaries, each needing a transition. A trailing final-fade exit
        # may also exist (and only on the LAST beat → "END").
        interior_pairs = list(zip(beat_labels, beat_labels[1:])) if len(beat_labels) >= 2 else []
        present_pairs = {
            (t.get("from_beat"), t.get("to_beat"))
            for t in transitions if isinstance(t, dict)
        }
        for src, dst in interior_pairs:
            if (src, dst) not in present_pairs:
                violations.append(
                    f"transitions missing interior boundary {src!r} → {dst!r}"
                )

        for i, t in enumerate(transitions):
            if not isinstance(t, dict):
                continue
            mech = t.get("mechanism")
            if mech not in _VALID_MECHANISMS:
                violations.append(
                    f"transitions[{i}] mechanism={mech!r}; must be one of "
                    f"{sorted(_VALID_MECHANISMS)}"
                )
            # final-fade is only valid as terminal exit on the last beat.
            if mech == "final-fade":
                if not beat_labels:
                    continue
                last = beat_labels[-1]
                if t.get("from_beat") != last:
                    violations.append(
                        f"transitions[{i}] mechanism=final-fade but from_beat="
                        f"{t.get('from_beat')!r}; final-fade is only valid on the last beat "
                        f"(last={last!r}) — canon `references/transitions.md` §Animation Rules"
                    )

        edl_beats = _edl_beats(state)
        if edl_beats:
            missing = [b for b in edl_beats if b not in beat_labels]
            if missing:
                violations.append(
                    f"plan beats missing EDL beats: {missing} (all EDL beats: {edl_beats})"
                )
            elif beat_labels[: len(edl_beats)] != edl_beats:
                violations.append(
                    f"plan beats out of EDL order: plan={beat_labels} edl={edl_beats}"
                )

        return violations


def plan_ok_gate_node(state: dict) -> dict:
    return PlanOkGate()(state)
