from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer_paragraphs: tuple[str, ...]


FAQ_ENTRIES: tuple[FaqEntry, ...] = (
    FaqEntry(
        question="¿En qué horario puedo comprar y vender acciones?",
        answer_paragraphs=(
            "Las acciones se negocian en los horarios definidos por la BVC en días hábiles. Fuera de ese horario puedes dejar órdenes programadas para que entren cuando el mercado abra.",
        ),
    ),
    FaqEntry(
        question="¿Qué es Acciones y Valores?",
        answer_paragraphs=(
            "Acciones y Valores S.A. SCB es la firma comisionista que intermedia las operaciones bursátiles asociadas a la experiencia de Trii.",
        ),
    ),
    FaqEntry(
        question="¿Cuál es la relación entre trii y Acciones y Valores S.A. SCB?",
        answer_paragraphs=(
            "Trii es la capa tecnológica y de experiencia de usuario. Acciones y Valores S.A. SCB es el intermediario que cursa las órdenes al mercado y custodia los recursos y posiciones dentro del marco regulatorio aplicable.",
        ),
    ),
    FaqEntry(
        question="¿Qué es la BVC?",
        answer_paragraphs=(
            "La Bolsa de Valores de Colombia es la infraestructura de mercado donde se negocian, registran y administran diferentes productos del mercado de capitales colombiano.",
        ),
    ),
    FaqEntry(
        question="¿Qué es la Superintendencia Financiera?",
        answer_paragraphs=(
            "Es la entidad que supervisa el sistema financiero colombiano y vela por la estabilidad, la confianza del mercado y la protección de inversionistas y ahorradores.",
        ),
    ),
    FaqEntry(
        question="¿Qué es Deceval?",
        answer_paragraphs=(
            "Deceval es el depósito centralizado de valores de Colombia. Custodia y administra valores, además de apoyar procesos de compensación y liquidación.",
        ),
    ),
    FaqEntry(
        question="¿Cuánto me cobran por realizar compras y ventas?",
        answer_paragraphs=(
            "La comisión depende del monto operado y del plan del usuario. En la referencia operativa actual, hasta cierto umbral se cobra una tarifa fija y por encima de ese nivel se aplica una comisión porcentual más IVA.",
            "Si necesitas usar este dato para decisión operativa, conviene confirmar la tarifa vigente directamente en Trii o Acciones y Valores antes de operar.",
        ),
    ),
    FaqEntry(
        question="¿Qué es la subasta de cierre y cómo funciona?",
        answer_paragraphs=(
            "Es el mecanismo que define el precio de cierre de la jornada. Durante ese tramo se acumulan órdenes y el calce final ocurre al terminar la subasta, no de forma inmediata como en la rueda continua.",
        ),
    ),
    FaqEntry(
        question="¿Qué se debe tener en cuenta para operar en la subasta de cierre?",
        answer_paragraphs=(
            "Conviene revisar precio indicativo, profundidad, volumen disponible y distancia entre compra y venta. Una orden puede ejecutar parcialmente o no ejecutar si al precio de equilibrio no hay suficiente contraparte.",
            "En ese contexto, las órdenes límite suelen ser más útiles que las órdenes a mercado para controlar el precio aceptado.",
        ),
    ),
    FaqEntry(
        question="¿Qué es un rebalanceo de índices?",
        answer_paragraphs=(
            "Es un ajuste en la composición o en los pesos de las acciones dentro de un índice. Cuando ocurre, los fondos que replican ese índice pueden necesitar comprar o vender acciones para alinearse con la nueva composición.",
        ),
    ),
    FaqEntry(
        question="¿Cómo puedo aprovechar la subasta de cierre para comprar o vender?",
        answer_paragraphs=(
            "La idea es usar el precio indicativo, la profundidad y el volumen para decidir un precio límite razonable, en vez de reaccionar solo al último precio negociado.",
            "Si el cierre final queda dentro de tu condición, la orden puede ejecutar; si no, simplemente no entra al precio que no querías aceptar.",
        ),
    ),
    FaqEntry(
        question="¿Cómo sé en Colombia que ese día existe un rebalanceo de índice que puede generar compras o ventas institucionales?",
        answer_paragraphs=(
            "Estos eventos suelen anunciarse con anticipación. Lo correcto es revisar calendarios y comunicados oficiales del proveedor del índice y de la infraestructura de mercado relevante antes de la jornada.",
        ),
    ),
    FaqEntry(
        question="¿Qué es un Stop Loss en trii Pro y cómo me sirve?",
        answer_paragraphs=(
            "Es una orden diseñada para limitar pérdidas al activar una venta cuando el precio cae hasta un umbral definido por ti.",
            "Su utilidad principal es ayudar a controlar riesgo y disciplinar salidas, especialmente cuando no puedes seguir el mercado tick a tick.",
        ),
    ),
    FaqEntry(
        question="¿Qué es Trader Trii MC?",
        answer_paragraphs=(
            "Es un perfil de operación enfocado en seguimiento intradía del mercado colombiano, con lectura continua de precio, volumen, profundidad, subasta de cierre y eventos relevantes para tomar decisiones tácticas.",
        ),
    ),
)
