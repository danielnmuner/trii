from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from trii_ingestion.models.types import SectionType


class JsonExporterService:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def save(self, document: BaseModel, section: SectionType) -> Path:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        symbol = getattr(document, "symbol", "unknown").lower()
        filename = f"{symbol}-{section.value}-{timestamp}.json"
        destination = self._output_dir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        return destination
