"""gate:lint — runs `hyperframes lint` against the assembled HF project.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks": the
lint subcommand statically scans `index.html` for known footguns
(repeat:-1 outside seek-driven adapters, missing seek bridges, malformed
hf-seek attributes, etc.). Pass = exit 0.

This gate is structurally trivial — it shells out, reports the exit code,
and surfaces stderr/stdout as a single violation when the run fails. The
heavy lifting lives in the HF CLI itself; we don't reinterpret its output.
"""

from __future__ import annotations

from ._base import Gate, hyperframes_dir, run_hf_cli


class LintGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:lint")

    def checks(self, state: dict) -> list[str]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot run lint"]
        if not hf_dir.is_dir():
            return [f"hyperframes dir not on disk: {hf_dir}"]

        result = run_hf_cli(["lint"], hf_dir)
        if result.ok:
            return []

        # Surface the meaningful tail of CLI output. lint prints violations
        # to stdout; npm/spawn errors land in stderr. Truncate to keep gate
        # records readable in Studio.
        out_tail = (result.stdout or "").strip()
        err_tail = (result.stderr or "").strip()
        body = out_tail or err_tail or "(no output)"
        if len(body) > 1500:
            body = body[:1500] + "\n…(truncated)"
        return [f"hyperframes lint exit={result.exit_code}:\n{body}"]


def lint_gate_node(state: dict) -> dict:
    return LintGate()(state)
