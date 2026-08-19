from __future__ import annotations

from contract_specs import CONTRACT_SPECS
from glossary_specs import GLOSSARY_SECTIONS
from trii_ingestion.models.types import SectionType


def test_contract_specs_keep_required_order() -> None:
    assert [spec.section for spec in CONTRACT_SPECS] == [SectionType.STOCK_SNAPSHOT]


def test_contract_specs_have_practical_copy_notes() -> None:
    for spec in CONTRACT_SPECS:
        assert spec.title
        assert spec.importance_note
        assert len(spec.importance_note.split()) >= 18


def test_glossary_sections_are_not_empty() -> None:
    assert GLOSSARY_SECTIONS
    assert len(GLOSSARY_SECTIONS) == 2
    for section in GLOSSARY_SECTIONS:
        assert section.title
        assert section.summary
        assert section.entries
