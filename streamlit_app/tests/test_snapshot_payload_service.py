from __future__ import annotations

from trii_ingestion.models.stock_snapshot import StockSnapshot
from trii_ingestion.services.snapshot_payload import SnapshotPayloadService


def test_snapshot_payload_service_adds_capture_metadata() -> None:
    service = SnapshotPayloadService()
    payload = service.build(
        StockSnapshot(
            symbol="PFAVAL",
            asset_name="Aval Preferencial",
            currency="COP",
            last_price=828,
            daily_change_amount=0,
            daily_change_percent=0,
            daily_change_direction="up",
            previous_close=828,
            best_bid_price=822,
            best_bid_quantity=33636,
            best_ask_price=846,
            best_ask_quantity=43067,
            spread=24,
            mid_price=834,
            high_price=0,
            low_price=0,
            traded_value=0,
            traded_volume=0,
            bid_levels=[],
            ask_levels=[],
        )
    )

    dumped = payload.model_dump(mode="json")
    assert dumped["symbol"] == "PFAVAL"
    assert dumped["timezone"] == "America/Bogota"
    assert dumped["captured_at"].endswith("-05:00")
