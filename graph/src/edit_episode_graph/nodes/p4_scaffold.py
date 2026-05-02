"""p4_scaffold node — wraps `scripts/scaffold_hyperframes.py`.

Runs `npx hyperframes init` and applies the orchestrator's standard patches
(viewport, video+audio pair with `data-has-audio="false"`, package.json,
hardlink to final.mp4). After this node the LLM portion of Phase 4 begins
(`p4_design_system`, etc.) — not implemented until v4. The graph appends a
`notices` entry so the halt is visible in Studio output.
"""

import json
import sys
from pathlib import Path

from ._deterministic import deterministic_node

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _cmd(state) -> list[str]:
    episode_dir = state.get("episode_dir")
    slug = state.get("slug")
    if not episode_dir or not slug:
        raise RuntimeError("p4_scaffold: episode_dir/slug missing from state (pickup must run first)")
    return [
        sys.executable,
        "-m",
        "scripts.scaffold_hyperframes",
        "--episode-dir", episode_dir,
        "--slug", slug,
    ]


def _parse(stdout: str) -> dict:
    parsed = json.loads(stdout)
    hf_dir = parsed.get("hyperframes_dir")
    index_html = str(Path(hf_dir) / "index.html") if hf_dir else None
    return {
        "compose": {
            "hyperframes_dir": hf_dir,
            "index_html_path": index_html,
        },
        "notices": [
            "v1 halt: scaffold complete; next phase `p4_design_system` requires LLM (v2+)",
        ],
    }


p4_scaffold_node = deterministic_node(
    name="p4_scaffold",
    cmd_factory=_cmd,
    parser=_parse,
    cwd=PROJECT_ROOT,
)
