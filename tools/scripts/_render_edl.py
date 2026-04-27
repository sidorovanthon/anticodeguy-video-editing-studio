#!/usr/bin/env python3
"""Render master.mp4 from edl.json + grade.json via a single ffmpeg invocation.

Spec-compliant output: 1440x2560, 60 fps, Rec.709 SDR, H.264 high@5.1,
~35 Mbps VBR, AAC 48 kHz stereo 320 kbps.
"""
from __future__ import annotations
import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def to_native_path(p: str) -> str:
    """Convert a POSIX-style path (e.g. from Git Bash) to a native OS path.

    On Windows, paths like /tmp/... must be converted to C:\\Users\\... so that
    native executables (ffmpeg, ffprobe) can open them. Uses cygpath when
    available; falls back to the path as-is.
    """
    if os.name == "nt" and p.startswith("/"):
        try:
            result = subprocess.run(
                ["cygpath", "-w", p],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    return p


def build_ffmpeg_cmd(edl: dict, grade: dict, output: Path) -> list[str]:
    ranges = edl["ranges"]
    if not ranges:
        sys.exit("edl.json has no ranges")

    # One -i per range, with -ss/-to for fast trim.
    inputs: list[str] = []
    for r in ranges:
        src_path = to_native_path(edl["sources"][r["source"]])
        inputs += ["-ss", f"{r['start']:.3f}", "-to", f"{r['end']:.3f}", "-i", src_path]

    n = len(ranges)
    # filter_complex: concat all (video+audio), then apply grade chain + scale + fps to video.
    # The trailing `format=yuv420p` and `setparams=range=tv` clamp the output to
    # studio-range yuv420p; without them, the eq filter inside grade_chain emits
    # `yuvj420p` (full-range PC), which violates the Rec.709 broadcast-range spec.
    concat_inputs = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    COLOR_PARAMS = (
        "setparams=range=tv:colorspace=bt709:color_trc=bt709:color_primaries=bt709"
    )
    grade_chain = grade.get("ffmpeg_filter_chain", "")
    # scale with explicit range conversion: full (yuvj420p, 0-255) → tv (yuv420p, 16-235).
    # Without out_range=tv the data stays full-range but gets tagged as tv, so players
    # crush shadows and highlights — picture goes dark.
    SCALE = "scale=1440:2560:flags=lanczos:in_range=auto:out_range=tv"
    if grade_chain:
        video_chain = (
            f"[vc]{grade_chain},{SCALE},fps=60,"
            f"format=yuv420p,{COLOR_PARAMS}[v]"
        )
    else:
        video_chain = (
            f"[vc]{SCALE},fps=60,"
            f"format=yuv420p,{COLOR_PARAMS}[v]"
        )

    # dynaudnorm normalizes per-frame without lookahead, so no startup PTS desync.
    # Two-pass loudnorm with measured values would hit -14 LUFS more precisely but
    # is integrated post-Audio-Isolator (see retro.md PROMOTE for pipeline upgrade).
    audio_chain = "[a]dynaudnorm=p=0.79:m=10:g=15:s=12[am]"

    filter_complex = (
        f"{concat_inputs}concat=n={n}:v=1:a=1[vc][a];"
        f"{video_chain};"
        f"{audio_chain}"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[am]",
        "-c:v", "libx264", "-profile:v", "high", "-level", "5.1",
        "-pix_fmt", "yuv420p",
        "-g", "60",  # one I-frame per second
        "-tune", "fastdecode",  # reduces decoder load (lighter B-pyramid, no CABAC quirks)
        "-b:v", "35M", "-maxrate", "40M", "-bufsize", "70M",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
        to_native_path(str(output)),
    ]
    return cmd


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--edl",    required=True, type=Path)
    p.add_argument("--grade",  required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    with args.edl.open() as f:
        edl = json.load(f)
    with args.grade.open() as f:
        grade = json.load(f)

    cmd = build_ffmpeg_cmd(edl, grade, args.output)
    print("Running:", " ".join(shlex.quote(c) for c in cmd), flush=True)
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc

    print(f"Rendered: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
