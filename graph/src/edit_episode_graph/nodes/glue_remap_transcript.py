"""glue_remap_transcript node — wraps `scripts/remap_transcript.py`.

Reads `<episode_dir>/edit/transcripts/raw.json` + `<episode_dir>/edit/edl.json`,
writes `<episode_dir>/edit/transcripts/final.json`. The wrapped script
self-heals: if `final.json` is already current for the EDL hash it short-
circuits silently, so re-runs are cheap.

Output contract: the script writes envelope `{edl_hash, words}` and prints a
status line to **stderr** (not stdout) — stdout is empty on success. This
node therefore returns the resolved paths and re-reads the envelope to
populate `transcripts.edl_hash`, rather than parsing subprocess stdout.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {"errors": [{"node": "glue_remap_transcript", "message": message, "timestamp": _now()}]}


def glue_remap_transcript_node(state):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return _error("episode_dir missing from state (pickup must run first)")
    ep = Path(episode_dir)
    raw_json = ep / "edit" / "transcripts" / "raw.json"
    edl_json = ep / "edit" / "edl.json"
    final_json = ep / "edit" / "transcripts" / "final.json"

    # Both raw.json and edl.json are produced by Phase 3 (video-use). When
    # Phase 3 is skipped via the `skip_phase3?` edge they must already exist
    # — surface a precise error rather than letting the script fail with a
    # less informative FileNotFoundError.
    missing = [p for p in (raw_json, edl_json) if not p.exists()]
    if missing:
        return _error(
            "missing Phase 3 artifact(s): " + ", ".join(str(p) for p in missing)
            + " — run `/edit-episode` Phase 3 (video-use) first, or wait for v3"
        )

    cmd = [
        sys.executable,
        "-m",
        "scripts.remap_transcript",
        "--raw", str(raw_json),
        "--edl", str(edl_json),
        "--out", str(final_json),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        combined = "\n".join(s for s in (result.stderr, result.stdout) if s).strip()
        return _error(combined or f"exit code {result.returncode}, no output")

    edl_hash: str | None = None
    try:
        envelope = json.loads(final_json.read_text(encoding="utf-8"))
        if isinstance(envelope, dict):
            edl_hash = envelope.get("edl_hash")
    except (OSError, json.JSONDecodeError) as exc:
        return _error(f"final.json unreadable after remap: {exc!r}")

    return {
        "transcripts": {
            "raw_json_path": str(raw_json),
            "final_json_path": str(final_json),
            "edl_hash": edl_hash,
        },
    }
