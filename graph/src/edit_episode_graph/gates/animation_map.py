"""gate:animation_map — runs the bundled `animation-map.mjs` helper, parses
the report, surfaces findings as **advisory** metadata by default with
narrow code-side hard-blocking for canon-absolute violations only.

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

## Pass criteria — narrow hard-blocking + LLM-triage advisory (HOM-317)

Canon (SKILL.md §"Quality Checks" §"Animation Map"):

> "Read the JSON. Scan summaries for anything unexpected. **Check every
>  flag — fix or justify.** Verify the timeline shows the intended
>  choreography rhythm. Re-run after fixes."

The mandate is on the *author*, not on a deterministic gate. Per HOM-203
(canon-alignment audit of 4 clean Claude Code sessions using the
`hyperframes` skill standalone — none invoked `animation-map.mjs`),
this gate started as **advisory only**: it ran the helper, surfaced
findings, and never blocked the run (HOM-204).

HOM-212 introduced per-flag carve-outs and HOM-316 extended them for
canonical caption (`#cg-N`, `span.w`) and `#scene-*` z-stack patterns.
HOM-317 retires the carve-out *vocabulary allowlists* entirely (per
CLAUDE.md §"Carve-out allowlists over LLM-emitted identifiers are
structurally wrong" — the `p4_beat` LLM emits a fresh class-name
vocabulary each prewarm: `halo` / `ghost` / `wash` / `plate-tint` /
`grain` / `pf-grain` / `bg-noise` / ... — substring allowlists never
converge). Architectural split:

* **Code-side hard-blocking — canon-absolute, vocabulary-independent:**
  - `offscreen` flag, unconditional. Per `SKILL.md:74` "CSS position is
    the ground truth" — an element off-canvas the full tween means the
    audience never sees it, regardless of class name.
  - `degenerate` flag whose bbox is ≥ `degenerate_min_bbox_px` (default
    2 px) on both width AND height across all samples. This is a
    **geometric** criterion on bbox dimensions, NOT a class-name match;
    1-2 px hairlines / ticks / underlines are intentional decoratives
    even if the LLM names them `kw-rule` one run and `accent-line` the
    next. The threshold is operator-tunable
    (`gates.animation_map.degenerate_min_bbox_px`).
  - Dead zones whose duration exceeds `dead_zone_threshold_s` (default
    2.0 s). Dead zones live on the **root timeline** (gaps between
    scenes); they are class-name-free by construction. The HOM-284
    trailing carve-out (yoyo+repeat tweens under-report total time vs
    `node.duration()`) is geometric — keyed on end-position-near-
    composition-duration, not on selector identity.
  - Infrastructure failures (helper missing, exit != 0, JSON
    unparseable, bootstrap blockers).

* **LLM-triage advisory — vocabulary-rich, canon-context-dependent:**
  - `collision` flags on ANY selector. Sibling overlaps during entrance
    / exit, captions canon word-spans, ambient yoyo+repeat decoratives,
    z-stacked scene containers — all produce by-construction collision
    flags whose disposition depends on canonical authoring patterns the
    `p4_beat` LLM applies with a fresh vocabulary each prewarm. These
    are sent to `gate_animation_map_classify` for per-flag
    canon-aware triage.
  - `invisible` flags on ANY selector. Captions canon keeps
    non-active groups in `opacity:0; visibility:hidden` between active
    windows — sampler reports `invisible` by construction. Ambient
    atmosphere layers fade in/out by canonical transition. Disposition
    again depends on the beat's intended choreography; LLM-triaged.
  - `paced-fast` / `paced-slow` flags (unchanged from HOM-204 — pace
    classifications were always LLM-judgement territory).

Both classifier-`decision="fix"` and `decision="justify"` outputs are
**advisory**. The classifier's output never affects routing — operators
read it as Studio metadata. This preserves the HOM-204 demotion.

`passed = True` whenever the helper itself ran successfully AND no
finding crossed a code-side hard-blocking threshold (offscreen,
degenerate≥2px, dead-zone>threshold). Hard-blocking findings populate
``record["violations"]`` so the routing layer's existing
cluster-retry helper re-dispatches the offending beat — symmetric to
HOM-212's wiring, but only for the narrow canon-absolute subset.

Successful-run findings live under ``record["advisory_findings"]`` —
a dict with three keys, always present (empty lists on a clean run):

* ``always_fix`` — list of human-readable strings for ``collision``,
  ``degenerate``, ``offscreen``, ``invisible`` flags (operator-visible
  even when classifier-triaged).
* ``dead_zones`` — list of human-readable strings for dead zones
  > 1.0s.
* ``pending_classify`` — list of flag dicts (``collision`` /
  ``invisible`` / ``paced-fast`` / ``paced-slow``) the
  ``gate_animation_map_classify`` LLM node will triage. After the
  classifier runs, each entry carries the per-flag decision + reason.

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
operator does not have to read the helper's diagnostic by hand. This
remains a hard ``passed=False`` — bootstrap failure is infrastructure,
not advisory authoring feedback.

## Notice format (HOM-205)

The advisory pattern (HOM-203/HOM-204) makes Studio's `notices` array
the operator's primary signal — `passed=True` means routing-wise
"don't redispatch", but the operator still wants a single-glance
breakdown of what the helper found. The canonical strings emitted by
this gate are:

* Successful run with findings:
  ``gate:animation_map: advisory — N finding(s) (always_fix: a, dead_zones: d, pending_classify: p). See {animation_map_json_path}.``
* Successful run, no findings:
  ``gate:animation_map: advisory — no findings (helper ran clean).``
* Global-fallback helper used (appended to either of the above):
  `` (via global fallback helper — consider pinning @hyperframes/producer + sharp in the HF project)``
* Hard-blocking finding (offscreen / degenerate≥2px / dead-zone>threshold):
  ``gate:animation_map: BLOCKING — N finding(s) require fix. <strings>. See {animation_map_json_path}.``
* Infrastructure failure (helper missing / exit != 0 / unparseable):
  ``gate:animation_map: infrastructure failure (N issue(s)) — see gate_results``

Keep the ``advisory`` / ``BLOCKING`` / ``infrastructure failure`` prefix
exactly as written — the prefix is the severity signal that downstream
surfaces (halt_llm_boundary, future Studio panels) key off.
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
from .._paths import EpisodePaths
from ..nodes._materialize_tmpdir import materialize_into_tmpdir
from ._base import Gate


# Bump on brief / schema / pass-criteria change. See HOM-132 spec §8.
# v3 = HOM-156 review-fix: gate is purely deterministic; LLM-justify dispatch
#   moved to nodes/gate_animation_map_classify.py (its own _CACHE_VERSION).
# v4 = HOM-204: demote to advisory.
# v5 = HOM-212: per-flag blocking carve-outs.
# v6 = HOM-225: cache key derives `hf_dir` via `EpisodePaths(slug)`.
# v7 = HOM-281: subprocess cwd migrated to materialized tmpdir.
# v8 = HOM-282: extras carry parsed animation_map_report.
# v9 = HOM-284: trailing dead-zone carve-out.
# v10 = HOM-316: caption word-span + invisible-on-cg + #scene-* carve-outs.
# v11 = HOM-317: vocabulary-allowlist carve-outs retired (caption-canon, scene-
#   container, decorative-allowlist predicates all dropped). `collision` and
#   `invisible` flags now route to LLM-triage advisory (pending_classify);
#   code-side hard-blocking restricted to canon-absolute geometric/structural
#   categories — `offscreen` (unconditional, per SKILL.md:74 "CSS position
#   is the ground truth"), `degenerate` with bbox ≥ degenerate_min_bbox_px
#   (geometric, vocabulary-independent), dead-zone-over-threshold, infra
#   failures. Output shape: `pending_classify` entries now mix flag types
#   (`paced-fast`/`paced-slow`/`collision`/`invisible`); a pre-HOM-317
#   cached row would replay the wrong blocking verdict on canonical
#   captions / scene z-stacks / LLM-emitted ambient classes (`halo`,
#   `ghost`, `wash`, ...) — version bump invalidates those rows.
#   Source: CLAUDE.md §"Carve-out allowlists over LLM-emitted identifiers
#   are structurally wrong"; retro 2026-05-17 §"Follow-up".
_CACHE_VERSION = 11


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

# Flags routed to LLM-triage advisory (`pending_classify`). HOM-317
# expanded this from just-pace-flags (HOM-204) to also cover
# `collision` + `invisible` — both are vocabulary-rich and
# canon-context-dependent (caption word-spans, ambient atmosphere layers,
# z-stacked scene containers). Pace flags were already triaged.
_LLM_TRIAGE_FLAGS = ("paced-fast", "paced-slow", "collision", "invisible")

# Default minimum bbox dimension (pixels) for a degenerate flag to be
# blocking. < this on either width or height across all bbox samples
# means the element is a 1-2px decorative (hairline / tick / underline)
# where degenerate-by-construction is the intended visual.
# GEOMETRIC, NOT VOCABULARY — this carve-out KEEPS post-HOM-317.
_DEFAULT_DEGENERATE_MIN_BBOX_PX = 2.0

# Default dead-zone-duration threshold (seconds). Above this, the dead
# zone flips from advisory to blocking. The ticket specifies 2.0s default.
_DEFAULT_DEAD_ZONE_THRESHOLD_S = 2.0

# HOM-284 trailing dead-zone carve-out — geometric (end-position-near-
# composition-duration), vocabulary-independent. KEEPS post-HOM-317.
_DEFAULT_DEAD_ZONE_TAIL_TOLERANCE_S = 0.5
_DEFAULT_DEAD_ZONE_TRAILING_MAX_S = 5.0


def _gate_config() -> dict:
    """Resolve the operator-tunable carve-out config from graph/config.yaml.

    Lazy-imported to keep module import-time side-effect-free for the
    fingerprint registry. Falls back to an empty dict (→ defaults) if the
    config file is absent (test environments without a graph/ root).
    """
    from ..config import load_default_config
    return load_default_config().resolve_gate("animation_map")


def _max_bbox_dim(tween: dict) -> tuple[float, float]:
    """Returns (max_width_observed, max_height_observed) across bbox
    samples on a tween. Used by the degenerate carve-out — a tween
    whose bbox stays below `degenerate_min_bbox_px` on either dimension
    is by-construction (1-2px hairline / tick).

    Returns (0.0, 0.0) when the helper emitted no bbox data (older
    helper versions; treated as "cannot prove decorative" → keep
    blocking, since the actual concern is content elements with zero
    bbox throughout, which is exactly what missing-bbox-data implies)."""
    boxes = tween.get("bboxes") or []
    if not boxes:
        return 0.0, 0.0
    max_w = 0.0
    max_h = 0.0
    for b in boxes:
        try:
            w = float(b.get("w") or 0.0)
            h = float(b.get("h") or 0.0)
        except (TypeError, ValueError):
            continue
        if w > max_w:
            max_w = w
        if h > max_h:
            max_h = h
    return max_w, max_h


def _degenerate_is_blocking(tween: dict, *, min_bbox_px: float) -> bool:
    """Degenerate flag is blocking only when the bbox is large enough
    that an authoring fix is plausible. 1-2px hairlines / ticks are
    intentional. This is a GEOMETRIC test on bbox dimensions, NOT a
    class-name allowlist — it is vocabulary-independent and survives
    HOM-317's retirement of vocab carve-outs."""
    max_w, max_h = _max_bbox_dim(tween)
    # Both dimensions must clear the threshold to count as a "real" element.
    return (max_w >= min_bbox_px) and (max_h >= min_bbox_px)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_helper(hf_dir: Path) -> tuple[Path | None, bool]:
    bundled = hf_dir / _BUNDLED_REL
    if bundled.is_file():  # disk-io-allow: helper-script discovery inside materialized tmpdir (HOM-281)
        return bundled, False
    if _GLOBAL_FALLBACK.is_file():  # disk-io-allow: global skill-copy fallback for helper-script discovery
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
    out_dir.mkdir(parents=True, exist_ok=True)  # disk-io-allow: prepare animation-map report output dir in materialized tmpdir
    stale = out_dir / _OUT_FILE
    if stale.is_file():  # disk-io-allow: clear stale report from prior run inside materialized tmpdir
        try:
            stale.unlink()  # disk-io-allow: see above
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


def _extract_flags(
    report: dict,
    *,
    degenerate_min_bbox_px: float | None = None,
    dead_zone_threshold_s: float | None = None,
    dead_zone_tail_tolerance_s: float | None = None,
    dead_zone_trailing_max_s: float | None = None,
) -> tuple[list[str], list[dict], list[str], list[str]]:
    """Split helper output into (always_fix, pending_classify, dead_zones,
    blocking_violations).

    HOM-317: vocabulary-allowlist carve-outs retired. `collision` and
    `invisible` flags route to `pending_classify` for LLM-triage advisory.
    Code-side hard-blocking restricted to canon-absolute
    vocabulary-independent categories:

      * `offscreen` (unconditional — `SKILL.md:74` "CSS position is the
        ground truth"; audience never sees off-canvas elements regardless
        of selector name).
      * `degenerate` with bbox ≥ `degenerate_min_bbox_px` on BOTH width
        and height (geometric criterion, vocabulary-independent — the
        HOM-211 1-2 px hairline/tick exemption stays as a geometric
        threshold, not a class-name allowlist).
      * Dead zones with duration > `dead_zone_threshold_s` (root-timeline
        concern, class-name-free by construction). The HOM-284 trailing
        carve-out (end-position-near-composition-duration) keeps —
        also geometric.

    Per CLAUDE.md §"Carve-out allowlists over LLM-emitted identifiers":
    `p4_beat`-emitted free-form class names (`halo`, `ghost`, `wash`,
    `plate-tint`, ...) produce a fresh vocabulary each prewarm; substring
    allowlists never converge. The classifier handles vocabulary-rich
    cases (collision/invisible) with canon-context awareness.
    """
    if degenerate_min_bbox_px is None:
        degenerate_min_bbox_px = _DEFAULT_DEGENERATE_MIN_BBOX_PX
    if dead_zone_threshold_s is None:
        dead_zone_threshold_s = _DEFAULT_DEAD_ZONE_THRESHOLD_S
    if dead_zone_tail_tolerance_s is None:
        dead_zone_tail_tolerance_s = _DEFAULT_DEAD_ZONE_TAIL_TOLERANCE_S
    if dead_zone_trailing_max_s is None:
        dead_zone_trailing_max_s = _DEFAULT_DEAD_ZONE_TRAILING_MAX_S

    try:
        composition_duration_s = float(report.get("duration") or 0.0)
    except (TypeError, ValueError):
        composition_duration_s = 0.0

    always_fix: list[str] = []
    pending_classify: list[dict] = []
    blocking: list[str] = []

    tweens = report.get("tweens") or []
    collisions: list[str] = []
    degenerate: list[str] = []
    blocking_degenerate: list[str] = []
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
            if _degenerate_is_blocking(tw, min_bbox_px=degenerate_min_bbox_px):
                blocking_degenerate.append(sel)
        if "offscreen" in flags:
            # Unconditional hard-block — `SKILL.md:74` "CSS position is the
            # ground truth"; audience never sees off-canvas elements
            # regardless of selector identity.
            offscreen.append(sel)
        if "invisible" in flags:
            invisible.append(sel)
        for flag in _LLM_TRIAGE_FLAGS:
            if flag in flags:
                pending_classify.append({
                    "flag_id": _flag_id(sel, idx if isinstance(idx, int) else -1, flag),
                    "selector": sel,
                    "flag": flag,
                    "duration": duration,
                    "index": idx,
                })

    if collisions:
        always_fix.append(
            "collision flag(s) on " + ", ".join(collisions)
            + " — overlapping animated elements; LLM-triage advisory (HOM-317)"
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
            + " — zero opacity throughout the tween; LLM-triage advisory (HOM-317)"
        )

    # Blocking violations — narrow code-side hard-blocks for canon-absolute
    # vocabulary-independent categories only. Collision + invisible no
    # longer code-side block; LLM-triage handles their disposition advisory.
    if blocking_degenerate:
        blocking.append(
            "blocking degenerate flag(s) on " + ", ".join(blocking_degenerate)
            + f" — bbox ≥ {degenerate_min_bbox_px}px throughout but element never renders"
        )
    if offscreen:
        blocking.append(
            "blocking offscreen flag(s) on " + ", ".join(offscreen)
            + " — element off-canvas throughout the tween (HOM-317)"
        )

    dead_zones: list[str] = []
    blocking_dead_zone_durs: list[float] = []
    for zone in report.get("deadZones") or []:
        try:
            dur = float(zone.get("duration", 0.0))
        except (TypeError, ValueError):
            dur = 0.0
        if dur > 1.0:
            start = zone.get("start")
            end = zone.get("end")
            try:
                end_f = float(end) if end is not None else None
            except (TypeError, ValueError):
                end_f = None
            # HOM-284 trailing carve-out — geometric, KEEPS post-HOM-317.
            is_trailing_artifact = (
                dead_zone_trailing_max_s > 0
                and composition_duration_s > 0
                and end_f is not None
                and abs(composition_duration_s - end_f) <= dead_zone_tail_tolerance_s
                and dur <= dead_zone_trailing_max_s
            )
            if is_trailing_artifact:
                dead_zones.append(
                    f"trailing dead zone {start}s–{end}s (duration {dur}s) — "
                    "advisory: ambient yoyo+repeat tweens under-report total "
                    "time vs node.duration() (HOM-284); raise "
                    "gates.animation_map.dead_zone_trailing_max_s in "
                    "graph/config.yaml to flag as blocking if intentional"
                )
                continue
            dead_zones.append(
                f"dead zone {start}s–{end}s (duration {dur}s > 1.0s) — "
                "no animation; intentional hold or missing entrance?"
            )
            if dur > dead_zone_threshold_s:
                blocking_dead_zone_durs.append(dur)
    if blocking_dead_zone_durs:
        worst = max(blocking_dead_zone_durs)
        blocking.append(
            f"blocking dead zone — max duration {worst}s exceeds threshold "
            f"{dead_zone_threshold_s}s (HOM-212)"
        )

    return always_fix, pending_classify, dead_zones, blocking


# ---------------------------------------------------------------------------
# Cache key — exposed for the L0 fingerprint-invalidation registry only.
# ---------------------------------------------------------------------------


def _gate_cache_key(state, *_args, **_kwargs):
    """Deterministic cache key for gate_animation_map (post-helper-run)."""
    if not isinstance(state, dict):
        raise TypeError(
            f"animation_map gate cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    if slug and slug != "__unbound__":
        animation_map_path: Path | None = (
            EpisodePaths(slug).hyperframes_dir / _OUT_SUBDIR / _OUT_FILE
        )
    else:
        animation_map_path = None
    return make_key(
        node="gate_animation_map",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            str(animation_map_path) if animation_map_path else None,
        ],
    )


_cache_key = _gate_cache_key  # alias for the fingerprint registry


def _animation_map_json_path(state: dict) -> str:
    slug = state.get("slug")
    if not slug:
        return _OUT_FILE
    return str(EpisodePaths(slug).hyperframes_dir / _OUT_SUBDIR / _OUT_FILE)


class AnimationMapGate(Gate):
    """gate:animation_map — bundled-helper invocation; narrow code-side
    hard-blocking + LLM-triage advisory (HOM-317).

    Overrides `Gate.__call__` so the gate record can carry helper-path
    provenance (`helper_path`, `fallback_helper_used`) and the
    `advisory_findings` dict (always_fix / dead_zones / pending_classify)
    that the `gate_animation_map_classify` LLM node will triage downstream
    and that the operator reads in Studio.

    `passed=False` ONLY on infrastructure failure OR canon-absolute
    hard-blocking (offscreen / degenerate≥2px / dead-zone>threshold).
    Vocabulary-rich findings (collision / invisible / paced-*) advance to
    LLM-triage.
    """

    def __init__(self) -> None:
        super().__init__(name="gate:animation_map")

    def _run(self, state: dict) -> tuple[list[str], dict, list[str], dict]:
        empty_advisory: dict = {"always_fix": [], "dead_zones": [], "pending_classify": []}

        slug = state.get("slug")
        if not slug:
            return (
                ["no slug in state — cannot materialize HF tmpdir for animation-map"],
                empty_advisory,
                [],
                {},
            )
        try:
            hf_dir = materialize_into_tmpdir(state, slug=slug)
        except RuntimeError as exc:
            return ([f"materialize_into_tmpdir failed: {exc}"], empty_advisory, [], {})

        canonical_hf_dir = EpisodePaths(slug).hyperframes_dir
        helper, used_fallback = _resolve_helper(canonical_hf_dir)
        if helper is None:
            return (
                [
                    "animation-map.mjs not found at bundled path "
                    f"{canonical_hf_dir / _BUNDLED_REL} or global fallback {_GLOBAL_FALLBACK}"
                ],
                empty_advisory,
                [],
                {},
            )

        extras: dict = {
            "helper_path": str(helper),
            "fallback_helper_used": used_fallback,
        }

        ran = _run_helper(hf_dir, helper, used_fallback)
        if isinstance(ran, str):
            return ([ran], empty_advisory, [], extras)

        if ran.exit_code != 0:
            bootstrap = _bootstrap_failure_violation(ran, hf_dir)
            if bootstrap is not None:
                return ([bootstrap], empty_advisory, [], extras)
            tail = (ran.stderr or ran.stdout or "(no output)").strip()
            if len(tail) > 1500:
                tail = tail[:1500] + "\n…(truncated)"
            return (
                [f"animation-map helper exit={ran.exit_code}:\n{tail}"],
                empty_advisory,
                [],
                extras,
            )

        report_path = ran.out_dir / _OUT_FILE
        if not report_path.is_file():  # disk-io-allow: read animation-map JSON report produced by node helper
            return (
                [f"animation-map helper exited 0 but {_OUT_FILE} not found at {report_path}"],
                empty_advisory,
                [],
                extras,
            )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))  # disk-io-allow: parse animation-map JSON report produced by node helper
        except (OSError, json.JSONDecodeError) as exc:
            return ([f"could not parse {report_path}: {exc}"], empty_advisory, [], extras)

        # HOM-282: hoist parsed report into extras for downstream consumers.
        extras["animation_map_report"] = report

        # HOM-317: resolve operator-tunable thresholds. The
        # `collision_decorative_allowlist` config key is RETIRED — its
        # presence in graph/config.yaml is silently ignored (legacy
        # configs continue to load). Geometric thresholds remain.
        cfg = _gate_config()
        degenerate_min_bbox_px = float(
            cfg.get("degenerate_min_bbox_px", _DEFAULT_DEGENERATE_MIN_BBOX_PX)
        )
        dead_zone_threshold_s = float(
            cfg.get("dead_zone_threshold_s", _DEFAULT_DEAD_ZONE_THRESHOLD_S)
        )
        dead_zone_tail_tolerance_s = float(
            cfg.get("dead_zone_tail_tolerance_s", _DEFAULT_DEAD_ZONE_TAIL_TOLERANCE_S)
        )
        dead_zone_trailing_max_s = float(
            cfg.get("dead_zone_trailing_max_s", _DEFAULT_DEAD_ZONE_TRAILING_MAX_S)
        )

        always_fix, pending_classify, dead_zones, blocking = _extract_flags(
            report,
            degenerate_min_bbox_px=degenerate_min_bbox_px,
            dead_zone_threshold_s=dead_zone_threshold_s,
            dead_zone_tail_tolerance_s=dead_zone_tail_tolerance_s,
            dead_zone_trailing_max_s=dead_zone_trailing_max_s,
        )
        advisory_findings = {
            "always_fix": always_fix,
            "dead_zones": dead_zones,
            "pending_classify": pending_classify,
        }
        return ([], advisory_findings, blocking, extras)

    def __call__(self, state: dict) -> dict:
        infra_failures, advisory_findings, blocking, extras = self._run(state)
        passed = not infra_failures and not blocking
        if infra_failures:
            violations = list(infra_failures)
        else:
            violations = list(blocking)
        record: dict = {
            "gate": self.name,
            "passed": passed,
            "violations": violations,
            "advisory_findings": advisory_findings,
            "blocking_findings": list(blocking),
            "iteration": self._iteration(state),
            "timestamp": _now(),
            **extras,
        }
        update: dict = {"gate_results": [record]}

        if infra_failures:
            update["notices"] = [
                f"{self.name}: infrastructure failure ({len(infra_failures)} issue(s)) — "
                "see gate_results"
            ]
            return update

        n_always = len(advisory_findings["always_fix"])
        n_dead = len(advisory_findings["dead_zones"])
        n_pending = len(advisory_findings["pending_classify"])
        total = n_always + n_dead + n_pending
        anim_map_path = _animation_map_json_path(state)
        fallback_hint = (
            " (via global fallback helper — consider pinning "
            "@hyperframes/producer + sharp in the HF project)"
            if extras.get("fallback_helper_used")
            else ""
        )

        if blocking:
            update["notices"] = [
                f"{self.name}: BLOCKING — {len(blocking)} finding(s) require fix. "
                + " | ".join(blocking)
                + f". See {anim_map_path}.{fallback_hint}"
            ]
            return update

        if total == 0:
            update["notices"] = [
                f"{self.name}: advisory — no findings (helper ran clean){fallback_hint}"
            ]
        else:
            update["notices"] = [
                f"{self.name}: advisory — {total} finding(s) "
                f"(always_fix: {n_always}, dead_zones: {n_dead}, "
                f"pending_classify: {n_pending}). See {anim_map_path}.{fallback_hint}"
            ]
        return update


def animation_map_gate_node(state: dict) -> dict:
    return AnimationMapGate()(state)
