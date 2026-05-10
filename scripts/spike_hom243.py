r"""HOM-243 spike — measure structured-output reliability of p4_beat.

Runs N (default 5) sequential dispatches of ``p4_beat`` against the
canonical fixture's ``hook`` beat with the BeatOutput Pydantic schema
swap (commit 1) already in place. Each dispatch goes straight through
``LLMNode.__call__`` against a freshly-built ``BackendRouter`` — the
production cache (``SqliteCache``) is bypassed by construction (the
LLMNode object is never wrapped in a ``CachePolicy``-decorated graph
node here), so every iteration is a real paid LLM call.

Records per attempt:
  * success bool          — True iff structured response decoded into
                            ``BeatOutput`` AND ``len(html) >= 5_000``.
  * html_chars            — character length of the returned ``html`` field
                            (``None`` on failure).
  * retry_count           — number of failed attempts before the final one
                            on this dispatch (router's
                            ``_SCHEMA_RETRIES_PER_BACKEND``-driven loop).
  * exception             — class name of the terminal exception, or None.
  * wall_time_s           — elapsed wall-clock for the whole dispatch.

Writes a summary JSON to ``docs/spikes/hom-243-results.json`` with
per-attempt records and ``acceptance_pass: bool`` (5/5 success + every
``html_chars >= 5_000`` + every ``retry_count == 0``). Exits non-zero
when acceptance fails.

DO NOT run this script under replay / $0 conditions. This is a paid
script. Operator authorisation required (~$10 cap, ~$1.50 per dispatch
of ``tier=expensive`` Opus on the canonical hook beat — see recorded
``tokens_out`` ~7-12 K in ``recordings/p4_beat.json``).

Invocation (PowerShell):

    $env:HOMESTUDIO_PROJECT_ROOT = "$PWD\tests\fixtures"
    $env:PYTHONPATH = "graph\src"
    graph\.venv\Scripts\python.exe scripts\spike_hom243.py

Optional ``--limit N`` (default 5) for a smoke run with a single dispatch
before committing the full $7.50 budget.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SLUG = "canonical-portrait-talking-head"
ACCEPTANCE_HTML_MIN_CHARS = 5_000
RESULTS_PATH = Path("docs/spikes/hom-243-results.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Reconstruct minimal state from the committed fixture cache.db.
# ---------------------------------------------------------------------------


def _load_compose_from_fixture(fixture_root: Path) -> dict[str, Any]:
    """Decode `compose.plan` + `compose.catalog` from the fixture cache.db.

    No graph runtime; raw SQLite + LangGraph's own JsonPlusSerializer
    (same path as ``tests/_helpers/replay_dispatch.py``).
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    db_path = fixture_root / "episodes" / SLUG / "cache.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"fixture cache.db not found: {db_path}")

    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        compose: dict[str, Any] = {}
        for node in ("p4_plan", "p4_catalog_scan"):
            rows = conn.execute(
                "SELECT encoding, val FROM cache WHERE ns LIKE ? LIMIT 1",
                (f"%,{node}",),
            ).fetchall()
            if not rows:
                raise RuntimeError(f"no recording for {node!r} in {db_path}")
            enc, raw = rows[0]
            decoded = serde.loads_typed((enc, raw))
            for entry in decoded:
                if not entry or len(entry) < 2:
                    continue
                ch, val = entry[0], entry[1]
                if ch == "compose" and isinstance(val, dict):
                    compose.update(val)
        return compose
    finally:
        conn.close()


def _build_state(fixture_root: Path) -> dict[str, Any]:
    """Build a minimal state dict carrying everything p4_beat needs.

    The dispatch payload (``_beat_dispatch``) mirrors what
    ``p4_dispatch_beats_node`` would produce for the FIRST beat (hook).
    ``data_width`` / ``data_height`` are read from the fixture's root
    ``index.html`` (same parser shape the dispatcher uses).
    """
    import re

    compose = _load_compose_from_fixture(fixture_root)
    beats = compose.get("plan", {}).get("beats") or []
    if not beats:
        raise RuntimeError("fixture compose.plan.beats is empty")

    hook = beats[0]
    duration_s = float(hook.get("duration_s") or 0.0)

    episode_dir = fixture_root / "episodes" / SLUG
    hf_dir = episode_dir / "hyperframes"
    index_path = hf_dir / "index.html"
    root_html = index_path.read_text(encoding="utf-8")

    viewport_re = re.compile(
        r'<meta\s+name=["\']viewport["\']\s+content=["\']\s*width=(\d+)\s*,\s*height=(\d+)',
        re.IGNORECASE,
    )
    m = viewport_re.search(root_html)
    if m:
        data_width, data_height = int(m.group(1)), int(m.group(2))
    else:
        # Fall back to the canonical portrait-talking-head dims
        data_width, data_height = 1080, 1920

    # scene_id derivation matches p4_dispatch_beats / scene_id_for("HOOK") = "hook"
    sid = "hook"
    scene_html_path = str(hf_dir / "compositions" / f"{sid}.html")

    beat_dispatch = {
        "scene_id": sid,
        "beat_index": 0,
        "total_beats": len(beats),
        "is_final": len(beats) == 1,
        "data_start_s": 0.0,
        "data_duration_s": duration_s,
        "data_track_index": 1,
        "data_width": data_width,
        "data_height": data_height,
        "plan_beat": hook,
        "scene_html_path": scene_html_path,
    }

    return {
        "slug": SLUG,
        "episode_dir": str(episode_dir),
        "compose": compose,
        "_beat_dispatch": beat_dispatch,
    }


# ---------------------------------------------------------------------------
# Per-attempt result.
# ---------------------------------------------------------------------------


@dataclass
class AttemptRecord:
    iteration: int
    success: bool
    html_chars: int | None
    retry_count: int
    exception: str | None
    exception_message: str | None
    wall_time_s: float
    runs: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "success": self.success,
            "html_chars": self.html_chars,
            "retry_count": self.retry_count,
            "exception": self.exception,
            "exception_message": self.exception_message,
            "wall_time_s": round(self.wall_time_s, 3),
            "timestamp": self.timestamp,
            "runs": self.runs,
        }


# ---------------------------------------------------------------------------
# Dispatch loop.
# ---------------------------------------------------------------------------


def _run_one(state: dict[str, Any], iteration: int) -> AttemptRecord:
    from edit_episode_graph._runtime import get_router
    from edit_episode_graph.nodes.p4_beat import _build_node

    node = _build_node()
    router = get_router()

    t0 = time.monotonic()
    try:
        update = node(state, router=router)
    except Exception as e:
        elapsed = time.monotonic() - t0
        # Attempts may be embedded in AllBackendsExhausted.attempts; surface them.
        attempts = list(getattr(e, "attempts", []) or [])
        retry_count = max(0, len(attempts) - 1)
        return AttemptRecord(
            iteration=iteration,
            success=False,
            html_chars=None,
            retry_count=retry_count,
            exception=type(e).__name__,
            exception_message=str(e)[:500],
            wall_time_s=elapsed,
            runs=attempts,
            timestamp=_now_iso(),
        )

    elapsed = time.monotonic() - t0
    runs = list(update.get("llm_runs") or [])
    failed_runs = [r for r in runs if not r.get("success")]
    retry_count = len(failed_runs)

    compose_update = update.get("compose") or {}
    payload = compose_update.get("_beat_html_spike") or {}
    html = payload.get("html") if isinstance(payload, dict) else None
    html_chars = len(html) if isinstance(html, str) else None

    success = (
        isinstance(html, str)
        and html_chars is not None
        and html_chars >= ACCEPTANCE_HTML_MIN_CHARS
        and retry_count == 0
    )

    return AttemptRecord(
        iteration=iteration,
        success=success,
        html_chars=html_chars,
        retry_count=retry_count,
        exception=None,
        exception_message=None,
        wall_time_s=elapsed,
        runs=runs,
        timestamp=_now_iso(),
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="HOM-243 p4_beat structured-output spike")
    parser.add_argument("--limit", type=int, default=5, help="Number of dispatches (default 5).")
    parser.add_argument(
        "--results",
        type=str,
        default=str(RESULTS_PATH),
        help=f"Output JSON path (default {RESULTS_PATH}).",
    )
    args = parser.parse_args(argv)

    fixture_root_env = os.environ.get("HOMESTUDIO_PROJECT_ROOT")
    if not fixture_root_env:
        print(
            "ERROR: HOMESTUDIO_PROJECT_ROOT must point at the fixture root "
            "(e.g. set $env:HOMESTUDIO_PROJECT_ROOT = \"$PWD\\tests\\fixtures\").",
            file=sys.stderr,
        )
        return 2
    fixture_root = Path(fixture_root_env).resolve()

    print(f"[spike-hom243] fixture_root = {fixture_root}", file=sys.stderr)
    state = _build_state(fixture_root)
    bd = state["_beat_dispatch"]
    print(
        f"[spike-hom243] hook dispatch: scene_id={bd['scene_id']!r} "
        f"duration={bd['data_duration_s']}s viewport={bd['data_width']}x{bd['data_height']}",
        file=sys.stderr,
    )

    attempts: list[AttemptRecord] = []
    for i in range(1, args.limit + 1):
        print(f"[spike-hom243] attempt {i}/{args.limit} dispatching…", file=sys.stderr)
        try:
            rec = _run_one(state, iteration=i)
        except Exception:
            traceback.print_exc()
            rec = AttemptRecord(
                iteration=i,
                success=False,
                html_chars=None,
                retry_count=0,
                exception="HarnessError",
                exception_message=traceback.format_exc()[-500:],
                wall_time_s=0.0,
                timestamp=_now_iso(),
            )
        attempts.append(rec)
        status = "OK " if rec.success else "FAIL"
        chars = rec.html_chars if rec.html_chars is not None else "-"
        exc = rec.exception or "-"
        print(
            f"[spike-hom243] attempt {i}/{args.limit}: {status} "
            f"html_chars={chars} retries={rec.retry_count} "
            f"wall={rec.wall_time_s:.1f}s exc={exc}",
            file=sys.stderr,
        )

    successes = [a for a in attempts if a.success]
    acceptance_pass = (
        len(successes) == args.limit
        and all(a.html_chars and a.html_chars >= ACCEPTANCE_HTML_MIN_CHARS for a in successes)
        and all(a.retry_count == 0 for a in successes)
    )

    summary = {
        "ticket": "HOM-243",
        "slug": SLUG,
        "limit": args.limit,
        "acceptance_pass": acceptance_pass,
        "successes": len(successes),
        "html_min_chars_required": ACCEPTANCE_HTML_MIN_CHARS,
        "started_at": attempts[0].timestamp if attempts else _now_iso(),
        "ended_at": attempts[-1].timestamp if attempts else _now_iso(),
        "attempts": [a.to_dict() for a in attempts],
    }

    out_path = Path(args.results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[spike-hom243] wrote {out_path} (acceptance_pass={acceptance_pass})", file=sys.stderr)

    return 0 if acceptance_pass else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
