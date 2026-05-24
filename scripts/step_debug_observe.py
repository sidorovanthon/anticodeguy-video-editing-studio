"""Orchestrator-side step-debug observability helper (HOM-369).

Pairs with the graph-side ``interrupt_after="*"`` wiring in
``graph/src/edit_episode_graph/graph.py::build_graph`` (gated on
``HOMESTUDIO_STEP_DEBUG=1``). When the graph pauses at a superstep
boundary, run this script against the live LangGraph server to dump
the four observability artifacts the operator needs for the 4-point
report (canon / what-it-did / clean-session / discrepancy):

    tmp/step-debug/<thread>/<node>/
        brief.md          — rendered Jinja brief for the node (LLM nodes only)
        context.json      — Jinja render context (LLM nodes only)
        post_output.json  — state-delta vs the previous checkpoint
        cli.txt           — resolved claude-CLI invocation parameters

Why the graph stays clean
-------------------------

PR #183/#184 (now reverted by this same HOM-369 PR) wrapped every node
with an in-place ``interrupt()`` AFTER the body executed but BEFORE the
function returned. LangGraph treats that as a dynamic interrupt and
re-executes the entire node body on resume — second paid LLM dispatch,
non-deterministic committed state, broken approve-equals-committed
contract. The native ``interrupt_after`` parameter raises ``GraphInterrupt``
BETWEEN nodes at the superstep boundary check, AFTER the previous
tick's results are committed to the checkpoint and the SqliteCache.
Resume only executes the next tick. No re-execution, no double-charge.

That moves all the "render a rich payload for the operator" work out of
the graph and into this helper — observability is a read-only operation
against committed state, not a mutation in the node body.

Usage
-----

    python -m scripts.step_debug_observe \\
        --thread-id <thread> \\
        --node <node_name> \\
        --base-url http://192.168.1.115:8124

The base-url defaults to the TrueNAS stack
(``http://192.168.1.115:8124``); ``langgraph dev`` runs on
``http://127.0.0.1:2024`` if you'd rather observe a local session.

Refs
----

- CLAUDE.md §"LangGraph primitives — search docs before rolling custom".
- CLAUDE.md memory ``feedback_langgraph_static_interrupts_for_step_debug``.
- HOM-369 brief (this ticket).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# We're a helper script invoked from the repo root via ``python -m scripts.X``.
# The graph package is shipped under ``graph/src``; the production deployment
# already sets ``PYTHONPATH=/deps/graph`` so ``edit_episode_graph`` is
# importable. On a developer machine the same path applies after
# ``cd graph && uv sync``.
try:
    from edit_episode_graph.config import load_default_config
    from edit_episode_graph.nodes._llm import _BRIEF_ENV, _load_brief
    _GRAPH_AVAILABLE = True
except ImportError:
    _GRAPH_AVAILABLE = False


_DEFAULT_BASE_URL = os.environ.get(
    "HOMESTUDIO_LANGGRAPH_URL", "http://192.168.1.115:8124"
)
_DEFAULT_OUT_ROOT = Path(os.environ.get("HOMESTUDIO_STEP_DEBUG_OUT", "tmp/step-debug"))


# ---------------------------------------------------------------------------
# LangGraph client glue — we use the SDK if available, else fall back to
# bare HTTP via urllib (no extra deps). The SDK ships with langgraph-cli's
# dev environment but is not a hard dep of the graph package.
# ---------------------------------------------------------------------------


def _fetch_state(base_url: str, thread_id: str) -> dict[str, Any]:
    """Return the current committed state of ``thread_id``.

    Tries ``langgraph_sdk.get_sync_client`` first, then falls back to
    ``urllib`` against the REST endpoint
    ``GET /threads/{thread_id}/state``.
    """
    try:
        from langgraph_sdk import get_sync_client  # type: ignore

        client = get_sync_client(url=base_url)
        return client.threads.get_state(thread_id)  # type: ignore[return-value]
    except ImportError:
        pass

    import urllib.request

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/threads/{thread_id}/state",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _fetch_history(base_url: str, thread_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return recent checkpoints for the thread.

    Used to compute the state-delta — the most recent checkpoint is the
    current state, the one before it is the pre-node state. Subtracting
    surfaces "what this node committed".
    """
    try:
        from langgraph_sdk import get_sync_client  # type: ignore

        client = get_sync_client(url=base_url)
        return list(client.threads.get_history(thread_id, limit=limit))  # type: ignore[arg-type]
    except ImportError:
        pass

    import urllib.request

    body = json.dumps({"limit": limit}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/threads/{thread_id}/history",
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# State-delta computation. Naive but adequate: walk the committed-state
# dict, mark keys that changed vs the prior checkpoint. List append-style
# channels (``llm_runs``, ``errors``) surface the *new* entries appended.
# ---------------------------------------------------------------------------


def _state_delta(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key, cur_val in current.items():
        prev_val = previous.get(key)
        if cur_val == prev_val:
            continue
        if isinstance(cur_val, list) and isinstance(prev_val, list) and \
                len(cur_val) >= len(prev_val) and cur_val[: len(prev_val)] == prev_val:
            # Append-only channel — surface only the new tail entries.
            delta[key] = {"appended": cur_val[len(prev_val):]}
        else:
            delta[key] = {"before": prev_val, "after": cur_val}
    return delta


# ---------------------------------------------------------------------------
# Brief rendering. Reuses the production Jinja environment so we get
# byte-identical output to what the LLM saw. LLM nodes only — deterministic
# nodes have no brief.
# ---------------------------------------------------------------------------


_LLM_NODES = {
    "p3_pre_scan",
    "p3_strategy",
    "p3_edl_select",
    "p3_self_eval",
    "p3_persist_session",
    "p4_design_system",
    "p4_prompt_expansion",
    "p4_plan",
    "p4_beat",
    "p4_captions_layer",
    "p4_assemble_index",
    "p4_transitions",
    "p4_persist_session",
    "p4_redispatch_beat",
    "gate_animation_map_classify",
}


def _render_brief_for_node(node_name: str, state_values: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Render the Jinja brief for ``node_name`` against committed state.

    Returns ``(rendered_brief_text, render_context_dict)`` on success;
    ``None`` for deterministic nodes that ship no brief or when the
    brief file is absent.

    NOTE: this is a *best-effort* surface — production briefs accept
    a node-specific context dict built by each LLM node's ``_render_ctx``.
    Reconstructing every node's exact context from committed state is
    fragile (some context fields are derived from upstream state at
    dispatch time and not re-derivable post-hoc). For the most accurate
    rendering, the operator should reach into the node's ``_render_ctx``
    helper directly — this helper renders with ``state_values`` as the
    full context, which is correct for briefs that key only on
    top-level state fields and approximate for the rest.
    """
    if not _GRAPH_AVAILABLE:
        return None
    if node_name not in _LLM_NODES:
        return None
    try:
        template_text = _load_brief(node_name)
    except FileNotFoundError:
        return None
    # Splat the entire committed state into the render context. Jinja
    # silently ignores unreferenced keys, so this is structurally safe.
    ctx = dict(state_values)
    rendered = _BRIEF_ENV.from_string(template_text).render(**ctx)
    return rendered, ctx


# ---------------------------------------------------------------------------
# CLI parameter resolution. Reads ``graph/config.yaml`` via the production
# config loader so the resolved tier/timeout/backend matches what the
# router would actually pick at dispatch time.
# ---------------------------------------------------------------------------


def _resolve_cli(node_name: str) -> str:
    if not _GRAPH_AVAILABLE:
        return f"node={node_name}\n(edit_episode_graph not importable — set PYTHONPATH=graph/src)\n"
    cfg = load_default_config()
    nc = cfg.resolve_node(node_name)
    lines = [
        f"node={node_name}",
        f"tier={nc.tier}",
        f"model={nc.model or '(tier-default)'}",
        f"backend_preference={nc.backend_preference or cfg.backend_preference}",
        f"timeout_s={nc.timeout_s}",
        "",
        "# Resolved via edit_episode_graph.config.RouterConfig.resolve_node(name)",
        "# Source: graph/config.yaml + node_overrides[<node>].",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Top-level entry point.
# ---------------------------------------------------------------------------


def observe(
    thread_id: str,
    node_name: str,
    *,
    base_url: str = _DEFAULT_BASE_URL,
    out_root: Path = _DEFAULT_OUT_ROOT,
) -> Path:
    """Dump the four step-debug artifacts for one paused thread+node.

    Returns the directory the artifacts landed in.
    """
    out_dir = out_root / thread_id / node_name
    out_dir.mkdir(parents=True, exist_ok=True)

    state = _fetch_state(base_url, thread_id)
    state_values = state.get("values", state) if isinstance(state, dict) else {}

    # State-delta vs the prior checkpoint. ``history[0]`` is the most
    # recent (== current); ``history[1]`` is the one this node committed
    # on top of. If the thread has only one checkpoint we emit the full
    # state as the "delta" — there's no prior to subtract.
    history = _fetch_history(base_url, thread_id, limit=2)
    if len(history) >= 2:
        prev_values = history[1].get("values", {}) if isinstance(history[1], dict) else {}
        delta = _state_delta(state_values, prev_values)
    else:
        delta = {"note": "no prior checkpoint — emitting full state", "values": state_values}

    (out_dir / "post_output.json").write_text(
        json.dumps(delta, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    rendered = _render_brief_for_node(node_name, state_values)
    if rendered is not None:
        brief_text, ctx = rendered
        (out_dir / "brief.md").write_text(brief_text, encoding="utf-8")
        (out_dir / "context.json").write_text(
            json.dumps(ctx, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    (out_dir / "cli.txt").write_text(_resolve_cli(node_name), encoding="utf-8")

    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dump step-debug observability artifacts for one paused LangGraph thread.",
    )
    parser.add_argument("--thread-id", required=True, help="LangGraph thread id (e.g. 019e58ea-...).")
    parser.add_argument("--node", required=True, help="Node name whose pause we just hit.")
    parser.add_argument(
        "--base-url",
        default=_DEFAULT_BASE_URL,
        help=f"LangGraph server base URL (default: {_DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--out-root",
        default=str(_DEFAULT_OUT_ROOT),
        help=f"Artifact root dir (default: {_DEFAULT_OUT_ROOT}).",
    )
    args = parser.parse_args(argv)

    out_dir = observe(
        thread_id=args.thread_id,
        node_name=args.node,
        base_url=args.base_url,
        out_root=Path(args.out_root),
    )
    print(f"step-debug artifacts written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
