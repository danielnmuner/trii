from __future__ import annotations

from glossary_specs import GLOSSARY_SECTIONS


def test_glossary_sections_remain_available() -> None:
    assert GLOSSARY_SECTIONS
    assert len(GLOSSARY_SECTIONS) == 5


def test_glossary_sections_are_not_empty() -> None:
    for section in GLOSSARY_SECTIONS:
        assert section.title
        assert section.summary
        assert section.entries
        for entry in section.entries:
            assert entry.term
            assert entry.formula
            assert entry.variables
            assert entry.practical_definition
            assert entry.how_to_use
            assert entry.decision_support
