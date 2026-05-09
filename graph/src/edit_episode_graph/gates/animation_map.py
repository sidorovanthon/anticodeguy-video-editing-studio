"""gate:animation_map — runs the bundled `animation-map.mjs` helper, then
classifies pace-flags as fix-or-justify via a cheap-tier LLM helper (HOM-156).

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

## Pass criteria (v5 — HOM-156 fix-or-justify)

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
  * `deadZones` with `duration > 1.0` (helper only collects ≥1.0s; the
    strict-greater-than threshold matches the v4 ticket).

- **Justifiable** — `paced-fast` (≤ 0.2s) and `paced-slow` (> 2.0s) flags
  may be intentional creative choices (high-energy slam vs. sustained
  ambient drift). When present, the gate dispatches a cheap-tier LLM
  helper (`briefs/gate_animation_map_justify.j2`) that reads the
  animation-map JSON + DESIGN.md + the plan beats and returns per-flag
  `{decision: "justify"|"fix", reason}`. Justified flags are recorded
  under `gate_results[*].justifications`; fix decisions become regular
  violations and route to `p4_redispatch_beat`.

When the justifiable set is empty, the LLM helper is skipped entirely —
the gate stays cheap on the happy path.

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

from langgraph.types import CachePolicy
from pydantic import BaseModel, ConfigDict, Field

from .._caching import make_llm_key, stable_fingerprint
from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..nodes._llm import LLMNode, _load_brief
from ._base import Gate, hyperframes_dir


# Bump on brief / schema / tool-list / pass-criteria change. See HOM-132 spec §8.
# v2 = HOM-156 fix-or-justify semantics replaces v4 strict paced-fast fail.
_CACHE_VERSION = 2


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

# Flags the LLM-justify helper is allowed to classify. Anything else stays
# in the always-fix set and never reaches the helper.
_JUSTIFIABLE_FLAGS = ("paced-fast", "paced-slow")


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
    except FileNotFoundError as exc:
        # Mirrors `_base.run_hf_cli`: gates must never raise — record a
        # structured failure instead. Reachable when `shutil.which` found
        # node but it disappeared (or when a Windows `.cmd` shim lookup
        # raced a path mutation).
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


# ---------------------------------------------------------------------------
# Flag extraction + LLM-justify dispatch (HOM-156)
# ---------------------------------------------------------------------------


def _flag_id(selector: str, idx: int, flag: str) -> str:
    """Stable id for a single flagged tween-flag pair.

    The selector alone is not unique (one element can carry multiple flags
    across multiple tweens); pairing with the helper's `index` keeps it
    one-to-one with the JSON, and including the flag name lets the helper
    output map back unambiguously when a single tween carries both
    paced-fast and paced-slow (rare but possible across siblings).
    """
    sel = selector or f"tween#{idx}"
    return f"{sel}::{idx}::{flag}"


def _extract_flags(report: dict) -> tuple[list[str], list[dict], list[dict]]:
    """Split helper output into (always_fix_violations, justifiable_flags, dead_zone_violations).

    Returns:
      always_fix_violations — strings ready to drop into `record["violations"]`
        (collisions, degenerate, offscreen, invisible).
      justifiable_flags — list of `{flag_id, selector, flag, duration, index}`
        dicts, one per paced-fast / paced-slow tween — input to the LLM helper.
      dead_zone_violations — strings, one per dead-zone with duration > 1.0s
        (these are always-fix and never go through the LLM).
    """
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
# LLM-justify helper — cheap tier, structured-JSON output, Read-only tools.
# ---------------------------------------------------------------------------


class _FlagDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str = Field(min_length=1, description="Stable id from flagged_tweens input.")
    decision: str = Field(
        pattern=r"^(justify|fix)$",
        description="`justify` if intentional creative choice; `fix` otherwise.",
    )
    reason: str = Field(
        min_length=1,
        description="One sentence citing the beat label and energy/mood that justifies, "
                    "or the specific mismatch that requires a fix.",
    )


class _JustifyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flags: list[_FlagDecision] = Field(
        description="One decision per flagged tween, in the same order as the input.",
    )


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


def _justify_render_ctx(animation_map_path: Path, flagged: list[dict]):
    """Closure factory — captures the per-call animation-map path + flagged set.

    The brief renders these as `{{ animation_map_json_path }}`,
    `{{ design_md_path }}`, `{{ plan_beats_json }}`, `{{ flagged_tweens_json }}`.
    """

    def _ctx(state: dict) -> dict:
        return {
            "animation_map_json_path": str(animation_map_path),
            "design_md_path": _design_md_path(state),
            "plan_beats_json": json.dumps(_plan_beats(state), ensure_ascii=False),
            "flagged_tweens_json": json.dumps(flagged, ensure_ascii=False),
        }

    return _ctx


def _justify_cache_key(state, *_args, **_kwargs):
    """Cache key for the LLM-justify helper.

    HOM-157: `make_llm_key` auto-prepends a `cfg:<sha>` extra so a
    `graph/config.yaml` bump on this node invalidates without manual cache
    wipe. We additionally bake in:
      - the animation-map.json content hash (`files=`) — different flags
        ⇒ different decision space.
      - DESIGN.md content hash (`files=`) — different visual identity
        ⇒ different justification surface.
      - plan beats fingerprint (`extras=`) — beats live in-memory on
        `state.compose.plan`, not on disk.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"animation_map_justify cache key requires dict state, got {type(state).__name__}"
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
    return make_llm_key(
        node="gate_animation_map_justify",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            str(animation_map_path) if animation_map_path else None,
            compose.get("design_md_path"),
        ],
        extras=(stable_fingerprint(_plan_beats(state)),),
    )


# Exposed for `graph.py` cache wiring AND for tests/_helpers/fingerprint_assertions.py.
CACHE_POLICY = CachePolicy(key_func=_justify_cache_key)
_cache_key = _justify_cache_key  # alias for the fingerprint registry


def _build_justify_node(animation_map_path: Path, flagged: list[dict]) -> LLMNode:
    return LLMNode(
        name="gate_animation_map_justify",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("gate_animation_map_justify"),
        output_schema=_JustifyOutput,
        result_namespace="compose",
        result_key="_animation_map_justify_unused",
        timeout_s=120,
        allowed_tools=["Read"],
        extra_render_ctx=_justify_render_ctx(animation_map_path, flagged),
    )


def _dispatch_justify(
    state: dict,
    *,
    animation_map_path: Path,
    flagged: list[dict],
    router: BackendRouter | None,
) -> tuple[dict[str, _FlagDecision], list[str]]:
    """Run the LLM-justify helper and parse its output.

    Returns `(decisions_by_flag_id, helper_errors)` — `helper_errors` is
    populated when the dispatch fails or returns a malformed payload, so
    the gate can record a hard violation instead of silently passing.
    """
    node = _build_justify_node(animation_map_path, flagged)
    try:
        update = node(state, router=router)
    except Exception as exc:  # AllBackendsExhausted etc. — gate must not raise.
        return {}, [
            f"animation-map justify dispatch failed: {type(exc).__name__}: {exc}"
        ]

    compose_update = update.get("compose") or {}
    payload = compose_update.get("_animation_map_justify_unused") or {}
    if isinstance(payload, dict) and "raw_text" in payload:
        # output_schema validation failed and the router fell through to
        # raw text — treat as a hard error.
        preview = (payload.get("raw_text") or "")[:300]
        return {}, [
            "animation-map justify helper returned unstructured output; "
            f"first 300 chars: {preview!r}"
        ]
    flags_out = payload.get("flags") if isinstance(payload, dict) else None
    if not isinstance(flags_out, list):
        return {}, [
            "animation-map justify helper output missing 'flags' list "
            f"(got {type(flags_out).__name__})"
        ]
    decisions: dict[str, _FlagDecision] = {}
    for entry in flags_out:
        if not isinstance(entry, dict):
            continue
        try:
            decision = _FlagDecision.model_validate(entry)
        except Exception:
            continue
        decisions[decision.flag_id] = decision
    return decisions, []


class AnimationMapGate(Gate):
    """gate:animation_map — bundled-helper invocation + LLM-justify classifier.

    Overrides `Gate.__call__` so the gate record can carry helper-path
    provenance (`helper_path`, `fallback_helper_used`), the cheap-tier
    LLM justifications (`justifications`), and the brief's input
    fingerprint (so reviewers can see why we did or didn't dispatch).
    """

    def __init__(self, *, router: BackendRouter | None = None) -> None:
        super().__init__(name="gate:animation_map")
        self._router = router

    def _run(self, state: dict) -> tuple[list[str], list[dict], dict]:
        """Returns `(violations, justifications, extras)`.

        Justifications are the LLM helper's `justify`-decision entries —
        recorded on the gate record for Studio visibility (per HOM-156
        DoD §4 halt-notice update + new state field).
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
        justifications: list[dict] = []

        # Cheap path: no justifiable flags ⇒ no LLM dispatch.
        if not justifiable:
            return violations, justifications, extras

        decisions, helper_errors = _dispatch_justify(
            state,
            animation_map_path=report_path,
            flagged=justifiable,
            router=self._router,
        )
        if helper_errors:
            # Helper failed: cannot justify, so every justifiable flag becomes
            # a fix-violation. This preserves the v4 strict-fail behaviour as a
            # safe fallback rather than silently passing on a broken helper.
            violations.extend(helper_errors)
            for flagged in justifiable:
                violations.append(
                    f"{flagged['flag']} flag on {flagged['selector']} "
                    f"(duration {flagged['duration']}s) — justify helper unavailable; "
                    "treat as fix until classifier is re-runnable"
                )
            return violations, justifications, extras

        # Merge per-flag decisions back.
        unhandled: list[dict] = []
        for flagged in justifiable:
            decision = decisions.get(flagged["flag_id"])
            if decision is None:
                unhandled.append(flagged)
                continue
            if decision.decision == "fix":
                violations.append(
                    f"{flagged['flag']} flag on {flagged['selector']} "
                    f"(duration {flagged['duration']}s) — fix per LLM classifier: "
                    f"{decision.reason}"
                )
            else:
                justifications.append({
                    "flag_id": flagged["flag_id"],
                    "selector": flagged["selector"],
                    "flag": flagged["flag"],
                    "duration": flagged["duration"],
                    "reason": decision.reason,
                })
        if unhandled:
            # The helper failed to classify some flags. Treat them as fixes —
            # we cannot pass an unclassified pace flag on canon's "fix or
            # justify" contract.
            for flagged in unhandled:
                violations.append(
                    f"{flagged['flag']} flag on {flagged['selector']} "
                    f"(duration {flagged['duration']}s) — classifier returned no "
                    f"decision for flag_id={flagged['flag_id']!r}"
                )

        return violations, justifications, extras

    def __call__(self, state: dict) -> dict:
        violations, justifications, extras = self._run(state)
        passed = not violations
        record = {
            "gate": self.name,
            "passed": passed,
            "violations": violations,
            "iteration": self._iteration(state),
            "timestamp": _now(),
            **extras,
        }
        if justifications:
            record["justifications"] = justifications
        update: dict = {"gate_results": [record]}
        if not passed:
            update["notices"] = [
                f"{self.name}: FAILED ({len(violations)} violation(s)) — see gate_results"
            ]
        elif justifications and extras.get("fallback_helper_used"):
            update["notices"] = [
                f"{self.name}: passed via global fallback helper with "
                f"{len(justifications)} justified pace flag(s) — "
                "consider pinning @hyperframes/producer + sharp in the HF project"
            ]
        elif justifications:
            update["notices"] = [
                f"{self.name}: passed with {len(justifications)} justified pace flag(s) — "
                "see gate_results[*].justifications"
            ]
        elif extras.get("fallback_helper_used"):
            update["notices"] = [
                f"{self.name}: passed via global fallback helper — "
                "consider pinning @hyperframes/producer + sharp in the HF project"
            ]
        return update


def animation_map_gate_node(state: dict, *, router: BackendRouter | None = None) -> dict:
    return AnimationMapGate(router=router)(state)
