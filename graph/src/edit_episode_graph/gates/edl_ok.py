"""gate:edl_ok — validates the EDL produced by p3_edl_select.

Per spec §6.2 / canon HR 6+7:
  - EDL parseable + non-empty (Pydantic schema absence of `subtitles` already
    enforced by `extra="forbid"` upstream; this gate cross-checks at dict
    level as defense-in-depth and emits a concrete violation if missed).
  - Every cut edge falls outside word intervals (HR 6) — no cut inside a word.
  - Each cut edge sits 30–200ms from the nearest word boundary (HR 7 padding).
  - Final-cut length matches the strategy's `length_estimate_s` within
    ±LENGTH_TOLERANCE. Canon does NOT specify a fixed pacing fraction —
    Step 4 strategy emits a length estimate from the material itself,
    and the gate validates against THAT, not a hard-coded ratio.
    `length_estimate_s` is required by `schemas.p3_strategy` (Pydantic
    `Field(gt=0)`); if it is missing here, the upstream contract was
    violated and the gate hard-fails rather than fall back to a
    one-artifact ratio that pretends to validate intent.
  - `overlays == []` (Phase-3 orchestrator policy; Phase 4 owns animation).
  - `subtitles` field absent at dict level.
  - `grade` (when raw ffmpeg filter chain): every `curves=master='...'`
    keypoint sits in [0,1] (ffmpeg constraint; built-in presets in
    `~/.claude/skills/video-use/helpers/grade.py` follow this). Pre-flight
    validation prevents `Invalid key point coordinates` failing the
    downstream render after expensive upstream work has already run.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from ._base import Gate

PADDING_MIN_S = 0.030
PADDING_MAX_S = 0.200
LENGTH_TOLERANCE = 0.20  # ±20% of strategy.length_estimate_s
EPSILON_S = 1e-6


def _word_intervals(transcript_path: Path) -> list[tuple[float, float]]:
    """Return [(start, end), ...] for type=='word' entries, sorted by start."""
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    words = [
        (float(w["start"]), float(w["end"]))
        for w in (data.get("words") or [])
        if w.get("type") == "word" and w.get("start") is not None and w.get("end") is not None
    ]
    words.sort()
    return words


def _inside_word(t: float, words: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Return the (start, end) of the word containing t, or None.

    `words` is sorted by start; the early break exits once a word starts at or
    after t, which is safe because Scribe transcripts do not contain
    overlapping word intervals.
    """
    for s, e in words:
        if s + EPSILON_S < t < e - EPSILON_S:
            return (s, e)
        if s >= t:
            break
    return None


def _bracketing_boundaries(
    t: float, words: list[tuple[float, float]]
) -> tuple[float | None, float | None]:
    """Return ``(prev_end, next_start)`` — the two bracketing word boundaries.

    Walks the sorted word list to find the latest word ending at-or-before ``t``
    (``prev_end``) and the first word starting at-or-after ``t`` (``next_start``).
    Either may be ``None`` at the head/tail of the transcript.
    """
    prev_end: float | None = None
    next_start: float | None = None
    for s, e in words:
        if e <= t + EPSILON_S:
            prev_end = e
        elif s >= t - EPSILON_S:
            next_start = s
            break
    return prev_end, next_start


def _padding_distance(t: float, words: list[tuple[float, float]]) -> float | None:
    """Min of the two bracketing-side padding distances; ``None`` if neither exists.

    HR 7 requires padding ≥ 30ms on BOTH sides of every cut, so the gate metric
    is ``min(t - prev_end, next_start - t)``. A global-min over every boundary
    in the transcript would falsely flag cuts in long silences between far-apart
    words; HR 7 specifies padding relative to the cut's *neighboring* word.
    """
    prev_end, next_start = _bracketing_boundaries(t, words)
    sides: list[float] = []
    if prev_end is not None:
        sides.append(t - prev_end)
    if next_start is not None:
        sides.append(next_start - t)
    if not sides:
        return None
    return min(sides)


def _hr7_violation(
    range_idx: int,
    label: str,
    t: float,
    words: list[tuple[float, float]],
) -> str:
    """Compose a prescriptive HR 7 violation that identifies the offending side(s).

    Computes the valid bracketing window where ``t`` would simultaneously satisfy
    the 30–200ms requirement on both sides; if non-empty, suggests a target.
    If the bracketing word gap is < 60ms (geometric infeasibility) the message
    instructs the model to drop or relocate the range — matching the brief's
    escape clause for unsatisfiable HR 7. The legacy `padding {dist}ms outside
    A–Bms` substring is preserved so existing tooling that scans for `padding`
    keeps matching.
    """
    prev_end, next_start = _bracketing_boundaries(t, words)
    side_strs: list[str] = []
    prev_dist_ms: float | None = None
    next_dist_ms: float | None = None
    if prev_end is not None:
        prev_dist_ms = (t - prev_end) * 1000.0
        side_strs.append(f"prev-side {prev_dist_ms:.0f}ms (prev_end={prev_end:.3f})")
    if next_start is not None:
        next_dist_ms = (next_start - t) * 1000.0
        side_strs.append(f"next-side {next_dist_ms:.0f}ms (next_start={next_start:.3f})")
    side_blob = "; ".join(side_strs) if side_strs else "no bracketing words"

    # Headline distance — the offending (smaller) side, for the legacy
    # `padding Nms outside A-Bms` substring scanners (incl. tests / brief feedback).
    headline_ms = _padding_distance(t, words)
    headline_ms = headline_ms * 1000.0 if headline_ms is not None else 0.0
    head = (
        f"range[{range_idx}].{label}={t:.3f}: padding {headline_ms:.0f}ms outside "
        f"{int(PADDING_MIN_S*1000)}–{int(PADDING_MAX_S*1000)}ms (HR 7) — "
        f"both sides must satisfy this; {side_blob}"
    )

    valid_lo: float | None = None
    valid_hi: float | None = None
    if prev_end is not None:
        valid_lo = prev_end + PADDING_MIN_S
        valid_hi = prev_end + PADDING_MAX_S
    if next_start is not None:
        next_lo = next_start - PADDING_MAX_S
        next_hi = next_start - PADDING_MIN_S
        valid_lo = next_lo if valid_lo is None else max(valid_lo, next_lo)
        valid_hi = next_hi if valid_hi is None else min(valid_hi, next_hi)

    if valid_lo is not None and valid_hi is not None and valid_lo <= valid_hi + EPSILON_S:
        target = (valid_lo + valid_hi) / 2.0
        return (
            f"{head} — valid window [{valid_lo:.3f}, {valid_hi:.3f}], "
            f"try {label}={target:.3f}"
        )
    if (
        prev_end is not None
        and next_start is not None
        and (next_start - prev_end) < (2 * PADDING_MIN_S) - EPSILON_S
    ):
        gap_ms = (next_start - prev_end) * 1000.0
        return (
            f"{head} — bracketing gap {gap_ms:.0f}ms < {int(2*PADDING_MIN_S*1000)}ms; "
            f"HR 7 infeasible at this position — drop or relocate this range"
        )
    return head


def _ffprobe_duration_s(path: Path) -> float | None:
    """Return container duration in seconds, or None on any failure.

    Used as a fallback when state.edit.inventory.sources is missing —
    happens when route_after_preflight skipped p3_inventory because
    takes_packed.md already existed (resume-on-cached-episode path).
    """
    if shutil.which("ffprobe") is None or not path.is_file():
        return None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        probe = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    raw = (probe.get("format") or {}).get("duration")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _source_duration_map(state: dict) -> dict[str, float]:
    """Build {stem: duration_s} from inventory state, falling back to ffprobe.

    Primary source: state.edit.inventory.sources (populated by p3_inventory).
    Fallback: ffprobe each path in state.edit.edl.sources directly.
    Skip-inventory routing — when preflight sees takes_packed.md and routes
    straight to p3_pre_scan — leaves inventory empty; without the fallback
    the gate would emit "pacing unverifiable" on every cached re-run.
    """
    inv = (state.get("edit") or {}).get("inventory") or {}
    out: dict[str, float] = {}
    for src in inv.get("sources") or []:
        stem = src.get("stem") or src.get("name")
        dur = src.get("duration_s")
        if stem and isinstance(dur, (int, float)) and dur > 0:
            out[str(stem)] = float(dur)
    if out:
        return out
    edl_sources = ((state.get("edit") or {}).get("edl") or {}).get("sources") or {}
    for stem, raw_path in edl_sources.items():
        if not isinstance(raw_path, str):
            continue
        dur = _ffprobe_duration_s(Path(raw_path))
        if dur and dur > 0:
            out[str(stem)] = dur
    return out


def _transcript_dir(state: dict) -> Path:
    episode_dir = state.get("episode_dir")
    return Path(episode_dir) / "edit" / "transcripts"


# Matches each occurrence of `curves=master='<keypoints>'` (or "double-quoted")
# inside an ffmpeg filter chain. The capture group is the keypoint payload —
# space-separated `x/y` pairs — which we then validate point-wise. Single + double
# quote variants both seen in the wild; ffmpeg accepts either. Empty quotes mean
# "use default curve", which we leave alone.
_CURVES_RE = re.compile(r"curves=master=(?:'([^']*)'|\"([^\"]*)\")")


def _grade_violations(grade: str) -> list[str]:
    """Validate the raw ffmpeg-filter-chain form of `edl.grade`.

    Canon (`SKILL.md` §"Color grade") allows raw ffmpeg filter strings via
    `grade.py --filter '<raw>'`. ffmpeg's `curves` filter requires every
    keypoint coordinate in [0, 1] — see `grade.py` PRESETS as worked
    examples. Pre-flight validation here catches `Invalid key point
    coordinates` before render burns the per-segment ffmpeg passes.

    Returns a list of violation strings; empty when grade is None / preset
    name / valid filter chain.
    """
    if not isinstance(grade, str) or not grade.strip():
        return []
    # Preset names contain no `=`; skip those.
    if "=" not in grade:
        return []
    out: list[str] = []
    for match in _CURVES_RE.finditer(grade):
        payload = match.group(1) if match.group(1) is not None else match.group(2)
        if not payload.strip():
            continue
        for token in payload.split():
            if "/" not in token:
                out.append(
                    f"grade.curves: malformed keypoint `{token}` "
                    f"(expected `x/y` with x,y in [0,1])"
                )
                continue
            x_str, _, y_str = token.partition("/")
            try:
                x = float(x_str)
                y = float(y_str)
            except ValueError:
                out.append(
                    f"grade.curves: non-numeric keypoint `{token}` "
                    f"(expected `x/y` with x,y in [0,1])"
                )
                continue
            if not (0.0 - EPSILON_S <= x <= 1.0 + EPSILON_S):
                out.append(
                    f"grade.curves: keypoint `{token}` x={x} outside [0,1] "
                    f"(ffmpeg curves filter rejects this)"
                )
            if not (0.0 - EPSILON_S <= y <= 1.0 + EPSILON_S):
                out.append(
                    f"grade.curves: keypoint `{token}` y={y} outside [0,1] "
                    f"(ffmpeg curves filter rejects this; clamp highlights "
                    f"to 1.0 or use eq=contrast/brightness instead)"
                )
    return out


def _strategy_length_estimate(state: dict) -> float | None:
    strategy = (state.get("edit") or {}).get("strategy") or {}
    estimate = strategy.get("length_estimate_s")
    if isinstance(estimate, (int, float)) and estimate > 0:
        return float(estimate)
    return None


class EdlOkGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:edl_ok")

    def checks(self, state: dict) -> list[str]:
        violations: list[str] = []
        edl = (state.get("edit") or {}).get("edl") or {}

        if edl.get("skipped"):
            return [f"edl skipped upstream: {edl.get('skip_reason')}"]
        if "raw_text" in edl and "ranges" not in edl:
            return ["edl unparseable (raw_text only — schema validation failed upstream)"]

        if "subtitles" in edl:
            violations.append("forbidden field `subtitles` present at top level")
        if edl.get("overlays") not in (None, []):
            violations.append(f"overlays must be [] (got {edl.get('overlays')!r})")
        violations.extend(_grade_violations(edl.get("grade") or ""))

        ranges = edl.get("ranges") or []
        if not ranges:
            violations.append("ranges is empty")
            return violations

        sources = edl.get("sources") or {}
        transcripts_dir = _transcript_dir(state)
        word_cache: dict[str, list[tuple[float, float]]] = {}

        def _load(source_key: str) -> list[tuple[float, float]] | None:
            if source_key in word_cache:
                return word_cache[source_key]
            tpath = transcripts_dir / f"{source_key}.json"
            if not tpath.is_file():
                return None
            try:
                words = _word_intervals(tpath)
            except (OSError, ValueError, KeyError) as exc:
                violations.append(f"transcript unreadable for source `{source_key}`: {exc}")
                return None
            word_cache[source_key] = words
            return words

        for i, r in enumerate(ranges):
            source = r.get("source")
            start = r.get("start")
            end = r.get("end")
            if source not in sources:
                violations.append(f"range[{i}].source `{source}` not in EDL.sources")
                continue
            words = _load(source)
            if words is None:
                violations.append(f"range[{i}]: missing transcript for source `{source}`")
                continue
            for label, t in (("start", start), ("end", end)):
                inside = _inside_word(t, words)
                if inside is not None:
                    violations.append(
                        f"range[{i}].{label}={t:.3f} cuts inside word [{inside[0]:.3f}, {inside[1]:.3f}] (HR 6)"
                    )
                    continue
                dist = _padding_distance(t, words)
                if dist is None:
                    violations.append(f"range[{i}].{label}: no word boundaries in transcript")
                    continue
                if dist < PADDING_MIN_S - EPSILON_S or dist > PADDING_MAX_S + EPSILON_S:
                    violations.append(_hr7_violation(i, label, t, words))

        cut_total = sum(max(0.0, float(r.get("end", 0)) - float(r.get("start", 0))) for r in ranges)
        durations = _source_duration_map(state)
        used_sources = {r.get("source") for r in ranges}
        source_total = sum(durations.get(s, 0.0) for s in used_sources)
        if source_total <= 0:
            violations.append(
                "pacing unverifiable: source durations missing from state.edit.inventory.sources"
            )
        else:
            estimate = _strategy_length_estimate(state)
            if estimate is None:
                # schemas.p3_strategy.Strategy declares length_estimate_s
                # as required (Field(gt=0)). Reaching this branch means
                # the upstream contract was violated — surface it loudly
                # rather than fall back to a one-artifact ratio that
                # pretends to validate strategy intent.
                violations.append(
                    "pacing unverifiable: strategy.length_estimate_s "
                    "missing — required by schemas.p3_strategy "
                    "(upstream contract violation)"
                )
            else:
                target_min = estimate * (1.0 - LENGTH_TOLERANCE)
                target_max = estimate * (1.0 + LENGTH_TOLERANCE)
                if cut_total < target_min - EPSILON_S or cut_total > target_max + EPSILON_S:
                    violations.append(
                        f"length {cut_total:.2f}s outside target "
                        f"{target_min:.2f}–{target_max:.2f}s "
                        f"(strategy.length_estimate_s={estimate:.2f}s "
                        f"±{int(LENGTH_TOLERANCE*100)}%)"
                    )

        return violations


def edl_ok_gate_node(state: dict) -> dict:
    return EdlOkGate()(state)
