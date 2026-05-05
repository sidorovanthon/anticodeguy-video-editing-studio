"""Unit tests for gate:animation_map.

Exercises:
  - the three v4 pass criteria (collision / paced-fast / dead zone >1s)
  - bundled-path resolution (preferred over global fallback)
  - bootstrap-failure triage emits an actionable `npm i -D` message
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edit_episode_graph.gates import animation_map as gate_mod
from edit_episode_graph.gates.animation_map import animation_map_gate_node


def _hf_dir(tmp_path: Path) -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir(parents=True)
    return hf_dir


def _state(hf_dir: Path) -> dict:
    return {"compose": {"hyperframes_dir": str(hf_dir)}}


def _stub_helper(monkeypatch, *, exit_code: int = 0, report: dict | None = None,
                 stderr: str = "", stdout: str = ""):
    """Replace `_run_helper` with a stub that synthesizes a result and writes
    `animation-map.json` into out_dir when `report` is provided.
    """

    def fake(hf_dir, helper, used_fallback, timeout=240.0):
        out_dir = hf_dir / gate_mod._OUT_SUBDIR
        out_dir.mkdir(parents=True, exist_ok=True)
        if report is not None:
            (out_dir / gate_mod._OUT_FILE).write_text(
                json.dumps(report), encoding="utf-8"
            )
        return gate_mod._HelperResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            helper_path=helper,
            used_fallback=used_fallback,
            out_dir=out_dir,
        )

    monkeypatch.setattr(gate_mod, "_run_helper", fake)


def _stub_resolver(monkeypatch, helper_path: Path, used_fallback: bool = False):
    monkeypatch.setattr(
        gate_mod, "_resolve_helper", lambda hf_dir: (helper_path, used_fallback)
    )


# ── Positive ─────────────────────────────────────────────────────────────────

def test_passes_with_clean_report(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "duration": 12.0,
        "tweens": [
            {"index": 1, "selector": ".title", "duration": 0.6, "flags": []},
            {"index": 2, "selector": ".body", "duration": 0.8, "flags": ["paced-slow"]},
        ],
        "deadZones": [
            {"start": 5.0, "end": 6.0, "duration": 1.0, "note": "exactly 1s — allowed"},
        ],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:animation_map"
    assert record["fallback_helper_used"] is False


# ── Negative: collision flag ─────────────────────────────────────────────────

def test_fails_on_collision_flag(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".a", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": ".b", "duration": 0.6, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    assert any("collision" in v and ".a" in v and ".b" in v for v in record["violations"])


# ── Negative: paced-fast at v4 ───────────────────────────────────────────────

def test_fails_on_paced_fast_at_v4(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    assert any("paced-fast" in v and "v5" in v for v in record["violations"])


# ── Negative: dead zone > 1s ─────────────────────────────────────────────────

def test_fails_on_dead_zone_over_one_second(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": ".a", "duration": 0.5, "flags": []}],
        "deadZones": [
            {"start": 4.0, "end": 5.5, "duration": 1.5, "note": "no anim"},
        ],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    assert any("1.5" in v and "dead zone" in v for v in record["violations"])


# ── Path resolution: bundled preferred over global fallback ──────────────────

def test_resolves_bundled_helper_in_preference_to_global(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    bundled = hf_dir / gate_mod._BUNDLED_REL
    bundled.parent.mkdir(parents=True)
    bundled.write_text("// stub", encoding="utf-8")

    fake_global = tmp_path / "fake-global-helper.mjs"
    fake_global.write_text("// stub", encoding="utf-8")
    monkeypatch.setattr(gate_mod, "_GLOBAL_FALLBACK", fake_global)

    helper, used_fallback = gate_mod._resolve_helper(hf_dir)
    assert helper == bundled
    assert used_fallback is False


def test_falls_back_to_global_when_bundled_missing(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    fake_global = tmp_path / "fake-global-helper.mjs"
    fake_global.write_text("// stub", encoding="utf-8")
    monkeypatch.setattr(gate_mod, "_GLOBAL_FALLBACK", fake_global)

    helper, used_fallback = gate_mod._resolve_helper(hf_dir)
    assert helper == fake_global
    assert used_fallback is True


def test_fallback_use_emits_notice(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs", used_fallback=True)
    _stub_helper(monkeypatch, report={"tweens": [], "deadZones": []})
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"]
    assert record["fallback_helper_used"] is True
    assert any("global fallback helper" in n for n in update.get("notices", []))


# ── Bootstrap failure → actionable npm i -D message ──────────────────────────

def test_bootstrap_failure_emits_actionable_npm_i_command(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Could not resolve required package(s): @hyperframes/producer\n"
        "  npm install --save-dev @hyperframes/producer@0.4.45 sharp@0.33.0\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer@0.4.45" in joined
    assert "sharp@0.33.0" in joined


def test_bootstrap_failure_global_fallback_no_version_pin(tmp_path, monkeypatch):
    """Surfaced by the smoke run: when the gate falls back to the global
    helper copy and the helper can't determine a version, the error reads
    `Could not determine the bundled HyperFrames version`. Ensure that
    phrasing also triggers actionable triage."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Error: Could not determine the bundled HyperFrames version for "
        "@hyperframes/producer.\nInstall the package yourself or pass a "
        "pinned options.npmPackages entry.\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer" in joined


def test_bootstrap_failure_without_install_line_uses_documented_fallback(tmp_path, monkeypatch):
    """When the helper's stderr doesn't include the advisory line (e.g. EINVAL
    raised before package-loader prints it), we still emit a usable command
    pulled from CLAUDE.md."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = "spawnSync npm.cmd EINVAL\nRequired helper package(s) are missing.\n"
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer" in joined
    assert "sharp" in joined


# ── Misc state failures ──────────────────────────────────────────────────────

def test_fails_when_no_hyperframes_dir_in_state():
    record = animation_map_gate_node({})["gate_results"][0]
    assert not record["passed"]


def test_fails_when_helper_not_found_anywhere(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    monkeypatch.setattr(gate_mod, "_GLOBAL_FALLBACK", tmp_path / "definitely-not-there.mjs")
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    assert any("animation-map.mjs not found" in v for v in record["violations"])


def test_fails_when_helper_exits_zero_but_no_json(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, exit_code=0, report=None)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert not record["passed"]
    assert any("not found" in v for v in record["violations"])
