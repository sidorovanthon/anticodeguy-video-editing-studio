"""gate:animation_map — runs the bundled `animation-map.mjs` helper, parses
the report, surfaces findings as **advisory** metadata by default with
per-flag blocking carve-outs (HOM-212).

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

## Pass criteria — ADVISORY by default + per-flag blocking carve-outs (HOM-212)

Canon (SKILL.md §"Quality Checks" §"Animation Map"):

> "Read the JSON. Scan summaries for anything unexpected. **Check every
>  flag — fix or justify.** Verify the timeline shows the intended
>  choreography rhythm. Re-run after fixes."

The mandate is on the *author*, not on a deterministic gate. Per HOM-203
(canon-alignment audit of 4 clean Claude Code sessions using the
`hyperframes` skill standalone — none invoked `animation-map.mjs`),
this gate started as **advisory only**: it ran the helper, surfaced
findings, and never blocked the run (HOM-204).

HOM-212 refines that: most findings remain advisory, but a small set of
**structural carve-outs** flip to blocking because they cannot be
justified post-hoc by an author (e.g. an `offscreen` flag on a content
element means the audience never sees it). The HOM-211 reviewer caveat
(`always_fix.count > 0` regresses to the HOM-203 redispatch loop on
canonical caption-chains and chrome decoratives) drove the per-flag
classification rather than per-category — see `_blocking_classification`
below for the precise rules.

`passed = True` whenever the helper itself ran successfully AND no
finding crossed a blocking threshold. Findings that are blocking-by-rule
populate ``record["violations"]`` so the routing layer (which still
reads ``violations`` for its retry decision) re-dispatches the offending
beat — symmetric to the wiring HOM-204 removed, but only for the
structurally-actionable subset.

Only **infrastructure failures** keep `passed=False` regardless of
findings:

* helper not found at bundled path or global fallback
* `node` executable not found on PATH
* helper exit_code != 0 (incl. dependency-bootstrap failure on Windows)
* `animation-map.json` missing despite exit 0
* JSON parse error

These are operator-actionable problems (install deps / fix PATH); the
run cannot be trusted until they're resolved. They are NOT findings
about the authored animation.

Successful-run findings live under ``record["advisory_findings"]`` —
a dict with three keys, always present (empty lists on a clean run):

* ``always_fix`` — list of human-readable strings for ``collision``,
  ``degenerate``, ``offscreen``, ``invisible`` flags.
* ``dead_zones`` — list of human-readable strings for dead zones
  > 1.0s.
* ``pending_classify`` — list of pace-flag dicts (``paced-fast`` /
  ``paced-slow``) the ``gate_animation_map_classify`` LLM node will
  triage. After the classifier runs, this list carries the per-flag
  decision + reason.

``record["violations"]`` is kept on every record (Gate base contract)
but stays empty ``[]`` on any successful helper run — the routing layer
no longer reads it for animation-map. Infrastructure failures still
populate ``violations`` so existing operator-error display surfaces
unchanged.

The deterministic gate **never calls an LLM**. The LLM dispatch lives
in ``nodes/gate_animation_map_classify.py`` so LangGraph's
``cache_policy=`` mechanism can apply (CLAUDE.md §"Idempotency" — re-run
on identical inputs produces zero LLM dispatches). Its output is also
advisory — it merges into ``advisory_findings.pending_classify`` and
never affects routing.

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
* Infrastructure failure (helper missing / exit != 0 / unparseable):
  ``gate:animation_map: infrastructure failure (N issue(s)) — see gate_results``

Keep the ``advisory`` / ``infrastructure failure`` prefix exactly as
written — the prefix is the severity signal that downstream surfaces
(halt_llm_boundary, future Studio panels) key off. Do not rephrase to
"WARN" / "FAILED" / "issue" without bumping ``_CACHE_VERSION`` and
revising the cross-referenced halt_llm_boundary branch. The
``halt_llm_boundary`` node uses the same breakdown shape
``(always_fix: a, dead_zones: d, pending_classify: p)`` when it folds
advisory counts into a cluster-halt notice — keep both sites aligned.
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
# v4 = HOM-204: demote to advisory. `passed=True` on any successful helper
#   run; findings move to `advisory_findings`; routing no longer reads
#   `violations` from this gate. Output shape change ⇒ cache invalidation.
# v5 = HOM-212: per-flag blocking carve-outs. Pass criteria now depends on
#   carved-out blocking conditions (collision off-canon, degenerate ≥ 2px,
#   offscreen, invisible, dead_zone > threshold); routing reads `violations`
#   again on the blocking branch. Output shape unchanged but verdict logic
#   changed ⇒ cache invalidation.
# v6 = HOM-225: cache key derives `hf_dir` via `EpisodePaths(slug)` rather
#   than reading the deprecated `compose.hyperframes_dir` /
#   `state["episode_dir"]` chain. Mirrors the HOM-224 p4 migration —
#   identity-only state. Same migration applied to `_animation_map_json_path`
#   (used in advisory notice surface) for consistency.
# v7 = HOM-281: subprocess cwd migrated from canonical hf_dir to a
#   transient tmpdir produced by ``materialize_into_tmpdir``. Helper-script
#   resolution still targets the canonical hf_dir so its bundled sibling
#   deps (`@hyperframes/producer`) resolve. The `animation-map.json`
#   output now lands under the tmpdir rather than `<hf_dir>/.hyperframes/`;
#   the advisory-notice path still surfaces the canonical hf_dir target
#   so the operator's path expectation is unchanged. Cache-key inputs
#   unchanged ⇒ semantic bump only.
_CACHE_VERSION = 7


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

# Pace flags the LLM-classify node triages. They land under
# `advisory_findings.pending_classify`; everything else with structural
# significance lands under `advisory_findings.always_fix`.
_JUSTIFIABLE_FLAGS = ("paced-fast", "paced-slow")

# HOM-212 carve-out defaults. Operator-tunable via `gates.animation_map.*`
# in `graph/config.yaml`; these are the fall-throughs when the YAML key is
# absent. Rationale lives in the HOM-211 reviewer caveat (Linear comment
# `0b8c433d-96c0-4b9f-9c4d-941178279564`, AMENDMENT section).

# Caption canonical chain. The `set(visible) → fromTo(entrance) → to(exit)
# → set(hidden)` pattern at each cg-N start/end produces by-construction
# bbox-overlap collision flags on every caption group. These are not
# authoring defects — refusing to demote them re-introduces the HOM-203
# redispatch loop on the canonical fixture's 17 caption groups (51 of 109
# collision findings).
_CG_SELECTOR_RE = re.compile(r"^#cg-\d+$")

# Default ambient-decorative selector substrings. The chrome decoratives
# (entrance fromTo + breathing yoyo on the same element) trigger
# helper bbox-overlap by construction; these are the elements canon DESIGN
# patterns explicitly call ambient. Operator can extend / shrink via
# `gates.animation_map.collision_decorative_allowlist` in graph/config.yaml.
_DEFAULT_DECORATIVE_ALLOWLIST = (
    "grain", "glow", "hairline", "vignette", "overline",
    "corner-mark", "footer-mark", "caption-strip", "margin-tick",
)

# Default minimum bbox dimension (pixels) for a degenerate flag to be
# blocking. < this on either width or height across all bbox samples
# means the element is a 1-2px decorative (hairline / tick / underline)
# where degenerate-by-construction is the intended visual.
_DEFAULT_DEGENERATE_MIN_BBOX_PX = 2.0

# Default dead-zone-duration threshold (seconds). Above this, the dead
# zone flips from advisory to blocking. The ticket specifies 2.0s default.
_DEFAULT_DEAD_ZONE_THRESHOLD_S = 2.0


def _gate_config() -> dict:
    """Resolve the operator-tunable carve-out config from graph/config.yaml.

    Lazy-imported to keep module import-time side-effect-free for the
    fingerprint registry. Falls back to an empty dict (→ defaults) if the
    config file is absent (test environments without a graph/ root).
    """
    from ..config import load_default_config
    return load_default_config().resolve_gate("animation_map")


def _is_caption_canon(selector: str) -> bool:
    """`#cg-N` selectors emit by-construction collision flags from the
    canon caption authoring pattern. Always carved out."""
    return bool(_CG_SELECTOR_RE.match(selector or ""))


def _is_decorative(selector: str, allowlist: tuple[str, ...]) -> bool:
    """Substring match against the chrome-decorative allowlist."""
    sel = (selector or "").lower()
    return any(needle.lower() in sel for needle in allowlist)


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


def _collision_is_blocking(tween: dict, selector: str, *, decorative_allowlist: tuple[str, ...]) -> bool:
    """Per HOM-211 reviewer caveat: collision flags are blocking unless
    the element is caption canon (`#cg-N`) or a chrome decorative whose
    entrance + ambient yoyo overlap by construction."""
    if _is_caption_canon(selector):
        return False
    if _is_decorative(selector, decorative_allowlist):
        return False
    return True


def _degenerate_is_blocking(tween: dict, *, min_bbox_px: float) -> bool:
    """Degenerate flag is blocking only when the bbox is large enough
    that an authoring fix is plausible. 1-2px hairlines / ticks are
    intentional (HOM-211 caveat: 5/5 canonical degenerate findings are
    on `pf-hairline` / `margin-tick` / `kw-underline`)."""
    max_w, max_h = _max_bbox_dim(tween)
    # Both dimensions must clear the threshold to count as a "real" element.
    return (max_w >= min_bbox_px) and (max_h >= min_bbox_px)


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


def _extract_flags(
    report: dict,
    *,
    decorative_allowlist: tuple[str, ...] | None = None,
    degenerate_min_bbox_px: float | None = None,
    dead_zone_threshold_s: float | None = None,
) -> tuple[list[str], list[dict], list[str], list[str]]:
    """Split helper output into (always_fix, pending_classify, dead_zones,
    blocking_violations).

    HOM-212: returns a fourth element — `blocking_violations` — populated
    when a finding crosses a per-flag carve-out (see
    `_collision_is_blocking` / `_degenerate_is_blocking` /
    threshold-based dead-zones / unconditional offscreen+invisible).

    The first three return values keep their HOM-204 shape (advisory
    metadata for Studio). Findings that ARE blocking still appear in the
    advisory lists too — they're not mutually exclusive — so the operator
    sees the full picture; the routing layer keys solely off
    `blocking_violations`.
    """
    if decorative_allowlist is None:
        decorative_allowlist = _DEFAULT_DECORATIVE_ALLOWLIST
    if degenerate_min_bbox_px is None:
        degenerate_min_bbox_px = _DEFAULT_DEGENERATE_MIN_BBOX_PX
    if dead_zone_threshold_s is None:
        dead_zone_threshold_s = _DEFAULT_DEAD_ZONE_THRESHOLD_S

    always_fix: list[str] = []
    pending_classify: list[dict] = []
    blocking: list[str] = []

    tweens = report.get("tweens") or []
    collisions: list[str] = []
    blocking_collisions: list[str] = []
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
            if _collision_is_blocking(tw, sel, decorative_allowlist=decorative_allowlist):
                blocking_collisions.append(sel)
        if "degenerate" in flags:
            degenerate.append(sel)
            if _degenerate_is_blocking(tw, min_bbox_px=degenerate_min_bbox_px):
                blocking_degenerate.append(sel)
        if "offscreen" in flags:
            # No canon-known FP class. Content element off-canvas throughout
            # is structurally always wrong (audience never sees it).
            offscreen.append(sel)
        if "invisible" in flags:
            # Same: zero-opacity throughout = element never renders. No FP
            # class identified in the HOM-211 audit.
            invisible.append(sel)
        for flag in _JUSTIFIABLE_FLAGS:
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

    # Blocking violations — distinct, structured strings the routing layer
    # reads. Decoratives + caption canon collisions are filtered out.
    if blocking_collisions:
        blocking.append(
            "blocking collision flag(s) on " + ", ".join(blocking_collisions)
            + " — overlapping animated content; refine layout (HOM-212)"
        )
    if blocking_degenerate:
        blocking.append(
            "blocking degenerate flag(s) on " + ", ".join(blocking_degenerate)
            + f" — bbox ≥ {degenerate_min_bbox_px}px throughout but element never renders"
        )
    if offscreen:
        blocking.append(
            "blocking offscreen flag(s) on " + ", ".join(offscreen)
            + " — element off-canvas throughout the tween (HOM-212)"
        )
    if invisible:
        blocking.append(
            "blocking invisible flag(s) on " + ", ".join(invisible)
            + " — zero opacity throughout the tween (HOM-212)"
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
#
# The gate is intentionally NOT bound to a `cache_policy=` in graph.py: the
# deterministic helper subprocess (animation-map.mjs) is fast enough that
# always re-running it on each gate visit is cheaper than fingerprint I/O.
# Post-HOM-204 there is no redispatch loop on this gate, but the cache-key
# helper is still exposed so the fingerprint-invalidation registry can
# parametrise the per-node invariants (`_CACHE_VERSION` bump, etc.).
# The LLM dispatch that actually justifies caching lives in
# `nodes/gate_animation_map_classify.py`.
# ---------------------------------------------------------------------------


def _gate_cache_key(state, *_args, **_kwargs):
    """Deterministic cache key for gate_animation_map (post-helper-run).

    HOM-225: ``hf_dir`` derives via ``EpisodePaths(slug)`` — identity-only
    state. Legacy ``compose.hyperframes_dir`` / ``state["episode_dir"]``
    chain removed (no p4 node writes those keys after HOM-224).
    """
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
    """Return the canonical path string for the animation-map.json output.

    Used in the advisory notice so the operator can open the helper
    output directly from Studio. HOM-225: derives via
    ``EpisodePaths(slug)`` — identity-only state.
    """
    slug = state.get("slug")
    if not slug:
        return _OUT_FILE
    return str(EpisodePaths(slug).hyperframes_dir / _OUT_SUBDIR / _OUT_FILE)


class AnimationMapGate(Gate):
    """gate:animation_map — bundled-helper invocation, advisory findings (HOM-204).

    Overrides `Gate.__call__` so the gate record can carry helper-path
    provenance (`helper_path`, `fallback_helper_used`) and the
    `advisory_findings` dict (always_fix / dead_zones / pending_classify)
    that the `gate_animation_map_classify` LLM node will triage downstream
    and that the operator reads in Studio.

    `passed=False` ONLY on infrastructure failure (helper not found, node
    missing, helper exit != 0, JSON unparseable). Successful helper runs
    always set `passed=True` regardless of how many findings the helper
    surfaced — findings are operator-visible metadata, not routing signals.
    """

    def __init__(self) -> None:
        super().__init__(name="gate:animation_map")

    def _run(self, state: dict) -> tuple[list[str], dict, list[str], dict]:
        """Returns ``(infra_failures, advisory_findings, blocking_violations, extras)``.

        ``infra_failures`` is non-empty only when the helper itself could
        not run — these become hard `passed=False` violations. On any
        successful helper run it is empty `[]`, regardless of how many
        findings landed in ``advisory_findings``.

        ``advisory_findings`` always has the canonical three-key shape:
        ``{"always_fix": [...], "dead_zones": [...], "pending_classify": [...]}``
        — empty lists on a clean run, populated otherwise.

        ``blocking_violations`` (HOM-212) is the carved-out subset of
        findings that should redispatch the offending beat. Empty list
        on a clean run OR on a run where every finding fell into a
        carve-out (caption canon, chrome decorative, sub-threshold
        dead zone, sub-2px degenerate). When non-empty AND no infra
        failure, the gate emits ``passed=False`` with these strings as
        ``violations`` so the routing layer's existing retry helper
        re-dispatches.
        """
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

        # Helper-script resolution prefers the bundled copy under
        # ``<canonical hf_dir>/node_modules/...`` so its sibling-deps
        # ancestor-walk (`@hyperframes/producer`) succeeds — the tmpdir
        # never carries ``node_modules/``. The script's input project
        # and output dir still point at the tmpdir so the analyzer reads
        # the materialized index.html and writes its JSON next to it.
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
        if not report_path.is_file():
            return (
                [f"animation-map helper exited 0 but {_OUT_FILE} not found at {report_path}"],
                empty_advisory,
                [],
                extras,
            )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ([f"could not parse {report_path}: {exc}"], empty_advisory, [], extras)

        # HOM-212: resolve operator-tunable carve-out config.
        cfg = _gate_config()
        # Distinguish "absent" (use defaults) from "explicit empty list"
        # (operator strict-mode toggle — no carve-out at all).
        if "collision_decorative_allowlist" in cfg:
            decorative_allowlist = tuple(cfg["collision_decorative_allowlist"] or ())
        else:
            decorative_allowlist = _DEFAULT_DECORATIVE_ALLOWLIST
        degenerate_min_bbox_px = float(
            cfg.get("degenerate_min_bbox_px", _DEFAULT_DEGENERATE_MIN_BBOX_PX)
        )
        dead_zone_threshold_s = float(
            cfg.get("dead_zone_threshold_s", _DEFAULT_DEAD_ZONE_THRESHOLD_S)
        )

        always_fix, pending_classify, dead_zones, blocking = _extract_flags(
            report,
            decorative_allowlist=decorative_allowlist,
            degenerate_min_bbox_px=degenerate_min_bbox_px,
            dead_zone_threshold_s=dead_zone_threshold_s,
        )
        advisory_findings = {
            "always_fix": always_fix,
            "dead_zones": dead_zones,
            "pending_classify": pending_classify,
        }
        return ([], advisory_findings, blocking, extras)

    def __call__(self, state: dict) -> dict:
        infra_failures, advisory_findings, blocking, extras = self._run(state)
        # HOM-212: passed=False on infra failure OR blocking carve-out hit.
        # `violations` carries either the infra strings (existing operator-
        # error UI) or the blocking strings (routing-layer retry helper).
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
            # HOM-212: blocking findings are also persisted as their own key
            # so Studio surfaces (and downstream test introspection) can
            # distinguish "blocking" from "infra-failure" violations even
            # though both populate the standard `violations` field.
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
            # HOM-212: blocking notice calls out the offending categories
            # explicitly so the operator can act before redispatch fires.
            # Notice prefix is `BLOCKING` (load-bearing — Studio surfaces /
            # halt_llm_boundary key off the prefix to choose severity).
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
