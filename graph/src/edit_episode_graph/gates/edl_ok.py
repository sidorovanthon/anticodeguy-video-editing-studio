"""gate:edl_ok — validates the EDL produced by p3_edl_select.

Per spec §6.2 / canon HR 6+7:
  - EDL parseable + non-empty (Pydantic schema absence of `subtitles` already
    enforced by `extra="forbid"` upstream; this gate cross-checks at dict
    level as defense-in-depth and emits a concrete violation if missed).
  - Every cut edge falls outside word intervals (HR 6) — no cut inside a word.
  - Each cut edge sits 30–200ms from the nearest word boundary (HR 7 padding).
  - Total cut runtime / total source runtime in [0.25, 0.35] (pacing).
  - `overlays == []` (Phase-3 orchestrator policy; Phase 4 owns animation).
  - `subtitles` field absent at dict level.
"""

from __future__ import annotations

import json
from pathlib import Path

from ._base import Gate

PADDING_MIN_S = 0.030
PADDING_MAX_S = 0.200
PACING_MIN = 0.25
PACING_MAX = 0.35
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


def _word_boundaries(words: list[tuple[float, float]]) -> list[float]:
    """Sorted unique list of every word start and end (the legal cut points before padding)."""
    out: set[float] = set()
    for s, e in words:
        out.add(s)
        out.add(e)
    return sorted(out)


def _inside_word(t: float, words: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Return the (start, end) of the word containing t, or None."""
    for s, e in words:
        if s + EPSILON_S < t < e - EPSILON_S:
            return (s, e)
        if s >= t:
            break
    return None


def _nearest_boundary_distance(t: float, boundaries: list[float]) -> float | None:
    if not boundaries:
        return None
    return min(abs(t - b) for b in boundaries)


def _source_duration_map(state: dict) -> dict[str, float]:
    inv = (state.get("edit") or {}).get("inventory") or {}
    out: dict[str, float] = {}
    for src in inv.get("sources") or []:
        stem = src.get("stem") or src.get("name")
        dur = src.get("duration_s")
        if stem and isinstance(dur, (int, float)) and dur > 0:
            out[str(stem)] = float(dur)
    return out


def _transcript_dir(state: dict) -> Path:
    episode_dir = state.get("episode_dir")
    return Path(episode_dir) / "edit" / "transcripts"


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
        boundary_cache: dict[str, list[float]] = {}

        def _load(source_key: str) -> tuple[list[tuple[float, float]], list[float]] | None:
            if source_key in word_cache:
                return word_cache[source_key], boundary_cache[source_key]
            tpath = transcripts_dir / f"{source_key}.json"
            if not tpath.is_file():
                return None
            try:
                words = _word_intervals(tpath)
            except (OSError, ValueError, KeyError) as exc:
                violations.append(f"transcript unreadable for source `{source_key}`: {exc}")
                return None
            word_cache[source_key] = words
            boundary_cache[source_key] = _word_boundaries(words)
            return words, boundary_cache[source_key]

        for i, r in enumerate(ranges):
            source = r.get("source")
            start = r.get("start")
            end = r.get("end")
            if source not in sources:
                violations.append(f"range[{i}].source `{source}` not in EDL.sources")
                continue
            loaded = _load(source)
            if loaded is None:
                violations.append(f"range[{i}]: missing transcript for source `{source}`")
                continue
            words, boundaries = loaded
            for label, t in (("start", start), ("end", end)):
                inside = _inside_word(t, words)
                if inside is not None:
                    violations.append(
                        f"range[{i}].{label}={t:.3f} cuts inside word [{inside[0]:.3f}, {inside[1]:.3f}] (HR 6)"
                    )
                    continue
                dist = _nearest_boundary_distance(t, boundaries)
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
            ratio = cut_total / source_total
            if ratio < PACING_MIN - EPSILON_S or ratio > PACING_MAX + EPSILON_S:
                violations.append(
                    f"pacing {ratio:.2%} outside {PACING_MIN:.0%}–{PACING_MAX:.0%} "
                    f"(cut {cut_total:.2f}s of {source_total:.2f}s)"
                )

        return violations


def edl_ok_gate_node(state: dict) -> dict:
    return EdlOkGate()(state)
