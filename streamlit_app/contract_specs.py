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
)


CONTRACT_SPEC_BY_SECTION = {spec.section: spec for spec in CONTRACT_SPECS}
