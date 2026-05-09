"""Unit tests for gate:animation_map.

HOM-204 demoted this gate to advisory: the helper still runs, but its
findings (collision / degenerate / dead-zone / paced-fast / paced-slow)
land under ``record["advisory_findings"]`` and never produce
``passed=False``. Only **infrastructure failures** (helper missing,
exit != 0, JSON unparseable) keep ``passed=False``.

Exercises:
  - successful helper runs always set ``passed=True`` regardless of
    finding count
  - ``advisory_findings`` always carries the canonical three-key shape
    ``{"always_fix": [...], "dead_zones": [...], "pending_classify": [...]}``
  - ``record["violations"]`` stays empty on successful runs (Gate base
    contract preserved; routing layer no longer reads it)
  - bundled-path resolution (preferred over global fallback)
  - bootstrap-failure triage emits an actionable ``npm i -D`` message
    and keeps ``passed=False`` (infrastructure issue)
  - cache version is 4 (HOM-204 bump)
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


# ── HOM-204: cache version bump ──────────────────────────────────────────────


def test_cache_version_is_4():
    """HOM-204 bumped 3→4 because output shape changed (advisory_findings).

    The fingerprint registry's CREATIVE_NODES parametrisation does not
    cover this deterministic gate (it uses ``make_key``, not
    ``make_llm_key``); this direct assertion is the version-bump gate.
    """
    assert gate_mod._CACHE_VERSION == 4


def test_cache_key_includes_version(tmp_path, monkeypatch):
    """Editing _CACHE_VERSION must change the cache key (HOM-184 invariant
    applied directly to a deterministic gate)."""
    hf_dir = _hf_dir(tmp_path)
    state = _state(hf_dir)
    before = gate_mod._cache_key(state)
    monkeypatch.setattr(gate_mod, "_CACHE_VERSION", gate_mod._CACHE_VERSION + 1)
    after = gate_mod._cache_key(state)
    assert before != after


# ── HOM-204: successful helper runs always pass, findings are advisory ───────


def test_clean_report_passes_with_empty_advisory_findings(tmp_path, monkeypatch):
    """No flags, no dead zones ⇒ passed=True; advisory_findings has empty lists."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "duration": 12.0,
        "tweens": [
            {"index": 1, "selector": ".title", "duration": 0.6, "flags": []},
            {"index": 2, "selector": ".body", "duration": 0.8, "flags": []},
        ],
        "deadZones": [
            {"start": 5.0, "end": 6.0, "duration": 1.0, "note": "exactly 1s — allowed"},
        ],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    advisory = record["advisory_findings"]
    assert advisory == {"always_fix": [], "dead_zones": [], "pending_classify": []}
    assert record["fallback_helper_used"] is False
    notice = update["notices"][0]
    assert "advisory" in notice and "no findings" in notice


def test_collision_flag_is_advisory_not_blocking(tmp_path, monkeypatch):
    """HOM-204: collision flag lands in advisory_findings.always_fix; passed=True."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".a", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": ".b", "duration": 0.6, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True, "successful helper run ⇒ pass even with findings"
    assert record["violations"] == [], "violations field reserved for infra failures"
    advisory = record["advisory_findings"]
    assert len(advisory["always_fix"]) == 1
    assert "collision" in advisory["always_fix"][0]
    assert ".a" in advisory["always_fix"][0] and ".b" in advisory["always_fix"][0]
    notice = update["notices"][0]
    assert "advisory" in notice and "always_fix: 1" in notice


def test_paced_fast_records_pending_classify(tmp_path, monkeypatch):
    """paced-fast tween → advisory_findings.pending_classify; passed=True."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    pending = record["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["flag"] == "paced-fast"
    assert pending[0]["selector"] == ".flash"
    assert pending[0]["flag_id"] == ".flash::1::paced-fast"


def test_paced_slow_records_pending_classify(tmp_path, monkeypatch):
    """paced-slow flags also surface under pending_classify."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 2, "selector": ".ambient", "duration": 3.0, "flags": ["paced-slow"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    pending = record["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["flag"] == "paced-slow"


def test_dead_zone_over_one_second_is_advisory(tmp_path, monkeypatch):
    """Dead zone > 1s ⇒ advisory_findings.dead_zones; passed=True (HOM-204)."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": ".a", "duration": 0.5, "flags": []}],
        "deadZones": [
            {"start": 4.0, "end": 5.5, "duration": 1.5, "note": "no anim"},
        ],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    dead_zones = record["advisory_findings"]["dead_zones"]
    assert len(dead_zones) == 1
    assert "1.5" in dead_zones[0] and "dead zone" in dead_zones[0]


def test_collision_and_pace_and_dead_zone_all_advisory(tmp_path, monkeypatch):
    """HOM-204 acceptance: a synth report with collision + degenerate +
    dead-zone + paced-fast all land as advisory findings; passed=True;
    violations=[]."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".a", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": ".b", "duration": 0.6, "flags": ["collision"]},
            {"index": 3, "selector": ".hairline", "duration": 0.4, "flags": ["degenerate"]},
            {"index": 4, "selector": ".flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [
            {"start": 10.0, "end": 12.0, "duration": 2.0, "note": "intentional hold"},
        ],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    advisory = record["advisory_findings"]
    assert any("collision" in s for s in advisory["always_fix"])
    assert any("degenerate" in s for s in advisory["always_fix"])
    assert len(advisory["dead_zones"]) == 1
    assert len(advisory["pending_classify"]) == 1
    assert advisory["pending_classify"][0]["flag"] == "paced-fast"
    notice = update["notices"][0]
    # Total = 2 always_fix (collision+degenerate) + 1 dead_zone + 1 pending.
    assert "4 finding(s)" in notice
    assert "always_fix: 2" in notice
    assert "dead_zones: 1" in notice
    assert "pending_classify: 1" in notice


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
    assert record["passed"] is True
    assert record["fallback_helper_used"] is True
    assert any("global fallback helper" in n for n in update.get("notices", []))


# ── Infrastructure failures keep passed=False ────────────────────────────────


def test_bootstrap_failure_emits_actionable_npm_i_command(tmp_path, monkeypatch):
    """HOM-204: bootstrap failure is infrastructure ⇒ passed=False stays."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Could not resolve required package(s): @hyperframes/producer\n"
        "  npm install --save-dev @hyperframes/producer@0.4.45 sharp@0.33.0\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False, "bootstrap failure is infrastructure"
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer@0.4.45" in joined
    assert "sharp@0.33.0" in joined
    # Advisory findings still present, just empty (no helper output to parse).
    assert record["advisory_findings"] == {
        "always_fix": [], "dead_zones": [], "pending_classify": []
    }


def test_bootstrap_failure_global_fallback_no_version_pin(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Error: Could not determine the bundled HyperFrames version for "
        "@hyperframes/producer.\nInstall the package yourself or pass a "
        "pinned options.npmPackages entry.\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer" in joined


def test_bootstrap_failure_without_install_line_uses_documented_fallback(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = "spawnSync npm.cmd EINVAL\nRequired helper package(s) are missing.\n"
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer" in joined
    assert "sharp" in joined


def test_fails_when_no_hyperframes_dir_in_state():
    record = animation_map_gate_node({})["gate_results"][0]
    assert record["passed"] is False
    assert record["advisory_findings"] == {
        "always_fix": [], "dead_zones": [], "pending_classify": []
    }


def test_fails_when_helper_not_found_anywhere(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path)
    monkeypatch.setattr(gate_mod, "_GLOBAL_FALLBACK", tmp_path / "definitely-not-there.mjs")
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("animation-map.mjs not found" in v for v in record["violations"])


def test_runtime_filenotfound_records_failure_does_not_raise(tmp_path, monkeypatch):
    """Gates MUST NOT raise (per _base.py contract). Infrastructure failure
    surfaces as passed=False with violation text."""
    hf_dir = _hf_dir(tmp_path)
    helper = tmp_path / "fake-helper.mjs"
    helper.write_text("// stub", encoding="utf-8")
    _stub_resolver(monkeypatch, helper)
    monkeypatch.setattr(gate_mod, "_node_executable", lambda: "node")

    def boom(*a, **kw):
        raise FileNotFoundError("node vanished mid-call")

    monkeypatch.setattr(gate_mod.subprocess, "run", boom)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("node executable not found" in v for v in record["violations"])


def test_fails_when_helper_exits_zero_but_no_json(tmp_path, monkeypatch):
    """Exit 0 but missing animation-map.json is infrastructure failure."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, exit_code=0, report=None)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("not found" in v for v in record["violations"])
