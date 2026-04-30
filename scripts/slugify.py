"""Pure-functional slug derivation from author script content.

Per docs/superpowers/specs/2026-04-30-pipeline-enforcement-design.md §3.2.
"""
import re
import unicodedata

CYRILLIC_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

TITLE_CAP = 45


def _transliterate(text: str) -> str:
    """Cyrillic→ASCII via explicit map, accented Latin→ASCII via NFKD, lowercase."""
    text = text.lower()
    out = []
    for ch in text:
        if ch in CYRILLIC_MAP:
            out.append(CYRILLIC_MAP[ch])
        else:
            decomposed = unicodedata.normalize("NFKD", ch)
            ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
            out.append(ascii_only)
    return "".join(out)


def _slugify_token(text: str) -> str:
    """Reduce to [a-z0-9-], collapse runs, trim ends."""
    text = _transliterate(text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text


def _first_sentence(text: str) -> str:
    """Take everything up to the first .!? — falling back to the first non-empty line."""
    text = text.lstrip()
    if not text:
        return ""
    paragraph = text.split("\n\n", 1)[0]
    match = re.search(r"[.!?]", paragraph)
    if match:
        return paragraph[: match.start()]
    return paragraph.split("\n", 1)[0]


def _cap_at_word_boundary(slug: str, cap: int) -> str:
    if len(slug) <= cap:
        return slug
    truncated = slug[:cap]
    last_dash = truncated.rfind("-")
    if last_dash > 0:
        return truncated[:last_dash]
    return truncated


def derive_slug(script_text: str, date: str) -> str:
    """Derive a slug from the script's first sentence, prefixed with date.

    Args:
        script_text: full content of the user's script.txt.
        date: ISO date string in YYYY-MM-DD format.

    Returns:
        slug like "2026-04-30-desktop-software-licensing-it-turns-out-is".
        Always starts with "<date>-" and ends without a trailing dash.
        If the script yields no usable title, returns "<date>-untitled".
    """
    sentence = _first_sentence(script_text)
    title = _slugify_token(sentence)
    title = _cap_at_word_boundary(title, TITLE_CAP)
    if not title:
        title = "untitled"
    return f"{date}-{title}"
