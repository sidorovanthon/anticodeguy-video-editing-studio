"""Unit tests for gate:animation_map.

HOM-317 architecture: vocabulary-allowlist carve-outs retired. Code-side
hard-blocking is restricted to canon-absolute vocabulary-independent
categories — `offscreen` (unconditional, per `SKILL.md:74` "CSS position
is the ground truth"), `degenerate` with bbox ≥ `degenerate_min_bbox_px`
(geometric, not vocab), dead-zones over threshold, infrastructure
failures. `collision` and `invisible` flags route to LLM-triage advisory
via the `gate_animation_map_classify` node — they no longer code-side
block on any selector. The HOM-204 demotion is preserved: classifier
output is advisory-only and never affects routing.

Exercises:
  - successful helper runs always emit `passed=True` for vocabulary-rich
    findings (collision/invisible/paced-*)
  - vocabulary-rich findings land in `pending_classify` for classifier
  - canon-absolute hard-blocking (offscreen unconditional, degenerate≥2px,
    dead-zone>threshold) populates `violations` + `blocking_findings`
  - `advisory_findings` always carries the canonical three-key shape
  - bundled-path resolution, bootstrap-failure triage, infrastructure
    failures unchanged from HOM-212
  - cache version is 11 (HOM-317 bump)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edit_episode_graph.gates import animation_map as gate_mod
from edit_episode_graph.gates.animation_map import animation_map_gate_node


_FIXTURE_SLUG = "anim-map-fixture"


def _hf_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch | None = None) -> Path:
    if monkeypatch is not None:
        monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    hf_dir = tmp_path / "episodes" / _FIXTURE_SLUG / "hyperframes"
    hf_dir.mkdir(parents=True)
    if monkeypatch is not None:
        monkeypatch.setattr(
            "edit_episode_graph.gates.animation_map.materialize_into_tmpdir",
            lambda state, slug=None: hf_dir,
        )
    return hf_dir


def _state(hf_dir: Path) -> dict:
    return {
        "slug": _FIXTURE_SLUG,
        "compose": {"hyperframes_dir": str(hf_dir)},
    }


def _stub_helper(monkeypatch, *, exit_code: int = 0, report: dict | None = None,
                 stderr: str = "", stdout: str = ""):
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


# ── HOM-317: cache version bump ─────────────────────────────────────────────


def test_cache_version_is_11():
    """HOM-317 bumps 10→11: vocabulary-allowlist carve-outs retired
    (caption-canon, scene-container, decorative-allowlist predicates all
    dropped). `collision` + `invisible` flags now route to LLM-triage
    advisory; code-side hard-blocking restricted to canon-absolute
    vocabulary-independent categories (offscreen unconditional, geometric
    degenerate≥2px, dead-zone>threshold). A pre-HOM-317 cached row would
    replay the wrong blocking verdict on LLM-emitted ambient class names
    (`halo`, `ghost`, `wash`, ...) — version bump invalidates those rows.
    Source: CLAUDE.md §"Carve-out allowlists over LLM-emitted identifiers
    are structurally wrong"; retro 2026-05-17 §"Follow-up".
    """
    assert gate_mod._CACHE_VERSION == 11


def test_cache_key_includes_version(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    state = _state(hf_dir)
    before = gate_mod._cache_key(state)
    monkeypatch.setattr(gate_mod, "_CACHE_VERSION", gate_mod._CACHE_VERSION + 1)
    after = gate_mod._cache_key(state)
    assert before != after


# ── HOM-204: successful helper runs always pass for advisory-only findings ──


def test_clean_report_passes_with_empty_advisory_findings(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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
    notice = update["notices"][0]
    assert "advisory" in notice and "no findings" in notice


def test_record_extras_hoist_parsed_animation_map_report(tmp_path, monkeypatch):
    """HOM-282 Class C fold-in: parsed report inlined into extras."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    report = {"duration": 12.0, "tweens": [], "deadZones": []}
    _stub_helper(monkeypatch, report=report)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record.get("animation_map_report") == report


# ── HOM-317: collision routes to LLM-triage advisory on ANY selector ────────


def test_collision_on_any_selector_routes_to_pending_classify(tmp_path, monkeypatch):
    """HOM-317: vocabulary-allowlist retired. `collision` flag on ANY
    selector (content element, decorative, LLM-emitted ambient class)
    routes to `pending_classify` for LLM-triage advisory — never
    code-side hard-blocks.
    """
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Mixed vocabulary: content element, classic decorative,
            # LLM-emitted ambient (halo/ghost/wash/plate-tint — the
            # vocabulary HOM-316 carve-outs failed to cover).
            {"index": 1, "selector": ".headline", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
            {"index": 3, "selector": "div.halo", "duration": 0.6, "flags": ["collision"]},
            {"index": 4, "selector": "div.ghost", "duration": 0.6, "flags": ["collision"]},
            {"index": 5, "selector": "#scene-hook", "duration": 0.6, "flags": ["collision"]},
            {"index": 6, "selector": "span.w", "duration": 0.32, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True, "collision never code-side hard-blocks post-HOM-317"
    assert record["violations"] == []
    assert record["blocking_findings"] == []
    pending = record["advisory_findings"]["pending_classify"]
    assert len(pending) == 6
    selectors = sorted(p["selector"] for p in pending)
    assert selectors == sorted([
        ".headline", "div.glow", "div.halo", "div.ghost", "#scene-hook", "span.w",
    ])
    for entry in pending:
        assert entry["flag"] == "collision"


def test_invisible_on_any_selector_routes_to_pending_classify(tmp_path, monkeypatch):
    """HOM-317: `invisible` flag on ANY selector routes to LLM-triage
    advisory (`pending_classify`). Captions canon's opacity-0 hidden state,
    ambient atmosphere layers fading in/out, and content elements with
    opacity-driven transitions all produce by-construction invisible
    flags — disposition depends on canonical authoring pattern context,
    not on selector name.
    """
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "#cg-3", "duration": 0.32, "flags": ["invisible"]},
            {"index": 2, "selector": "span.w", "duration": 0.32, "flags": ["invisible"]},
            {"index": 3, "selector": ".headline", "duration": 0.6, "flags": ["invisible"]},
            {"index": 4, "selector": "div.wash", "duration": 0.6, "flags": ["invisible"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["violations"] == []
    assert record["blocking_findings"] == []
    pending = record["advisory_findings"]["pending_classify"]
    assert len(pending) == 4
    for entry in pending:
        assert entry["flag"] == "invisible"


def test_collision_and_invisible_coexist_in_pending_classify(tmp_path, monkeypatch):
    """A tween with both `collision` and `invisible` produces two
    `pending_classify` entries (one per flag) — the classifier triages
    each independently."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "#cg-7", "duration": 0.32,
             "flags": ["collision", "invisible"]},
        ],
        "deadZones": [],
    })
    pending = animation_map_gate_node(_state(hf_dir))["gate_results"][0][
        "advisory_findings"
    ]["pending_classify"]
    flags = sorted(p["flag"] for p in pending)
    assert flags == ["collision", "invisible"]


# ── Pace flags route to pending_classify (HOM-204 behaviour preserved) ──────


def test_paced_fast_records_pending_classify(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".flash", "duration": 0.12, "flags": ["paced-fast"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    pending = record["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["flag"] == "paced-fast"
    assert pending[0]["selector"] == ".flash"
    assert pending[0]["flag_id"] == ".flash::1::paced-fast"


def test_paced_slow_records_pending_classify(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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


# ── Dead-zone advisory (>1s) vs blocking (>threshold) ───────────────────────


def test_dead_zone_over_one_second_is_advisory(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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


# ── Path resolution: bundled preferred over global fallback ──────────────────


def test_resolves_bundled_helper_in_preference_to_global(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    fake_global = tmp_path / "fake-global-helper.mjs"
    fake_global.write_text("// stub", encoding="utf-8")
    monkeypatch.setattr(gate_mod, "_GLOBAL_FALLBACK", fake_global)

    helper, used_fallback = gate_mod._resolve_helper(hf_dir)
    assert helper == fake_global
    assert used_fallback is True


def test_fallback_use_emits_notice(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs", used_fallback=True)
    _stub_helper(monkeypatch, report={"tweens": [], "deadZones": []})
    update = animation_map_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"] is True
    assert record["fallback_helper_used"] is True
    assert any("global fallback helper" in n for n in update.get("notices", []))


# ── Infrastructure failures keep passed=False ────────────────────────────────


def test_bootstrap_failure_emits_actionable_npm_i_command(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Could not resolve required package(s): @hyperframes/producer\n"
        "  npm install --save-dev @hyperframes/producer@0.4.45 sharp@0.33.0\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    joined = " ".join(record["violations"])
    assert "npm i -D" in joined
    assert "@hyperframes/producer@0.4.45" in joined
    assert "sharp@0.33.0" in joined
    assert record["advisory_findings"] == {
        "always_fix": [], "dead_zones": [], "pending_classify": []
    }


def test_bootstrap_failure_global_fallback_no_version_pin(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(gate_mod, "_GLOBAL_FALLBACK", tmp_path / "definitely-not-there.mjs")
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("animation-map.mjs not found" in v for v in record["violations"])


def test_runtime_filenotfound_records_failure_does_not_raise(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, exit_code=0, report=None)
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("not found" in v for v in record["violations"])


# ── HOM-205: canonical advisory notice format ────────────────────────────────


def test_clean_run_notice_matches_canonical_format(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={"tweens": [], "deadZones": []})
    update = animation_map_gate_node(_state(hf_dir))
    assert update["notices"] == [
        "gate:animation_map: advisory — no findings (helper ran clean)"
    ]


def test_mixed_findings_notice_matches_canonical_format(tmp_path, monkeypatch):
    """HOM-317: collision+invisible+paced all route to pending_classify;
    only degenerate at 1px stays advisory-only; dead-zone within threshold."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Collision flags route to pending_classify (LLM-triage advisory).
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
            {"index": 2, "selector": "div.grain", "duration": 0.6, "flags": ["collision"]},
            # 1px hairline degenerate carved out (geometric, max h = 1 < 2).
            {"index": 3, "selector": "div.hairline", "duration": 0.4, "flags": ["degenerate"],
             "bboxes": [{"t": 0.0, "x": 0, "y": 0, "w": 100, "h": 1}]},
            # Paced-fast routes to pending_classify.
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
    # collision + degenerate both surface under always_fix for visibility.
    assert any("collision" in s for s in advisory["always_fix"])
    assert any("degenerate" in s for s in advisory["always_fix"])
    assert len(advisory["dead_zones"]) == 1
    # 2 collisions + 1 paced-fast = 3 pending_classify entries.
    assert len(advisory["pending_classify"]) == 3
    notice = update["notices"][0]
    assert notice.startswith("gate:animation_map: advisory — ")
    assert "always_fix: 2" in notice
    assert "dead_zones: 1" in notice
    assert "pending_classify: 3" in notice


def test_fallback_helper_notice_appends_pin_deps_hint(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs", used_fallback=True)
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.grain", "duration": 0.6, "flags": ["collision"]}],
        "deadZones": [],
    })
    notice = animation_map_gate_node(_state(hf_dir))["notices"][0]
    assert notice.startswith("gate:animation_map: advisory — ")
    assert (
        "(via global fallback helper — consider pinning "
        "@hyperframes/producer + sharp in the HF project)"
    ) in notice


def test_infrastructure_failure_notice_uses_strong_wording(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    stderr = (
        "Could not resolve required package(s): @hyperframes/producer\n"
        "  npm install --save-dev @hyperframes/producer@0.4.45 sharp@0.33.0\n"
    )
    _stub_helper(monkeypatch, exit_code=1, stderr=stderr)
    notice = animation_map_gate_node(_state(hf_dir))["notices"][0]
    assert notice.startswith("gate:animation_map: infrastructure failure (")
    assert "issue(s))" in notice
    assert "see gate_results" in notice
    assert "advisory" not in notice


# ── HOM-317: code-side hard-blocking — canon-absolute categories only ───────


def test_dead_zone_over_threshold_is_blocking(tmp_path, monkeypatch):
    """Dead-zone duration > config threshold (default 2.0s) → blocking with
    the threshold value cited in the violation."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.grain", "duration": 0.6, "flags": []}],
        "deadZones": [
            {"start": 22.5, "end": 26.5, "duration": 4.0, "note": "mid-comp gap"},
        ],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking dead zone" in v for v in record["violations"])
    assert any("4.0" in v and "2.0" in v for v in record["violations"])


def test_pending_classify_only_stays_advisory_no_redispatch(tmp_path, monkeypatch):
    """pending_classify-only run advances to classifier, never redispatches."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
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


def test_degenerate_on_1px_hairline_stays_advisory(tmp_path, monkeypatch):
    """1-px hairline → degenerate flag carved out geometrically (bbox h=1 < 2px).
    Vocabulary-independent — class name doesn't matter; only bbox dimensions.
    """
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": "div.kw-rule", "duration": 0.6,
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
    blocking — geometric threshold, vocabulary-independent."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
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
    """No FP class for offscreen — element off-canvas the entire tween means
    audience never sees it. Per `SKILL.md:74` "CSS position is the ground
    truth"; selector identity is irrelevant. Blocking always."""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # Even a previously-decorative-named selector — offscreen has
            # no carve-out post-HOM-317 (and never did pre-HOM-317).
            {"index": 1, "selector": "div.grain", "duration": 0.6,
             "flags": ["offscreen"]},
        ],
        "deadZones": [],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("blocking offscreen" in v for v in record["violations"])


def test_blocking_notice_lists_offending_categories(tmp_path, monkeypatch):
    """Notice format on blocking: `gate:animation_map: BLOCKING — N
    finding(s) require fix. <cat strs>. See <path>.`"""
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            {"index": 1, "selector": ".off-bar", "duration": 0.6, "flags": ["offscreen"]},
            {"index": 2, "selector": ".content-card", "duration": 0.6,
             "flags": ["degenerate"],
             "bboxes": [{"t": 0.0, "x": 0, "y": 0, "w": 100, "h": 50}]},
        ],
        "deadZones": [],
    })
    update = animation_map_gate_node(_state(hf_dir))
    notice = update["notices"][0]
    assert notice.startswith("gate:animation_map: BLOCKING — ")
    assert "blocking offscreen" in notice
    assert "blocking degenerate" in notice
    assert "See " in notice and ".hyperframes" in notice


def test_dead_zone_threshold_is_strict_greater_than(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.glow", "duration": 0.6, "flags": []}],
        "deadZones": [
            {"start": 5.0, "end": 7.0, "duration": 2.0, "note": "right at threshold"},
        ],
    })
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["blocking_findings"] == []


def test_dead_zone_threshold_overridable_via_config(tmp_path, monkeypatch):
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [{"index": 1, "selector": "div.glow", "duration": 0.6, "flags": []}],
        "deadZones": [
            {"start": 5.0, "end": 6.5, "duration": 1.5, "note": "1.5s hold"},
        ],
    })
    monkeypatch.setattr(
        gate_mod, "_gate_config",
        lambda: {"dead_zone_threshold_s": 1.0},
    )
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is False
    assert any("1.0" in v and "1.5" in v for v in record["violations"])


def test_legacy_decorative_allowlist_config_is_silently_ignored(tmp_path, monkeypatch):
    """HOM-317: the `collision_decorative_allowlist` config key is retired.
    Legacy config entries are silently ignored — the gate does not crash on
    their presence, and collision still routes to LLM-triage advisory
    regardless of any allowlist contents.
    """
    hf_dir = _hf_dir(tmp_path, monkeypatch)
    _stub_resolver(monkeypatch, tmp_path / "fake-helper.mjs")
    _stub_helper(monkeypatch, report={
        "tweens": [
            # `div.glow` was previously in the default allowlist; verify
            # collision still routes to pending_classify regardless.
            {"index": 1, "selector": "div.glow", "duration": 0.6, "flags": ["collision"]},
        ],
        "deadZones": [],
    })
    # Legacy config — gate must not crash, must ignore.
    monkeypatch.setattr(
        gate_mod, "_gate_config",
        lambda: {"collision_decorative_allowlist": ["grain", "glow"]},
    )
    record = animation_map_gate_node(_state(hf_dir))["gate_results"][0]
    assert record["passed"] is True
    assert record["blocking_findings"] == []
    assert len(record["advisory_findings"]["pending_classify"]) == 1


# ── Routing: HOM-317 behaviour ──────────────────────────────────────────────


def test_route_after_animation_map_blocking_offscreen_redispatches():
    """HOM-317 routing: offscreen (beat-actionable) at iter<3 routes to
    p4_redispatch_beat. Collision/invisible no longer code-side block, so
    those never reach the redispatch path."""
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": False,
            "violations": ["blocking offscreen flag(s) on .off-bar — element off-canvas (HOM-317)"],
            "blocking_findings": ["blocking offscreen flag(s) on .off-bar — element off-canvas (HOM-317)"],
            "advisory_findings": {"always_fix": [], "dead_zones": [], "pending_classify": []},
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "p4_redispatch_beat"


def test_route_after_animation_map_blocking_degenerate_redispatches():
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": False,
            "violations": ["blocking degenerate flag(s) on .content-card — bbox ≥ 2px"],
            "blocking_findings": ["blocking degenerate flag(s) on .content-card — bbox ≥ 2px"],
            "advisory_findings": {"always_fix": [], "dead_zones": [], "pending_classify": []},
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "p4_redispatch_beat"


def test_route_after_animation_map_blocking_dead_zone_only_halts():
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
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": False,
            "violations": ["blocking offscreen flag(s) on .off-bar"],
            "blocking_findings": ["blocking offscreen flag(s) on .off-bar"],
            "advisory_findings": {"always_fix": [], "dead_zones": [], "pending_classify": []},
            "iteration": 3,
        }],
    }
    assert route_after_animation_map(state) == "halt_llm_boundary"


def test_route_after_animation_map_advisory_advances():
    from edit_episode_graph.nodes._routing import route_after_animation_map
    state = {
        "gate_results": [{
            "gate": "gate:animation_map",
            "passed": True,
            "violations": [],
            "blocking_findings": [],
            "advisory_findings": {
                "always_fix": ["collision flag(s) on div.glow — LLM-triage advisory"],
                "dead_zones": [],
                "pending_classify": [],
            },
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "gate_snapshot"


def test_route_after_animation_map_pending_classify_routes_to_classifier():
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
                    {"flag_id": "div.halo::1::collision", "selector": "div.halo",
                     "flag": "collision", "duration": 0.6, "index": 1},
                ],
            },
            "iteration": 1,
        }],
    }
    assert route_after_animation_map(state) == "gate_animation_map_classify"


# ── HOM-317: dropped predicates no longer exist ─────────────────────────────


def test_vocabulary_carveout_predicates_dropped():
    """HOM-317: `_is_caption_canon`, `_is_scene_container`, `_is_decorative`,
    `_collision_is_blocking`, `_DEFAULT_DECORATIVE_ALLOWLIST`,
    `_CG_SELECTOR_RE`, `_SCENE_CONTAINER_RE`, `_CAPTION_WORD_SPAN_RE` are
    retired. The architectural rule (CLAUDE.md §"Carve-out allowlists over
    LLM-emitted identifiers are structurally wrong") rejects vocabulary
    carve-outs; this test pins their absence so a re-introduction is
    caught at import time.
    """
    for name in (
        "_is_caption_canon",
        "_is_scene_container",
        "_is_decorative",
        "_collision_is_blocking",
        "_DEFAULT_DECORATIVE_ALLOWLIST",
        "_CG_SELECTOR_RE",
        "_SCENE_CONTAINER_RE",
        "_CAPTION_WORD_SPAN_RE",
    ):
        assert not hasattr(gate_mod, name), (
            f"{name} is a retired vocabulary carve-out (HOM-317); "
            "re-introduction violates CLAUDE.md §\"Carve-out allowlists "
            "over LLM-emitted identifiers are structurally wrong\""
        )


def test_degenerate_geometric_carveout_preserved():
    """HOM-317: `_degenerate_is_blocking` + `_max_bbox_dim` are GEOMETRIC,
    vocabulary-independent — they survive the carve-out retirement."""
    assert hasattr(gate_mod, "_degenerate_is_blocking")
    assert hasattr(gate_mod, "_max_bbox_dim")
    assert gate_mod._DEFAULT_DEGENERATE_MIN_BBOX_PX == 2.0
