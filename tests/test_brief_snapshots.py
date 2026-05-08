"""L0 brief snapshot tests (HOM-183).

One test per creative LLM node. Each renders the production Jinja
brief through ``edit_episode_graph.nodes._llm._BRIEF_ENV`` (via
``tests._helpers.brief_snapshots.render_brief``) with a stable
fixture context, and asserts the result matches the pinned
snapshot at ``tests/snapshots/briefs/<node>.txt``.

When a brief is intentionally edited:

    python -m pytest tests/test_brief_snapshots.py --update-snapshots

then commit the snapshot diff alongside the brief change in the same
PR. Reviewers read the textual diff to verify the canon-citation
contract (CLAUDE.md §"Decomposition via brief-references-canon"
item 1: briefs reference SKILL.md by path; never embed canon).

Spec: ``docs/superpowers/specs/2026-05-08-testing-infra-fixture-replay-design.md`` § 3.
"""

from __future__ import annotations

import pytest

from tests._helpers.brief_render_contexts import NODE_CONTEXTS
from tests._helpers.brief_snapshots import assert_brief_snapshot, render_brief


@pytest.mark.parametrize("node_name", sorted(NODE_CONTEXTS))
def test_brief_snapshot(node_name: str, pytestconfig) -> None:
    ctx = NODE_CONTEXTS[node_name]()
    rendered = render_brief(node_name, ctx)
    assert_brief_snapshot(node_name, rendered, pytestconfig=pytestconfig)
