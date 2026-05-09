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


def test_cache_version_is_5():
    """HOM-212 bumps 4→5 because verdict logic changed (per-flag blocking
    carve-outs flip `passed` from True→False on structural findings).

    HOM-204 bumped 3→4 for the original advisory output-shape change.
    The fingerprint registry's CREATIVE_NODES parametrisation does not
    cover this deterministic gate (it uses ``make_key``, not
    ``make_llm_key``); this direct assertion is the version-bump gate.
    """
    assert gate_mod._CACHE_VERSION == 5


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


def test_collision_on_decorative_is_advisory_not_blocking(tmp_path, monkeypatch):
    """HOM-212: collision flag on chrome decoratives (caption-strip, glow,
    grain, hairline, etc.) is by-construction FP — entrance + ambient yoyo
    on the same element. Lands in advisory_findings.always_fix, passed=True.

    Pre-HOM-212 wording was 'collision flag lands in advisory; passed=True'
    unconditionally — the carve-out only catches the FP class; off-canon
    selectors (e.g. `.headline`) now flip to BLOCKING (see
    `test_collision_on_content_element_is_blocking`).
    """
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Both selectors hit the default decorative allowlist — `glow`
            # and `grain` substrings — so the collision flag is carved out.
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": "div.grain", "duration": 0.6, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True, "decoratives carved out ⇒ pass"
    assert record["violations"] == [], "no blocking violations on decorative collisions"
    assert record["blocking_findings"] == []
    advisory = record["advisory_findings"]
    assert len(advisory["always_fix"]) == 1
    assert "collision" in advisory["always_fix"][0]
    assert "div.glow" in advisory["always_fix"][0] and "div.grain" in advisory["always_fix"][0]
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
    """HOM-204 acceptance, refined for HOM-212: a synth report with all-
    decorative collisions + 1px hairline degenerate + sub-threshold dead-
    zone + paced-fast all land as advisory findings; passed=True;
    violations=[]."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Decorative substring → carved out.
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": "div.grain", "duration": 0.6, "flags": ["collision"]},
            # 1px hairline → degenerate is carved out (max h = 1 < 2).
            {"index": 3, "selector": "div.hairline", "duration": 0.4, "flags": ["degenerate"],
             "bboxes": [{"t": 0.0, "x": 0, "y": 0, "w": 100, "h": 1}]},
            {"index": 4, "selector": ".flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [
            # 2.0s == default threshold — strictly NOT > threshold ⇒ advisory.
            {"start": 10.0, "end": 12.0, "duration": 2.0, "note": "intentional hold"},
        ],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    assert record["blocking_findings"] == []
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


# ── HOM-205: canonical advisory notice format ────────────────────────────────
#
# Exact format strings are documented in the gate's module docstring under
# "## Notice format". These assertions pin the format so future drift breaks
# the unit suite before it can leak into Studio.


def test_clean_run_notice_matches_canonical_format(tmp_path, monkeypatch):
    """HOM-205: success-no-findings notice is exactly the canonical line."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={"tweens": [], "deadZones": []})
    update = animation_map_gate_node(_state(hf_dir))
    assert update["notices"] == [
        "gate:animation_map: advisory — no findings (helper ran clean)"
    ]


def test_mixed_findings_notice_matches_canonical_format(tmp_path, monkeypatch):
    """HOM-205: success-with-findings notice carries the canonical breakdown
    line — `N finding(s) (always_fix: a, dead_zones: d, pending_classify: p)`
    plus the JSON path so the operator can open the helper output without
    hunting."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Decoratives — collision flag carved out (advisory).
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": "div.grain", "duration": 0.6, "flags": ["collision"]},
            # 1px hairline degenerate carved out.
            {"index": 3, "selector": "div.hairline", "duration": 0.4, "flags": ["degenerate"],
             "bboxes": [{"t": 0.0, "x": 0, "y": 0, "w": 100, "h": 1}]},
            {"index": 4, "selector": ".flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [
            # 2.0s == threshold — strictly NOT > 2.0 ⇒ advisory.
            {"start": 10.0, "end": 12.0, "duration": 2.0, "note": "intentional hold"},
        ],
    })
    notice = animation_map_gate_node(_state(hf_dir))["notices"][0]
    # Severity prefix — load-bearing for Studio surfaces.
    assert notice.startswith("gate:animation_map: advisory — ")
    # Total + breakdown — single-glance view of finding mix.
    assert "4 finding(s) (always_fix: 2, dead_zones: 1, pending_classify: 1)" in notice
    # JSON path — operator can open helper output directly.
    expected_path = gate_mod._animation_map_json_path(_state(hf_dir))
    assert f"See {expected_path}." in notice
    # No fallback hint when bundled helper resolved.
    assert "global fallback" not in notice


def test_fallback_helper_notice_appends_pin_deps_hint(tmp_path, monkeypatch):
    """HOM-205: when the global fallback helper ran, the canonical notice
    appends the pin-deps suggestion in parentheses."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs", used_fallback=True)
    _stub_helper(monkeypatch, report={
        # HOM-212: decorative selector → carved out, stays advisory so the
        # canonical advisory notice format is exercised.
        "tweens": [{"index": 1, "selector": "div.grain", "duration": 0.6, "flags": ["collision"]}],
        "deadZones": [],
    })
    notice = animation_map_gate_node(_state(hf_dir))["notices"][0]
    assert notice.startswith("gate:animation_map: advisory — ")
    assert "1 finding(s) (always_fix: 1, dead_zones: 0, pending_classify: 0)" in notice
    assert (
        "(via global fallback helper — consider pinning "
        "@hyperframes/producer + sharp in the HF project)"
    ) in notice


def test_infrastructure_failure_notice_uses_strong_wording(tmp_path, monkeypatch):
    """HOM-205: infra-failure notice is unchanged — 'infrastructure failure'
    prefix (NOT 'advisory') so the operator sees the severity clearly."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Could not resolve required package(s): @hyperframes/producer\n"
        "  npm install --save-dev @hyperframes/producer@0.4.45 sharp@0.33.0\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    update = animation_map_gate_node(_state(hf_dir))
    notice = update["notices"][0]
    assert notice.startswith(
        "gate:animation_map: infrastructure failure ("
    )
    assert "issue(s))" in notice
    assert "see gate_results" in notice
    # Critically: do NOT advertise this as "advisory".
    assert "advisory" not in notice


# ── HOM-212: per-flag blocking carve-outs ────────────────────────────────────
#
# HOM-204 demoted the gate wholesale; HOM-212 refines that with per-flag
# carve-outs. The HOM-211 reviewer caveat established that the bare ticket
# rule (`always_fix.count > 0 → block`) regresses to the HOM-203 redispatch
# loop because the canonical fixture's collision aggregate folds in 51
# `#cg-N` caption-canon findings + chrome-decorative entrance+yoyo FPs;
# carve-outs are the structural fix.


def test_collision_on_content_element_is_blocking(tmp_path, monkeypatch):
    """HOM-212 — Test 1 of 5 (ticket DoD).

    Collision on a non-canon, non-decorative selector → blocking. The
    routing layer reads `violations` (the standard cluster-retry-helper
    contract) so this routes to p4_redispatch_beat with iter<3.
    """
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # `.headline` is neither caption-canon (`#cg-N`) nor a chrome
            # decorative (no allowlist substring match) — so this collision
            # represents a real layout overlap the author should fix.
            {"index": 1, "selector": ".headline", "duration": 0.6, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is False, "non-canon non-decorative collision is blocking"
    assert record["blocking_findings"], "blocking_findings populated"
    assert any("blocking collision" in v for v in record["violations"]), (
        "violations carries the blocking strings for the cluster-retry router"
    )
    assert any(".headline" in v for v in record["violations"])
    notice = update["notices"][0]
    assert notice.startswith("gate:animation_map: BLOCKING — ")
    assert ".headline" in notice


def test_dead_zone_over_threshold_is_blocking(tmp_path, monkeypatch):
    """HOM-212 — Test 2 of 5 (ticket DoD).

    Dead-zone duration > config threshold (default 2.0s) → blocking with
    the threshold value cited in the violation. Sub-threshold dead zones
    (≤ 2.0s) stay advisory."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.grain", "duration": 0.6, "flags": []}],
        "deadZones": [
            # 4s > 2.0s default threshold ⇒ blocking.
            {"start": 22.5, "end": 26.5, "duration": 4.0, "note": "tail silence"},
        ],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking dead zone" in v for v in record["violations"])
    assert any("4.0" in v and "2.0" in v for v in record["violations"]), (
        "violation cites the offending duration AND the threshold"
    )


def test_pending_classify_only_stays_advisory_no_redispatch(tmp_path, monkeypatch):
    """HOM-212 — Test 3 of 5 (ticket DoD).

    `pending_classify`-only run is HOM-203's correct case: paced flags
    are LLM-judgement territory; routing must stay advisory and advance
    to the classifier (or snapshot if no pending), never redispatch."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "div.grain", "duration": 5.0, "flags": ["paced-slow"]},
            {"index": 2, "selector": "div.flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    assert record["blocking_findings"] == []
    assert len(record["advisory_findings"]["pending_classify"]) == 2
    notice = update["notices"][0]
    assert notice.startswith("gate:animation_map: advisory — ")
    assert "BLOCKING" not in notice


def test_caption_canon_collision_stays_advisory(tmp_path, monkeypatch):
    """HOM-212 — Test 4 of 5 (canonical FP cross-check).

    The `#cg-N` caption set+fromTo+to chain produces by-construction
    bbox-overlap collisions on every caption group (51 of 109 collision
    findings on the canonical fixture). Promoting these wholesale to
    blocking would re-introduce the HOM-203 redispatch loop on the
    canonical fixture. Carved out — must stay advisory."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "#cg-7", "duration": 0.32, "flags": ["collision"]},
            {"index": 2, "selector": "#cg-12", "duration": 0.32, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True, "caption canon carved out ⇒ pass"
    assert record["violations"] == []
    assert record["blocking_findings"] == []


def test_decorative_collision_stays_advisory(tmp_path, monkeypatch):
    """HOM-212 — Test 5 of 5 (canonical FP cross-check).

    Chrome decoratives (entrance fromTo + ambient yoyo on the same
    element) trigger helper bbox-overlap by construction. Default
    decorative allowlist covers grain/glow/hairline/vignette/overline/
    corner-mark/footer-mark/caption-strip/margin-tick. Operator can
    extend via `gates.animation_map.collision_decorative_allowlist`.
    """
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": "div.pf-grain", "duration": 0.8, "flags": ["collision"]},
            {"index": 3, "selector": "div.hairline-rule", "duration": 0.4, "flags": ["collision"]},
            {"index": 4, "selector": "div.vignette-top", "duration": 0.5, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    assert record["blocking_findings"] == []


# ── HOM-212: per-flag carve-out details ──────────────────────────────────────


def test_degenerate_on_1px_hairline_stays_advisory(tmp_path, monkeypatch):
    """1-px hairline → degenerate flag carved out; bbox h=1 < 2px default.

    HOM-211 found 5/5 canonical degenerate findings on `pf-hairline` /
    `margin-tick` / `kw-underline` — all 1-2 px decoratives whose
    `scaleX:0` initial state samples to zero-size bbox by construction."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "div.pf-hairline", "duration": 0.6,
             "flags": ["degenerate"],
             "bboxes": [
                 {"t": 0.1, "x": 0, "y": 0, "w": 0, "h": 1},
                 {"t": 0.3, "x": 0, "y": 0, "w": 200, "h": 1},
             ]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["blocking_findings"] == []


def test_degenerate_on_real_element_is_blocking(tmp_path, monkeypatch):
    """Degenerate flag on an element with bbox >= 2px both dimensions IS
    blocking — that's the failure mode the canon Step 4 mandate targets."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # 100×50 — far above the 2px floor; still degenerate-flagged
            # by the helper means a real authoring defect.
            {"index": 1, "selector": ".content-card", "duration": 0.6,
             "flags": ["degenerate"],
             "bboxes": [
                 {"t": 0.1, "x": 0, "y": 0, "w": 100, "h": 50},
                 {"t": 0.3, "x": 0, "y": 0, "w": 100, "h": 50},
             ]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking degenerate" in v for v in record["violations"])
    assert any(".content-card" in v for v in record["violations"])


def test_offscreen_is_unconditionally_blocking(tmp_path, monkeypatch):
    """No FP class identified for offscreen — element off-canvas the
    entire tween means audience never sees it. Blocking always."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Even a decorative-named selector — offscreen has no carve-out.
            {"index": 1, "selector": "div.grain", "duration": 0.6,
             "flags": ["offscreen"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking offscreen" in v for v in record["violations"])


def test_invisible_is_unconditionally_blocking(tmp_path, monkeypatch):
    """Same as offscreen — zero-opacity throughout = element never renders."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "div.glow", "duration": 0.6,
             "flags": ["invisible"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking invisible" in v for v in record["violations"])


def test_blocking_notice_lists_offending_categories(tmp_path, monkeypatch):
    """HOM-212 ticket DoD: 'blocking findings call out the offending
    category explicitly'. Notice format is
    `gate:animation_map: BLOCKING — N finding(s) require fix. <cat strs>. See <path>.`
    """
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".headline", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": ".off-bar", "duration": 0.6, "flags": ["offscreen"]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    notice = update["notices"][0]
    assert notice.startswith("gate:animation_map: BLOCKING — ")
    assert "blocking collision" in notice
    assert "blocking offscreen" in notice
    # Operator can still find the JSON for full triage.
    assert "See " in notice and ".hyperframes" in notice


def test_dead_zone_threshold_is_strict_greater_than(tmp_path, monkeypatch):
    """HOM-212: threshold comparison is `>`, not `>=`. A dead zone whose
    duration equals the threshold stays advisory (intentional pacing
    beat at the boundary). Only strictly-greater-than blocks."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.glow", "duration": 0.6, "flags": []}],
        "deadZones": [
            {"start": 5.0, "end": 7.0, "duration": 2.0, "note": "right at threshold"},
        ],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True, "dead-zone == threshold ⇒ advisory (strict >)"
    assert record["blocking_findings"] == []


def test_dead_zone_threshold_overridable_via_config(tmp_path, monkeypatch):
    """`gates.animation_map.dead_zone_threshold_s` from graph/config.yaml
    overrides the 2.0s default. Lower threshold ⇒ more dead-zones flip
    to blocking; higher threshold ⇒ fewer."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.glow", "duration": 0.6, "flags": []}],
        "deadZones": [
            {"start": 5.0, "end": 6.5, "duration": 1.5, "note": "1.5s hold"},
        ],
    })
    # Override config: drop the threshold to 1.0s so the 1.5s zone blocks.
    monkeypatch.setattr(
        gate_mod, "_gate_config",
        lambda: {"dead_zone_threshold_s": 1.0},
    )
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("1.0" in v and "1.5" in v for v in record["violations"])


def test_route_after_animation_map_blocking_collision_redispatches():
    """HOM-212 routing: blocking collision (beat-actionable) at iter<3
    routes to p4_redispatch_beat — the cluster-retry contract."""
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": False,
            "violations": ["blocking collision flag(s) on .headline — refine layout (HOM-212)"],
            "blocking_findings": ["blocking collision flag(s) on .headline — refine layout (HOM-212)"],
            "advisory_findings": {"always_fix": [], "dead_zones": [], "pending_classify": []},
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "p4_redispatch_beat"


def test_route_after_animation_map_blocking_dead_zone_only_halts():
    """HOM-212 routing: dead-zone-only blocking is a root-timeline /
    assembler concern, NOT beat-actionable. Routes to halt rather than
    redispatching a beat that can't fix the issue."""
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": False,
            "violations": ["blocking dead zone — max duration 4.0s exceeds threshold 2.0s (HOM-212)"],
            "blocking_findings": ["blocking dead zone — max duration 4.0s exceeds threshold 2.0s (HOM-212)"],
            "advisory_findings": {"always_fix": [], "dead_zones": [], "pending_classify": []},
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "halt_llm_boundary"


def test_route_after_animation_map_iter_cap_halts():
    """Beat-actionable blocking but iter>=3: halts (no infinite loop)."""
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": False,
            "violations": ["blocking collision flag(s) on .headline — refine layout (HOM-212)"],
            "blocking_findings": ["blocking collision flag(s) on .headline — refine layout (HOM-212)"],
            "advisory_findings": {"always_fix": [], "dead_zones": [], "pending_classify": []},
            "iteration": 3,
        }],
    }
    assert route_after_animation_map(state) == "halt_llm_boundary"


def test_route_after_animation_map_advisory_advances():
    """HOM-212: advisory-only run with no pending classify advances to snapshot."""
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": True,
            "violations": [],
            "blocking_findings": [],
            "advisory_findings": {
                "always_fix": ["collision flag(s) on div.glow — overlapping animated elements; refine layout"],
                "dead_zones": [],
                "pending_classify": [],
            },
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "gate_snapshot"


def test_route_after_animation_map_pending_classify_routes_to_classifier():
    """HOM-212: advisory + pending pace flags route to the LLM classifier
    (HOM-204 behaviour preserved on the no-blocking branch)."""
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": True,
            "violations": [],
            "blocking_findings": [],
            "advisory_findings": {
                "always_fix": [],
                "dead_zones": [],
                "pending_classify": [
                    {"flag_id": "div.grain::1::paced-slow", "selector": "div.grain",
                     "flag": "paced-slow", "duration": 5.2, "index": 1},
                ],
            },
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "gate_animation_map_classify"


def test_decorative_allowlist_overridable_via_config(tmp_path, monkeypatch):
    """Operator can extend / shrink the decorative allowlist via
    `gates.animation_map.collision_decorative_allowlist`. With an empty
    allowlist, even the chrome decoratives flip to blocking — useful as
    a strict-mode toggle."""
    hf_dir = _hf_dir(tmp_path)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    # Empty allowlist ⇒ no decorative carve-out.
    monkeypatch.setattr(
        gate_mod, "_gate_config",
        lambda: {"collision_decorative_allowlist": []},
    )
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking collision" in v for v in record["violations"])
    assert any("div.glow" in v for v in record["violations"])
