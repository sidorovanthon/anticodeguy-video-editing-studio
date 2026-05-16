"""p4_scaffold node — wraps `scripts/scaffold_hyperframes.py`.

Runs `npx hyperframes init` and applies the orchestrator's standard patches
(viewport, video+audio pair with `data-has-audio="false"`, package.json,
hardlink to final.mp4). After this node the LLM portion of Phase 4 begins
(`p4_design_system`, etc.) — not implemented until v4. The graph appends a
`notices` entry so the halt is visible in Studio output.
"""

import json
import sys

from langgraph.types import CachePolicy

from .._caching import make_key
from .._paths import EpisodePaths, scripts_root
from ._deterministic import deterministic_node

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
_CACHE_VERSION = 4


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


def _parse(stdout: str) -> dict:
    # HOM-224: subprocess still emits `hyperframes_dir` for back-compat /
    # operator visibility, but we no longer echo it into state — consumers
    # derive via `EpisodePaths(slug).hyperframes_dir`. Parse the stdout
    # for its JSON-validity side effect (raises on malformed scaffold
    # output) and discard the value.
    json.loads(stdout)
    return {
        "notices": [
            "v1 halt: scaffold complete; next phase `p4_design_system` requires LLM (v2+)",
        ],
    }


p4_scaffold_node = deterministic_node(
    name="p4_scaffold",
    cmd_factory=_cmd,
    parser=_parse,
    cwd=SCRIPTS_ROOT,
)
