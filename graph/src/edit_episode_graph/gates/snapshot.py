"""gate:snapshot — runs `hyperframes snapshot` at beat timestamps.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks":
`snapshot` captures key frames as PNG screenshots for visual
verification (`hyperframes snapshot --help`: "Capture key frames from a
composition as PNG screenshots for visual verification").

## What this gate actually checks

`snapshot` produces PNGs but no JSON describing visible elements, so we
cannot canonically verify "expected element present in frame N" without
adding OCR or DOM extraction (out of scope; canon doesn't pin a JSON
shape for snapshot). Instead the gate enforces the structural health
checks that *do* have authority:

  1. CLI exits zero (snapshot ran without launch / runtime error).
  2. One PNG was produced per requested timestamp.
  3. Each PNG is non-trivially sized — anything below
     `_MIN_PNG_BYTES` is flagged as a probable blank/black render.

Item 3 is the productively useful check: the canonical
`<template>+data-composition-src` black-render bug
(memory `feedback_hf_subcomp_loader_data_composition_src`) yields
~5–15 kB PNGs versus 200 kB+ for normal content. Catching that here
is exactly the value the gate provides.

Beat starts come from `state.compose.plan.beats[*].duration_s`,
mirroring `gate:inspect`. With no plan we fall back to the CLI's
default `--frames=5` even sampling.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from ._base import Gate, hyperframes_dir, run_hf_cli


# Blank/black 1080x1920 PNG compresses to ~5–15 kB. Real content with
# text + colors typically 100 kB+. 30 kB is a conservative flag — well
# above true-black size, well below normal content size.
_MIN_PNG_BYTES = 30 * 1024

# Per CLI naming (verified against snapshot v0.4.45):
#   `frame-NN-at-T.Ts.png` when --at is passed (timestamps in seconds)
#   `frame-NN-at-NNpct.png` when --frames is used (evenly spaced, percent)
_FRAME_FILENAME = re.compile(r"^frame-\d+-at-[\d.]+(?:s|pct)\.png$", re.IGNORECASE)


def _beat_start_offsets(state: dict) -> list[float]:
    plan = ((state.get("compose") or {}).get("plan") or {})
    beats = plan.get("beats") or []
    offsets: list[float] = []
    cursor = 0.0
    for beat in beats:
        offsets.append(round(cursor, 3))
        try:
            duration = float(beat.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        cursor += duration
    return offsets


def _format_at_arg(offsets: Sequence[float]) -> str:
    return ",".join(f"{t:g}" for t in offsets)


def _png_files(snapshots_dir: Path) -> list[Path]:
    if not snapshots_dir.is_dir():
        return []
    return sorted(
        p for p in snapshots_dir.iterdir()
        if p.is_file() and _FRAME_FILENAME.match(p.name)
    )


class SnapshotGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:snapshot")

    def checks(self, state: dict) -> list[str]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot run snapshot"]
        if not hf_dir.is_dir():
            return [f"hyperframes dir not on disk: {hf_dir}"]

        offsets = _beat_start_offsets(state)
        args: list[str] = ["snapshot"]
        if offsets:
            args.extend(["--at", _format_at_arg(offsets)])
            expected_frames = len(offsets)
        else:
            expected_frames = 5  # CLI default for --frames

        # snapshot writes into <hf_dir>/snapshots/. Clear stale frames so
        # blank-render detection isn't masked by a previous good run.
        snapshots_dir = hf_dir / "snapshots"
        if snapshots_dir.is_dir():
            for stale in _png_files(snapshots_dir):
                try:
                    stale.unlink()
                except OSError:
                    pass

        result = run_hf_cli(args, hf_dir, timeout=180.0)

        if not result.ok:
            body = (result.stderr or result.stdout or "(no output)").strip()
            if len(body) > 1500:
                body = body[:1500] + "\n…(truncated)"
            return [f"hyperframes snapshot exit={result.exit_code}:\n{body}"]

        frames = _png_files(snapshots_dir)
        violations: list[str] = []

        if len(frames) < expected_frames:
            violations.append(
                f"expected {expected_frames} snapshot PNG(s) in {snapshots_dir}, "
                f"found {len(frames)}"
            )

        for png in frames:
            try:
                size = png.stat().st_size
            except OSError as exc:
                violations.append(f"could not stat {png.name}: {exc}")
                continue
            if size < _MIN_PNG_BYTES:
                violations.append(
                    f"{png.name} is {size} bytes (< {_MIN_PNG_BYTES}) — "
                    "probable blank/black render; check sub-composition loader "
                    "(see memory feedback_hf_subcomp_loader_data_composition_src)"
                )

        return violations


def snapshot_gate_node(state: dict) -> dict:
    return SnapshotGate()(state)
