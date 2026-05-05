"""gate:animation_map — runs the bundled `animation-map.mjs` helper.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks":
`animation-map` enumerates every GSAP timeline tween, samples bounding
boxes at N points per tween, computes per-tween flags
(`paced-fast`, `collision`, …) and composition-level dead zones. Output
is a single JSON file `animation-map.json`.

## Path resolution (bundled-first)

Per memory `feedback_bundled_helper_path`: the helper bootstraps its own
dependencies via ancestor-walk from its location. That works only when
the script lives inside the package's own `node_modules/<skill>/dist/...`
layout. So we prefer the bundled copy under the HF project's
`node_modules/`; only when absent do we fall back to the global
`~/.agents/skills/...` copy and annotate the gate record with
`fallback_helper_used=True` so the operator can see the project should
have its dependencies pinned.

## Pass criteria (v4)

The ticket pins these to the JSON output, derived from canon §
"Quality Checks":

  1. No tween has the `collision` flag.
  2. No tween has the `paced-fast` flag (v4 — the LLM-justify helper
     that would let `paced-fast` be intentional is HOM-77/v5; until
     then ANY paced-fast tween fails).
  3. No `deadZones` entry with `duration > 1.0` (helper only collects
     zones ≥1.0; ticket criterion is strict greater-than).

## Windows bootstrap blocker

Per CLAUDE.md §"Skill copies": both `animation-map.mjs` and
`contrast-report.mjs` bootstrap `@hyperframes/producer` via `npm.cmd`
`spawnSync`, which on Windows-Node yields `EINVAL`. The documented
workaround is a one-time `npm i -D @hyperframes/producer@<v> sharp@<v>`
inside the HF project. When the helper exits with a missing-deps marker
in stderr, this gate parses the package list out of the error and
re-emits an actionable `npm i -D` line as the violation, so the
operator does not have to read the helper's diagnostic by hand.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ._base import Gate, hyperframes_dir


# Helper script paths (relative to roots; joined with appropriate root).
_BUNDLED_REL = Path("node_modules/hyperframes/dist/skills/hyperframes/scripts/animation-map.mjs")
_GLOBAL_FALLBACK = Path.home() / ".agents/skills/hyperframes/scripts/animation-map.mjs"

# Where the helper writes its JSON. Helper default is `.hyperframes/anim-map`
# resolved relative to *cwd*; we pin it under the HF dir explicitly via --out
# so the gate isn't sensitive to the cwd of the calling process.
_OUT_SUBDIR = Path(".hyperframes/anim-map")
_OUT_FILE = "animation-map.json"

# Markers in the helper's stderr that indicate dependency bootstrap failure.
# `package-loader.mjs` emits one of two phrasings depending on whether it
# never tried to install or tried and failed (Windows EINVAL falls in the
# second). Match either.
_MISSING_DEPS_MARKERS = (
    "Could not resolve required package(s)",
    "Required helper package(s) are missing",
    "HyperFrames helper package(s) are missing",
    # Surfaced by the global fallback copy when it has no neighboring
    # package.json from which to pin a version. Verified live on
    # `~/.agents/skills/hyperframes/scripts/package-loader.mjs:51` —
    # the fix is the same "install in the HF project" workaround.
    "Could not determine the bundled HyperFrames version",
)
# Pulled out of the helper's `npm install --save-dev <spec> <spec>` advisory line.
_NPM_INSTALL_LINE = re.compile(
    r"npm install\s+(?:--[\w-]+\s+)*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
# Windows spawn EINVAL marker — the helper's own bootstrap path stderr.
_WINDOWS_EINVAL = re.compile(r"\bEINVAL\b|\bspawnSync\b.*\bnpm", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_helper(hf_dir: Path) -> tuple[Path | None, bool]:
    """Pick the helper script path, preferring the bundled copy.

    Returns `(path, used_fallback)`. `path` is `None` when neither
    location has the script — that's a hard failure.
    """
    bundled = hf_dir / _BUNDLED_REL
    if bundled.is_file():
        return bundled, False
    if _GLOBAL_FALLBACK.is_file():
        return _GLOBAL_FALLBACK, True
    return None, False


def _node_executable() -> str | None:
    return shutil.which("node.exe" if os.name == "nt" else "node") or shutil.which("node")


def _format_npm_workaround(stderr: str) -> str | None:
    """Extract `npm i -D <pkgs>` workaround from helper missing-deps stderr.

    The helper emits a line like `npm install --save-dev <spec> <spec>`
    when it can't resolve dependencies. We rewrite that as `npm i -D`
    (matching the wording in CLAUDE.md §"Skill copies").
    """
    match = _NPM_INSTALL_LINE.search(stderr)
    if not match:
        return None
    specs = match.group(1).strip()
    # `--ignore-scripts --no-save` may sneak in if the line was the bootstrap
    # subcommand rather than the user-facing advisory; drop them.
    specs = re.sub(r"--[\w-]+\s+", "", specs).strip()
    if not specs:
        return None
    return f"npm i -D {specs}"


@dataclass
class _HelperResult:
    exit_code: int
    stdout: str
    stderr: str
    helper_path: Path
    used_fallback: bool
    out_dir: Path


def _run_helper(hf_dir: Path, helper: Path, used_fallback: bool, timeout: float = 240.0) -> _HelperResult | str:
    """Invoke the animation-map helper. Returns _HelperResult on launch
    success (regardless of exit code) or a string violation when node
    isn't reachable at all.
    """
    node = _node_executable()
    if node is None:
        return "node executable not found on PATH — cannot run animation-map helper"

    out_dir = hf_dir / _OUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stale = out_dir / _OUT_FILE
    if stale.is_file():
        try:
            stale.unlink()
        except OSError:
            pass

    cmd = [node, str(helper), str(hf_dir), "--out", str(out_dir)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(hf_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _HelperResult(
            exit_code=124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTIMEOUT after {timeout}s",
            helper_path=helper,
            used_fallback=used_fallback,
            out_dir=out_dir,
        )

    return _HelperResult(
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        helper_path=helper,
        used_fallback=used_fallback,
        out_dir=out_dir,
    )


def _bootstrap_failure_violation(result: _HelperResult, hf_dir: Path) -> str | None:
    """If the helper failed for a missing-deps / Windows-EINVAL reason,
    return a single actionable violation. Otherwise return None.
    """
    blob = result.stderr + "\n" + result.stdout
    is_missing_deps = any(marker in blob for marker in _MISSING_DEPS_MARKERS)
    is_windows_einval = bool(_WINDOWS_EINVAL.search(blob)) and "npm" in blob.lower()
    if not (is_missing_deps or is_windows_einval):
        return None

    workaround = _format_npm_workaround(blob)
    if workaround is None:
        # Fallback to the wording documented in CLAUDE.md.
        workaround = "npm i -D @hyperframes/producer sharp"

    head = (
        "animation-map helper could not bootstrap its dependencies "
        "(see memory feedback_bundled_helper_path — Windows blocker). "
        f"Run inside the HF project ({hf_dir}): "
        f"  {workaround}"
    )
    return head


def _evaluate_report(report: dict) -> list[str]:
    """Apply the three v4 pass criteria to a parsed animation-map.json."""
    violations: list[str] = []
    tweens = report.get("tweens") or []

    collisions: list[str] = []
    paced_fast: list[str] = []
    for tw in tweens:
        flags = tw.get("flags") or []
        sel = tw.get("selector") or f"tween#{tw.get('index')}"
        if "collision" in flags:
            collisions.append(sel)
        if "paced-fast" in flags:
            paced_fast.append(f"{sel} ({tw.get('duration')}s)")

    if collisions:
        violations.append(
            "collision flag(s) on " + ", ".join(collisions)
            + " — overlapping animated elements; refine layout"
        )
    if paced_fast:
        violations.append(
            "paced-fast flag(s) on " + ", ".join(paced_fast)
            + " — at v4 ANY paced-fast fails (LLM-justify deferred to HOM-77/v5)"
        )

    for zone in report.get("deadZones") or []:
        try:
            dur = float(zone.get("duration", 0.0))
        except (TypeError, ValueError):
            dur = 0.0
        if dur > 1.0:
            start = zone.get("start")
            end = zone.get("end")
            violations.append(
                f"dead zone {start}s–{end}s (duration {dur}s > 1.0s) — "
                "no animation; intentional hold or missing entrance?"
            )

    return violations


class AnimationMapGate(Gate):
    """gate:animation_map — bundled-helper invocation with bootstrap triage.

    Overrides `Gate.__call__` so the gate record can carry helper-path
    provenance (`helper_path`, `fallback_helper_used`) without abusing
    the violations list.
    """

    def __init__(self) -> None:
        super().__init__(name="gate:animation_map")

    def _run(self, state: dict) -> tuple[list[str], dict]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot run animation-map"], {}
        if not hf_dir.is_dir():
            return [f"hyperframes dir not on disk: {hf_dir}"], {}

        helper, used_fallback = _resolve_helper(hf_dir)
        if helper is None:
            return [
                "animation-map.mjs not found at bundled path "
                f"{hf_dir / _BUNDLED_REL} or global fallback {_GLOBAL_FALLBACK}"
            ], {}

        extras: dict = {
            "helper_path": str(helper),
            "fallback_helper_used": used_fallback,
        }

        ran = _run_helper(hf_dir, helper, used_fallback)
        if isinstance(ran, str):
            return [ran], extras

        if ran.exit_code != 0:
            bootstrap = _bootstrap_failure_violation(ran, hf_dir)
            if bootstrap is not None:
                return [bootstrap], extras
            tail = (ran.stderr or ran.stdout or "(no output)").strip()
            if len(tail) > 1500:
                tail = tail[:1500] + "\n…(truncated)"
            return [f"animation-map helper exit={ran.exit_code}:\n{tail}"], extras

        report_path = ran.out_dir / _OUT_FILE
        if not report_path.is_file():
            return [
                f"animation-map helper exited 0 but {_OUT_FILE} not found at {report_path}"
            ], extras
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"could not parse {report_path}: {exc}"], extras

        return _evaluate_report(report), extras

    def __call__(self, state: dict) -> dict:
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
        elif extras.get("fallback_helper_used"):
            update["notices"] = [
                f"{self.name}: passed via global fallback helper — "
                "consider pinning @hyperframes/producer + sharp in the HF project"
            ]
        return update


def animation_map_gate_node(state: dict) -> dict:
    return AnimationMapGate()(state)
