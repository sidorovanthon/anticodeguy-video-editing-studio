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
from .._paths import EpisodePaths, scripts_root

SCRIPTS_ROOT = scripts_root()

# Bump on remap_transcript.py shape / output-schema change. Spec §8.
# v2 (HOM-223): identity-only state writes — `transcripts.raw_json_path`
# / `transcripts.final_json_path` no longer emitted by this node;
# consumers derive via `EpisodePaths(slug).transcripts_raw_json_path` /
# `transcripts_final_json_path`.
# v3 (HOM-279): node also hoists `raw.json` + `final.json` bodies into
# `transcripts.bodies` (state-channel) so Phase-4 consumers
# (`gate:edl_ok`, `p4_captions_layer`, `p4_prompt_expansion`) can read
# transcript content from state instead of re-opening disk files. The
# disk artifacts remain authoritative — they are Phase 3 ffmpeg outputs.
# Output schema change → cache invalidation (pre-HOM-279 recordings
# don't carry `transcripts.bodies` and would feed downstream consumers
# nothing). Cache key inputs (`files=[edl_json, raw_json]`) unchanged —
# both bodies are derived from those two files.
# v4 (HOM-285): raw body responsibility hoisted upstream to `p3_inventory`
# (the Scribe producer). This node now only writes `final` + `final_path`
# to `transcripts.bodies` — raw is already populated when we arrive.
# Pre-HOM-285 dual-write removed so future readers can't accidentally
# depend on the in-glue raw write. Output shape change → cache bump.
_CACHE_VERSION = 4


def _edl_path_for_key(state: dict) -> str | None:
    """Resolve `edit/edl.json` for cache-key fingerprinting (HOM-223 — slug only)."""
    slug = state.get("slug")
    if not slug:
        return None
    return str(EpisodePaths(slug).edit_dir / "edl.json")


def _raw_json_path_for_key(state: dict) -> str | None:
    """Resolve `edit/transcripts/raw.json` for cache-key fingerprinting."""
    slug = state.get("slug")
    if not slug:
        return None
    return str(EpisodePaths(slug).transcripts_raw_json_path)


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
    # HOM-334 Phase A.5: step-debug pre/post interrupts around the
    # remap_transcript subprocess. No-op when ``HOMESTUDIO_STEP_DEBUG`` is
    # unset.
    from .._step_debug import is_enabled as _sd_enabled, wrap_deterministic_node

    if _sd_enabled():
        return wrap_deterministic_node(
            "glue_remap_transcript",
            state=state,
            context={"slug": state.get("slug")},
            inner=lambda: _glue_remap_transcript_body(state),
        )
    return _glue_remap_transcript_body(state)


def _glue_remap_transcript_body(state):
    slug = state.get("slug")
    if not slug:
        return _error("slug missing from state (pickup must run first)")
    paths = EpisodePaths(slug)
    raw_json = paths.transcripts_raw_json_path
    edl_json = paths.edit_dir / "edl.json"
    final_json = paths.transcripts_final_json_path

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
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPTS_ROOT)
    if result.returncode != 0:
        combined = "\n".join(s for s in (result.stderr, result.stdout) if s).strip()
        return _error(combined or f"exit code {result.returncode}, no output")

    edl_hash: str | None = None
    final_body: str | None = None
    try:
        final_body = final_json.read_text(encoding="utf-8")
        envelope = json.loads(final_body)
        if isinstance(envelope, dict):
            edl_hash = envelope.get("edl_hash")
    except (OSError, json.JSONDecodeError) as exc:
        return _error(f"final.json unreadable after remap: {exc!r}")

    # HOM-285: only `final` + `final_path` are this node's responsibility.
    # The raw body was hoisted upstream to `p3_inventory` (the Scribe
    # producer) so `gate_edl_ok` (which runs BEFORE this node) can read
    # it from state without a disk fallback. Because the `transcripts`
    # state reducer (`dict_merge`) is shallow, we must preserve any
    # pre-existing `bodies` entries — otherwise our emitted `bodies` dict
    # would overwrite p3_inventory's `raw`/`raw_path` keys and silently
    # break the gate read. Re-emitting the prior `raw`/`raw_path` slots
    # is idempotent (identical content) and keeps this node's surface
    # narrowed to "produce final".
    prior_bodies = ((state.get("transcripts") or {}).get("bodies") or {})
    new_bodies = dict(prior_bodies)
    new_bodies["final"] = final_body
    new_bodies["final_path"] = str(final_json)

    # HOM-223: identity-only state — `raw_json_path` / `final_json_path`
    # no longer echoed; consumers derive via
    # `EpisodePaths(slug).transcripts_raw_json_path` /
    # `transcripts_final_json_path`. `edl_hash` remains (content fingerprint).
    return {
        "transcripts": {
            "edl_hash": edl_hash,
            "bodies": new_bodies,
        },
        "edit": {"edl": edl_payload},
    }
