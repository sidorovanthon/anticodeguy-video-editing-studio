"""gate:animation_map — runs the bundled `animation-map.mjs` helper, parses
the report, classifies flags into always-fix vs. justifiable buckets.

Per canon `~/.agents/skills/hyperframes/SKILL.md` §"Quality Checks":
`animation-map` enumerates every GSAP timeline tween, samples bounding
boxes at N points per tween, computes per-tween flags
(`paced-fast`, `paced-slow`, `collision`, `degenerate`, `offscreen`,
`invisible`) and composition-level dead zones. Output is a single JSON
file `animation-map.json`.

## Path resolution (bundled-first)

Per memory `feedback_bundled_helper_path`: the helper bootstraps its own
dependencies via ancestor-walk from its location. That works only when
the script lives inside the package's own `node_modules/<skill>/dist/...`
layout. So we prefer the bundled copy under the HF project's
`node_modules/`; only when absent do we fall back to the global
`~/.agents/skills/...` copy and annotate the gate record with
`fallback_helper_used=True` so the operator can see the project should
have its dependencies pinned.

## Pass criteria — fix-or-justify split (HOM-156)

Canon (SKILL.md §"Quality Checks" §"Animation Map", lines 384-385):
> "Read the JSON. Scan summaries for anything unexpected. **Check every
>  flag — fix or justify.** Verify the timeline shows the intended
>  choreography rhythm. Re-run after fixes."

Two flag classes:

- **Always-fix** — never legitimate; recorded as violations directly:
  * `collision` (overlapping animated elements)
  * `degenerate` (zero-size bbox throughout)
  * `offscreen` (off-canvas throughout)
  * `invisible` (zero opacity throughout)
  * `deadZones` with `duration > 1.0`.

- **Justifiable** — `paced-fast` (≤ 0.2s) and `paced-slow` (> 2.0s) flags
  may be intentional creative choices (high-energy slam vs. sustained
  ambient drift). They are NOT classified inside the gate; instead the
  gate records them in the gate record's ``pending_justifiable`` list,
  and the routing layer sends the run to the dedicated
  ``gate_animation_map_classify`` LLM node, whose result merges back
  into a follow-up gate record.

The deterministic gate **never calls an LLM**. The LLM dispatch lives
in ``nodes/gate_animation_map_classify.py`` so LangGraph's
``cache_policy=`` mechanism can apply (CLAUDE.md §"Idempotency" — re-run
on identical inputs produces zero LLM dispatches).

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

from .._caching import make_key
from ._base import Gate, hyperframes_dir


# Bump on brief / schema / pass-criteria change. See HOM-132 spec §8.
# v3 = HOM-156 review-fix: gate is purely deterministic; LLM-justify dispatch
#   moved to nodes/gate_animation_map_classify.py (its own _CACHE_VERSION).
_CACHE_VERSION = 3


# Helper script paths (relative to roots; joined with appropriate root).
_BUNDLED_REL = Path("node_modules/hyperframes/dist/skills/hyperframes/scripts/animation-map.mjs")
_GLOBAL_FALLBACK = Path.home() / ".agents/skills/hyperframes/scripts/animation-map.mjs"

# Where the helper writes its JSON. Helper default is `.hyperframes/anim-map`
# resolved relative to *cwd*; we pin it under the HF dir explicitly via --out
# so the gate isn't sensitive to the cwd of the calling process.
_OUT_SUBDIR = Path(".hyperframes/anim-map")
_OUT_FILE = "animation-map.json"

# Markers in the helper's stderr that indicate dependency bootstrap failure.
_MISSING_DEPS_MARKERS = (
    "Could not resolve required package(s)",
    "Required helper package(s) are missing",
    "HyperFrames helper package(s) are missing",
    "Could not determine the bundled HyperFrames version",
)
_NPM_INSTALL_LINE = re.compile(
    r"npm install\s+(?:--[\w-]+\s+)*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
_WINDOWS_EINVAL = re.compile(r"\bEINVAL\b|\bspawnSync\b.*\bnpm", re.IGNORECASE)

# Flags the LLM-classify node is allowed to triage. Anything else stays
# in the always-fix set and never reaches the helper.
_JUSTIFIABLE_FLAGS = ("paced-fast", "paced-slow")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_helper(hf_dir: Path) -> tuple[Path | None, bool]:
    bundled = hf_dir / _BUNDLED_REL
    if bundled.is_file():
        return bundled, False
    if _GLOBAL_FALLBACK.is_file():
        return _GLOBAL_FALLBACK, True
    return None, False


def _node_executable() -> str | None:
    return shutil.which("node.exe" if os.name == "nt" else "node") or shutil.which("node")


def _format_npm_workaround(stderr: str) -> str | None:
    match = _NPM_INSTALL_LINE.search(stderr)
    if not match:
        return None
    specs = match.group(1).strip()
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
    except FileNotFoundError as exc:
        return _HelperResult(
            exit_code=127,
            stdout="",
            stderr=f"node executable not found at runtime: {exc}",
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
    blob = result.stderr + "\n" + result.stdout
    is_missing_deps = any(marker in blob for marker in _MISSING_DEPS_MARKERS)
    is_windows_einval = bool(_WINDOWS_EINVAL.search(blob)) and "npm" in blob.lower()
    if not (is_missing_deps or is_windows_einval):
        return None

    workaround = _format_npm_workaround(blob)
    if workaround is None:
        workaround = "npm i -D @hyperframes/producer sharp"

    head = (
        "animation-map helper could not bootstrap its dependencies "
        "(see memory feedback_bundled_helper_path — Windows blocker). "
        f"Run inside the HF project ({hf_dir}): "
        f"  {workaround}"
    )
    return head


# ---------------------------------------------------------------------------
# Flag extraction
# ---------------------------------------------------------------------------


def _flag_id(selector: str, idx: int, flag: str) -> str:
    sel = selector or f"tween#{idx}"
    return f"{sel}::{idx}::{flag}"


def _extract_flags(report: dict) -> tuple[list[str], list[dict], list[dict]]:
    """Split helper output into (always_fix_violations, justifiable_flags, dead_zone_violations)."""
    always_fix: list[str] = []
    justifiable: list[dict] = []

    tweens = report.get("tweens") or []
    collisions: list[str] = []
    degenerate: list[str] = []
    offscreen: list[str] = []
    invisible: list[str] = []

    for tw in tweens:
        flags = tw.get("flags") or []
        idx = tw.get("index")
        sel = tw.get("selector") or f"tween#{idx}"
        duration = tw.get("duration")
        if "collision" in flags:
            collisions.append(sel)
        if "degenerate" in flags:
            degenerate.append(sel)
        if "offscreen" in flags:
            offscreen.append(sel)
        if "invisible" in flags:
            invisible.append(sel)
        for flag in _JUSTIFIABLE_FLAGS:
            if flag in flags:
                justifiable.append({
                    "flag_id": _flag_id(sel, idx if isinstance(idx, int) else -1, flag),
                    "selector": sel,
                    "flag": flag,
                    "duration": duration,
                    "index": idx,
                })

    if collisions:
        always_fix.append(
            "collision flag(s) on " + ", ".join(collisions)
            + " — overlapping animated elements; refine layout"
        )
    if degenerate:
        always_fix.append(
            "degenerate flag(s) on " + ", ".join(degenerate)
            + " — zero-size bbox throughout; element never renders"
        )
    if offscreen:
        always_fix.append(
            "offscreen flag(s) on " + ", ".join(offscreen)
            + " — element off-canvas throughout the tween"
        )
    if invisible:
        always_fix.append(
            "invisible flag(s) on " + ", ".join(invisible)
            + " — zero opacity throughout the tween"
        )

    dead_zone_violations: list[str] = []
    for zone in report.get("deadZones") or []:
        try:
            dur = float(zone.get("duration", 0.0))
        except (TypeError, ValueError):
            dur = 0.0
        if dur > 1.0:
            start = zone.get("start")
            end = zone.get("end")
            dead_zone_violations.append(
                f"dead zone {start}s–{end}s (duration {dur}s > 1.0s) — "
                "no animation; intentional hold or missing entrance?"
            )

    return always_fix, justifiable, dead_zone_violations


# ---------------------------------------------------------------------------
# Cache key — exposed for the L0 fingerprint-invalidation registry only.
#
# The gate is intentionally NOT bound to a `cache_policy=` in graph.py: the
# deterministic helper subprocess (animation-map.mjs) is fast enough that
# always re-running it on each gate visit is cheaper than fingerprint I/O,
# AND we want every gate-cluster iteration to re-detect flags after a
# p4_redispatch_beat re-author (caching would skip that). The LLM dispatch
# that actually justifies caching lives in
# `nodes/gate_animation_map_classify.py`, where it has its own
# `CACHE_POLICY` wired via `g.add_node(... cache_policy=...)`.
# ---------------------------------------------------------------------------


def _gate_cache_key(state, *_args, **_kwargs):
    """Deterministic cache key for gate_animation_map (post-helper-run)."""
    if not isinstance(state, dict):
        raise TypeError(
            f"animation_map gate cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    hf_dir = compose.get("hyperframes_dir")
    if not hf_dir:
        episode_dir = state.get("episode_dir")
        hf_dir = str(Path(episode_dir) / "hyperframes") if episode_dir else ""
    animation_map_path = (
        Path(hf_dir) / _OUT_SUBDIR / _OUT_FILE if hf_dir else None
    )
    return make_key(
        node="gate_animation_map",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            str(animation_map_path) if animation_map_path else None,
        ],
    )


_cache_key = _gate_cache_key  # alias for the fingerprint registry


class AnimationMapGate(Gate):
    """gate:animation_map — bundled-helper invocation + flag classification.

    Overrides `Gate.__call__` so the gate record can carry helper-path
    provenance (`helper_path`, `fallback_helper_used`) and the list of
    `pending_justifiable` flag dicts that the
    `gate_animation_map_classify` LLM node will triage downstream.

    Records `passed=False` whenever there are always-fix violations OR
    pending justifiable flags. The router (`route_after_animation_map`)
    distinguishes the two: pending-only ⇒ classify; violations present
    or no pending ⇒ existing pass/fail routing.
    """

    def __init__(self) -> None:
        super().__init__(name="gate:animation_map")

    def _run(self, state: dict) -> tuple[list[str], list[dict], dict]:
        """Returns `(violations, pending_justifiable, extras)`.

        `pending_justifiable` is a list of flag dicts to be classified by
        the `gate_animation_map_classify` LLM node downstream. The gate
        itself never dispatches an LLM.
        """
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot run animation-map"], [], {}
        if not hf_dir.is_dir():
            return [f"hyperframes dir not on disk: {hf_dir}"], [], {}

        helper, used_fallback = _resolve_helper(hf_dir)
        if helper is None:
            return [
                "animation-map.mjs not found at bundled path "
                f"{hf_dir / _BUNDLED_REL} or global fallback {_GLOBAL_FALLBACK}"
            ], [], {}

        extras: dict = {
            "helper_path": str(helper),
            "fallback_helper_used": used_fallback,
        }

        ran = _run_helper(hf_dir, helper, used_fallback)
        if isinstance(ran, str):
            return [ran], [], extras

        if ran.exit_code != 0:
            bootstrap = _bootstrap_failure_violation(ran, hf_dir)
            if bootstrap is not None:
                return [bootstrap], [], extras
            tail = (ran.stderr or ran.stdout or "(no output)").strip()
            if len(tail) > 1500:
                tail = tail[:1500] + "\n…(truncated)"
            return [f"animation-map helper exit={ran.exit_code}:\n{tail}"], [], extras

        report_path = ran.out_dir / _OUT_FILE
        if not report_path.is_file():
            return [
                f"animation-map helper exited 0 but {_OUT_FILE} not found at {report_path}"
            ], [], extras
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"could not parse {report_path}: {exc}"], [], extras

        always_fix, justifiable, dead_zone_violations = _extract_flags(report)
        violations = list(always_fix) + list(dead_zone_violations)
        return violations, justifiable, extras

    def __call__(self, state: dict) -> dict:
        violations, pending_justifiable, extras = self._run(state)
        # `passed` reflects the deterministic surface only:
        # - violations present  → False (always-fix or dead-zone fired)
        # - violations empty AND pending_justifiable empty → True
        # - violations empty AND pending_justifiable non-empty → False
        #   (route to classifier; a follow-up gate record after classify
        #   may then mark passed=True if the LLM justifies all flags)
        passed = not violations and not pending_justifiable
        record = {
            "gate": self.name,
            "passed": passed,
            "violations": violations,
            "iteration": self._iteration(state),
            "timestamp": _now(),
            **extras,
        }
        if pending_justifiable:
            record["pending_justifiable"] = pending_justifiable
        update: dict = {"gate_results": [record]}
        if violations:
            update["notices"] = [
                f"{self.name}: FAILED ({len(violations)} violation(s)) — see gate_results"
            ]
        elif pending_justifiable and extras.get("fallback_helper_used"):
            update["notices"] = [
                f"{self.name}: {len(pending_justifiable)} pace-flag(s) pending LLM "
                "classification (via global fallback helper) — "
                "consider pinning @hyperframes/producer + sharp in the HF project"
            ]
        elif pending_justifiable:
            update["notices"] = [
                f"{self.name}: {len(pending_justifiable)} pace-flag(s) pending LLM "
                "classification — gate_animation_map_classify dispatches next"
            ]
        elif extras.get("fallback_helper_used"):
            update["notices"] = [
                f"{self.name}: passed via global fallback helper — "
                "consider pinning @hyperframes/producer + sharp in the HF project"
            ]
        return update


def animation_map_gate_node(state: dict) -> dict:
    return AnimationMapGate()(state)
