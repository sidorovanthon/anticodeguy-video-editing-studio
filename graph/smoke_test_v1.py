"""Headless smoke test for v1 (HOM-73) — routing + node wiring.

Covers:
  R1: route_after_pickup → END on errors / idle
  R2: route_after_pickup → preflight_canon when raw is tagged (skip_phase2 = yes)
  R3: route_after_pickup → isolate_audio when raw is untagged
  R4: route_after_preflight → glue_remap_transcript when final.mp4 exists
  R5: route_after_preflight → halt_llm_boundary when final.mp4 missing
  R6: route_after_remap → p4_scaffold when index.html missing
  R7: route_after_remap → END when index.html exists
  R8: glue_remap_transcript_node returns precise error on missing Phase 3 artifacts
  R9: build_graph_uncompiled().compile() exposes all v1 nodes
  R10: full graph traversal halts at halt_llm_boundary with correct notice

The wrapped subprocess scripts (`scripts/isolate_audio.py`, `remap_transcript.py`,
`scaffold_hyperframes.py`) are tested independently via their own design specs;
re-running them here would burn ElevenLabs credits and require `npx`. Live
end-to-end runs are exercised manually through `langgraph dev` + Studio, per
v0's case 1.

Run from repo root:
    .venv\\Scripts\\python.exe graph\\smoke_test_v1.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from edit_episode_graph.graph import build_graph_uncompiled
from edit_episode_graph.nodes._routing import (
    TAG_KEY,
    TAG_VALUE,
    route_after_pickup,
    route_after_preflight,
    route_after_remap,
)
from edit_episode_graph.nodes.glue_remap_transcript import glue_remap_transcript_node
from langgraph.graph import END

REPO_ROOT = Path(__file__).resolve().parent.parent


def _stamp_tag(video: Path) -> None:
    """Re-mux `video` adding the clean-audio container tag (in place)."""
    tmp = video.with_name(video.stem + ".tagged" + video.suffix)
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-c", "copy",
        "-movflags", "use_metadata_tags",
        "-metadata", f"{TAG_KEY}={TAG_VALUE}",
        str(tmp),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg tag stamp failed: {result.stderr.decode(errors='replace')[-400:]}")
    tmp.replace(video)


def _make_minimal_mp4(dst: Path) -> None:
    """Synthesize a 1-second silent black mp4 via ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
        "-f", "lavfi", "-i", "anullsrc=cl=stereo:r=48000",
        "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg fixture mp4 failed: {result.stderr.decode(errors='replace')[-400:]}")


def _print_case(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{suffix}")


def main() -> int:
    failures: list[str] = []

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("FATAL: ffmpeg/ffprobe not on PATH — required to build tagged-mp4 fixtures.")
        return 2

    print("\n=== Routing decisions ===")

    with tempfile.TemporaryDirectory() as td:
        ep = Path(td) / "episode"
        ep.mkdir()
        raw = ep / "raw.mp4"
        _make_minimal_mp4(raw)

        # R1: errors/idle short-circuits to END.
        ok = route_after_pickup({"errors": [{"node": "x", "message": "y", "timestamp": "z"}]}) == END
        _print_case("R1a route_after_pickup → END on errors", ok)
        if not ok:
            failures.append("R1a")
        ok = route_after_pickup({"pickup": {"idle": True}}) == END
        _print_case("R1b route_after_pickup → END on idle", ok)
        if not ok:
            failures.append("R1b")

        # R3: untagged raw → isolate_audio.
        decision = route_after_pickup({"episode_dir": str(ep)})
        ok = decision == "isolate_audio"
        _print_case("R3 untagged raw → isolate_audio", ok, f"got {decision!r}")
        if not ok:
            failures.append("R3")

        # R2: tag the raw and re-check.
        _stamp_tag(raw)
        decision = route_after_pickup({"episode_dir": str(ep)})
        ok = decision == "preflight_canon"
        _print_case("R2 tagged raw → preflight_canon (skip_phase2)", ok, f"got {decision!r}")
        if not ok:
            failures.append("R2")

        # R4 / R5: final.mp4 presence.
        decision = route_after_preflight({"episode_dir": str(ep)})
        ok = decision == "halt_llm_boundary"
        _print_case("R5 no final.mp4 → halt_llm_boundary", ok, f"got {decision!r}")
        if not ok:
            failures.append("R5")

        edit = ep / "edit"
        edit.mkdir()
        (edit / "final.mp4").write_bytes(b"\x00" * 16)
        decision = route_after_preflight({"episode_dir": str(ep)})
        ok = decision == "glue_remap_transcript"
        _print_case("R4 final.mp4 present → glue_remap_transcript", ok, f"got {decision!r}")
        if not ok:
            failures.append("R4")

        # R6 / R7: index.html presence.
        decision = route_after_remap({"episode_dir": str(ep)})
        ok = decision == "p4_scaffold"
        _print_case("R6 no index.html → p4_scaffold", ok, f"got {decision!r}")
        if not ok:
            failures.append("R6")

        hf = ep / "hyperframes"
        hf.mkdir()
        (hf / "index.html").write_text("<html></html>", encoding="utf-8")
        decision = route_after_remap({"episode_dir": str(ep)})
        ok = decision == END
        _print_case("R7 index.html present → END", ok, f"got {decision!r}")
        if not ok:
            failures.append("R7")

        # R8: glue_remap precise error on missing artifacts.
        result = glue_remap_transcript_node({"episode_dir": str(ep)})
        errs = result.get("errors") or []
        ok = bool(errs) and "missing Phase 3 artifact" in errs[0]["message"]
        _print_case("R8 glue_remap → error on missing Phase 3 artifacts", ok,
                    f"got errors={errs}")
        if not ok:
            failures.append("R8")

    print("\n=== Compiled graph shape ===")

    # R9: graph compiles with all v1 nodes.
    g = build_graph_uncompiled().compile()
    expected = {
        "pickup", "isolate_audio", "preflight_canon",
        "glue_remap_transcript", "p4_scaffold", "halt_llm_boundary",
    }
    actual = {n for n in g.nodes if not n.startswith("__")}
    missing = expected - actual
    ok = not missing
    _print_case("R9 compiled graph contains v1 nodes", ok,
                f"missing={sorted(missing)}" if missing else f"got {sorted(actual)}")
    if not ok:
        failures.append("R9")

    print("\n=== End-to-end traversal (LLM-boundary halt) ===")

    # R10: full traversal with stubbed pickup → halt_llm_boundary.
    # We patch pickup_node and isolate_audio_node so no subprocess runs; the
    # routing functions still see real state/disk.
    with tempfile.TemporaryDirectory() as td:
        ep = Path(td) / "ep"
        ep.mkdir()
        # No raw.mp4, no final.mp4 → skip_phase2 returns isolate_audio,
        # but we stub isolate_audio to a no-op and let preflight_canon route
        # us to halt_llm_boundary (no final.mp4).
        from langgraph.checkpoint.memory import InMemorySaver
        import edit_episode_graph.graph as gmod

        def _stub_pickup(state):
            return {"slug": "fixture", "episode_dir": str(ep), "pickup": {"idle": False}}

        def _stub_isolate(state):
            return {"audio": {"cached": False, "api_called": False, "reason": "stubbed"}}

        with patch.object(gmod, "pickup_node", _stub_pickup), \
             patch.object(gmod, "isolate_audio_node", _stub_isolate):
            compiled = gmod.build_graph_uncompiled().compile(checkpointer=InMemorySaver())
            cfg = {"configurable": {"thread_id": "smoke-v1-r10"}}
            final_state = compiled.invoke({}, config=cfg)

        notices = final_state.get("notices") or []
        ok = any("halt" in n and "LLM" in n for n in notices)
        _print_case("R10 traversal halts with LLM-boundary notice", ok, f"notices={notices}")
        if not ok:
            failures.append("R10")

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED ({len(failures)}): {failures}")
        return 1
    print("ALL HEADLESS V1 CASES PASSED (R1–R10)")
    print("Live `langgraph dev` + Studio run (per HOM-73 DoD) — manual verification required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
