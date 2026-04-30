"""Remap Scribe word-level transcript to hyperframes captions schema.

Input:  edit/transcripts/raw.json (Scribe nested {words: [...]})
        edit/edl.json             (video-use EDL)
Output: edit/transcripts/final.json (flat [{text,start,end}, ...])

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §4.3.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def remap(*, raw: dict, edl: dict) -> list[dict]:
    """Convert Scribe word-level + EDL ranges → hyperframes captions array.

    Drops `type != "word"` entries (spacing, audio_event, ...).
    Drops words whose source-timeline `start` falls outside any kept range.
    Output timeline = cumulative_output_offset + (word.start - range.start).
    """
    ranges = edl.get("ranges", [])
    output: list[dict] = []
    cumulative = 0.0
    for r in ranges:
        r_start = float(r["start"])
        r_end = float(r["end"])
        for w in raw.get("words", []):
            if w.get("type") != "word":
                continue
            ws = float(w["start"])
            if not (r_start <= ws < r_end):
                continue
            we = float(w["end"])
            output.append({
                "text": w["text"],
                "start": round(cumulative + (ws - r_start), 6),
                "end": round(cumulative + (we - r_start), 6),
            })
        cumulative += (r_end - r_start)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remap Scribe transcript to hyperframes captions schema.")
    parser.add_argument("--raw", type=Path, required=True, help="Path to edit/transcripts/raw.json")
    parser.add_argument("--edl", type=Path, required=True, help="Path to edit/edl.json")
    parser.add_argument("--out", type=Path, required=True, help="Path to write edit/transcripts/final.json")
    args = parser.parse_args(argv)

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    edl = json.loads(args.edl.read_text(encoding="utf-8"))
    result = remap(raw=raw, edl=edl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(result)} word entries to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
