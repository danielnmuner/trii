from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from trii_ingestion.models.stock_snapshot import CapturedStockSnapshot, StockSnapshot


class SnapshotPayloadService:
    def __init__(self, timezone_name: str = "America/Bogota") -> None:
        self._timezone_name = timezone_name

    def build(self, snapshot: StockSnapshot) -> CapturedStockSnapshot:
        timezone = ZoneInfo(self._timezone_name)
        captured_at = datetime.now(timezone).isoformat()
        return CapturedStockSnapshot(
            captured_at=captured_at,
            timezone=self._timezone_name,
            **snapshot.model_dump(mode="python"),
        )
