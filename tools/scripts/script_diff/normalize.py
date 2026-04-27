"""Tokenization shared by script and Scribe sides."""
from __future__ import annotations

import re
from dataclasses import dataclass


# Lowercase letters, digits, and apostrophes inside words. Everything else is a separator.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


@dataclass(frozen=True)
class Token:
    """A normalized token. Script tokens carry (None, None); Scribe tokens carry seconds."""
    text: str
    start: float | None
    end: float | None


def normalize_text(s: str) -> str:
    return s.lower()


def tokenize_script(script_text: str) -> list[Token]:
    """Verbatim plain-text script → tokens with no timestamps."""
    return [Token(text=m.group(0), start=None, end=None)
            for m in _TOKEN_RE.finditer(normalize_text(script_text))]


def tokenize_scribe(words: list[dict]) -> list[Token]:
    """Scribe `words` array → tokens. Filters out `spacing` and `audio_event`.
    A single Scribe word may contain multiple alphanumeric runs (rare); each
    run becomes its own token, sharing the parent's (start, end).
    """
    out: list[Token] = []
    for w in words:
        if w.get("type") != "word":
            continue
        text = w.get("text") or ""
        start = float(w["start"])
        end = float(w["end"])
        for m in _TOKEN_RE.finditer(normalize_text(text)):
            out.append(Token(text=m.group(0), start=start, end=end))
    return out
