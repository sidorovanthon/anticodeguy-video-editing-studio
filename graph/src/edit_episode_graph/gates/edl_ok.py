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
"""

from __future__ import annotations

import json
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


def _padding_distance(t: float, words: list[tuple[float, float]]) -> float | None:
    """Distance from `t` to the nearer of the two bracketing word boundaries.

    Walks the sorted word list to find the latest word ending at-or-before `t`
    (`prev_end`) and the first word starting at-or-after `t` (`next_start`).
    Returns `min(t - prev_end, next_start - t)` over whichever sides exist.

    A global-min over every boundary in the transcript would falsely flag cuts
    that sit in long silences between far-apart words: HR 7 specifies padding
    relative to the cut's *neighboring* word, not the closest word anywhere.
    """
    prev_end = None
    next_start = None
    for s, e in words:
        if e <= t + EPSILON_S:
            prev_end = e
        elif s >= t - EPSILON_S:
            next_start = s
            break
    sides: list[float] = []
    if prev_end is not None:
        sides.append(t - prev_end)
    if next_start is not None:
        sides.append(next_start - t)
    if not sides:
        return None
    return min(sides)


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
                    violations.append(
                        f"range[{i}].{label}={t:.3f}: padding {dist*1000:.0f}ms outside "
                        f"{int(PADDING_MIN_S*1000)}–{int(PADDING_MAX_S*1000)}ms (HR 7)"
                    )

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
