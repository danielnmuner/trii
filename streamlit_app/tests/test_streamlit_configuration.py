from __future__ import annotations

from glossary_specs import GLOSSARY_SECTIONS


def test_glossary_sections_remain_available() -> None:
    assert GLOSSARY_SECTIONS
    assert len(GLOSSARY_SECTIONS) == 2


def test_glossary_sections_are_not_empty() -> None:
    for section in GLOSSARY_SECTIONS:
        assert section.title
        assert section.summary
        assert section.entries
