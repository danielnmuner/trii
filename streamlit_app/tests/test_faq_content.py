from __future__ import annotations

from faq_content import FAQ_ENTRIES


EXPECTED_QUESTIONS = (
    "¿En qué horario puedo comprar y vender acciones?",
    "¿Qué es Acciones y Valores?",
    "¿Cuál es la relación entre trii y Acciones y Valores S.A. SCB?",
    "¿Qué es la BVC?",
    "¿Qué es la Superintendencia Financiera?",
    "¿Qué es Deceval?",
    "¿Cuánto me cobran por realizar compras y ventas?",
    "¿Qué es la subasta de cierre y cómo funciona?",
    "¿Qué se debe tener en cuenta para operar en la subasta de cierre?",
    "¿Qué es un rebalanceo de índices?",
    "¿Cómo puedo aprovechar la subasta de cierre para comprar o vender?",
    "¿Cómo sé en Colombia que ese día existe un rebalanceo de índice que puede generar compras o ventas institucionales?",
    "¿Qué es un Stop Loss en trii Pro y cómo me sirve?",
    "¿Qué es Trader Trii MC?",
)


def test_faq_entries_match_expected_questions() -> None:
    assert tuple(entry.question for entry in FAQ_ENTRIES) == EXPECTED_QUESTIONS


def test_faq_entries_have_non_empty_answers() -> None:
    for entry in FAQ_ENTRIES:
        assert entry.answer_paragraphs
        for paragraph in entry.answer_paragraphs:
            assert paragraph.strip()
