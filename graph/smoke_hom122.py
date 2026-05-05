"""HOM-122d smoke: end-to-end Phase 4 fan-out via LangGraph native primitives.

Resumes a primed Phase 4 thread from `p4_catalog_scan` using
`update_state(as_node=…)` (memory: `feedback_langgraph_native_primitives`),
then triggers a run that exercises the full HOM-122 chain:

    p4_dispatch_beats ──► Send(p4_beat) ×N ──► p4_assemble_index ──► halt_llm_boundary

`p4_beat` is pinned to Haiku via the `model:` override in `graph/config.yaml`
(documented in HOM-122d). Cost: ≈ $0.001 × N beats. Re-run is free under
cached-skip (the per-fragment FS check inside `p4_beat`).

Prerequisites:
  - `langgraph dev` running locally (defaults to http://127.0.0.1:2024)
  - At least one thread for SLUG that has progressed through `p4_catalog_scan`
    (the primed handoff slug below was prepared in HOM-135 follow-up).

Skip with SMOKE_SKIP=1; override URL with LANGGRAPH_URL.

Run:
    .venv/Scripts/python smoke_hom122.py
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SLUG = os.environ.get(
    "SMOKE_SLUG",
    "2026-05-04-desktop-software-licensing-it-turns-out-is",
)
LANGGRAPH_URL = os.environ.get("LANGGRAPH_URL", "http://127.0.0.1:2024")
ASSISTANT_ID = os.environ.get("SMOKE_ASSISTANT_ID", "edit_episode")
RESUME_AS_NODE = "p4_catalog_scan"
RUN_POLL_TIMEOUT_S = int(os.environ.get("SMOKE_RUN_TIMEOUT_S", "900"))
RUN_POLL_INTERVAL_S = 5


def _slug_from_state_values(values: dict[str, Any]) -> str | None:
    if not isinstance(values, dict):
        return None
    slug = values.get("slug")
    if isinstance(slug, str):
        return slug
    return None


async def _find_thread_id(client, slug: str) -> str | None:
    """Return the most-recently-updated thread whose state.values.slug == slug."""
    threads = await client.threads.search(limit=100)
    candidates: list[tuple[str, str]] = []
    for t in threads:
        thread_id = t.get("thread_id")
        if not thread_id:
            continue
        # Some servers return values inside the search payload; fall back to
        # an explicit get_state when that field is missing or empty.
        values = (t.get("values") or {}) if isinstance(t.get("values"), dict) else {}
        if not values:
            try:
                state = await client.threads.get_state(thread_id)
                values = state.get("values") or {}
            except Exception as exc:  # pragma: no cover — diagnostic
                print(f"  warn: get_state({thread_id}) failed: {exc!r}")
                continue
        if _slug_from_state_values(values) == slug:
            candidates.append((t.get("updated_at", ""), thread_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


async def _poll_run(client, thread_id: str, run_id: str) -> str:
    deadline = time.monotonic() + RUN_POLL_TIMEOUT_S
    last_status = "?"
    while time.monotonic() < deadline:
        run = await client.runs.get(thread_id, run_id)
        status = run.get("status") or "?"
        if status != last_status:
            print(f"  run {run_id}: status={status}")
            last_status = status
        if status in {"success", "error", "interrupted", "timeout", "cancelled", "cancelling"}:
            return status
        await asyncio.sleep(RUN_POLL_INTERVAL_S)
    return "timeout-poll"


def _verify_artefacts(slug: str) -> int:
    print("\n=== Verify on-disk artefacts ===")
    hf = REPO_ROOT / "episodes" / slug / "edit" / "hyperframes"
    comps_dir = hf / "compositions"
    index_html = hf / "index.html"

    if not comps_dir.is_dir():
        print(f"SMOKE FAIL: compositions dir missing: {comps_dir}", file=sys.stderr)
        return 1
    fragments = sorted(comps_dir.glob("*.html"))
    if not fragments:
        print(f"SMOKE FAIL: no fragments under {comps_dir}", file=sys.stderr)
        return 1
    print(f"  fragments: {len(fragments)}")

    problems: list[str] = []
    for f in fragments:
        body = f.read_text(encoding="utf-8")
        scene_id = f.stem
        if "<template" in body.lower():
            problems.append(f"{f.name}: contains <template> wrapper (Pattern A forbids it)")
        if 'data-composition-id' in body:
            problems.append(
                f"{f.name}: scene fragment carries data-composition-id "
                "(catalog.md L13: root-only)"
            )
        if "tl.fromTo" not in body:
            problems.append(f"{f.name}: no tl.fromTo entrances (motion-principles.md L115-123)")
        # CSS scoping: every rule prefixed with #scene-<id>. We approximate
        # by asserting at least one selector with the prefix exists and no
        # bare class selectors leak (heuristic: lines that start with `.`
        # before `{` inside a <style> block).
        if f"#scene-{scene_id}" not in body:
            problems.append(f"{f.name}: no #scene-{scene_id} CSS scoping")
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", body, flags=re.S | re.I)
        for sb in style_blocks:
            for line in sb.splitlines():
                stripped = line.strip()
                if stripped.startswith(".") and "{" in stripped:
                    problems.append(
                        f"{f.name}: bare class selector found ('{stripped[:40]}…') — "
                        "every rule must be prefixed with #scene-<id>"
                    )
                    break
        if "repeat: -1" in body:
            problems.append(f"{f.name}: forbidden literal `repeat: -1` (HF lint regex bug)")

    if problems:
        print("SMOKE FAIL: Pattern A markers / scoping violations:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("  ✓ all fragments: Pattern A shape (no <template>, no scene-div data-composition-id, "
          "tl.fromTo entrances, scoped CSS, no `repeat: -1`)")

    if not index_html.is_file():
        print(f"SMOKE FAIL: assembled index.html missing: {index_html}", file=sys.stderr)
        return 1
    idx = index_html.read_text(encoding="utf-8")
    if "<!-- p4_assemble_index: shim begin -->" not in idx \
       or "<!-- p4_assemble_index: shim end -->" not in idx:
        print("SMOKE FAIL: v4 visibility shim markers missing in index.html", file=sys.stderr)
        return 1
    inlined_count = sum(1 for f in fragments if f"#scene-{f.stem}" in idx)
    if inlined_count != len(fragments):
        print(
            f"SMOKE FAIL: only {inlined_count}/{len(fragments)} fragments inlined into index.html",
            file=sys.stderr,
        )
        return 1
    print(f"  ✓ index.html inlines all {len(fragments)} fragment(s) and contains v4 shim block")
    return 0


async def _amain() -> int:
    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE SKIP: SMOKE_SKIP=1")
        return 0

    print(f"=== HOM-122d smoke ===")
    print(f"  langgraph url:  {LANGGRAPH_URL}")
    print(f"  assistant_id:   {ASSISTANT_ID}")
    print(f"  slug:           {SLUG}")
    print(f"  resume as_node: {RESUME_AS_NODE}")

    try:
        from langgraph_sdk import get_client
    except ImportError:
        print("SMOKE FAIL: langgraph_sdk not installed in this venv", file=sys.stderr)
        return 1

    client = get_client(url=LANGGRAPH_URL)

    # Health check + thread lookup
    try:
        thread_id = await _find_thread_id(client, SLUG)
    except Exception as exc:
        print(
            f"SMOKE FAIL: could not reach LangGraph at {LANGGRAPH_URL} — is "
            f"`langgraph dev` running? ({exc!r})",
            file=sys.stderr,
        )
        return 1

    if not thread_id:
        print(
            f"SMOKE FAIL: no thread found for slug={SLUG!r}. Prime one by running "
            "the graph in Studio through p4_catalog_scan first, or set SMOKE_SLUG.",
            file=sys.stderr,
        )
        return 1
    print(f"  thread_id:      {thread_id}")

    state = await client.threads.get_state(thread_id)
    values = state.get("values") or {}
    plan_beats = (
        ((values.get("compose") or {}).get("plan") or {}).get("beats") or []
    )
    catalog = (values.get("compose") or {}).get("catalog") or {}
    print(f"  primed: plan.beats={len(plan_beats)} "
          f"catalog.blocks={len(catalog.get('blocks') or [])} "
          f"catalog.components={len(catalog.get('components') or [])}")
    if not plan_beats:
        print(
            "SMOKE FAIL: thread has no compose.plan.beats — re-prime via "
            "p4_plan/p4_catalog_scan before running smoke_hom122.",
            file=sys.stderr,
        )
        return 1

    # Re-stamp current values as if `p4_catalog_scan` just produced them.
    # The graph's outgoing edges from p4_catalog_scan will fire next:
    # → p4_dispatch_beats → Send(p4_beat) ×N → p4_assemble_index → halt.
    # Strip `_beat_dispatch` defensively — the spec (§"Send payload") calls
    # it a transient namespace that "never reaches the parent thread
    # checkpoint as a stable channel"; if it lingers from a previously
    # interrupted run, re-stamping it here would inject a stale per-beat
    # payload into the resumed graph state.
    clean_values = {k: v for k, v in values.items() if k != "_beat_dispatch"}
    print(f"\n=== update_state(as_node={RESUME_AS_NODE!r}) ===")
    await client.threads.update_state(
        thread_id, values=clean_values, as_node=RESUME_AS_NODE
    )

    print(f"\n=== runs.create (assistant={ASSISTANT_ID}) ===")
    run = await client.runs.create(thread_id, ASSISTANT_ID, input=None)
    run_id = run.get("run_id")
    if not run_id:
        print(f"SMOKE FAIL: runs.create returned no run_id: {run!r}", file=sys.stderr)
        return 1
    print(f"  run_id: {run_id}")

    status = await _poll_run(client, thread_id, run_id)
    if status != "success":
        print(f"SMOKE FAIL: run terminated with status={status!r}", file=sys.stderr)
        # Print the latest notices/errors for diagnosis
        try:
            final = await client.threads.get_state(thread_id)
            v = final.get("values") or {}
            print(f"  notices: {v.get('notices')}", file=sys.stderr)
            print(f"  errors:  {v.get('errors')}", file=sys.stderr)
        except Exception:
            pass
        return 1
    print(f"  ✓ run finished with status=success")

    return _verify_artefacts(SLUG)


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
