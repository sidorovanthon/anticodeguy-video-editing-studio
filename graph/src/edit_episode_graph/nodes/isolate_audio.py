"""isolate_audio node — wraps `scripts/isolate_audio.py` via the deterministic-node factory.

Phase 2 (ElevenLabs Audio Isolation). The wrapped script is itself idempotent
(tag check first, then WAV cache, then mux), but the v1 graph adds a structural
`skip_phase2?` conditional edge upstream so Studio can visualize the skip
decision without the script being invoked at all.

When this node *does* run, the script's own tag/cache layers may still
short-circuit and return cached=true / api_called=false — that's expected and
distinct from the upstream skip-edge.
"""

import json
import sys
from pathlib import Path

from langgraph.types import CachePolicy

from .._caching import make_key
from ._deterministic import deterministic_node

PROJECT_ROOT = Path(__file__).resolve().parents[4]

# Bump on script behavior / parser / output-shape change. Spec §8 review checkpoint.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `isolate_audio` (HOM-132.4 — primary cost saving of HOM-132 epic).

    The wrapped subprocess re-spends ElevenLabs Scribe credits on every cold
    invocation. Caching at the graph layer skips the subprocess entirely on
    warm re-runs.

    `pickup.raw_path` is the canonical upstream artifact (set by `pickup`
    before this node ever runs); content-fingerprinting it invalidates
    naturally when the user replaces the raw video.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"isolate_audio cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    raw_path = (state.get("pickup") or {}).get("raw_path")
    return make_key(
        node="isolate_audio",
        version=_CACHE_VERSION,
        slug=slug,
        files=[raw_path],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _cmd(state) -> list[str]:
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        raise RuntimeError("isolate_audio: episode_dir missing from state (pickup must run first)")
    return [
        sys.executable,
        "-m",
        "scripts.isolate_audio",
        "--episode-dir",
        episode_dir,
    ]


def _parse(stdout: str) -> dict:
    parsed = json.loads(stdout)
    return {
        "audio": {
            "cached": parsed.get("cached", False),
            "api_called": parsed.get("api_called", False),
            "wav_path": parsed.get("wav_path"),
            "reason": parsed.get("reason"),
        },
    }


isolate_audio_node = deterministic_node(
    name="isolate_audio",
    cmd_factory=_cmd,
    parser=_parse,
    cwd=PROJECT_ROOT,
)
