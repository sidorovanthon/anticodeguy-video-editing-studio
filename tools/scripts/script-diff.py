#!/usr/bin/env python
"""CLI: run the script fidelity check for one episode.

Usage:
    python tools/scripts/script-diff.py --episode <path-to-episode-dir>

Reads:
    <episode>/source/script.txt
    <episode>/stage-1-cut/edit/transcripts/raw.json
    <episode>/stage-1-cut/edl.json

Writes:
    <episode>/stage-1-cut/script-diff.md
    <episode>/stage-1-cut/script-diff.json

Exits 0 with a skip note if any input is missing — never fails the pipeline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the sibling package importable when run as a script.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from script_diff.normalize import tokenize_script, tokenize_scribe
from script_diff.reconstruct import reconstruct_final
from script_diff.align import diff
from script_diff.retake import find_retakes
from script_diff.render import build_payload, render_md, build_alignment_preview, write_outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True, type=Path)
    args = ap.parse_args()

    episode: Path = args.episode
    script_path = episode / "source" / "script.txt"
    raw_path = episode / "stage-1-cut" / "edit" / "transcripts" / "raw.json"
    edl_path = episode / "stage-1-cut" / "edl.json"
    out_dir = episode / "stage-1-cut"

    for label, p in [("script.txt", script_path), ("raw.json", raw_path), ("edl.json", edl_path)]:
        if not p.is_file():
            print(f"script-diff: skipping ({label} not found at {p})")
            return 0

    script_text = script_path.read_text(encoding="utf-8")
    raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
    edl = json.loads(edl_path.read_text(encoding="utf-8"))

    script_tokens = tokenize_script(script_text)
    raw_tokens = tokenize_scribe(raw_data.get("words", []))
    final_tokens = reconstruct_final(raw_tokens, edl)

    d1 = diff(script_tokens, final_tokens)
    d2 = diff(script_tokens, raw_tokens)
    retakes = find_retakes(script_tokens, raw_tokens, edl)

    payload = build_payload(d1, d2, retakes)
    md = render_md(payload, build_alignment_preview(d1))
    write_outputs(out_dir, payload, md)

    print(f"script-diff: coverage {payload['script_coverage_pct']}%, "
          f"{len(payload['dropped_spans'])} dropped, "
          f"{len(payload['ad_libs'])} ad-libs, "
          f"{len(payload['retakes'])} retakes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
