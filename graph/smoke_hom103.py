"""HOM-103 real-CLI smoke: drive p3_render_segments through canon render.py
against a synthetic ffmpeg-testsrc episode. Verifies the subprocess shape,
ffprobe duration parsing, and the ±100ms tolerance gate.

Run:  PYTHONPATH=src python smoke_hom103.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "graph" / "src"))

from edit_episode_graph.nodes.p3_render_segments import p3_render_segments_node  # noqa: E402


def _make_testsrc(out_path: Path, duration: int = 10) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=24",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg/ffprobe not on PATH", file=sys.stderr)
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="hom103-smoke-"))
    print(f"smoke workdir: {workdir}")
    try:
        episode = workdir / "ep"
        edit = episode / "edit"
        edit.mkdir(parents=True)
        raw = episode / "raw.mp4"

        print("[1/3] synthesizing 10s testsrc episode...")
        _make_testsrc(raw, duration=10)

        ranges = [
            {"source": "raw", "start": 0.5, "end": 2.0, "beat": "A", "quote": "x", "reason": "smoke"},
            {"source": "raw", "start": 3.0, "end": 5.5, "beat": "B", "quote": "x", "reason": "smoke"},
            {"source": "raw", "start": 7.0, "end": 7.5, "beat": "C", "quote": "x", "reason": "smoke"},
        ]
        total = sum(r["end"] - r["start"] for r in ranges)
        edl = {
            "version": 1,
            "sources": {"raw": str(raw)},
            "ranges": ranges,
            "grade": "neutral_punch",
            "overlays": [],
            "total_duration_s": total,
        }
        (edit / "edl.json").write_text(json.dumps(edl, indent=2), encoding="utf-8")

        state = {
            "episode_dir": str(episode),
            "edit": {"edl": dict(edl)},
        }

        print(f"[2/3] invoking p3_render_segments_node (expected duration {total:.2f}s)...")
        update = p3_render_segments_node(state)

        print("[3/3] result:")
        print(json.dumps(update, indent=2, default=str))

        if "errors" in update:
            print("SMOKE FAIL: errors recorded", file=sys.stderr)
            return 1
        render = update["edit"]["render"]
        if not render.get("final_mp4"):
            print("SMOKE FAIL: no final_mp4 path", file=sys.stderr)
            return 1
        delta = render.get("delta_ms")
        if delta is None or delta > 100:
            print(f"SMOKE FAIL: delta_ms {delta} out of tolerance", file=sys.stderr)
            return 1
        if not Path(render["final_mp4"]).exists():
            print("SMOKE FAIL: final.mp4 path missing on disk", file=sys.stderr)
            return 1
        print(f"SMOKE OK: final.mp4 duration {render['duration_s']:.3f}s, "
              f"expected {render['expected_duration_s']:.3f}s, Δ {delta}ms")
        return 0
    finally:
        if os.environ.get("HOM103_SMOKE_KEEP", "1") != "1":
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
