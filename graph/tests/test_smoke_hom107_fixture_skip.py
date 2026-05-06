"""Unit test for HOM-116f — `_fixture_skip` honors `HOM107_SMOKE_REQUIRE_FIXTURE=1`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

GRAPH_DIR = Path(__file__).resolve().parents[1]
SMOKE_PATH = GRAPH_DIR / "smoke_hom107.py"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("smoke_hom107", SMOKE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["smoke_hom107"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_fixture_skip_returns_0_by_default(monkeypatch, capsys):
    monkeypatch.delenv("HOM107_SMOKE_REQUIRE_FIXTURE", raising=False)
    smoke = _load_smoke()
    rc = smoke._fixture_skip("fixture absent")
    assert rc == 0
    out = capsys.readouterr().out
    assert "SMOKE SKIP" in out
    assert "fixture absent" in out


def test_fixture_skip_hard_fails_when_required(monkeypatch, capsys):
    monkeypatch.setenv("HOM107_SMOKE_REQUIRE_FIXTURE", "1")
    smoke = _load_smoke()
    rc = smoke._fixture_skip("fixture absent")
    assert rc == 1
    err = capsys.readouterr().err
    assert "SMOKE FAIL" in err
    assert "HOM107_SMOKE_REQUIRE_FIXTURE=1" in err


def test_fixture_skip_other_values_still_skip(monkeypatch, capsys):
    monkeypatch.setenv("HOM107_SMOKE_REQUIRE_FIXTURE", "true")  # only "1" enables
    smoke = _load_smoke()
    rc = smoke._fixture_skip("x")
    assert rc == 0
