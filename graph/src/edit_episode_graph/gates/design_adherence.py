"""gate:design_adherence — verifies index.html matches DESIGN.md.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Design Adherence":

  1. Colors — every hex in `index.html` ⊆ DESIGN.md palette.
  2. Typography — every font-family in `index.html` ⊆ DESIGN.md fonts.
  3. Avoidance rules — best-effort grep against bullets under
     "What NOT to Do" / "Don'ts" / "Anti-patterns" sections.

Soft-fail on missing avoidance section per memory `feedback_design_md_opt_outs`:
the section is *not* required by canon, so absent → skip that check, do
not violate. Same for absent typography spec.

Hex / font sources of truth:

  * `state.compose.design.palette[*].hex` — set by p4_design_system.
  * `state.compose.design.typography[*].family` — same node.

If `compose.design` is empty/skipped, the gate degrades to a path-based
read of `state.compose.design.design_md_path` so it still has *something*
to compare against. If that's also missing, it skips quietly (the gate
upstream of this one — `gate:design_ok` — owns DESIGN.md presence).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from ._base import Gate, hyperframes_dir


_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FONT_FAMILY_RE = re.compile(
    r"font-family\s*:\s*([^;}\n\r]+)",
    re.IGNORECASE,
)

# Section headers canon names (SKILL.md §"Design Adherence" item 6).
_AVOIDANCE_HEADERS = (
    "what not to do",
    "don'ts",
    "donts",
    "anti-patterns",
    "antipatterns",
    "do's and don'ts",
    "dos and don'ts",
)

# Negation words that introduce a bullet whose target keyword is what to
# avoid. Order matters — we strip the longest prefix first.
_NEGATION_PREFIXES = ("never ", "avoid ", "don't ", "dont ", "do not ", "no ")

# Minimum length for a normalized avoidance keyword to be checked. Below
# this we get noisy matches on common words like "ai" or "div".
_MIN_AVOID_KEYWORD_LEN = 6


def _normalize_hex(s: str) -> str:
    """Lowercase, expand 3- and 4-digit hex to 6/8-digit form for comparison."""
    s = s.strip().lower()
    if not s.startswith("#"):
        return s
    body = s[1:]
    if len(body) == 3:
        return "#" + "".join(ch * 2 for ch in body)
    if len(body) == 4:
        return "#" + "".join(ch * 2 for ch in body)
    return "#" + body


def _palette_hexes(state: dict) -> set[str]:
    design = (state.get("compose") or {}).get("design") or {}
    palette = design.get("palette") or []
    out: set[str] = set()
    for entry in palette:
        if isinstance(entry, dict):
            hx = entry.get("hex")
            if isinstance(hx, str) and hx.startswith("#"):
                out.add(_normalize_hex(hx))
    return out


def _typography_families(state: dict) -> set[str]:
    design = (state.get("compose") or {}).get("design") or {}
    typography = design.get("typography") or []
    out: set[str] = set()
    for entry in typography:
        if isinstance(entry, dict):
            fam = entry.get("family")
            if isinstance(fam, str) and fam.strip():
                out.add(_normalize_family(fam))
    return out


def _normalize_family(family: str) -> str:
    """Strip quotes/whitespace and lowercase a single CSS font-family token."""
    return family.strip().strip("'\"").strip().lower()


def _split_font_family_value(value: str) -> list[str]:
    """Split a `font-family: A, B, "C D"` value into individual families."""
    parts: list[str] = []
    current = []
    in_quote: str | None = None
    for ch in value:
        if in_quote:
            if ch == in_quote:
                in_quote = None
            else:
                current.append(ch)
        elif ch in ("'", '"'):
            in_quote = ch
        elif ch == ",":
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


# CSS generic font keywords aren't real families and shouldn't be flagged.
_CSS_GENERIC_FAMILIES = frozenset(
    {
        "serif", "sans-serif", "monospace", "cursive", "fantasy",
        "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded",
        "math", "emoji", "fangsong", "inherit", "initial", "unset", "revert",
    }
)


def _extract_html_hexes(html: str) -> set[str]:
    return {_normalize_hex(m.group(0)) for m in _HEX_RE.finditer(html)}


def _extract_html_families(html: str) -> set[str]:
    out: set[str] = set()
    for m in _FONT_FAMILY_RE.finditer(html):
        for fam in _split_font_family_value(m.group(1)):
            norm = _normalize_family(fam)
            if norm and norm not in _CSS_GENERIC_FAMILIES:
                out.add(norm)
    return out


def _design_md_text(state: dict) -> tuple[str | None, Path | None]:
    design = (state.get("compose") or {}).get("design") or {}
    path_str = design.get("design_md_path")
    if not path_str:
        return None, None
    path = Path(path_str)
    if not path.is_file():
        return None, path
    try:
        return path.read_text(encoding="utf-8", errors="replace"), path
    except OSError:
        return None, path


def _avoidance_keywords(design_md: str) -> list[str]:
    """Pull keywords from any section whose header is a canon avoidance label.

    Returns the lowercased noun-phrase part of each negated bullet. Empty
    list when no matching section / no parseable bullets — the gate
    treats that as "skip this check", not "fail".
    """
    if not design_md:
        return []
    lines = design_md.splitlines()
    keywords: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        # Detect markdown headers
        header_match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", stripped)
        if header_match:
            header_text = header_match.group(1).strip().lower().strip(":")
            if any(label in header_text for label in _AVOIDANCE_HEADERS):
                in_section = True
                continue
            # A new header ends the previous avoidance section.
            in_section = False
            continue
        if not in_section:
            continue
        bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
        if not bullet:
            continue
        text = bullet.group(1).strip().lower()
        kw = _strip_negation(text)
        if kw and len(kw) >= _MIN_AVOID_KEYWORD_LEN:
            keywords.append(kw)
    return keywords


def _strip_negation(bullet_text: str) -> str:
    """Strip a leading negation prefix, returning the avoidance noun phrase."""
    text = bullet_text
    for prefix in _NEGATION_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    # Cut at the first em/en-dash or " — " explanation, "(", or "."
    for sep in (" — ", " - ", " – ", "(", ".", ":"):
        idx = text.find(sep)
        if idx > 0:
            text = text[:idx]
            break
    return text.strip()


class DesignAdherenceGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:design_adherence")

    def checks(self, state: dict) -> list[str]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot read index.html"]
        index_path = hf_dir / "index.html"
        if not index_path.is_file():
            return [f"index.html not on disk at {index_path}"]
        try:
            html = index_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return [f"could not read index.html: {exc}"]

        violations: list[str] = []

        # 1. Colors
        palette = _palette_hexes(state)
        html_hexes = _extract_html_hexes(html)
        if palette:
            stray = sorted(h for h in html_hexes if h not in palette)
            if stray:
                violations.append(
                    "hex(es) in index.html not in DESIGN.md palette: "
                    + ", ".join(stray)
                    + f" (palette: {sorted(palette)})"
                )

        # 2. Typography
        families = _typography_families(state)
        html_families = _extract_html_families(html)
        if families and html_families:
            stray = sorted(
                f for f in html_families
                if not any(f == d or f.startswith(d) or d.startswith(f) for d in families)
            )
            if stray:
                violations.append(
                    "font-family value(s) in index.html not in DESIGN.md typography: "
                    + ", ".join(stray)
                    + f" (typography: {sorted(families)})"
                )

        # 3. Avoidance rules — best-effort, soft-fail when section absent.
        design_md, _ = _design_md_text(state)
        if design_md:
            html_lc = html.lower()
            for kw in _avoidance_keywords(design_md):
                if kw in html_lc:
                    violations.append(
                        f"DESIGN.md avoidance rule matched in index.html: {kw!r}"
                    )

        return violations


def design_adherence_gate_node(state: dict) -> dict:
    return DesignAdherenceGate()(state)
