"""Drive a full real-tier graph run against a fixture episode and record cache.db.

HOM-189: rebuild ``tests/fixtures/episodes/<slug>/cache.db`` against the actual
fixture clip (not whatever production episode the operator's main checkout
happens to surface). Critical env to set BEFORE importing
``edit_episode_graph``: ``HOMESTUDIO_PROJECT_ROOT=<repo>/tests/fixtures`` so
``_paths.project_root()`` resolves ``episodes/<slug>/`` under the fixture
tree, not the gitignored production ``episodes/``. Pickup captures
``project_root()`` at import time, hence the early ``os.environ`` mutation
below.

HOM-307: a 5-check preflight (``run_preflight``) runs before mounting the
cache. It validates project_root resolution, fixture HF ``node_modules``
versions vs pinned devDeps, the Windows-blocker ``sharp`` smoke, brief
snapshot collectability, and raw-input presence — fail-fast at <10s before
any paid LLM call. Default ON; ``--no-preflight`` + a required justification
arg overrides for emergencies.

Usage::

    python -m scripts.record_fixture --slug canonical-portrait-talking-head [--dry-run]

The driver:

1. Mounts the fixture cache.db via :mod:`tests._helpers.replay_harness` in
   ``record-on-miss`` mode (working tmp file seeded from any existing
   fixture cache.db; finalize VACUUMs into the canonical fixture path,
   atomic rename). Hits short-circuit on already-recorded entries — only
   misses spend real LLM. For a fully-fresh re-record, ``rm`` the fixture
   ``cache.db`` before running.
2. Compiles the graph with ``cache=<that working SqliteCache>`` and an
   :class:`~langgraph.checkpoint.memory.InMemorySaver` (we are not running
   under ``langgraph dev``; the langgraph-api-rejected checkpointer
   constraint does not apply here).
3. ``invoke`` with ``{"slug": <slug>}``, then loops:
   each :class:`~langgraph.errors.GraphInterrupt` is resumed via
   ``Command(resume="approved")``. Two interrupts are expected on the
   recorded happy path (``strategy_confirmed_interrupt`` after
   ``p3_strategy`` and ``p3_review_interrupt`` after
   ``p3_persist_session``); we loop generically so a third surprise
   interrupt is still handled.
4. On clean termination, finalizes the working cache via
   :func:`finalize_record_on_miss` so the fixture file is in deterministic
   raw form (``VACUUM INTO`` + atomic rename — no WAL artefacts, no
   spurious diff).

Native primitives: ``Command(resume=...)`` for HITL resume — see
https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/ and
``langgraph.types.Command``. No custom dispatch / no Studio API roundtrip.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

# 1. Resolve the worktree root (this file is at <root>/scripts/record_fixture.py).
_WORKTREE = Path(__file__).resolve().parents[1]

# 2. Pin HOMESTUDIO_PROJECT_ROOT before any edit_episode_graph import. Pickup
#    and other deterministic nodes capture project_root() at module load time.
#    HOM-307: use setdefault so an operator-supplied value wins — the preflight
#    will catch nonsense values explicitly with a remediation hint, which is
#    far less destructive than the silent override that masked operator-set
#    fingerprint mistakes (HOM-189 retro).
os.environ.setdefault("HOMESTUDIO_PROJECT_ROOT", str(_WORKTREE / "tests" / "fixtures"))

# 3. Make the worktree's graph/src importable ahead of any global editable
#    install (which may resolve to a different checkout). Mirrors
#    tests/conftest.py.
_GRAPH_SRC = _WORKTREE / "graph" / "src"
if _GRAPH_SRC.is_dir() and str(_GRAPH_SRC) not in sys.path:
    sys.path.insert(0, str(_GRAPH_SRC))

# 4. Make the worktree itself importable so `tests._helpers.*` and
#    `scripts.*` resolve from this checkout.
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))


# ---------------------------------------------------------------------------
# HOM-307 preflight
# ---------------------------------------------------------------------------


def _print_ok(check: str, msg: str) -> None:
    print(f"[preflight] OK {check}: {msg}")


def _print_fail(check: str, msg: str, hint: str) -> None:
    print(f"[preflight] FAIL {check}: {msg}")
    print(f"[preflight]   -> {hint}")


def _strip_semver_prefix(spec: str) -> str:
    """Strip leading ``^``/``~``/``=``/whitespace from a semver spec.

    npm-style pins (``^0.4.39``, ``~0.4.39``, ``=0.4.39``) all collapse to
    ``0.4.39`` for the simple major-match + ``>=`` comparison this preflight
    needs. No need to pull in a full semver lib.
    """
    return re.sub(r"^[\s\^~=v]+", "", spec.strip())


def _parse_simple_semver(v: str) -> tuple[int, int, int]:
    """Parse ``X.Y.Z`` (ignoring any prerelease/build suffix). Raises on garbage."""
    v = _strip_semver_prefix(v)
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        raise ValueError(f"unparseable semver: {v!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _satisfies_pin(resolved: str, pin: str) -> bool:
    """Crude ^x.y.z compatibility check, matching npm caret semantics.

    For ``major >= 1``: same major, resolved >= pinned (npm ``^1.4.39`` allows
    ``>=1.4.39 <2.0.0``).

    For ``major == 0`` (npm special-case): minor must also match, and patch
    must be ``>=`` pinned patch (npm ``^0.4.39`` allows ``>=0.4.39 <0.5.0``).
    Without this special-case ``0.5.0`` would falsely satisfy ``^0.4.39``.

    Sufficient for the preflight's "is this install compatible with the
    devDep pin" question; we do not need full npm semver semantics here
    (no prerelease ordering, no ``~``/``>=``/range parsing).
    """
    rmaj, rmin, rpatch = _parse_simple_semver(resolved)
    pmaj, pmin, ppatch = _parse_simple_semver(pin)
    if rmaj != pmaj:
        return False
    if pmaj == 0:
        # npm caret on 0.x: ^0.4.39 means >=0.4.39 <0.5.0 — minor must match.
        if rmin != pmin:
            return False
        return rpatch >= ppatch
    return (rmin, rpatch) >= (pmin, ppatch)


def _check_project_root(slug: str, project_root_fn: Callable[[], Path]) -> tuple[bool, str, str, str]:
    """Check 1: project_root resolves under tests/fixtures and episode dir exists."""
    try:
        root = project_root_fn()
    except Exception as e:
        return False, "project_root", f"project_root() raised: {e!r}", (
            "Set HOMESTUDIO_PROJECT_ROOT to <worktree>/tests/fixtures, "
            "or run from the main worktree."
        )

    root_str = str(root)
    if ("tests" + os.sep + "fixtures") not in root_str and "tests/fixtures" not in root_str.replace("\\", "/"):
        return False, "project_root", (
            f"resolved to {root} which is not under tests/fixtures — "
            "fingerprints would bake the wrong root"
        ), (
            "Set HOMESTUDIO_PROJECT_ROOT to <worktree>/tests/fixtures, "
            "or run from the main worktree."
        )

    episode_dir = root / "episodes" / slug
    if not episode_dir.is_dir():
        return False, "project_root", (
            f"episode dir not found: {episode_dir}"
        ), (
            f"Verify slug '{slug}' exists under {root / 'episodes'}, "
            "or set HOMESTUDIO_PROJECT_ROOT to the correct fixtures dir."
        )

    return True, "project_root", f"{root} (episode dir found)", ""


def _check_hf_node_modules(fixture_hf_dir: Path) -> tuple[bool, str, str, str]:
    """Check 2: @hyperframes/producer + sharp installed, versions satisfy pins."""
    hint = f"Run `npm install` in {fixture_hf_dir}"
    pkg_json_path = fixture_hf_dir / "package.json"
    if not pkg_json_path.is_file():
        return False, "hf_node_modules", f"missing {pkg_json_path}", hint
    try:
        pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, "hf_node_modules", f"package.json parse failed: {e!r}", hint

    dev = pkg.get("devDependencies", {}) or {}
    pins = {
        "@hyperframes/producer": dev.get("@hyperframes/producer"),
        "sharp": dev.get("sharp"),
    }
    for name, pin in pins.items():
        if not pin:
            return False, "hf_node_modules", (
                f"package.json devDependencies missing pin for {name}"
            ), hint
        installed_pkg = fixture_hf_dir / "node_modules" / Path(*name.split("/")) / "package.json"
        if not installed_pkg.is_file():
            return False, "hf_node_modules", f"{name} not installed", hint
        try:
            resolved = json.loads(installed_pkg.read_text(encoding="utf-8")).get("version", "")
        except Exception as e:
            return False, "hf_node_modules", (
                f"{name}: failed to read installed package.json: {e!r}"
            ), hint
        try:
            if not _satisfies_pin(resolved, pin):
                return False, "hf_node_modules", (
                    f"{name}@{resolved} does not satisfy pin {pin}"
                ), hint
        except ValueError as e:
            return False, "hf_node_modules", f"{name}: {e}", hint

    return True, "hf_node_modules", (
        f"@hyperframes/producer + sharp installed, versions satisfy pins"
    ), ""


def _check_sharp_smoke(fixture_hf_dir: Path) -> tuple[bool, str, str, str]:
    """Check 3: ``node -e "require('sharp')"`` returns 0 inside the fixture HF dir."""
    hint = (
        f"Run `npm install` in {fixture_hf_dir} "
        "(Windows-Node EINVAL on `npm.cmd` shim — CLAUDE.md Known Windows blocker)."
    )
    try:
        proc = subprocess.run(
            ["node", "-e", "require('sharp')"],
            cwd=str(fixture_hf_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return False, "sharp_smoke", "node executable not found on PATH", (
            "Install Node.js or ensure `node` is on PATH."
        )
    except subprocess.TimeoutExpired:
        return False, "sharp_smoke", "node -e require('sharp') timed out after 30s", hint
    if proc.returncode != 0:
        stderr_one = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        return False, "sharp_smoke", (
            f"node -e require('sharp') exited {proc.returncode}: {stderr_one[0]}"
        ), hint
    return True, "sharp_smoke", "require('sharp') OK", ""


def _check_brief_snapshots_collect(worktree: Path) -> tuple[bool, str, str, str]:
    """Check 4: ``pytest tests/test_brief_snapshots.py --collect-only`` succeeds."""
    hint = (
        "Run `pytest tests/test_brief_snapshots.py` — fix failures, "
        "or run with `--update-snapshots` if the diff is intentional."
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_brief_snapshots.py",
             "--collect-only", "-q", "--no-header"],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "brief_snapshots", "pytest --collect-only timed out after 60s", hint
    if proc.returncode != 0:
        last = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        return False, "brief_snapshots", (
            f"pytest --collect-only exited {proc.returncode}: {' | '.join(last)}"
        ), hint
    return True, "brief_snapshots", "test_brief_snapshots.py collects cleanly", ""


def _check_raw_input(slug: str, project_root_fn: Callable[[], Path]) -> tuple[bool, str, str, str]:
    """Check 5: ``episodes/<slug>/raw.mp4`` exists under project_root()."""
    try:
        root = project_root_fn()
    except Exception as e:
        return False, "raw_input", f"project_root() raised: {e!r}", (
            "Re-run preflight check 1 first."
        )
    raw = root / "episodes" / slug / "raw.mp4"
    if not raw.is_file():
        return False, "raw_input", f"raw.mp4 not found: {raw}", (
            f"Place the source clip at {raw} (see "
            "tests/fixtures/episodes/<slug>/README.md for the canonical ffmpeg command)."
        )
    return True, "raw_input", str(raw), ""


def run_preflight(
    slug: str,
    *,
    worktree: Path = _WORKTREE,
    project_root_fn: Callable[[], Path] | None = None,
) -> int:
    """Run the 5 preflight checks. Return 0 on full pass, 2 on first failure.

    HOM-307. Factored out so unit tests can call it without triggering the
    LangGraph import / SqliteCache mount path. ``project_root_fn`` defaults
    to ``edit_episode_graph._paths.project_root`` (imported lazily to keep
    this function's import surface small — same reason the graph imports
    in ``main()`` are deferred until after env pinning).
    """
    if project_root_fn is None:
        from edit_episode_graph._paths import project_root as _pr
        project_root_fn = _pr

    # The fixture HF dir follows project_root() — not the worktree —
    # because HOMESTUDIO_PROJECT_ROOT may point at the main worktree's
    # tests/fixtures (where node_modules actually lives; the linked
    # worktree's tests/fixtures/.../node_modules is gitignored and
    # typically empty). Resolved lazily so a check-1 failure surfaces
    # first with the clearer remediation hint.
    def _fixture_hf_dir() -> Path:
        return project_root_fn() / "episodes" / slug / "hyperframes"

    checks = [
        lambda: _check_project_root(slug, project_root_fn),
        lambda: _check_hf_node_modules(_fixture_hf_dir()),
        lambda: _check_sharp_smoke(_fixture_hf_dir()),
        lambda: _check_brief_snapshots_collect(worktree),
        lambda: _check_raw_input(slug, project_root_fn),
    ]
    total = len(checks)
    started = time.time()
    for i, fn in enumerate(checks, 1):
        ok, name, msg, hint = fn()
        if ok:
            _print_ok(name, msg)
        else:
            _print_fail(name, msg, hint)
            print(
                f"[preflight] FAILED at check {i}/{total} — "
                "aborting before any LLM cost"
            )
            return 2
    elapsed = time.time() - started
    print(f"[preflight] {total}/{total} passed in {elapsed:.1f}s")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        default="canonical-portrait-talking-head",
        help="Fixture episode slug (default: canonical-portrait-talking-head)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mount + compile but do not invoke (smoke test wiring without LLM spend).",
    )
    parser.add_argument(
        "--mode",
        choices=["replay", "record-on-miss", "record"],
        default="record-on-miss",
        help=(
            "Cache mount mode. 'replay' opens fixture cache.db read-only and "
            "raises ReplayCacheMissError on the first miss — $0 dry-run for "
            "auditing recording coverage. 'record-on-miss' (default) pays "
            "only for misses. 'record' starts empty + pays for the full run."
        ),
    )
    parser.add_argument(
        "--max-resumes",
        type=int,
        default=8,
        help="Defensive ceiling on interrupt-resume loop iterations (default 8).",
    )
    parser.add_argument(
        "--preflight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run the 5-check HOM-307 preflight before mounting the cache "
            "(default: on). Use --no-preflight + --preflight-override-reason "
            "to skip (emergency only — the checks exist to fail-fast before "
            "$3-12 LLM spend)."
        ),
    )
    parser.add_argument(
        "--preflight-override-reason",
        type=str,
        default=None,
        help=(
            "Required when --no-preflight is set. Logged in stdout. "
            "Reviewer reads this on the resulting cache.db diff."
        ),
    )
    args = parser.parse_args()

    if not args.preflight:
        if not args.preflight_override_reason:
            print(
                "[record_fixture] FATAL: preflight override requires "
                "--preflight-override-reason",
                file=sys.stderr,
            )
            return 2
        print(
            f"[record_fixture] PREFLIGHT SKIPPED (override reason: "
            f"{args.preflight_override_reason})"
        )
    else:
        rc = run_preflight(args.slug)
        if rc != 0:
            return rc

    # Imports deferred until after env is pinned + preflight passed.
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Command

    from edit_episode_graph import graph as graph_mod
    from edit_episode_graph._paths import project_root

    from tests._helpers.replay_harness import (
        finalize_record_on_miss,
        mount_fixture_cache,
        open_cache,
    )

    print(f"[record_fixture] HOMESTUDIO_PROJECT_ROOT = {os.environ['HOMESTUDIO_PROJECT_ROOT']}")
    print(f"[record_fixture] project_root()         = {project_root()}")
    print(f"[record_fixture] slug                    = {args.slug}")

    fixture_root = _WORKTREE / "tests" / "fixtures"
    episode_dir = fixture_root / "episodes" / args.slug
    raw_path = episode_dir / "raw.mp4"
    if not raw_path.exists():
        # Defensive — preflight check 5 already covers this, but a
        # --no-preflight run still needs the guard.
        print(f"[record_fixture] FATAL: fixture raw not found at {raw_path}", file=sys.stderr)
        return 2

    # Mount fixture in record mode — empty tmp working file. finalize_record_on_miss
    # will VACUUM INTO the canonical fixture path on success.
    mounted = mount_fixture_cache(args.slug, mode=args.mode, fixtures_root=fixture_root)
    print(f"[record_fixture] mounted cache mode={mounted.mode}")
    print(f"[record_fixture]   working_path={mounted.working_path}")
    print(f"[record_fixture]   fixture_path={mounted.fixture_path}")

    cache = open_cache(mounted)

    # Compile graph with our working cache + InMemorySaver. langgraph-api
    # rejects user-supplied checkpointers but we are not running under it.
    saver = InMemorySaver()
    compiled = graph_mod.build_graph_uncompiled().compile(cache=cache, checkpointer=saver)

    if args.dry_run:
        print("[record_fixture] --dry-run: graph compiled, no invoke. Exiting clean.")
        mounted.cleanup()
        return 0

    thread_id = f"hom-189-record-{int(time.time())}"
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 200}
    print(f"[record_fixture] thread_id={thread_id}")

    # First invocation seeds the slug; subsequent invocations resume.
    invocation_input = {"slug": args.slug}
    started = time.time()
    resumes = 0
    final_state: dict | None = None

    try:
        while True:
            try:
                final_state = compiled.invoke(invocation_input, config=cfg)
            except GraphInterrupt as gi:
                # Older / different code paths may still raise; treat the same
                # as the channel-based signal below.
                final_state = {"__interrupt__": list(gi.args[0]) if gi.args else []}

            # langgraph 1.x: an interrupt sets the `__interrupt__` channel
            # on the returned state instead of raising. Reference:
            # https://docs.langchain.com/oss/python/langgraph/use-graph-api#human-in-the-loop
            # https://docs.langchain.com/oss/python/langgraph/types#interrupt
            ints = (final_state or {}).get("__interrupt__") or []
            if not ints:
                print(f"[record_fixture] graph terminated after {resumes} resume(s)")
                break

            resumes += 1
            if resumes > args.max_resumes:
                print(
                    f"[record_fixture] FATAL: exceeded --max-resumes={args.max_resumes}",
                    file=sys.stderr,
                )
                break

            preview = []
            for i in ints[:3]:
                val = getattr(i, "value", None) if not isinstance(i, dict) else i.get("value")
                if isinstance(val, dict):
                    preview.append(val.get("checkpoint", "?"))
                else:
                    preview.append(repr(val)[:60])
            print(f"[record_fixture] interrupt #{resumes}: {preview} — resuming with 'approved'")
            invocation_input = Command(resume="approved")  # type: ignore[assignment]

        # Pull the final state via checkpoint, in case invoke returned a partial dict.
        snap = compiled.get_state(cfg)
        if snap is not None:
            final_state = snap.values
        elapsed = time.time() - started
        print(f"[record_fixture] elapsed: {elapsed:.1f}s, resumes: {resumes}")
        if isinstance(final_state, dict):
            errs = final_state.get("errors") or []
            notices = final_state.get("notices") or []
            print(f"[record_fixture] errors: {len(errs)} | notices: {len(notices)}")
            if errs:
                print(f"[record_fixture] FIRST ERROR: {errs[0]}", file=sys.stderr)
            for n in notices[-3:]:
                print(f"[record_fixture] NOTICE: {n}")

    finally:
        # Always try to persist whatever the run produced — partial recordings
        # are still valuable. finalize is a no-op in replay mode; safe.
        try:
            finalize_record_on_miss(mounted, cache)
            print(f"[record_fixture] finalized -> {mounted.fixture_path}")
        except Exception as e:  # pragma: no cover — diagnostic only
            print(f"[record_fixture] finalize failed: {e!r}", file=sys.stderr)
        mounted.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
