"""Bare-repro for HF sub-composition loader bug (upstream #589).

Memory entry: ``feedback_hf_subcomp_loader_data_composition_src``.

Scaffolds a clean ``npx hyperframes init`` project, wires up a canonical
``<template id="...-template">`` sub-composition mounted via
``data-composition-src``, then runs ``npx hyperframes compositions`` and
inspects whether the sub-composition reports ``0 elements / 0.0s``.

The canonical pattern is documented in ``~/.agents/skills/hyperframes/SKILL.md``
section "Composition Structure" — root carries
``<div data-composition-src="compositions/<name>.html">`` and the sub-comp
file uses a ``<template id="<name>-template">`` wrapper around the
``data-composition-id`` div.

Exit codes:

* ``0`` — bug reproduces (sub-comp reports ``0 elements`` / ``0.0s``).
* ``1`` — bug does NOT reproduce — the sub-comp now loads with non-zero
  element count. Memory entry needs a human review before clearing.
* ``2`` — inconclusive (timeout, missing ``npx``, scaffold failure, parser
  could not locate the sub-comp in CLI output).

This script is invoked by ``graph/src/edit_episode_graph/nodes/preflight_canon.py``;
it can also be run manually to spot-check upstream status.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SUB_COMP_ID = "beat-one"
SUB_COMP_FILE = f"compositions/{SUB_COMP_ID}.html"

ROOT_INDEX_TEMPLATE = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <style>
      html, body {{ margin: 0; padding: 0; }}
      body {{ width: 1920px; height: 1080px; background: #000; overflow: hidden; }}
    </style>
  </head>
  <body>
    <div id="root"
         data-composition-id="root"
         data-start="0"
         data-duration="3"
         data-width="1920"
         data-height="1080">
      <div id="el-sub"
           data-composition-id="{sub_id}"
           data-composition-src="{sub_src}"
           data-start="0"
           data-duration="3"
           data-track-index="1"></div>
    </div>
  </body>
</html>
"""

SUB_COMP_TEMPLATE = """<template id="{sub_id}-template">
  <div data-composition-id="{sub_id}"
       data-width="1920"
       data-height="1080"
       data-duration="3">
    <h1 id="el-h1" class="title" data-start="0" data-duration="3"
        style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
               color:#fff; font-family:sans-serif; font-size:120px;">Hello</h1>
    <script>
      // Minimal entrance to ensure GSAP rules don't trip lint independently.
      window.addEventListener('hf-ready', () => {{
        if (window.gsap) {{
          gsap.fromTo('#el-h1', {{opacity: 0}}, {{opacity: 1, duration: 0.5}});
        }}
      }});
    </script>
  </div>
</template>
"""


def _npx_cmd() -> list[str]:
    """Resolve the ``npx`` invocation for the current platform.

    Windows ships ``npx`` as ``npx.cmd`` — a batch shim that
    ``subprocess.CreateProcess`` cannot launch directly (raises ``WinError 193``,
    same Node-on-Windows quirk class as ``npm.cmd``; see CLAUDE.md
    "Known Windows blocker"). Prepending ``cmd.exe /c`` is the portable
    workaround that keeps ``shell=False`` and avoids the quoting hazards
    of ``shell=True``.
    """
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return []
    if os.name == "nt":
        return ["cmd.exe", "/c", npx]
    return [npx]


def _run(cmd: list[str], *, cwd: Path, timeout_s: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        shell=False,
    )


def _scaffold(workdir: Path, *, timeout_s: float) -> Path:
    """Run ``npx hyperframes init bare --yes`` inside *workdir*.

    Returns the created project directory (``workdir/bare``).
    """
    npx = _npx_cmd()
    if not npx:
        raise RuntimeError("npx is not available on PATH")
    workdir.mkdir(parents=True, exist_ok=True)
    result = _run(
        [*npx, "hyperframes", "init", "bare", "--yes"],
        cwd=workdir,
        timeout_s=timeout_s,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"hyperframes init failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )
    project = workdir / "bare"
    if not (project / "index.html").exists():
        raise RuntimeError(f"hyperframes init did not produce {project / 'index.html'}")
    return project


def _wire_subcomp(project: Path) -> None:
    """Overwrite ``index.html`` with the sub-comp loader and create the sub-comp file."""
    (project / "index.html").write_text(
        ROOT_INDEX_TEMPLATE.format(sub_id=SUB_COMP_ID, sub_src=SUB_COMP_FILE),
        encoding="utf-8",
    )
    sub_path = project / "compositions" / f"{SUB_COMP_ID}.html"
    sub_path.parent.mkdir(parents=True, exist_ok=True)
    sub_path.write_text(SUB_COMP_TEMPLATE.format(sub_id=SUB_COMP_ID), encoding="utf-8")


def _interpret_compositions_output(stdout: str, stderr: str) -> str | None:
    """Look for the sub-comp's element count in CLI output.

    Returns ``"reproduced"`` when the bug is present (0 elements / 0.0s near
    the sub-comp id), ``"fixed"`` when the sub-comp shows non-zero elements
    or duration, or ``None`` when the parser cannot locate the sub-comp at all
    (caller maps to inconclusive).
    """
    blob = f"{stdout}\n{stderr}"
    # Window of text near the sub-comp id — captures whatever line/columns
    # the CLI uses to report element count + duration.
    pattern = re.compile(
        rf"{re.escape(SUB_COMP_ID)}.{{0,400}}",
        flags=re.DOTALL,
    )
    matches = pattern.findall(blob)
    if not matches:
        return None
    chunk = " ".join(matches)
    # Bug signature per memory entry (verified 2026-05-01): "0 elements / 0.0s".
    if re.search(r"\b0\s*elements?\b", chunk) and re.search(r"\b0\.0+\s*s\b", chunk):
        return "reproduced"
    # Any positive element count + non-zero duration in the same window
    # indicates the loader is unwrapping <template>.content correctly now.
    if re.search(r"\b[1-9]\d*\s*elements?\b", chunk):
        return "fixed"
    return None


def main() -> int:
    overall_timeout_s = 60.0
    if "--timeout-s" in sys.argv:
        idx = sys.argv.index("--timeout-s")
        overall_timeout_s = float(sys.argv[idx + 1])

    if not _npx_cmd():
        print("npx not found on PATH; skipping bare-repro.", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="hf-bare-repro-") as tmp:
        workdir = Path(tmp)
        try:
            project = _scaffold(workdir, timeout_s=overall_timeout_s)
        except subprocess.TimeoutExpired:
            print("hyperframes init timed out", file=sys.stderr)
            return 2
        except RuntimeError as exc:
            print(f"scaffold failure: {exc}", file=sys.stderr)
            return 2

        _wire_subcomp(project)

        try:
            cli = _run(
                [*_npx_cmd(), "hyperframes", "compositions"],
                cwd=project,
                timeout_s=overall_timeout_s,
            )
        except subprocess.TimeoutExpired:
            print("hyperframes compositions timed out", file=sys.stderr)
            return 2

        verdict = _interpret_compositions_output(cli.stdout, cli.stderr)
        # Echo a short tail of CLI output for human triage.
        print("---- compositions stdout (tail) ----")
        print(cli.stdout[-800:])
        print("---- compositions stderr (tail) ----")
        print(cli.stderr[-400:])

        if verdict == "reproduced":
            print(f"VERDICT: reproduced — sub-comp {SUB_COMP_ID!r} reports 0 elements / 0.0s")
            return 0
        if verdict == "fixed":
            print(f"VERDICT: fixed — sub-comp {SUB_COMP_ID!r} reports non-zero element count")
            return 1
        print(
            f"VERDICT: inconclusive — could not locate {SUB_COMP_ID!r} "
            f"or interpret element-count line in CLI output",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
