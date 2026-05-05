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

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hyperframes_dir(state: dict) -> Path | None:
    """Resolve the HF project root for the current episode.

    Mirrors the convention used by Phase 4 nodes: prefer
    `state.compose.hyperframes_dir`; fall back to `<episode_dir>/hyperframes`.
    """
    compose = state.get("compose") or {}
    hf_dir = compose.get("hyperframes_dir")
    if hf_dir:
        return Path(hf_dir)
    episode_dir = state.get("episode_dir")
    if episode_dir:
        return Path(episode_dir) / "hyperframes"
    return None


@dataclass
class CliResult:
    """Outcome of a hyperframes CLI subprocess invocation."""

    cmd: list[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    used_bundled_cli: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def _bundled_hf_cli(hf_dir: Path) -> Path | None:
    """Return path to the project-bundled hyperframes CLI binary, if present.

    Looks for `<hf_dir>/node_modules/.bin/hyperframes` (POSIX) or
    `hyperframes.cmd` (Windows). Per memory `feedback_bundled_helper_path`,
    the bundled copy is preferred for helpers that bootstrap sibling deps.
    """
    bin_dir = hf_dir / "node_modules" / ".bin"
    candidates = ["hyperframes.cmd", "hyperframes"] if os.name == "nt" else ["hyperframes"]
    for name in candidates:
        p = bin_dir / name
        if p.is_file():
            return p
    return None


def run_hf_cli(
    args: Sequence[str],
    hf_dir: Path,
    timeout: float = 120.0,
    extra_env: dict[str, str] | None = None,
) -> CliResult:
    """Run a hyperframes CLI subcommand inside an HF project directory.

    Prefers the project-bundled CLI under `<hf_dir>/node_modules/.bin/`;
    falls back to `npx hyperframes` on PATH. The HF project itself is the
    cwd — every subcommand we use (lint/validate/inspect/snapshot) reads
    `index.html` relative to cwd.
    """
    bundled = _bundled_hf_cli(hf_dir)
    if bundled is not None:
        cmd = [str(bundled), *args]
        used_bundled = True
    else:
        npx = "npx.cmd" if os.name == "nt" else "npx"
        if shutil.which(npx) is None:
            return CliResult(
                cmd=[npx, "hyperframes", *args],
                cwd=str(hf_dir),
                exit_code=127,
                stdout="",
                stderr=f"{npx} not found on PATH and no bundled CLI under {hf_dir}/node_modules/.bin",
                used_bundled_cli=False,
            )
        cmd = [npx, "hyperframes", *args]
        used_bundled = False

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(hf_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CliResult(
            cmd=list(cmd),
            cwd=str(hf_dir),
            exit_code=124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTIMEOUT after {timeout}s",
            used_bundled_cli=used_bundled,
        )
    except FileNotFoundError as exc:
        return CliResult(
            cmd=list(cmd),
            cwd=str(hf_dir),
            exit_code=127,
            stdout="",
            stderr=f"executable not found: {exc}",
            used_bundled_cli=used_bundled,
        )

    return CliResult(
        cmd=list(cmd),
        cwd=str(hf_dir),
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        used_bundled_cli=used_bundled,
    )


def parse_cli_json(result: CliResult) -> tuple[object | None, str | None]:
    """Parse a CLI result's stdout as JSON.

    Returns `(payload, None)` on success, `(None, error_message)` on failure.
    On non-zero exit, the stderr tail is folded into the error so the gate's
    violation list shows what actually went wrong instead of a bare
    "JSONDecodeError".
    """
    text = (result.stdout or "").strip()
    if not text:
        tail = (result.stderr or "").strip().splitlines()[-3:]
        return None, "empty stdout from CLI" + (
            f"; stderr tail: {' | '.join(tail)}" if tail else ""
        )
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        preview = text[:200].replace("\n", "\\n")
        return None, f"stdout was not valid JSON ({exc.msg}); first 200 chars: {preview!r}"


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
