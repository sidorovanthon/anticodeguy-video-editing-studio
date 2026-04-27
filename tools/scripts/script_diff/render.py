"""Emit script-diff.json and script-diff.md from alignment results."""
from __future__ import annotations

import json
from pathlib import Path

from .align import DiffResult, Span
from .retake import Retake


def _span_in_raw_text(span_text: str, raw_text_joined: str) -> bool:
    """Cheap check: is this dropped script span literally present in raw transcript?"""
    return span_text in raw_text_joined


def _ad_lib_range(span: Span) -> tuple[float, float] | None:
    if not span.tokens:
        return None
    s = span.tokens[0].start
    e = span.tokens[-1].end
    if s is None or e is None:
        return None
    return (s, e)


def build_payload(d1: DiffResult, d2: DiffResult, retakes: list[Retake]) -> dict:
    """d1 = script vs final, d2 = script vs raw."""
    script_total = len(d1.script_tokens)
    final_total = len(d1.target_tokens)
    coverage_pct = (d1.matched_script_count / script_total * 100.0) if script_total else 0.0

    raw_text_joined = " ".join(t.text for t in d2.target_tokens)

    dropped_spans = []
    for span in d1.dropped:
        in_raw = _span_in_raw_text(span.text, raw_text_joined)
        # raw_ranges left empty here — span-level raw-range lookup would require
        # another pass; the in_raw flag is the actionable signal.
        dropped_spans.append({
            "text": span.text,
            "in_raw": in_raw,
            "raw_ranges": [],
        })

    ad_libs = []
    for span in d1.inserted:
        rng = _ad_lib_range(span)
        ad_libs.append({
            "text": span.text,
            "raw_range": list(rng) if rng else None,
        })

    retakes_json = []
    for r in retakes:
        retakes_json.append({
            "text": r.text,
            "raw_ranges": [list(rg) for rg in r.raw_ranges],
            "kept_range": list(r.kept_range) if r.kept_range else None,
        })

    return {
        "script_words_total": script_total,
        "final_words_total": final_total,
        "script_coverage_pct": round(coverage_pct, 1),
        "dropped_spans": dropped_spans,
        "ad_libs": ad_libs,
        "retakes": retakes_json,
    }


def render_md(payload: dict, alignment_preview: str) -> str:
    p = payload
    lines: list[str] = []
    lines.append("# Script fidelity report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Script words: {p['script_words_total']}")
    lines.append(f"- Final words: {p['final_words_total']}")
    lines.append(f"- Script coverage: {p['script_coverage_pct']}%")
    lines.append(f"- Dropped script spans: {len(p['dropped_spans'])}")
    lines.append(f"- Ad-libs in final: {len(p['ad_libs'])}")
    lines.append(f"- Retakes detected: {len(p['retakes'])}")
    lines.append("")

    lines.append("## Dropped from script")
    if not p["dropped_spans"]:
        lines.append("_None._")
    else:
        for d in p["dropped_spans"]:
            origin = "agent-cut (present in raw)" if d["in_raw"] else "host-skipped (not in raw)"
            lines.append(f"- [{origin}] {d['text']}")
    lines.append("")

    lines.append("## Ad-libs in final")
    if not p["ad_libs"]:
        lines.append("_None._")
    else:
        for a in p["ad_libs"]:
            rng = a["raw_range"]
            tag = f"[{rng[0]:.2f}–{rng[1]:.2f}s] " if rng else ""
            lines.append(f"- {tag}{a['text']}")
    lines.append("")

    lines.append("## Retakes detected")
    if not p["retakes"]:
        lines.append("_None._")
    else:
        for r in p["retakes"]:
            ranges_s = ", ".join(f"{a:.2f}–{b:.2f}s" for a, b in r["raw_ranges"])
            kept = r["kept_range"]
            kept_s = f"{kept[0]:.2f}–{kept[1]:.2f}s" if kept else "none survived"
            lines.append(f"- _{r['text']}_ — takes at {ranges_s}; kept: {kept_s}")
    lines.append("")

    lines.append("## Word alignment (script ↔ final)")
    lines.append("```diff")
    lines.append(alignment_preview if alignment_preview else "(empty)")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def build_alignment_preview(d1: DiffResult, max_lines: int = 200) -> str:
    """Unified-diff-style preview, ≤ max_lines."""
    s = [t.text for t in d1.script_tokens]
    f = [t.text for t in d1.target_tokens]
    from difflib import SequenceMatcher
    sm = SequenceMatcher(a=s, b=f, autojunk=False)
    out: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for w in s[i1:i2]:
                out.append(f"  {w}")
        elif tag == "delete":
            for w in s[i1:i2]:
                out.append(f"- {w}")
        elif tag == "insert":
            for w in f[j1:j2]:
                out.append(f"+ {w}")
        elif tag == "replace":
            for w in s[i1:i2]:
                out.append(f"- {w}")
            for w in f[j1:j2]:
                out.append(f"+ {w}")
        if len(out) >= max_lines:
            out.append(f"... (truncated at {max_lines} lines)")
            break
    return "\n".join(out)


def write_outputs(out_dir: Path, payload: dict, md_text: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "script-diff.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "script-diff.md").write_text(md_text, encoding="utf-8")
