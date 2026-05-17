"""p4_scaffold node — wraps `scripts/scaffold_hyperframes.py`.

Runs `npx hyperframes init` and applies the orchestrator's standard patches
(viewport, video+audio pair with `data-has-audio="false"`, package.json,
hardlink to final.mp4). After this node the LLM portion of Phase 4 begins
(`p4_design_system`, etc.) — not implemented until v4. The graph appends a
`notices` entry so the halt is visible in Studio output.

HOM-280 — the scaffolded ``<hf>/index.html`` body is hoisted into
``state.compose.scaffold.index_html`` after the subprocess returns. The
disk write becomes a transient side-effect; downstream consumers
(``p4_assemble_index``, ``p4_dispatch_beats``) read the body from state
instead of re-opening the disk file. This closes the
deterministic-node-side-effect-vs-cache-hit bug where a cache hit on this
node skipped the subprocess (and disk write), leaving downstream nodes
without an ``index.html`` to read.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone

from langgraph.types import CachePolicy

from .._caching import make_key
from .._paths import EpisodePaths, scripts_root

SCRIPTS_ROOT = scripts_root()

# Bump on scaffold_hyperframes.py shape / patch-set change. Spec §8.
# v2 (HOM-191): patch_index_html now rewrites literal `background: #000;` to
# `background: var(--bg, transparent);` so palette tokens land via
# p4_assemble_index's `:root` block instead of a hard-coded hex that
# `gate:design_adherence` (rightly) flags as out-of-palette.
# v3 (HOM-224): identity-only state writes — `compose.hyperframes_dir` and
# `compose.index_html_path` no longer echoed; consumers derive via
# `EpisodePaths(slug)`. Brief / subprocess shape unchanged.
# v4 (HOM-216 phase 2): force re-run after HOM-239 stripped fixture index.html;
# scaffold's subprocess writes are not state-tracked, so cache hit skipped the
# disk-write and downstream p4_assemble_index failed to find index.html.
# v5 (HOM-280): node output contract changed — the scaffolded `<hf>/index.html`
# body is now hoisted into `compose.scaffold.index_html` after the subprocess
# returns. A cache hit replays the state update (body + timestamp), so the
# downstream consumers no longer depend on the disk file. The v4 force-re-run
# rationale is obsolete and the cache-hit-vs-disk-write race is closed by
# construction.
_CACHE_VERSION = 5


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p4_scaffold` (HOM-132.4).

    The scaffolding subprocess is deterministic given a slug + episode_dir
    (fresh `npx hyperframes init` + orchestrator patches). It produces files
    under `<episode>/hyperframes/` — those are the node's OUTPUTS and are
    NOT in `files=` (mirrors the `p3_render_segments` mutated-output rule).

    Per spec §6: `files=[]` (depends on slug only).
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_scaffold cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    return make_key(
        node="p4_scaffold",
        version=_CACHE_VERSION,
        slug=slug,
        files=[],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cmd(state) -> list[str]:
    slug = state.get("slug")
    if not slug:
        raise RuntimeError("p4_scaffold: slug missing from state (pickup must run first)")
    # HOM-224: derive episode_dir via EpisodePaths instead of consuming the
    # state echo. The scaffold subprocess wants an explicit --episode-dir
    # so it can write under it; we pass the EpisodePaths-derived value.
    # Legacy state echo (`state["episode_dir"]`) is honored as fallback so
    # synthetic-state unit tests / pre-pickup states keep working.
    episode_dir = state.get("episode_dir") or str(EpisodePaths(slug).episode_dir)
    return [
        sys.executable,
        "-m",
        "scripts.scaffold_hyperframes",
        "--episode-dir", episode_dir,
        "--slug", slug,
    ]


def _error(message: str) -> dict:
    return {
        "errors": [
            {"node": "p4_scaffold", "message": message, "timestamp": _now()},
        ]
    }


def p4_scaffold_node(state: dict) -> dict:
    """Run the scaffold subprocess and hoist the resulting index.html body into state.

    HOM-280: post-subprocess, read ``<hf>/index.html`` from disk and store
    its body under ``compose.scaffold.index_html``. The disk write is a
    transient side-effect of the subprocess — downstream consumers read
    from state, so a cache hit (which skips the subprocess) replays the
    same state update without depending on the file's disk presence.
    """
    cmd = _cmd(state)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=SCRIPTS_ROOT,
    )
    if result.returncode != 0:
        combined = "\n".join(s for s in (result.stderr, result.stdout) if s).strip()
        return _error(combined or f"exit code {result.returncode}, no output")
    # HOM-224: subprocess still emits `hyperframes_dir` for back-compat /
    # operator visibility, but we no longer echo it into state — consumers
    # derive via `EpisodePaths(slug).hyperframes_dir`. Parse the stdout
    # for its JSON-validity side effect (raises on malformed scaffold
    # output) and discard the value.
    try:
        json.loads(result.stdout)
    except Exception as exc:
        return _error(
            f"parser error: {exc!r}\n--- stdout ---\n{result.stdout}"
        )

    # HOM-280: hoist the scaffolded index.html body into state. The
    # subprocess writes the file under `EpisodePaths(slug).index_html_path`
    # (see `scripts/scaffold_hyperframes.py:patch_index_html`); we re-read
    # it here so a cache hit replays the same state update without
    # re-running the subprocess. EpisodePaths is the canonical resolver
    # (HOM-224); no legacy fallback because this is a fresh write site.
    slug = state.get("slug")
    if not slug:
        return _error("slug missing from state — cannot resolve index.html path")
    index_path = EpisodePaths(slug).index_html_path
    try:
        body = index_path.read_text(encoding="utf-8")  # disk-io-allow: re-read scaffolded index.html written by npx hyperframes init subprocess (HOM-280)
    except OSError as exc:
        return _error(
            f"failed to read scaffolded index.html at {index_path}: {exc!r}"
        )

    return {
        "compose": {
            "scaffold": {
                "index_html": body,
                "scaffolded_at": _now(),
            },
        },
        "notices": [
            "v1 halt: scaffold complete; next phase `p4_design_system` requires LLM (v2+)",
        ],
    }
