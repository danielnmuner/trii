from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from trii_ingestion.models.types import SectionType


class TextParser(ABC):
    section: SectionType

    @abstractmethod
    def score(self, text: str) -> tuple[float, list[str]]:
        raise NotImplementedError

    @abstractmethod
    def parse(self, text: str) -> BaseModel:
        raise NotImplementedError

    @staticmethod
    def _bounded_score(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _ensure_parseable(lines: list[str], required_markers: list[str]) -> None:
        for marker in required_markers:
            if marker not in lines:
                raise ValueError(f"Missing required marker: {marker}")
