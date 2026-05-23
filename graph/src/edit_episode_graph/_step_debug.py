"""HOMESTUDIO_STEP_DEBUG=1 interrupt wrapper (HOM-334 Phase A).

Wraps every step-debug-eligible node (see ``docs/step-debug-inventory.md``)
with a pair of native LangGraph ``interrupt()`` calls — one before the node
body executes, one after it returns. When ``$HOMESTUDIO_STEP_DEBUG`` is
unset (production default), every helper here is a complete no-op: no
interrupt fires, no disk write happens. When set to ``"1"``, the pre-
interrupt publishes a structured JSON blob the orchestrator session reads,
the operator decides ``approve`` / ``abort``, and the same machinery
re-fires after the node returns with the actual output.

Why this lives in ``_step_debug.py`` (sibling of ``_caching.py``), not
under ``nodes/``: the disk-I/O lint (``tests/test_disk_io_allowlist.py``)
only scans ``nodes/`` and ``gates/``. Step-debug *must* write context /
output dumps to disk so the orchestrator can read more than the excerpt
without bloating the interrupt payload — putting the helper one level up
keeps the lint surface clean.

The single primitive at the heart of this is native LangGraph
``langgraph.types.interrupt({...})`` + ``Command(resume=...)`` per
CLAUDE.md §"LangGraph primitives". Resume semantics: when the operator
sends ``Command(resume="approved")``, LangGraph re-executes the node body
from the start; ``interrupt()`` then returns the resume payload without
re-firing (replay-safe by construction). Each LLM node is wired with
``cache_policy=`` in ``graph.py``, so the LLM dispatch lands on the
SqliteCache hit path on replay — no re-charge. Per HOM-334 acceptance §1.

The ``abort`` resume string raises ``StepDebugAborted`` cleanly. The
graph runner sees the exception, halts the run, and ``halt_llm_boundary``
(if routed) surfaces the notice.

Resume vocabulary (the pre/post payload publishes this list):
  * ``"approve"`` / ``"approved"`` / ``"yes"`` / ``"ok"`` / empty payload
    → graph continues.
  * ``"abort"`` → ``StepDebugAborted`` raised; the runner terminates.
  * ``"rerun-with-edit:<state-patch-json>"`` → handled by the ORCHESTRATOR
    via ``client.threads.update_state(as_node=...)`` + ``runs.create()``,
    not by this wrapper. See ``docs/runbooks/2026-05-step-debug.md``.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ._paths import project_root


_FLAG_ENV = "HOMESTUDIO_STEP_DEBUG"
_DUMP_ROOT_OVERRIDE_ENV = "HOMESTUDIO_STEP_DEBUG_DUMP_ROOT"
_EXCERPT_CHARS = 4000
_APPROVE_TOKENS = frozenset({"", "approve", "approved", "yes", "ok", "y", "continue"})
_ABORT_TOKENS = frozenset({"abort", "stop", "cancel", "halt"})
_RESUME_VOCAB = ("approve", "rerun-with-edit:<state-patch-json>", "abort")


class StepDebugAborted(RuntimeError):
    """Raised when the operator sends ``Command(resume="abort")`` to a step-debug stop.

    The graph runner catches at the outermost level (raise propagates out of
    the node body); LangGraph treats it like any other terminal exception,
    so the run halts without committing further writes. The catch-and-notice
    pattern lives in ``halt_llm_boundary`` for ordinary halts; ``StepDebugAborted``
    is deliberately uncaught here so it's unambiguous in the trace that the
    operator made the call.
    """

    def __init__(self, node: str, phase: str) -> None:
        super().__init__(
            f"step-debug operator abort at {node} ({phase}); see "
            "HOMESTUDIO_STEP_DEBUG runbook for resume options"
        )
        self.node = node
        self.phase = phase


def is_enabled() -> bool:
    """Return True iff ``$HOMESTUDIO_STEP_DEBUG`` is set to a truthy value.

    Defaults to False so production runs are unaffected (HOM-334 acceptance §1
    "Default off …; on under the flag for the operator session").
    """
    val = os.environ.get(_FLAG_ENV, "")
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _excerpt(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    if len(s) <= _EXCERPT_CHARS:
        return s
    return s[:_EXCERPT_CHARS] + f"\n... (truncated; total {len(s)} chars)"


def _safe_json(value: Any) -> str:
    """Best-effort JSON serialisation for the dump file.

    State / brief context contains arbitrary Pydantic models, dataclasses,
    nested dicts. Fall back to ``repr`` on anything ``json.dumps`` chokes on
    so the dump is always written (even if lossy in one branch).
    """
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=_to_jsonable)
    except (TypeError, ValueError):
        return repr(value)


def _to_jsonable(o: Any) -> Any:
    # Pydantic v2 BaseModel
    dump = getattr(o, "model_dump", None)
    if callable(dump):
        try:
            return dump()
        except Exception:  # pragma: no cover - defensive
            return repr(o)
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    return repr(o)


def _dump_root(thread_id: str | None) -> Path:
    override = os.environ.get(_DUMP_ROOT_OVERRIDE_ENV)
    if override:
        base = Path(override)
    else:
        base = project_root() / "tmp" / "step-debug"
    tid = thread_id or "_no_thread"
    return base / tid


def _thread_id_from_state(state: Any) -> str | None:
    if isinstance(state, dict):
        for k in ("thread_id", "_thread_id"):
            v = state.get(k)
            if isinstance(v, str) and v:
                return v
    # LangGraph runtime exposes the active config; try a best-effort lookup.
    try:
        from langgraph.config import get_config  # type: ignore

        cfg = get_config() or {}
        cfg_dict = cfg.get("configurable") if isinstance(cfg, dict) else None
        if isinstance(cfg_dict, dict):
            tid = cfg_dict.get("thread_id")
            if isinstance(tid, str) and tid:
                return tid
    except Exception:
        return None
    return None


def _schema_repr(schema: type | None) -> str | None:
    if schema is None:
        return None
    mod = getattr(schema, "__module__", "?")
    name = getattr(schema, "__qualname__", getattr(schema, "__name__", repr(schema)))
    return f"{mod}.{name}"


def _interpret_resume(decision: Any) -> str:
    """Classify a resume payload as ``approve``, ``abort``, or ``other``.

    ``other`` is passed through to the caller untouched. Phase A only
    implements ``approve`` + ``abort`` per ticket §A.5; ``rerun-with-edit``
    is an orchestrator-side dispatch pattern (CLAUDE.md §"LangGraph
    primitives" — ``update_state(as_node=...) + runs.create()``).
    """
    if decision is None or decision is True:
        return "approve"
    if isinstance(decision, str):
        token = decision.strip().lower()
        if token.startswith("rerun-with-edit"):
            return "other"
        if token in _APPROVE_TOKENS:
            return "approve"
        if token in _ABORT_TOKENS:
            return "abort"
        return "other"
    if isinstance(decision, dict):
        action = str(decision.get("action") or decision.get("resume") or "").strip().lower()
        if action in _ABORT_TOKENS:
            return "abort"
        if action in _APPROVE_TOKENS or not decision:
            return "approve"
        if decision.get("approved") is True:
            return "approve"
        return "other"
    return "other"


def _write_dump(path: Path, payload: Any) -> str:
    """Write a JSON dump and return its string path. Best-effort; never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)  # disk-io-allow: step-debug dump (HOM-334)
        path.write_text(_safe_json(payload), encoding="utf-8")  # disk-io-allow: step-debug dump (HOM-334)
    except Exception as exc:  # pragma: no cover - defensive
        return f"<dump-failed: {exc!r}>"
    return str(path)


# --------------------------------------------------------------------------- #
# Public API — see module docstring + docs/runbooks/2026-05-step-debug.md
# --------------------------------------------------------------------------- #


def step_debug_pre(
    node_name: str,
    state: Any,
    *,
    brief_path: str | None = None,
    brief_rendered: str | None = None,
    context: dict[str, Any] | None = None,
    expected_schema: type | None = None,
    upstream_gate_findings: Iterable[Any] | None = None,
) -> None:
    """Pre-node step-debug interrupt. No-op unless ``HOMESTUDIO_STEP_DEBUG`` is set.

    Publishes a structured JSON blob via ``langgraph.types.interrupt``. The
    orchestrator session reads it and presents the operator with the
    resume-vocabulary options listed in the module docstring. Idempotent on
    resume — LangGraph's ``interrupt()`` contract re-executes the node body
    and ``interrupt()`` returns the resume payload without re-firing.
    """
    if not is_enabled():
        return
    from langgraph.types import interrupt  # imported lazily so tests can stub

    thread_id = _thread_id_from_state(state)
    base = _dump_root(thread_id) / node_name
    ctx_dict = dict(context or {})
    ctx_path = _write_dump(base / "pre_context.json", {"state_keys": sorted(state.keys()) if isinstance(state, dict) else None, "context": ctx_dict})
    payload = {
        "phase": "pre",
        "node": node_name,
        "ts": _now(),
        "brief_path": brief_path,
        "brief_rendered_excerpt": _excerpt(brief_rendered) if isinstance(brief_rendered, str) else None,
        "context_keys": sorted(ctx_dict.keys()),
        "context_dump_path": ctx_path,
        "expected_schema": _schema_repr(expected_schema),
        "upstream_gate_findings": list(upstream_gate_findings or []),
        "resume_vocabulary": list(_RESUME_VOCAB),
    }
    decision = interrupt(payload)
    intent = _interpret_resume(decision)
    if intent == "abort":
        raise StepDebugAborted(node_name, "pre")
    # approve + other both fall through (other = caller-defined extension /
    # rerun-with-edit handled by the orchestrator via update_state).
    return


def step_debug_post(
    node_name: str,
    output: Any,
    *,
    token_usage: dict[str, Any] | None = None,
    latency_s: float | None = None,
    snapshot_png_path: str | None = None,
    lint_findings: Iterable[Any] | None = None,
    state: Any = None,
) -> None:
    """Post-node step-debug interrupt. No-op unless ``HOMESTUDIO_STEP_DEBUG`` is set.

    Captures the parsed output, token usage, wall-clock latency, optional
    snapshot PNG path, and any per-node lint findings. Same resume contract
    as ``step_debug_pre``.
    """
    if not is_enabled():
        return
    from langgraph.types import interrupt

    thread_id = _thread_id_from_state(state)
    base = _dump_root(thread_id) / node_name
    out_path = _write_dump(base / "post_output.json", output)
    rendered = _safe_json(output)
    payload = {
        "phase": "post",
        "node": node_name,
        "ts": _now(),
        "output_excerpt": _excerpt(rendered),
        "output_dump_path": out_path,
        "tokens": dict(token_usage) if token_usage else None,
        "latency_s": latency_s,
        "snapshot_png_path": snapshot_png_path,
        "lint_findings": list(lint_findings or []),
        "resume_vocabulary": list(_RESUME_VOCAB),
    }
    decision = interrupt(payload)
    intent = _interpret_resume(decision)
    if intent == "abort":
        raise StepDebugAborted(node_name, "post")
    return


# --------------------------------------------------------------------------- #
# Convenience: snapshot helper for the three boundaries that warrant one
# (per p4_assemble_index / p4_beat / p4_transitions — ticket §A.4).
# Wrapped in a single try/except: snapshot failures NEVER halt the graph.
# --------------------------------------------------------------------------- #


def try_capture_snapshot(
    *,
    node_name: str,
    state: Any,
    hyperframes_dir: Path | str | None,
    at_seconds: float | None,
) -> str | None:
    """Attempt ``npx hyperframes snapshot --at <t>`` and return the PNG path.

    Returns ``None`` on any failure (missing CLI, composition not yet
    renderable, network) — the caller MUST tolerate ``None`` and feed it
    to ``step_debug_post(snapshot_png_path=None, ...)``.

    Only invoked under the step-debug flag (callers gate on
    ``is_enabled()``); no overhead in production.
    """
    if not is_enabled():
        return None
    if hyperframes_dir is None or at_seconds is None:
        return None
    try:
        import subprocess

        thread_id = _thread_id_from_state(state)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        out_dir = _dump_root(thread_id) / node_name
        out_dir.mkdir(parents=True, exist_ok=True)  # disk-io-allow: step-debug dump (HOM-334)
        out_png = out_dir / f"{ts}.png"
        cmd = [
            "npx",
            "hyperframes",
            "snapshot",
            "--at",
            f"{float(at_seconds):.3f}",
            "--out",
            str(out_png),
        ]
        # 60s ceiling — the snapshot path is best-effort, never blocking.
        result = subprocess.run(
            cmd,
            cwd=str(hyperframes_dir),
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )
        if result.returncode != 0 or not out_png.exists():
            import sys
            sys.stderr.write(
                f"[step-debug] snapshot failed at {node_name}: "
                f"rc={result.returncode} stderr={result.stderr[:400]!r}\n"
            )
            return None
        return str(out_png)
    except Exception as exc:  # pragma: no cover - defensive
        import sys
        sys.stderr.write(f"[step-debug] snapshot error at {node_name}: {exc!r}\n")
        return None


# --------------------------------------------------------------------------- #
# Wrapping helper for deterministic nodes (no brief, no schema).
# --------------------------------------------------------------------------- #


def wrap_deterministic_node(
    node_name: str,
    *,
    state: Any,
    context: dict[str, Any] | None,
    inner: Any,
    hyperframes_dir_fn: Any = None,
    snapshot_at_fn: Any = None,
) -> Any:
    """Wrap a deterministic-node body with pre/post step-debug interrupts.

    ``inner`` is a zero-arg callable returning the node's output dict.
    ``hyperframes_dir_fn`` and ``snapshot_at_fn`` (when provided) are
    callables taking ``(state, output)`` that return the HF project dir
    and snapshot timestamp for a post-node ``npx hyperframes snapshot --at``
    capture. Snapshot failure is swallowed and ``snapshot_png_path=None``
    is recorded.

    No-op pass-through when ``HOMESTUDIO_STEP_DEBUG`` is unset.
    """
    if not is_enabled():
        return inner()
    step_debug_pre(
        node_name,
        state,
        brief_path=None,
        brief_rendered=None,
        context=context or {},
        expected_schema=None,
        upstream_gate_findings=None,
    )
    t0 = time.monotonic()
    result = inner()
    latency = time.monotonic() - t0
    snapshot_png_path: str | None = None
    if hyperframes_dir_fn is None and snapshot_at_fn is None:
        hyperframes_dir_fn, snapshot_at_fn = _per_node_snapshot_callables(node_name)
    if hyperframes_dir_fn is not None and snapshot_at_fn is not None:
        try:
            hf_dir = hyperframes_dir_fn(state, result)
            at_s = snapshot_at_fn(state, result)
            snapshot_png_path = try_capture_snapshot(
                node_name=node_name,
                state=state,
                hyperframes_dir=hf_dir,
                at_seconds=at_s,
            )
        except Exception:  # pragma: no cover - defensive
            snapshot_png_path = None
    step_debug_post(
        node_name,
        result,
        token_usage=None,
        latency_s=latency,
        snapshot_png_path=snapshot_png_path,
        lint_findings=None,
        state=state,
    )
    return result


# --------------------------------------------------------------------------- #
# Wrapping helper for the LLMNode call boundary.
# --------------------------------------------------------------------------- #


def wrap_llm_node_call(
    node_name: str,
    *,
    brief_template: str,
    output_schema: type | None,
    state: Any,
    render_ctx: dict[str, Any],
    upstream_gate_findings: Iterable[Any] | None,
    inner: Any,
    hyperframes_dir_fn: Any = None,
    snapshot_at_fn: Any = None,
) -> Any:
    """Wrap a single LLM-node invocation with pre + post step-debug interrupts.

    ``inner`` is a zero-arg callable that performs the actual dispatch (e.g.
    ``lambda: LLMNode.__call__(state)``). Latency is measured around it.

    When step-debug is disabled the wrapper is a thin pass-through (one
    extra function call) — never imports ``langgraph.types`` or touches disk.
    """
    if not is_enabled():
        return inner()

    # Render the brief once for the pre-report. This duplicates the rendering
    # inside _llm.py's _invoke_with, but the cost is microseconds and the
    # alternative (passing the rendered string out from inside _llm.py)
    # required threading the variable through three call sites for marginal
    # benefit. The pre-report uses the same _BRIEF_ENV as the production
    # call, so the operator sees the exact brief the LLM will receive.
    try:
        from .nodes._llm import _BRIEF_ENV  # local import to avoid cycle at import time

        rendered = _BRIEF_ENV.from_string(brief_template).render(**render_ctx)
    except Exception as exc:  # pragma: no cover - defensive
        rendered = f"<brief render failed: {exc!r}>"

    brief_path = _brief_path_for(node_name)
    step_debug_pre(
        node_name,
        state,
        brief_path=brief_path,
        brief_rendered=rendered,
        context=render_ctx,
        expected_schema=output_schema,
        upstream_gate_findings=upstream_gate_findings,
    )
    t0 = time.monotonic()
    result = inner()
    latency = time.monotonic() - t0
    tokens = _extract_tokens(result)
    snapshot_png_path: str | None = None
    if hyperframes_dir_fn is None and snapshot_at_fn is None:
        hyperframes_dir_fn, snapshot_at_fn = _per_node_snapshot_callables(node_name)
    if hyperframes_dir_fn is not None and snapshot_at_fn is not None:
        try:
            hf_dir = hyperframes_dir_fn(state, result)
            at_s = snapshot_at_fn(state, result)
            snapshot_png_path = try_capture_snapshot(
                node_name=node_name,
                state=state,
                hyperframes_dir=hf_dir,
                at_seconds=at_s,
            )
        except Exception:  # pragma: no cover - defensive
            snapshot_png_path = None
    step_debug_post(
        node_name,
        result,
        token_usage=tokens,
        latency_s=latency,
        snapshot_png_path=snapshot_png_path,
        lint_findings=None,
        state=state,
    )
    return result


def _per_node_snapshot_callables(node_name: str):
    """Return (hf_dir_fn, snapshot_at_fn) tuple for nodes that warrant a snapshot.

    Per HOM-334 §A.4: after `p4_beat`, `p4_assemble_index`, `p4_transitions`.
    For `p4_beat` we use the beat's midpoint (data_start_s + duration/2);
    for the two whole-composition nodes we use the composition midpoint.

    Callables are defined inline (not at import time) so importing this
    module doesn't touch ``_paths`` / ``EpisodePaths`` until needed.
    """
    if node_name == "p4_beat":
        def _hf_dir(state, _result):
            from ._paths import EpisodePaths
            slug = state.get("slug") if isinstance(state, dict) else None
            if not slug:
                return None
            return EpisodePaths(slug).hyperframes_dir

        def _at(state, _result):
            bd = (state.get("_beat_dispatch") if isinstance(state, dict) else None) or {}
            start = float(bd.get("data_start_s") or 0.0)
            dur = float(bd.get("data_duration_s") or 0.0)
            return start + dur / 2.0

        return _hf_dir, _at
    if node_name in {"p4_assemble_index", "p4_transitions"}:
        def _hf_dir(state, _result):
            from ._paths import EpisodePaths
            slug = state.get("slug") if isinstance(state, dict) else None
            if not slug:
                return None
            return EpisodePaths(slug).hyperframes_dir

        def _at(state, _result):
            beats = (
                ((state.get("compose") or {}).get("plan") or {}).get("beats")
                if isinstance(state, dict) else None
            ) or []
            total = 0.0
            for b in beats:
                try:
                    total += float(b.get("duration") or b.get("data_duration_s") or 0.0)
                except Exception:
                    continue
            return total / 2.0 if total > 0 else 0.5

        return _hf_dir, _at
    return None, None


def _brief_path_for(node_name: str) -> str | None:
    """Resolve the relative brief path for the node, if a brief exists."""
    rel = f"graph/src/edit_episode_graph/briefs/{node_name}.j2"
    try:
        full = project_root() / rel
        if full.is_file():  # disk-io-allow: step-debug dump (HOM-334)
            return rel
    except Exception:
        return None
    return None


def _extract_tokens(result: Any) -> dict[str, Any] | None:
    """Pull aggregated token usage from an LLMNode result dict (best-effort)."""
    if not isinstance(result, dict):
        return None
    runs = result.get("llm_runs") or []
    if not runs:
        return None
    last = runs[-1] if isinstance(runs[-1], dict) else None
    if not last:
        return None
    return {
        "input": last.get("tokens_in"),
        "output": last.get("tokens_out"),
        "backend": last.get("backend"),
        "model": last.get("model"),
        "wall_time_s": last.get("wall_time_s"),
    }
