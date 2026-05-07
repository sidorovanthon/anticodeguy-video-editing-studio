"""gate:lint — runs `hyperframes lint` against the assembled HF project.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks": the
lint subcommand statically scans `index.html` for known footguns
(repeat:-1 outside seek-driven adapters, missing seek bridges, malformed
hf-seek attributes, etc.). Pass = exit 0.

This gate uses `lint --json` so we can drop findings whose underlying
remedy is blocked upstream and would otherwise hold the pipeline at this
gate forever:

    composition_file_too_large
    timeline_track_too_dense

Both findings recommend splitting `index.html` into sub-compositions
mounted via `data-composition-src`. That mechanism is broken in HF
0.4.41+ (sub-comp loader yields black renders; HF #589 closed without a
fix — see memory `feedback_multi_beat_sub_compositions` and
`feedback_hf_subcomp_loader_data_composition_src`). Until upstream
restores the loader, our orchestrator authors beats inline; the two
findings are advisory and unactionable for us. Real failure modes
(`overlapping_gsap_tweens`, `gsap_repeat_ceil_overshoot`, missing
registry, missing composition-id, etc.) still fail the gate.

If `--json` parsing fails for any reason, the gate falls back to the
prior text-mode behavior so we never silently pass a real lint break.
"""

from __future__ import annotations

import json

from ._base import Gate, hyperframes_dir, run_hf_cli


# Findings we suppress because the canonical remedy (split into
# sub-compositions via data-composition-src) is blocked by HF #589.
_SUPPRESSED_CODES = frozenset(
    {
        "composition_file_too_large",
        "timeline_track_too_dense",
    }
)

# Findings we suppress *only* on files under the per-scene fragments dir
# (`<hf_dir>/compositions/`). p4_beat persists each scene as a `<div>`
# fragment for traceability/replay; the orchestrator inlines those into
# `index.html` via `<!-- beat: ... -->` markers (Pattern A inline mode —
# memories `feedback_hf_pattern_a_vs_b`, `feedback_multi_beat_sub_compositions`).
# HF lint scans every .html in the project and treats each fragment as a
# standalone composition, so it raises `root_missing_composition_id` and
# `missing_timeline_registry` against fragments that geometrically can't
# satisfy those rules — they aren't roots. The same lint rules ARE valid
# against `index.html` and remain unsuppressed there.
_FRAGMENT_ONLY_SUPPRESSED_CODES = frozenset(
    {
        "root_missing_composition_id",
        "missing_timeline_registry",
    }
)
_FRAGMENT_DIR_MARKER = "compositions"


def _format_finding(f: dict) -> str:
    code = f.get("code") or "unknown"
    severity = f.get("severity") or "?"
    message = (f.get("message") or "").strip()
    file_ = f.get("file") or ""
    selector = f.get("selector") or ""
    parts = [f"[{severity}] {code}: {message}"]
    if selector:
        parts.append(f"  selector={selector}")
    if file_:
        parts.append(f"  file={file_}")
    return "\n".join(parts)


def _violations_from_json(payload: object) -> list[str] | None:
    """Convert lint --json payload to violation strings, applying the
    suppression list. Returns None if the payload shape is unexpected so
    the caller can fall back to text mode.
    """
    if not isinstance(payload, dict):
        return None
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return None
    violations: list[str] = []
    for f in findings:
        if not isinstance(f, dict):
            # Malformed entry inside an otherwise-parseable payload: surface
            # it as a violation rather than aborting the whole list. Bailing
            # out (return None) would fall back to text-mode lint, which can
            # exit 0 and silently mask real errors that *were* parseable.
            violations.append(f"[warn] malformed lint finding (not a dict): {f!r}")
            continue
        if f.get("severity") != "error" and f.get("severity") != "warning":
            # info-level: skip (matches HF default behavior without --verbose)
            continue
        if f.get("code") in _SUPPRESSED_CODES:
            continue
        if f.get("code") in _FRAGMENT_ONLY_SUPPRESSED_CODES:
            file_path = (f.get("file") or "").replace("\\", "/")
            if f"/{_FRAGMENT_DIR_MARKER}/" in file_path:
                continue
        violations.append(_format_finding(f))
    return violations


class LintGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:lint")

    def checks(self, state: dict) -> list[str]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot run lint"]
        if not hf_dir.is_dir():
            return [f"hyperframes dir not on disk: {hf_dir}"]

        json_result = run_hf_cli(["lint", "--json"], hf_dir)
        stdout = (json_result.stdout or "").strip()
        if stdout:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = None
            if payload is not None:
                violations = _violations_from_json(payload)
                if violations is not None:
                    return violations

        # Fall back to text mode: re-run without --json so the operator
        # sees CLI output exactly as the binary prints it. We only get
        # here if --json invocation produced unparseable output (CLI
        # crash, npm bootstrap failure, unexpected schema).
        text_result = run_hf_cli(["lint"], hf_dir)
        if text_result.ok:
            return []
        out_tail = (text_result.stdout or "").strip()
        err_tail = (text_result.stderr or "").strip()
        body = out_tail or err_tail or "(no output)"
        if len(body) > 1500:
            body = body[:1500] + "\n…(truncated)"
        return [f"hyperframes lint exit={text_result.exit_code}:\n{body}"]


def lint_gate_node(state: dict) -> dict:
    return LintGate()(state)
