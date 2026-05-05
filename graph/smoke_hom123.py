"""HOM-123 smoke: real-CLI captions authoring via LangGraph native primitives.

Resumes a primed Phase 4 thread from `p4_catalog_scan` using
`update_state(as_node=…)` (memory: `feedback_langgraph_native_primitives`),
then triggers a run that exercises the full HOM-123 wire-up:

    p4_catalog_scan ─► p4_captions_layer ──► p4_dispatch_beats ──►
        Send(p4_beat) ×N (cached) ──► p4_assemble_index ──► halt_llm_boundary

`p4_captions_layer` is pinned to Haiku via `model:` override in
`graph/config.yaml` (HOM-123 amendment of spec §6.3 from `cheap` → `smart`).
Per-beat fragments from the HOM-122 prior run are cached-skipped, so spend
is dominated by the single captions dispatch (~$0.001).

Prerequisites:
  - `langgraph dev` running locally (defaults to http://127.0.0.1:2024).
  - At least one thread for SLUG that has progressed through
    `p4_catalog_scan` (the HOM-122 follow-up primed slug below works).

Skip with SMOKE_SKIP=1; override URL with LANGGRAPH_URL.

Run:
    .venv/Scripts/python smoke_hom123.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

from edit_episode_graph._paths import repo_root

REPO_ROOT = repo_root()
SLUG = os.environ.get(
    "SMOKE_SLUG",
    "2026-05-05-desktop-software-licensing-it-turns-out-is",
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
    threads = await client.threads.search(limit=100)
    candidates: list[tuple[str, str]] = []
    for t in threads:
        thread_id = t.get("thread_id")
        if not thread_id:
            continue
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
    hf = REPO_ROOT / "episodes" / slug / "hyperframes"
    captions_html = hf / "captions.html"
    index_html = hf / "index.html"

    if not captions_html.is_file():
        print(f"SMOKE FAIL: captions block missing: {captions_html}", file=sys.stderr)
        return 1
    body = captions_html.read_text(encoding="utf-8")
    problems: list[str] = []

    # Canon §"Caption Exit Guarantee" — every group's `tl.set` deterministic kill
    if "tl.set(" not in body:
        problems.append("no `tl.set(` deterministic kill (canon §Caption Exit Guarantee)")

    # Canon §"Positioning" — position: absolute container, never relative
    if "position: absolute" not in body and "position:absolute" not in body:
        problems.append("no `position: absolute` container (canon §Positioning)")
    if "position: relative" in body or "position:relative" in body:
        problems.append("`position: relative` present — canon §Positioning forbids it")

    # gate:captions_track precondition — transcript file referenced (filename
    # is enough; the brief instructs the sub-agent to comment it in).
    transcript_filenames = {"transcript.json", "raw.json", "final.json"}
    if not any(name in body for name in transcript_filenames):
        problems.append(
            "no transcript filename referenced (gate:captions_track precondition — "
            "expected one of transcript.json / raw.json / final.json)"
        )

    # CSS scoping — at least one #captions-layer rule
    if "#captions-layer" not in body:
        problems.append("no `#captions-layer` CSS scoping (orchestrator-house brief rule)")

    # tl.fromTo entrances per motion-principles.md L115-123 (also
    # canon-implied — captions inherit the seek-determinism rules)
    if "tl.fromTo" not in body and "tl.fromto" not in body.lower():
        problems.append("no tl.fromTo entrances (motion-principles.md L115-123)")

    # No bare gsap.from / gsap.to outside tl.* (heuristic — flag literal `gsap.from(`)
    if "gsap.from(" in body:
        problems.append(
            "bare `gsap.from(` present — entrances must use tl.fromTo for non-linear seek"
        )

    # HF lint regex bug — avoid the literal `repeat: -1` substring
    if "repeat: -1" in body:
        problems.append("forbidden literal `repeat: -1` (HF lint regex bug)")

    if problems:
        print("SMOKE FAIL: captions canon/scoping violations:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"  ✓ captions.html: {captions_html}")
    print("    canon markers ok (tl.set kill, position:absolute, transcript ref, "
          "scoped CSS, tl.fromTo entrances)")

    # Assemble sanity — captions block must be inlined into the root index.html
    if not index_html.is_file():
        print(f"SMOKE FAIL: assembled index.html missing: {index_html}", file=sys.stderr)
        return 1
    idx = index_html.read_text(encoding="utf-8")
    if "<!-- p4_assemble_index: captions -->" not in idx:
        print(
            "SMOKE FAIL: captions injection marker missing in index.html — "
            "p4_assemble_index did not inline the captions block",
            file=sys.stderr,
        )
        return 1
    if "captions-layer" not in idx:
        print(
            "SMOKE FAIL: captions block id `captions-layer` not present in index.html",
            file=sys.stderr,
        )
        return 1
    print(f"  ✓ index.html inlines captions block (marker + #captions-layer present)")
    return 0


async def _amain() -> int:
    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE SKIP: SMOKE_SKIP=1")
        return 0

    print("=== HOM-123 smoke ===")
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
    plan_beats = (((values.get("compose") or {}).get("plan") or {}).get("beats") or [])
    catalog = (values.get("compose") or {}).get("catalog") or {}
    print(
        f"  primed: plan.beats={len(plan_beats)} "
        f"catalog.blocks={len(catalog.get('blocks') or [])} "
        f"catalog.components={len(catalog.get('components') or [])}"
    )

    # Drop transient `_beat_dispatch` and any pre-existing `compose.captions*`
    # so the captions node authors fresh under this run (the on-disk cached
    # skip stays in place and is exercised only when captions.html is
    # already there; we want the LLM dispatch to fire on the first smoke).
    clean_values = {k: v for k, v in values.items() if k != "_beat_dispatch"}
    print(f"\n=== update_state(as_node={RESUME_AS_NODE!r}) ===")
    await client.threads.update_state(
        thread_id, values=clean_values, as_node=RESUME_AS_NODE
    )

    # If a stale captions.html lingers from a prior smoke, the cached-skip
    # gate would short-circuit the dispatch and we'd never exercise the LLM.
    # Remove it so the smoke actually invokes Haiku.
    captions_html = REPO_ROOT / "episodes" / SLUG / "hyperframes" / "captions.html"
    if captions_html.is_file():
        print(f"  removing stale captions cache: {captions_html}")
        captions_html.unlink()

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
