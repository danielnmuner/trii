from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trii_ingestion.models.types import SectionType


@dataclass(frozen=True)
class ContractSpec:
    section: SectionType
    title: str
    summary: str
    what_to_copy: str
    where_to_find_it: str
    how_to_copy: str
    placeholder: str
    image_path: Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT_DIR / "fixtures" / "trii" / "stocks" / "pfaval"

CONTRACT_SPECS: tuple[ContractSpec, ...] = (
    ContractSpec(
        section=SectionType.STOCK_SNAPSHOT,
        title="Resumen de la acción",
        summary="Ticker, precio, profundidad e indicadores básicos de mercado.",
        what_to_copy=(
            "Desde el ticker y el precio actual hasta el final del bloque `Indicadores`."
        ),
        where_to_find_it=(
            "En la vista principal de la acción, pestaña `Técnico`, dentro del bloque "
            "que contiene `Líneas de profundidad` e `Indicadores`."
        ),
        how_to_copy=(
            "Incluye `Mejor compra`, `Mejor venta`, las cinco puntas de cada lado y "
            "los indicadores hasta `Volumen`."
        ),
        placeholder="Pega aquí el bloque completo del resumen de la acción...",
        image_path=FIXTURE_ROOT / "stock_snapshot" / "pfaval-aval_preferencial.png",
    ),
    ContractSpec(
        section=SectionType.TECHNICAL_OSCILLATORS,
        title="Osciladores técnicos",
        summary="Resumen técnico de osciladores con tabla de indicadores y comentarios.",
        what_to_copy=(
            "Todo el bloque de `Osciladores`, incluyendo fecha, resumen de señales y tabla."
        ),
        where_to_find_it=(
            "En `Ver detalles técnicos`, subsección `Osciladores`."
        ),
        how_to_copy=(
            "Empieza en `Osciladores` y termina en la última fila visible del cuadro."
        ),
        placeholder="Pega aquí el bloque completo de osciladores...",
        image_path=FIXTURE_ROOT / "technical_oscillators" / "pfaval-aval_preferencial.png",
    ),
    ContractSpec(
        section=SectionType.TECHNICAL_MOVING_AVERAGES,
        title="Medias móviles técnicas",
        summary="Medias móviles, momento, bandas y señales de esa sección técnica.",
        what_to_copy=(
            "Todo el bloque de `Media Móvil`, incluyendo fecha, conteos y tabla completa."
        ),
        where_to_find_it=(
            "En `Ver detalles técnicos`, subsección `Media Móvil`."
        ),
        how_to_copy=(
            "Empieza en `Media Móvil` y termina en la última fila de `Bollinger Down`."
        ),
        placeholder="Pega aquí el bloque completo de medias móviles...",
        image_path=FIXTURE_ROOT / "technical_moving_averages" / "pfaval-aval_preferencial.png",
    ),
    ContractSpec(
        section=SectionType.SUPPORT_AND_RESISTANCE,
        title="Soportes y resistencias",
        summary="Bloque diario y de largo plazo con niveles, variación y análisis.",
        what_to_copy=(
            "Los dos bloques: `Soporte y resistencia diario` y `Soporte y resistencia a largo plazo`."
        ),
        where_to_find_it=(
            "En la sección técnica donde Trii muestra tablas de niveles y comentarios de análisis."
        ),
        how_to_copy=(
            "Debes incluir el precio de cierre, las cuatro filas de niveles y el comentario "
            "de cada horizonte."
        ),
        placeholder="Pega aquí el bloque completo de soportes y resistencias...",
        image_path=FIXTURE_ROOT / "support_and_resistance" / "pfaval-aval_preferencial.png",
    ),
)


CONTRACT_SPEC_BY_SECTION = {spec.section: spec for spec in CONTRACT_SPECS}
