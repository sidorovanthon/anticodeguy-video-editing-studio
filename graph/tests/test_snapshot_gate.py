"""Unit tests for gate:snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.gates import _base
from edit_episode_graph.gates.snapshot import (
    SnapshotGate,
    _beat_start_offsets,
    snapshot_gate_node,
)


# Two PNG sentinels — one definitely above the 30 KB threshold (good
# render), one well below (blank/black render simulation).
_GOOD_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * (50 * 1024)
_BLANK_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024


def _hf(tmp_path: Path) -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    (hf_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return hf_dir


def _state(hf_dir: Path, beats: list[dict] | None = None) -> dict:
    state: dict = {"compose": {"hyperframes_dir": str(hf_dir)}}
    if beats is not None:
        state["compose"]["plan"] = {"beats": beats}
    return state


def _patch_run_writing_frames(
    monkeypatch: pytest.MonkeyPatch,
    *,
    exit_code: int = 0,
    frame_sizes: list[int] | None = None,
    blank_indices: tuple[int, ...] = (),
    stderr: str = "",
) -> dict:
    """Replace run_hf_cli with a fake that writes PNGs to <hf_dir>/snapshots/.

    `frame_sizes`: explicit byte counts per frame. If omitted, mirrors the
    `--at` count and writes good-sized frames. `blank_indices` substitutes
    a tiny PNG at those positions (simulating black/blank render).
    """
    captured: dict = {}

    def fake_run(args, hf_dir, **kw):
        captured["args"] = list(args)
        captured["hf_dir"] = hf_dir

        if "--at" in args:
            at_value = args[args.index("--at") + 1]
            timestamps = [float(t) for t in at_value.split(",")]
        else:
            # Default --frames=5 even sampling (timestamps don't matter for
            # the gate's checks — only filenames + sizes do).
            timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]

        n = len(timestamps)
        sizes = frame_sizes if frame_sizes is not None else [len(_GOOD_PNG)] * n

        snapshots_dir = hf_dir / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)
        for i, (ts, size) in enumerate(zip(timestamps, sizes)):
            blob = (b"\x89PNG\r\n\x1a\n" + b"\x00" * size) if i in blank_indices else (
                b"\x89PNG\r\n\x1a\n" + b"\x00" * size
            )
            (snapshots_dir / f"frame-{i:02d}-at-{ts:.1f}s.png").write_bytes(blob)

        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=exit_code,
            stdout="",
            stderr=stderr,
        )

    monkeypatch.setattr("edit_episode_graph.gates.snapshot.run_hf_cli", fake_run)
    return captured


def test_passes_when_all_frames_above_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf(tmp_path)
    _patch_run_writing_frames(monkeypatch, exit_code=0)

    update = snapshot_gate_node(
        _state(hf_dir, beats=[{"duration_s": 2.0}, {"duration_s": 3.0}])
    )
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:snapshot"


def test_fails_when_any_frame_below_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf(tmp_path)
    # Two frames; second is tiny (simulated black/blank render).
    _patch_run_writing_frames(
        monkeypatch,
        exit_code=0,
        frame_sizes=[60 * 1024, 1024],
    )

    update = snapshot_gate_node(
        _state(hf_dir, beats=[{"duration_s": 2.0}, {"duration_s": 3.0}])
    )
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("blank/black render" in v for v in record["violations"])


def test_fails_when_cli_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf(tmp_path)

    def fake_run(args, hf_dir, **kw):
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=2,
            stdout="",
            stderr="puppeteer: Failed to launch browser",
        )

    monkeypatch.setattr("edit_episode_graph.gates.snapshot.run_hf_cli", fake_run)

    update = snapshot_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("exit=2" in v for v in record["violations"])


def test_fails_when_fewer_frames_than_expected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """CLI succeeds but only writes some of the expected PNGs."""
    hf_dir = _hf(tmp_path)
    captured: dict = {}

    def fake_run(args, hf_dir, **kw):
        captured["args"] = list(args)
        snapshots_dir = hf_dir / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)
        # Only write 1 of 3 expected frames.
        (snapshots_dir / "frame-00-at-0.0s.png").write_bytes(_GOOD_PNG)
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("edit_episode_graph.gates.snapshot.run_hf_cli", fake_run)

    update = snapshot_gate_node(
        _state(
            hf_dir,
            beats=[{"duration_s": 1}, {"duration_s": 1}, {"duration_s": 1}],
        )
    )
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("expected 3" in v for v in record["violations"])


def test_passes_at_arg_at_beat_offsets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf(tmp_path)
    captured = _patch_run_writing_frames(monkeypatch, exit_code=0)

    snapshot_gate_node(
        _state(
            hf_dir,
            beats=[
                {"duration_s": 2.5},
                {"duration_s": 3.0},
                {"duration_s": 4.5},
            ],
        )
    )
    args = captured["args"]
    assert "--at" in args
    assert args[args.index("--at") + 1] == "0,2.5,5.5"


def test_omits_at_when_no_beats(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf(tmp_path)
    captured = _patch_run_writing_frames(monkeypatch, exit_code=0)

    snapshot_gate_node(_state(hf_dir))
    assert "--at" not in captured["args"]


def test_clears_stale_frames_before_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Stale frames from a prior good run must not mask a new blank-render
    failure when fewer fresh frames are produced."""
    hf_dir = _hf(tmp_path)
    snapshots_dir = hf_dir / "snapshots"
    snapshots_dir.mkdir()
    # Pre-populate with an old good frame that should NOT survive.
    (snapshots_dir / "frame-99-at-99.0s.png").write_bytes(_GOOD_PNG)

    def fake_run(args, hf_dir, **kw):
        # New run produces only one tiny frame.
        snaps = hf_dir / "snapshots"
        snaps.mkdir(exist_ok=True)
        (snaps / "frame-00-at-0.0s.png").write_bytes(_BLANK_PNG)
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("edit_episode_graph.gates.snapshot.run_hf_cli", fake_run)

    update = snapshot_gate_node(_state(hf_dir, beats=[{"duration_s": 1}]))
    record = update["gate_results"][0]
    # Stale was cleared, so we see exactly one frame and it's blank-sized.
    assert not record["passed"]
    assert any("blank/black render" in v for v in record["violations"])


def test_fails_when_no_hyperframes_dir_in_state():
    update = snapshot_gate_node({})
    assert not update["gate_results"][0]["passed"]


def test_fails_when_hyperframes_dir_missing_on_disk(tmp_path: Path):
    update = snapshot_gate_node(
        {"compose": {"hyperframes_dir": str(tmp_path / "nope")}}
    )
    assert not update["gate_results"][0]["passed"]


def test_beat_start_offsets_cumulative():
    state = {
        "compose": {
            "plan": {
                "beats": [
                    {"duration_s": 2},
                    {"duration_s": 3.5},
                    {"duration_s": 1.25},
                ]
            }
        }
    }
    assert _beat_start_offsets(state) == [0.0, 2.0, 5.5]
