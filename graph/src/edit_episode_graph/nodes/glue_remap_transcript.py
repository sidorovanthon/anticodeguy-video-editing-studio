"""glue_remap_transcript node — wraps `scripts/remap_transcript.py`.

Reads `<episode_dir>/edit/transcripts/raw.json` + `<episode_dir>/edit/edl.json`,
writes `<episode_dir>/edit/transcripts/final.json`. The wrapped script
self-heals: if `final.json` is already current for the EDL hash it short-
circuits silently, so re-runs are cheap.

Output contract: the script writes envelope `{edl_hash, words}` and prints a
status line to **stderr** (not stdout) — stdout is empty on success. This
node therefore returns the resolved paths and re-reads the envelope to
populate `transcripts.edl_hash`, rather than parsing subprocess stdout.

## EDL hydration (HOM-144)

When Phase 3 ran offline via `/edit-episode` and we resume in-graph at
Phase 4, no upstream node has populated `state.edit.edl` — the EDL only
exists on disk at `edit/edl.json`. Phase 4 nodes that gate on EDL beats
(`p4_design_system`, `p4_plan`, etc.) would skip with "no EDL beats to
map" and the entire chain collapses. This node loads `edl.json` into
`state.edit.edl` so the in-graph Phase 4 sees the same EDL as the legacy
flow. The file is in canonical EDL shape — no transformation needed.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import CachePolicy

from .._caching import make_key
from .._paths import project_root

PROJECT_ROOT = project_root()

# Bump on remap_transcript.py shape / output-schema change. Spec §8.
_CACHE_VERSION = 1


def _edl_path_for_key(state: dict) -> str | None:
    """Resolve `edit/edl.json` for cache-key fingerprinting.

    Falls back to `<episode_dir>/edit/edl.json` when state hasn't yet been
    populated (e.g. resume-in-graph after offline `/edit-episode` Phase 3 —
    see HOM-144 docstring above).
    """
    edl = (state.get("edit") or {}).get("edl") or {}
    explicit = edl.get("edl_path")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "edl.json")


def _raw_json_path_for_key(state: dict) -> str | None:
    """Resolve `edit/transcripts/raw.json` for cache-key fingerprinting."""
    explicit = (state.get("transcripts") or {}).get("raw_json_path")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "transcripts" / "raw.json")


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `glue_remap_transcript` (HOM-132.4).

    Output `final.json` is deterministic in (`edl.json`, `raw.json`) — the
    wrapped `remap_transcript.py` is pure given those inputs. `final.json`
    is the OUTPUT and deliberately NOT in `files=` (mirrors the
    `p3_persist_session` / `p3_render_segments` rule — listing a mutated
    output forces cold→warm to cache-miss, defeating idempotency).
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"glue_remap_transcript cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    return make_key(
        node="glue_remap_transcript",
        version=_CACHE_VERSION,
        slug=slug,
        files=[_edl_path_for_key(state), _raw_json_path_for_key(state)],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


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

    # Load the EDL into state. We read this BEFORE invoking the subprocess
    # so a malformed file fails fast with a precise message, instead of the
    # remap script erroring out half-way and leaving final.json in a
    # questionable state.
    try:
        edl_payload = json.loads(edl_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error(f"{edl_json} unreadable: {exc!r}")
    if not isinstance(edl_payload, dict) or not isinstance(edl_payload.get("ranges"), list):
        return _error(
            f"{edl_json} is not a valid EDL — expected object with `ranges` list, "
            f"got {type(edl_payload).__name__}"
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
        "edit": {"edl": edl_payload},
    }
