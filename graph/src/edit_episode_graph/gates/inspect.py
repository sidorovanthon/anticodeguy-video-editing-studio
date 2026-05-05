"""gate:inspect — runs `hyperframes inspect --at <beat_ts> --json`.

Per canon `~/.claude/skills/hyperframes/SKILL.md` §"Quality Checks /
Visual Inspect": runs the composition in headless Chrome, seeks through
the timeline, and reports text-overflow / clipping / off-canvas issues.

This gate passes when:

  1. CLI exits zero with no overflow issues, OR
  2. Every reported overflow target is inside an element (or ancestor)
     marked `data-layout-allow-overflow` / `data-layout-ignore` —
     the canonical opt-out per the SKILL.md paragraph and memory
     `feedback_text_box_overflow_glyph_bearing` (2-3px glyph-bearing
     overflows on heavy display fonts are expected; the marker is the
     authored intent signal).

Beat timestamps for `--at` are derived from the cumulative start of each
beat in `state.compose.plan.beats[]` (canonical FS-truth source per
`p4_assemble_index` notes; `compose.beats` is deprecated). We pass beat
*start* offsets — `inspect` interpolates between samples, so hitting one
frame inside each beat is enough to catch per-beat layout issues.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence

from ._base import Gate, hyperframes_dir, parse_cli_json, run_hf_cli


_OPT_OUT_ATTRS = ("data-layout-allow-overflow", "data-layout-ignore")

# Tags that don't take a closing tag in HTML5. We don't push them onto
# the open-element stack, so they don't carry scope.
_VOID_TAGS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
)


def _beat_start_offsets(state: dict) -> list[float]:
    """Return cumulative start offsets for each beat in the plan.

    `compose.plan.beats[*].duration_s` is the canonical source per
    `p4_assemble_index`. Returns offsets for beat *starts* (so beat 0 is
    at 0.0). Empty list if no plan / no beats.
    """
    plan = ((state.get("compose") or {}).get("plan") or {})
    beats = plan.get("beats") or []
    offsets: list[float] = []
    cursor = 0.0
    for beat in beats:
        offsets.append(round(cursor, 3))
        try:
            duration = float(beat.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        cursor += duration
    return offsets


def _format_at_arg(offsets: Sequence[float]) -> str:
    """`--at` takes a comma-separated list of seconds. Strip 0.0 if it's
    the only entry (CLI default samples cover t=0 already), but keep it
    when there are subsequent timestamps so per-beat boundaries are hit."""
    return ",".join(f"{t:g}" for t in offsets)


def _leaf_token(selector: str) -> str | None:
    """Reduce a CSS selector to its rightmost simple-selector token.

    `.scene-1 .headline` → `.headline`
    `body > div > #card.big` → `#card`
    `div.stat` → `.stat`
    `h1` → `h1`

    Returns lowercase tag name or `#id`/`.class` token. None for selectors
    we can't parse (caller treats unknown leaves as not-opted-out).
    """
    if not selector:
        return None
    last = re.split(r"[\s>+~]", selector.strip())[-1]
    if not last:
        return None
    m = re.search(r"#([\w-]+)", last)
    if m:
        return f"#{m.group(1)}"
    m = re.search(r"\.([\w-]+)", last)
    if m:
        return f".{m.group(1)}"
    m = re.match(r"([a-zA-Z][\w-]*)", last)
    if m:
        return m.group(1).lower()
    return None


class _OptOutScanner(HTMLParser):
    """Walk index.html tracking which leaf tokens appear inside a marker scope.

    A "marker scope" is the subtree rooted at an element carrying
    `data-layout-allow-overflow` or `data-layout-ignore`. A leaf token
    (`#id` / `.class` / tag) is considered opted-out the first time we
    see an element matching it AND either (a) the element itself has
    a marker or (b) any open ancestor has one.
    """

    def __init__(self, leaf_tokens: Iterable[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.leaf_tokens = list(dict.fromkeys(leaf_tokens))
        self._stack: list[tuple[str, bool]] = []
        self.found: dict[str, bool] = {tok: False for tok in self.leaf_tokens}

    def _check_match(self, tag: str, attr_dict: dict[str, str], element_marked: bool) -> None:
        in_scope = element_marked or any(marker for _, marker in self._stack)
        if not in_scope:
            return
        classes = (attr_dict.get("class") or "").split()
        elem_id = attr_dict.get("id") or ""
        for tok in self.leaf_tokens:
            if self.found[tok]:
                continue
            if tok.startswith("."):
                if tok[1:] in classes:
                    self.found[tok] = True
            elif tok.startswith("#"):
                if tok[1:] == elem_id:
                    self.found[tok] = True
            else:
                if tok == tag.lower():
                    self.found[tok] = True

    def _attrs_to_dict(self, attrs):
        out: dict[str, str] = {}
        for k, v in attrs:
            out[k.lower()] = v if v is not None else ""
        return out

    def handle_starttag(self, tag, attrs):
        attr_dict = self._attrs_to_dict(attrs)
        marked = any(a in attr_dict for a in _OPT_OUT_ATTRS)
        self._check_match(tag, attr_dict, marked)
        if tag.lower() not in _VOID_TAGS:
            self._stack.append((tag.lower(), marked))

    def handle_startendtag(self, tag, attrs):
        attr_dict = self._attrs_to_dict(attrs)
        marked = any(a in attr_dict for a in _OPT_OUT_ATTRS)
        self._check_match(tag, attr_dict, marked)
        # No push for self-closing.

    def handle_endtag(self, tag):
        tag_l = tag.lower()
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag_l:
                del self._stack[i:]
                return


def _opted_out_tokens(html: str, leaf_tokens: Iterable[str]) -> set[str]:
    scanner = _OptOutScanner(leaf_tokens)
    try:
        scanner.feed(html)
        scanner.close()
    except Exception:  # noqa: BLE001 — malformed HTML must not crash the gate
        pass
    return {tok for tok, found in scanner.found.items() if found}


def _extract_overflows(payload: object) -> list[dict]:
    """Pull overflow issues out of an inspect-JSON payload.

    The CLI shape isn't pinned in canon — it's documented descriptively
    ("issues with timestamps, selectors, bounding boxes, fix hints"). We
    accept either a top-level `issues`/`overflows` list, or a list at the
    root, and filter to entries whose `type` (or absence thereof) reads
    as overflow-related.
    """
    if isinstance(payload, dict):
        candidates = payload.get("issues") or payload.get("overflows") or []
    elif isinstance(payload, list):
        candidates = payload
    else:
        return []
    overflows: list[dict] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        kind = (entry.get("type") or entry.get("kind") or "").lower()
        # If `type` is absent, treat the entry as an overflow — `inspect`
        # only reports layout failures, so a typeless issue still counts.
        if not kind or "overflow" in kind or "clip" in kind or "off-canvas" in kind:
            overflows.append(entry)
    return overflows


class InspectGate(Gate):
    def __init__(self) -> None:
        super().__init__(name="gate:inspect")

    def checks(self, state: dict) -> list[str]:
        hf_dir = hyperframes_dir(state)
        if hf_dir is None:
            return ["no hyperframes_dir / episode_dir in state — cannot run inspect"]
        if not hf_dir.is_dir():
            return [f"hyperframes dir not on disk: {hf_dir}"]

        args = ["inspect", "--json"]
        offsets = _beat_start_offsets(state)
        if offsets:
            args.extend(["--at", _format_at_arg(offsets)])

        result = run_hf_cli(args, hf_dir)
        payload, parse_err = parse_cli_json(result)

        if not result.ok and payload is None:
            body = (result.stderr or result.stdout or parse_err or "(no output)").strip()
            if len(body) > 1500:
                body = body[:1500] + "\n…(truncated)"
            return [f"hyperframes inspect exit={result.exit_code}:\n{body}"]

        if payload is None:
            return [f"could not parse inspect JSON: {parse_err}"]

        overflows = _extract_overflows(payload)
        if not overflows:
            # Catch the case where the CLI exited non-zero AND the payload
            # held no overflow entries — usually means a launch error
            # (e.g. `{"error": "puppeteer launch failed"}`) rather than a
            # clean run. Don't silently pass; surface the CLI tail.
            if not result.ok:
                body = (result.stderr or result.stdout or "(no output)").strip()
                if len(body) > 1500:
                    body = body[:1500] + "\n…(truncated)"
                return [
                    f"hyperframes inspect exit={result.exit_code} with no overflow "
                    f"issues parsed — may be a CLI / browser launch failure:\n{body}"
                ]
            return []

        index_path = hf_dir / "index.html"
        html = ""
        if index_path.is_file():
            try:
                html = index_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                html = ""

        leaf_by_overflow: list[tuple[dict, str | None]] = []
        leaves: list[str] = []
        for entry in overflows:
            selector = entry.get("selector") or entry.get("target") or ""
            leaf = _leaf_token(selector)
            leaf_by_overflow.append((entry, leaf))
            if leaf:
                leaves.append(leaf)

        opted_out = _opted_out_tokens(html, leaves) if leaves and html else set()

        violations: list[str] = []
        for entry, leaf in leaf_by_overflow:
            if leaf and leaf in opted_out:
                continue
            selector = entry.get("selector") or entry.get("target") or "(no selector)"
            ts = entry.get("timestamp") or entry.get("t")
            hint = entry.get("hint") or entry.get("fix") or ""
            ts_part = f" @ t={ts}" if ts is not None else ""
            hint_part = f" — {hint}" if hint else ""
            violations.append(
                f"overflow at {selector}{ts_part} not marked "
                f"data-layout-allow-overflow / data-layout-ignore{hint_part}"
            )
        return violations


def inspect_gate_node(state: dict) -> dict:
    return InspectGate()(state)
