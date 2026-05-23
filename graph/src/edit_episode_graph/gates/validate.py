"""gate:validate — runs `hyperframes validate` with opacity-0 headless triage.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks":
`validate` runs schema + WCAG contrast checks via a headless browser. Pass
= exit 0.

## Why the opacity-0 triage exists

The headless WCAG check captures one static frame. Elements that *enter*
the timeline with `fromTo({opacity: 0}, {opacity: 1})` (a near-universal
HF entrance pattern) are still at opacity 0 when that frame is captured,
so their text contrast is computed against an invisible body — which the
WCAG sampler sees as black-on-background and routinely flags as failing
even though at any non-entrance timestamp the contrast is fine.

Iterating the DESIGN.md palette in response to that false fail is the
documented anti-pattern (memory `feedback_wcag_headless_opacity_artifact`).

So when `validate` fails, this gate inspects `index.html` for the
opacity-0 entrance pattern and the validate output for WCAG/contrast
markers. If both are present, the failure is annotated as a headless
artifact and the gate passes with a `headless_artifact_suspected` note in
its record. Real schema failures or non-contrast WCAG violations still
fail loudly.

The triage is structural — a regex over `index.html`, not a re-render —
so it cannot itself trigger a palette-iteration loop.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..nodes._materialize_tmpdir import materialize_into_tmpdir
from ._base import Gate, CliResult, run_hf_cli

# Markers that the validate failure is contrast/WCAG-related rather than
# a structural schema failure. Lower-cased; matched case-insensitively.
_WCAG_MARKERS = ("wcag", "contrast", "luminance", "a11y", "accessibility")

# Heuristic regex for the GSAP opacity-0 entrance pattern. Scoped to
# call sites — `fromTo(..., { opacity: 0 }, ...)` or `.from({ opacity: 0 })`
# — so a permanently-hidden element with static `style="opacity: 0"`
# does NOT mask a real WCAG failure on its (correctly-flagged) zero
# alpha. Per memory feedback_wcag_headless_opacity_artifact the
# documented artifact is specifically about entrance animations, not
# arbitrary opacity:0 elements.
_OPACITY_ZERO_ENTRANCE = re.compile(
    r"(?:fromTo|\.from)\s*\([^)]*opacity\s*:\s*0",
    re.IGNORECASE | re.DOTALL,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_opacity_zero_entrance(state: dict) -> bool:
    """True if `index.html` body in state contains the opacity-0 entrance pattern.

    Deliberately conservative: presence of *any* `opacity: 0` is enough
    to suspect headless artifact. The downside of a false positive here
    is at most one missed real WCAG fail; the upside is we never
    accidentally trigger palette iteration on the documented artifact.

    HOM-278 (Class A): state-first read. Under HOM-239 the assembled
    index.html body lives in ``state.compose.index_html`` and is
    written to disk later by ``p4_materialize_disk_node``. Reading
    from disk here would race the materializer; read from state.
    """
    compose = state.get("compose") or {}
    html = compose.get("index_html")
    if not isinstance(html, str) or not html:
        return False
    return bool(_OPACITY_ZERO_ENTRANCE.search(html))


def _looks_like_wcag_failure(result: CliResult) -> bool:
    blob = ((result.stdout or "") + "\n" + (result.stderr or "")).lower()
    return any(marker in blob for marker in _WCAG_MARKERS)


def _format_violation(result: CliResult) -> str:
    out_tail = (result.stdout or "").strip()
    err_tail = (result.stderr or "").strip()
    body = out_tail or err_tail or "(no output)"
    if len(body) > 1500:
        body = body[:1500] + "\n…(truncated)"
    return f"hyperframes validate exit={result.exit_code}:\n{body}"


class ValidateGate(Gate):
    """gate:validate with structural opacity-0 headless triage.

    Overrides `Gate.__call__` rather than just `checks` so the triage can
    add a `headless_artifact_suspected` annotation onto the gate_results
    record without using the violations list as a side channel.
    """

    def __init__(self) -> None:
        super().__init__(name="gate:validate")

    def _run(self, state: dict) -> tuple[list[str], dict]:
        """Return (violations, extra_record_fields)."""
        slug = state.get("slug")
        if not slug:
            return ["no slug in state — cannot materialize HF tmpdir for validate"], {}
        try:
            hf_dir = materialize_into_tmpdir(state, slug=slug)
        except RuntimeError as exc:
            return [f"materialize_into_tmpdir failed: {exc}"], {}

        result = run_hf_cli(["validate"], hf_dir)
        if result.ok:
            return [], {}

        if _looks_like_wcag_failure(result) and _has_opacity_zero_entrance(state):
            return [], {
                "headless_artifact_suspected": True,
                "annotation": (
                    "validate exit non-zero with WCAG/contrast markers; "
                    "index.html contains opacity:0 entrance pattern. "
                    "Treating as headless screenshot artifact per "
                    "memory feedback_wcag_headless_opacity_artifact — "
                    "do NOT iterate DESIGN.md palette in response."
                ),
                "validate_exit_code": result.exit_code,
            }

        return [_format_violation(result)], {}

    def __call__(self, state: dict) -> dict:
        # HOM-334 Phase A.5: step-debug pre/post interrupts around the
        # validate gate. The subclass overrides ``Gate.__call__`` so the
        # base-class wrap doesn't apply — wire it explicitly here.
        # No-op when ``HOMESTUDIO_STEP_DEBUG`` is unset.
        from .._step_debug import is_enabled as _sd_enabled, wrap_deterministic_node

        if _sd_enabled():
            return wrap_deterministic_node(
                self.name.replace(":", "_"),
                state=state,
                context={
                    "slug": state.get("slug") if isinstance(state, dict) else None,
                    "gate_name": self.name,
                    "iteration": self._iteration(state),
                },
                inner=lambda: self._invoke_body(state),
            )
        return self._invoke_body(state)

    def _invoke_body(self, state: dict) -> dict:
        violations, extras = self._run(state)
        passed = not violations
        record = {
            "gate": self.name,
            "passed": passed,
            "violations": violations,
            "iteration": self._iteration(state),
            "timestamp": _now(),
            **extras,
        }
        update: dict = {"gate_results": [record]}
        if not passed:
            update["notices"] = [
                f"{self.name}: FAILED ({len(violations)} violation(s)) — see gate_results"
            ]
        elif extras.get("headless_artifact_suspected"):
            update["notices"] = [
                f"{self.name}: passed with headless_artifact_suspected — "
                "do not iterate palette"
            ]
        return update


def validate_gate_node(state: dict) -> dict:
    return ValidateGate()(state)
