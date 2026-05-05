"""Unit tests for gate:design_adherence."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.gates.design_adherence import (
    DesignAdherenceGate,
    _avoidance_keywords,
    _extract_html_families,
    _extract_html_hexes,
    _normalize_hex,
    design_adherence_gate_node,
)


def _hf_with(tmp_path: Path, html: str) -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    (hf_dir / "index.html").write_text(html, encoding="utf-8")
    return hf_dir


def _state(hf_dir: Path, palette=None, typography=None, design_md_path=None) -> dict:
    design: dict = {}
    if palette is not None:
        design["palette"] = palette
    if typography is not None:
        design["typography"] = typography
    if design_md_path is not None:
        design["design_md_path"] = str(design_md_path)
    return {"compose": {"hyperframes_dir": str(hf_dir), "design": design}}


def test_passes_when_only_palette_hexes_used(tmp_path: Path):
    hf_dir = _hf_with(
        tmp_path,
        '<html><body style="background:#0a0a0a;color:#f0f0f0">'
        '<h1 style="color:#0066ff">x</h1></body></html>',
    )
    palette = [
        {"role": "background", "hex": "#0a0a0a"},
        {"role": "foreground", "hex": "#f0f0f0"},
        {"role": "accent", "hex": "#0066FF"},
    ]
    update = design_adherence_gate_node(_state(hf_dir, palette=palette))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]


def test_fails_when_html_uses_hex_outside_palette(tmp_path: Path):
    hf_dir = _hf_with(
        tmp_path,
        '<html><body><h1 style="color:#ff00aa">x</h1></body></html>',
    )
    palette = [
        {"role": "background", "hex": "#0a0a0a"},
        {"role": "foreground", "hex": "#f0f0f0"},
        {"role": "accent", "hex": "#0066FF"},
    ]
    update = design_adherence_gate_node(_state(hf_dir, palette=palette))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("#ff00aa" in v for v in record["violations"])


def test_passes_when_typography_matches(tmp_path: Path):
    hf_dir = _hf_with(
        tmp_path,
        "<html><body>"
        "<style>h1 { font-family: 'Helvetica Neue', sans-serif; }</style>"
        "<h1>x</h1>"
        "</body></html>",
    )
    typography = [
        {"role": "headline", "family": "Helvetica Neue"},
        {"role": "body", "family": "Inter"},
    ]
    update = design_adherence_gate_node(_state(hf_dir, typography=typography))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]


def test_fails_when_html_uses_font_outside_typography(tmp_path: Path):
    hf_dir = _hf_with(
        tmp_path,
        "<html><body>"
        "<style>h1 { font-family: 'Comic Sans MS', cursive; }</style>"
        "</body></html>",
    )
    typography = [{"role": "headline", "family": "Helvetica Neue"}]
    update = design_adherence_gate_node(_state(hf_dir, typography=typography))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("comic sans" in v.lower() for v in record["violations"])


def test_avoidance_rule_violation_from_design_md(tmp_path: Path):
    design_md = tmp_path / "DESIGN.md"
    design_md.write_text(
        "# Design\n\n## Palette\n- bg #000\n\n"
        "## What NOT to Do\n"
        "- No gradient text — looks like every AI landing page\n"
        "- Avoid cyan-on-dark gradients\n",
        encoding="utf-8",
    )
    hf_dir = _hf_with(
        tmp_path,
        "<html><body>"
        "<style>.hero { background-image: linear-gradient(...); color: transparent; "
        "/* gradient text */ }</style>"
        "<h1 class='hero'>X</h1></body></html>",
    )
    update = design_adherence_gate_node(
        _state(hf_dir, palette=[{"role": "x", "hex": "#000"}], design_md_path=design_md)
    )
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("gradient text" in v for v in record["violations"])


def test_no_avoidance_section_is_soft_fail(tmp_path: Path):
    """DESIGN.md without an avoidance section must NOT block the gate."""
    design_md = tmp_path / "DESIGN.md"
    design_md.write_text("# Design\n\n## Palette\n- bg #000\n", encoding="utf-8")
    hf_dir = _hf_with(
        tmp_path,
        "<html><body><h1 style='color:#000'>x</h1></body></html>",
    )
    update = design_adherence_gate_node(
        _state(hf_dir, palette=[{"role": "x", "hex": "#000"}], design_md_path=design_md)
    )
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]


def test_passes_with_no_design_state_at_all(tmp_path: Path):
    """If `compose.design` is empty (gate ran out of order), don't fabricate
    violations — let `gate:design_ok` upstream catch the absence."""
    hf_dir = _hf_with(tmp_path, "<html><body></body></html>")
    update = design_adherence_gate_node(_state(hf_dir))
    assert update["gate_results"][0]["passed"]


def test_missing_index_html_fails(tmp_path: Path):
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    update = design_adherence_gate_node(_state(hf_dir, palette=[{"hex": "#000"}]))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("index.html not on disk" in v for v in record["violations"])


def test_short_hex_normalizes_against_palette(tmp_path: Path):
    """`#fff` in HTML must compare equal to `#ffffff` in palette."""
    hf_dir = _hf_with(
        tmp_path, "<html><body style='color:#fff'></body></html>"
    )
    palette = [{"role": "fg", "hex": "#FFFFFF"}]
    update = design_adherence_gate_node(_state(hf_dir, palette=palette))
    assert update["gate_results"][0]["passed"]


def test_html_family_shorter_than_design_family_is_flagged(tmp_path: Path):
    """If DESIGN.md specifies "Inter Tight" and the HTML uses bare "Inter",
    those are different fonts — must NOT be silently allowed by prefix
    matching."""
    hf_dir = _hf_with(
        tmp_path,
        "<html><body><style>h1 { font-family: 'Inter'; }</style></body></html>",
    )
    typography = [{"role": "headline", "family": "Inter Tight"}]
    update = design_adherence_gate_node(_state(hf_dir, typography=typography))
    record = update["gate_results"][0]
    assert not record["passed"]


def test_html_family_longer_variant_of_design_family_passes(tmp_path: Path):
    """The reverse direction is fine: DESIGN.md says "Helvetica Neue", HTML
    uses "Helvetica Neue Italic" — that's just a style of the declared
    family, not a different typeface."""
    hf_dir = _hf_with(
        tmp_path,
        "<html><body><style>h1 { font-family: 'Helvetica Neue Italic'; }</style></body></html>",
    )
    typography = [{"role": "headline", "family": "Helvetica Neue"}]
    update = design_adherence_gate_node(_state(hf_dir, typography=typography))
    assert update["gate_results"][0]["passed"]


def test_generic_css_keywords_ignored(tmp_path: Path):
    """`sans-serif`, `monospace` etc. are CSS generics, not real families."""
    hf_dir = _hf_with(
        tmp_path,
        "<html><body><style>body { font-family: sans-serif; }</style></body></html>",
    )
    typography = [{"role": "body", "family": "Inter"}]
    update = design_adherence_gate_node(_state(hf_dir, typography=typography))
    assert update["gate_results"][0]["passed"]


# --- Helper tests ---


def test_normalize_hex_expands_short_form():
    assert _normalize_hex("#fff") == "#ffffff"
    assert _normalize_hex("#0A0A0A") == "#0a0a0a"
    assert _normalize_hex("#abcd") == "#aabbccdd"


def test_extract_html_hexes():
    html = "color:#fff; bg:#0066FF; rgba(...); color:#abcdef;"
    out = _extract_html_hexes(html)
    assert "#ffffff" in out
    assert "#0066ff" in out
    assert "#abcdef" in out


def test_extract_html_families_splits_stack():
    html = "font-family: 'Helvetica Neue', Arial, sans-serif;"
    out = _extract_html_families(html)
    assert "helvetica neue" in out
    assert "arial" in out
    assert "sans-serif" not in out  # generic stripped


def test_avoidance_keywords_picks_only_negated_bullets_in_section():
    md = (
        "# Design\n\n"
        "## What NOT to Do\n"
        "- No gradient text — neon AI default\n"
        "- Avoid cyan-on-dark\n"
        "- Use real grids\n"  # not negated → keep as-is, also kept (best-effort)
        "\n## Palette\n"
        "- Don't pick neon — wrong section, must NOT pick this up\n"
    )
    kws = _avoidance_keywords(md)
    assert any("gradient text" in k for k in kws)
    assert any("cyan-on-dark" in k for k in kws)
    # The "## Palette" bullet should be ignored — wrong section.
    assert not any("neon" == k for k in kws)
