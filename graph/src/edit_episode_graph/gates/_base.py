"""Gate base — class-2 nodes (artifact validation between phases) per spec §6.2.

A gate is a pure function: state in, decision + state-update out. It
appends one record to `state["gate_results"]` per invocation:

    {"gate": <name>, "passed": <bool>, "violations": [str],
     "iteration": <int>, "timestamp": <iso>}

Routing decisions live on conditional edges that read the latest
`gate_results` entry for the gate's name. A gate does NOT raise; failures
are visible state, not exceptions, so Studio can render the violation
list and an operator can decide.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Gate:
    name: str
    max_iterations: int = 3

    def checks(self, state: dict) -> list[str]:
        """Return a list of violation strings. Empty list = passed."""
        raise NotImplementedError

    def _iteration(self, state: dict) -> int:
        prior = [r for r in (state.get("gate_results") or []) if r.get("gate") == self.name]
        return len(prior) + 1

    def __call__(self, state: dict) -> dict:
        violations = list(self.checks(state))
        passed = not violations
        record = {
            "gate": self.name,
            "passed": passed,
            "violations": violations,
            "iteration": self._iteration(state),
            "timestamp": _now(),
        }
        update: dict = {"gate_results": [record]}
        if not passed:
            update["notices"] = [
                f"{self.name}: FAILED ({len(violations)} violation(s)) — see gate_results"
            ]
        return update


def latest_gate_result(state: dict, name: str) -> dict | None:
    for record in reversed(state.get("gate_results") or []):
        if record.get("gate") == name:
            return record
    return None
