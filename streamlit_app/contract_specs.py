from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trii_ingestion.models.types import SectionType


@dataclass(frozen=True)
class ContractSpec:
    section: SectionType
    title: str
    importance_note: str
    placeholder: str
    image_path: Path

APP_DIR = Path(__file__).resolve().parent
FIXTURE_ROOT = APP_DIR / "fixtures" / "trii" / "stocks" / "pfaval"

CONTRACT_SPECS: tuple[ContractSpec, ...] = (
    ContractSpec(
        section=SectionType.STOCK_SNAPSHOT,
        title="Indicadores principales",
        importance_note=(
            "Este bloque fija el contexto operativo completo del snapshot: identifica la acción, el precio observado, "
            "la profundidad disponible en compra y venta, y las métricas mínimas de mercado. Las líneas de profundidad "
            "permiten estimar liquidez real, presión de demanda u oferta y el posible deslizamiento antes de tomar una "
            "decisión sobre precio límite, tamaño de orden o viabilidad inmediata de ejecución."
        ),
        placeholder="Pega aquí el bloque completo del resumen de la acción...",
        image_path=FIXTURE_ROOT / "stock_snapshot" / "pfaval-aval_preferencial.png",
    ),
    ContractSpec(
        section=SectionType.TECHNICAL_OSCILLATORS,
        title="Osciladores técnicos",
        importance_note=(
            "Este bloque aporta señales de momentum, agotamiento y posible giro del precio a muy corto y corto plazo. "
            "Indicadores como RSI, estocásticos, MACD y Williams %R ayudan a distinguir si el activo está acelerando, "
            "neutral o sobreextendido, y sirven para decidir si conviene esperar confirmación, evitar perseguir precio "
            "o validar una entrada táctica junto con el snapshot principal."
        ),
        placeholder="Pega aquí el bloque completo de osciladores...",
        image_path=FIXTURE_ROOT / "technical_oscillators" / "pfaval-aval_preferencial.png",
    ),
    ContractSpec(
        section=SectionType.TECHNICAL_MOVING_AVERAGES,
        title="Medias móviles técnicas",
        importance_note=(
            "Este bloque describe la tendencia dominante, la velocidad del movimiento y el rango esperado de volatilidad "
            "mediante medias móviles, momento y bandas de Bollinger. Es especialmente útil para separar un impulso "
            "sano de un movimiento agotado, y para decidir si el precio actual todavía acompaña la tendencia o ya se "
            "está alejando demasiado de una zona razonable de entrada."
        ),
        placeholder="Pega aquí el bloque completo de medias móviles...",
        image_path=FIXTURE_ROOT / "technical_moving_averages" / "pfaval-aval_preferencial.png",
    ),
    ContractSpec(
        section=SectionType.SUPPORT_AND_RESISTANCE,
        title="Soportes y resistencias",
        importance_note=(
            "Este bloque cierra la lectura técnica con niveles diarios y de mayor horizonte donde el precio podría "
            "frenarse, rebotar o romper estructura. Sirve para convertir el análisis en decisiones concretas: ubicar "
            "zonas de entrada y salida, anticipar objetivos o riesgo de retroceso, y verificar si el precio actual está "
            "cerca de una referencia crítica que cambie por completo el escenario operativo."
        ),
        placeholder="Pega aquí el bloque completo de soportes y resistencias...",
        image_path=FIXTURE_ROOT / "support_and_resistance" / "pfaval-aval_preferencial.png",
    ),
)


CONTRACT_SPEC_BY_SECTION = {spec.section: spec for spec in CONTRACT_SPECS}
