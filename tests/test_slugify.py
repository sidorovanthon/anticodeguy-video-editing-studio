"""Tests for slugify.derive_slug."""
import pytest
from scripts.slugify import derive_slug


def test_simple_english_sentence():
    text = "Desktop software licensing, it turns out, is also a whole story."
    assert derive_slug(text, date="2026-04-30") == (
        "2026-04-30-desktop-software-licensing-it-turns-out-is"
    )


def test_no_terminal_punctuation_uses_first_line():
    text = "Hello world\n\nrest of script"
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-hello-world"


def test_first_paragraph_is_inspected_for_terminal_punct():
    text = "First sentence. Second sentence."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-first-sentence"


def test_question_mark_terminates():
    text = "Why does this work? Because it does."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-why-does-this-work"


def test_exclamation_terminates():
    text = "Wow! This is great."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-wow"


def test_cyrillic_transliteration():
    text = "Привет мир, как дела?"
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-privet-mir-kak-dela"


def test_accented_latin_strips_to_ascii():
    text = "Café résumé naïve."
    assert derive_slug(text, date="2026-04-30") == "2026-04-30-cafe-resume-naive"


def test_60_char_cap_with_word_boundary():
    text = "This is a very long sentence that absolutely must be truncated somewhere reasonable."
    slug = derive_slug(text, date="2026-04-30")
    title_part = slug[len("2026-04-30-"):]
    assert len(title_part) <= 60
    assert not title_part.endswith("-")
    assert "-trunc" not in title_part  # backed up before mid-word


def test_empty_input_returns_just_date_with_dash():
    assert derive_slug("", date="2026-04-30") == "2026-04-30-untitled"


def test_only_punctuation_returns_untitled():
    assert derive_slug("...!?,", date="2026-04-30") == "2026-04-30-untitled"
