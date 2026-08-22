import base64
import csv
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from zoneinfo import ZoneInfo


DYNAMODB_CLIENT = boto3.client("dynamodb")
DYNAMODB_RESOURCE = boto3.resource("dynamodb")
S3_CLIENT = boto3.client("s3")
SERIALIZER = TypeSerializer()

CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
SNAPSHOT_INGESTION_RAW_TABLE = os.environ["SNAPSHOT_INGESTION_RAW_TABLE"]
SNAPSHOT_INGESTION_CHECKSUMS_TABLE = os.environ["SNAPSHOT_INGESTION_CHECKSUMS_TABLE"]
HISTORIC_STATS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["HISTORIC_STATS_TABLE"])
DAILY_CLOSING_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["DAILY_CLOSING_SNAPSHOTS_TABLE"])
ZSCORE_OPPORTUNITIES_TABLE = DYNAMODB_RESOURCE.Table(os.environ["ZSCORE_OPPORTUNITIES_TABLE"])
MARKET_AI_RECOMMENDATIONS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["MARKET_AI_RECOMMENDATIONS_TABLE"])
ANALYTICS_CATALOG_TABLE = DYNAMODB_RESOURCE.Table(os.environ["ANALYTICS_CATALOG_TABLE"])
STOCK_ORDERS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["STOCK_ORDERS_TABLE"])
API_SHARED_TOKEN = os.environ["API_SHARED_TOKEN"]
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
RAW_SNAPSHOT_TTL_SECONDS = 72 * 60 * 60
CURRENT_SNAPSHOT_TTL_SECONDS = 365 * 24 * 60 * 60
EXPECTED_STOCK_ORDER_COLUMNS = (
    "Fecha y hora",
    "Símbolo de la acción",
    "Tipo de orden",
    "Estado",
    "Acciones completadas",
    "Acciones pendientes",
    "Precio por acción",
    "Total invertido",
    "Valor comisión",
    "Total estimado",
)

SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}
SPANISH_DATETIME_PATTERN = re.compile(
    r"^\s*(?P<day>\d{1,2})\s+"
    r"(?P<month>[A-Za-záéíóúñÁÉÍÓÚÑ]{3,})\s+"
    r"(?P<year>\d{4}),\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+"
    r"(?P<meridiem>[ap])\.\s*m\.\s*$",
    re.IGNORECASE,
)

def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def _normalize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items() if value is not None}


def _query_params(event: dict[str, Any]) -> dict[str, str]:
    raw_params = event.get("queryStringParameters") or {}
    return {str(key): str(value) for key, value in raw_params.items() if value is not None}


def _is_authorized(event: dict[str, Any]) -> bool:
    iam_context = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("iam")
    )
    if isinstance(iam_context, dict) and iam_context:
        return True

    headers = _normalize_headers(event.get("headers"))
    provided_token = headers.get("x-api-token")
    if provided_token:
        return provided_token == API_SHARED_TOKEN

    authorization_header = headers.get("authorization", "")
    if authorization_header.lower().startswith("bearer "):
        return authorization_header[7:] == API_SHARED_TOKEN

    return False


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body")
    if not raw_body:
        return {}

    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    if isinstance(raw_body, str):
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("El cuerpo del request no contiene un JSON válido.") from exc

    if isinstance(raw_body, dict):
        return raw_body

    raise ValueError("El cuerpo del request tiene un formato no soportado.")


def _decode_base64_field(payload: dict[str, Any], field_name: str) -> bytes:
    value = payload.get(field_name)
    if not value:
        raise ValueError(f"El campo `{field_name}` es obligatorio.")
    try:
        return base64.b64decode(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"El campo `{field_name}` no contiene base64 válido.") from exc


def _json_checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def _decimalize(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, list):
        return [_decimalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _decimalize(item) for key, item in value.items()}
    return value


def _validate_snapshot_levels(levels: Any, *, field_name: str) -> None:
    if not isinstance(levels, list):
        raise ValueError(f"El campo `{field_name}` debe ser una lista.")
    if not levels:
        raise ValueError(f"El campo `{field_name}` no puede estar vacio.")

    for index, level in enumerate(levels, start=1):
        if not isinstance(level, dict):
            raise ValueError(f"Cada item de `{field_name}` debe ser un objeto.")
        required_level_keys = {"level", "quantity", "price"}
        missing_level_keys = required_level_keys - level.keys()
        if missing_level_keys:
            raise ValueError(
                f"El item {index} de `{field_name}` no incluye: {', '.join(sorted(missing_level_keys))}."
            )


def _validate_snapshot_schema(snapshot: dict[str, Any]) -> None:
    disallowed_legacy_keys = {
        "stock_snapshot",
        "technical_oscillators",
        "technical_moving_averages",
        "support_and_resistance",
    }
    legacy_keys_present = sorted(disallowed_legacy_keys & snapshot.keys())
    if legacy_keys_present:
        raise ValueError(
            "El payload de snapshots ya no soporta contratos tecnicos legacy: "
            + ", ".join(legacy_keys_present)
            + "."
        )

    required_keys = {
        "symbol",
        "asset_name",
        "currency",
        "captured_at",
        "timezone",
        "last_price",
        "daily_change_amount",
        "daily_change_percent",
        "daily_change_direction",
        "previous_close",
        "best_bid_price",
        "best_bid_quantity",
        "best_ask_price",
        "best_ask_quantity",
        "high_price",
        "low_price",
        "traded_value",
        "traded_volume",
        "bid_levels",
        "ask_levels",
    }
    missing_keys = sorted(required_keys - snapshot.keys())
    if missing_keys:
        raise ValueError(
            "El payload de snapshots no incluye todos los campos requeridos: "
            + ", ".join(missing_keys)
            + "."
        )

    _validate_snapshot_levels(snapshot.get("bid_levels"), field_name="bid_levels")
    _validate_snapshot_levels(snapshot.get("ask_levels"), field_name="ask_levels")


def _persist_snapshot(body: dict[str, Any]) -> dict[str, Any]:
    snapshot = body.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("El payload de snapshots debe incluir un objeto `snapshot`.")
    _validate_snapshot_schema(snapshot)

    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    normalized_snapshot = dict(snapshot)
    normalized_snapshot["symbol"] = symbol
    normalized_snapshot["captured_at"] = captured_at

    item = dict(normalized_snapshot)
    item["symbol"] = symbol
    item["captured_at"] = captured_at
    item["captured_date"] = captured_at[:10]
    item["snapshot_checksum"] = _json_checksum(normalized_snapshot)
    item["symbol_captured_at"] = f"{symbol}#{captured_at}"
    accepted_timestamp = datetime.now(BOGOTA_TIMEZONE)
    accepted_at = accepted_timestamp.isoformat()
    accepted_epoch = int(accepted_timestamp.timestamp())
    raw_item = dict(item)
    raw_item["expires_at"] = accepted_epoch + RAW_SNAPSHOT_TTL_SECONDS
    item["expires_at"] = accepted_epoch + CURRENT_SNAPSHOT_TTL_SECONDS

    checksum_item = {
        "snapshot_checksum": item["snapshot_checksum"],
        "captured_date": item["captured_date"],
        "symbol": symbol,
        "captured_at": captured_at,
        "symbol_captured_at": item["symbol_captured_at"],
        "accepted_at": accepted_at,
        "source": str(snapshot.get("source") or "unknown"),
    }

    DYNAMODB_CLIENT.transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": SNAPSHOT_INGESTION_CHECKSUMS_TABLE,
                    "Item": _serialize_item(_decimalize(checksum_item)),
                    "ConditionExpression": "attribute_not_exists(snapshot_checksum)",
                }
            },
            {
                "Put": {
                    "TableName": SNAPSHOT_INGESTION_RAW_TABLE,
                    "Item": _serialize_item(_decimalize(raw_item)),
                    "ConditionExpression": "attribute_not_exists(symbol) AND attribute_not_exists(captured_at)",
                }
            },
            {
                "Put": {
                    "TableName": os.environ["CURRENT_SNAPSHOTS_TABLE"],
                    "Item": _serialize_item(_decimalize(item)),
                    "ConditionExpression": "attribute_not_exists(symbol) AND attribute_not_exists(captured_at)",
                }
            },
        ]
    )

    return {
        "table": os.environ["CURRENT_SNAPSHOTS_TABLE"],
        "symbol": symbol,
        "captured_at": captured_at,
        "snapshot_checksum": item["snapshot_checksum"],
    }


def _parse_positive_int(raw_value: str | None, *, default: int) -> int:
    if raw_value is None or raw_value == "":
        return default
    parsed = int(raw_value)
    if parsed <= 0:
        raise ValueError("El parámetro `days` debe ser un entero positivo.")
    return parsed


def _parse_positive_limit(raw_value: str | None, *, default: int, maximum: int) -> int:
    parsed = _parse_positive_int(raw_value, default=default)
    return min(parsed, maximum)


def _parse_iso_date(raw_value: str | None, *, field_name: str) -> str | None:
    if raw_value is None or raw_value == "":
        return None
    try:
        return date.fromisoformat(str(raw_value).strip()).isoformat()
    except ValueError as exc:
        raise ValueError(f"El parámetro `{field_name}` debe tener formato YYYY-MM-DD.") from exc


def _parse_year_month(raw_value: str | None, *, field_name: str) -> str | None:
    if raw_value is None or raw_value == "":
        return None
    normalized = str(raw_value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", normalized):
        raise ValueError(f"El parámetro `{field_name}` debe tener formato YYYY-MM.")
    return normalized


def _parse_snapshot_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def _date_range(start_date, end_date) -> list[str]:
    total_days = (end_date - start_date).days
    return [(start_date + timedelta(days=offset)).isoformat() for offset in range(total_days + 1)]


def _list_recent_snapshots(event: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(event)
    days = _parse_positive_int(params.get("days"), default=7)
    now_bogota = datetime.now(BOGOTA_TIMEZONE)
    from_bogota = now_bogota - timedelta(days=days)
    now_utc = now_bogota.astimezone(timezone.utc)
    from_utc = from_bogota.astimezone(timezone.utc)
    candidate_dates = sorted(
        set(_date_range(from_bogota.date(), now_bogota.date()))
        | set(_date_range(from_utc.date(), now_utc.date()))
    )

    items: list[dict[str, Any]] = []
    for target_date in candidate_dates:
        query_kwargs = {
            "IndexName": "captured-date-index",
            "KeyConditionExpression": Key("captured_date").eq(target_date),
        }
        while True:
            response = CURRENT_SNAPSHOTS_TABLE.query(**query_kwargs)
            items.extend(response.get("Items", []))
            last_evaluated_key = response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

    filtered_items = []
    for item in items:
        try:
            captured_at = _parse_snapshot_timestamp(str(item["captured_at"]))
        except Exception:
            continue
        if from_bogota <= captured_at <= now_bogota:
            filtered_items.append((captured_at, item))

    filtered_items.sort(key=lambda pair: pair[0], reverse=True)

    return {
        "timezone": "America/Bogota",
        "from_date": from_bogota.date().isoformat(),
        "to_timestamp": now_bogota.isoformat(),
        "records": _json_ready([item for _, item in filtered_items]),
        "record_count": len(filtered_items),
    }


def _list_analytics_catalog(event: dict[str, Any]) -> dict[str, Any]:
    response = ANALYTICS_CATALOG_TABLE.get_item(Key={"pk": "analytics_catalog"})
    item = response.get("Item")
    if not item:
        return {
            "catalog": None,
            "symbols": [],
            "symbol_count": 0,
            "trading_date": None,
            "to_timestamp": None,
            "record_count": 0,
            "records": [],
        }

    return {
        "catalog": _json_ready(item),
        "symbols": _json_ready(item.get("symbols", [])),
        "symbol_count": int(item.get("symbol_count", 0) or 0),
        "trading_date": item.get("trading_date"),
        "to_timestamp": item.get("to_timestamp"),
        "record_count": int(item.get("record_count", 0) or 0),
        "records": _json_ready(item.get("records", [])),
    }


def _find_latest_snapshot_captured_date(*, lookback_days: int = 14) -> str | None:
    for offset in range(lookback_days + 1):
        candidate = (datetime.now(BOGOTA_TIMEZONE).date() - timedelta(days=offset)).isoformat()
        response = CURRENT_SNAPSHOTS_TABLE.query(
            IndexName="captured-date-index",
            KeyConditionExpression=Key("captured_date").eq(candidate),
            Limit=1,
        )
        if response.get("Items"):
            return candidate
    return None


def _list_zscore_opportunities(event: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(event)
    snapshot_checksum = str(params.get("snapshot_checksum") or "").strip()
    symbol = str(params.get("symbol") or "").strip().upper()
    trading_date = _parse_iso_date(params.get("trading_date"), field_name="trading_date")
    limit = _parse_positive_limit(params.get("limit"), default=100, maximum=500)

    if snapshot_checksum:
        response = ZSCORE_OPPORTUNITIES_TABLE.get_item(Key={"snapshot_checksum": snapshot_checksum})
        item = response.get("Item")
        records = [] if item is None else [_json_ready(item)]
        return {
            "snapshot_checksum": snapshot_checksum,
            "record_count": len(records),
            "records": records,
        }

    records: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any]

    if symbol:
        key_condition = Key("symbol").eq(symbol)
        if trading_date:
            key_condition &= Key("captured_at").begins_with(trading_date)
        query_kwargs = {
            "IndexName": "symbol-created-at-index",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": False,
            "Limit": limit,
        }
        response = ZSCORE_OPPORTUNITIES_TABLE.query(**query_kwargs)
        records = response.get("Items", [])
        normalized_trading_date = trading_date
    else:
        normalized_trading_date = trading_date or datetime.now(BOGOTA_TIMEZONE).date().isoformat()
        query_kwargs = {
            "IndexName": "trading-date-index",
            "KeyConditionExpression": Key("trading_date").eq(normalized_trading_date),
            "ScanIndexForward": False,
        }
        while len(records) < limit:
            response = ZSCORE_OPPORTUNITIES_TABLE.query(**query_kwargs)
            records.extend(response.get("Items", []))
            last_evaluated_key = response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

        records = sorted(
            records,
            key=lambda item: (
                str(item.get("captured_at") or ""),
                str(item.get("symbol") or ""),
            ),
            reverse=True,
        )[:limit]

    return {
        "symbol": symbol or None,
        "trading_date": normalized_trading_date,
        "record_count": len(records),
        "records": _json_ready(records),
    }


def _project_order_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "imported_at": str(item.get("imported_at") or "").strip() or None,
        "created_at_symbol": str(item.get("created_at_symbol") or "").strip() or None,
    }


def _list_orders(event: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(event)
    record_checksum = str(params.get("record_checksum") or "").strip()
    symbol = str(params.get("symbol") or "").strip().upper()
    created_month = _parse_year_month(params.get("created_month"), field_name="created_month")
    limit = _parse_positive_limit(params.get("limit"), default=100, maximum=500)

    filters_used = [
        bool(record_checksum),
        bool(symbol),
        bool(created_month),
    ]
    if sum(filters_used) != 1:
        raise ValueError(
            "Debes enviar exactamente uno de estos parámetros: `record_checksum`, `symbol`, o `created_month`."
        )

    projection_expression = "imported_at, created_at_symbol"

    if record_checksum:
        response = STOCK_ORDERS_TABLE.get_item(
            Key={"record_checksum": record_checksum},
            ProjectionExpression=projection_expression,
        )
        item = response.get("Item")
        records = [] if item is None else [_project_order_record(item)]
        return {
            "lookup_mode": "record_checksum",
            "record_checksum": record_checksum,
            "record_count": len(records),
            "records": records,
        }

    if symbol:
        response = STOCK_ORDERS_TABLE.query(
            IndexName="symbol-created-at-index",
            KeyConditionExpression=Key("symbol").eq(symbol),
            ProjectionExpression=projection_expression,
            ScanIndexForward=False,
            Limit=limit,
        )
        records = [_project_order_record(item) for item in response.get("Items", [])]
        return {
            "lookup_mode": "symbol",
            "symbol": symbol,
            "record_count": len(records),
            "records": records,
        }

    response = STOCK_ORDERS_TABLE.query(
        IndexName="created-month-index",
        KeyConditionExpression=Key("created_month").eq(created_month),
        ProjectionExpression=projection_expression,
        ScanIndexForward=False,
        Limit=limit,
    )
    records = [_project_order_record(item) for item in response.get("Items", [])]
    return {
        "lookup_mode": "created_month",
        "created_month": created_month,
        "record_count": len(records),
        "records": records,
    }


def _find_latest_daily_closing_trading_date(*, lookback_days: int = 14) -> str | None:
    for offset in range(lookback_days + 1):
        candidate = (datetime.now(BOGOTA_TIMEZONE).date() - timedelta(days=offset)).isoformat()
        response = DAILY_CLOSING_SNAPSHOTS_TABLE.query(
            IndexName="trading-date-index",
            KeyConditionExpression=Key("trading_date").eq(candidate),
            Limit=1,
        )
        if response.get("Items"):
            return candidate
    return None


def _list_daily_closing_snapshots(event: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(event)
    symbol = str(params.get("symbol") or "").strip().upper()
    trading_date = _parse_iso_date(params.get("trading_date"), field_name="trading_date")
    limit = _parse_positive_limit(params.get("limit"), default=60, maximum=500)

    if symbol and trading_date:
        response = DAILY_CLOSING_SNAPSHOTS_TABLE.get_item(
            Key={"symbol": symbol, "trading_date": trading_date}
        )
        item = response.get("Item")
        records = [] if item is None else [_json_ready(item)]
        return {
            "symbol": symbol,
            "trading_date": trading_date,
            "record_count": len(records),
            "records": records,
        }

    if symbol:
        response = DAILY_CLOSING_SNAPSHOTS_TABLE.query(
            KeyConditionExpression=Key("symbol").eq(symbol),
            ScanIndexForward=False,
            Limit=limit,
        )
        records = response.get("Items", [])
        return {
            "symbol": symbol,
            "trading_date": None,
            "record_count": len(records),
            "records": _json_ready(records),
        }

    normalized_trading_date = trading_date or _find_latest_daily_closing_trading_date()
    if normalized_trading_date is None:
        return {
            "symbol": None,
            "trading_date": None,
            "record_count": 0,
            "records": [],
        }

    records: list[dict[str, Any]] = []
    query_kwargs = {
        "IndexName": "trading-date-index",
        "KeyConditionExpression": Key("trading_date").eq(normalized_trading_date),
    }
    while len(records) < limit:
        response = DAILY_CLOSING_SNAPSHOTS_TABLE.query(**query_kwargs)
        records.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_evaluated_key

    records = sorted(records, key=lambda item: str(item.get("symbol") or ""))[:limit]
    return {
        "symbol": None,
        "trading_date": normalized_trading_date,
        "record_count": len(records),
        "records": _json_ready(records),
    }


def _latest_snapshot_for_symbol(symbol: str) -> dict[str, Any] | None:
    response = CURRENT_SNAPSHOTS_TABLE.query(
        KeyConditionExpression=Key("symbol").eq(symbol),
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None
    return items[0]


def _query_snapshots_for_symbol(
    symbol: str,
    *,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    limit: int = 2,
) -> list[dict[str, Any]]:
    key_condition = Key("symbol").eq(symbol)
    if from_timestamp is not None and to_timestamp is not None:
        key_condition &= Key("captured_at").between(
            from_timestamp.isoformat(),
            to_timestamp.isoformat(),
        )
    elif to_timestamp is not None:
        key_condition &= Key("captured_at").lte(to_timestamp.isoformat())
    elif from_timestamp is not None:
        key_condition &= Key("captured_at").gte(from_timestamp.isoformat())

    query_kwargs = {
        "KeyConditionExpression": key_condition,
        "ScanIndexForward": False,
        "Limit": limit,
    }
    response = CURRENT_SNAPSHOTS_TABLE.query(**query_kwargs)
    return response.get("Items", [])


def _load_historic_stats_for_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    symbol = str(snapshot["symbol"]).strip().upper()
    return _load_historic_stats(symbol)


def _load_historic_stats(symbol: str, metric: str | None = None) -> dict[str, Any]:
    response = HISTORIC_STATS_TABLE.query(
        KeyConditionExpression=Key("pk").eq(symbol),
    )
    items = response.get("Items", [])
    seasonality_key = "seasonality_profile"

    filtered_items = []
    for item in items:
        item_metric = str(item.get("metric") or "").strip()
        item_sk = str(item.get("sk") or "").strip()
        item_record_type = str(item.get("record_type") or "").strip()
        is_seasonality_profile = item_sk == seasonality_key or item_record_type == seasonality_key

        if metric is None:
            if item_metric or is_seasonality_profile:
                filtered_items.append(item)
            continue

        if metric == seasonality_key:
            if is_seasonality_profile:
                filtered_items.append(item)
            continue

        if item_metric == metric:
            filtered_items.append(item)

    filtered_items.sort(
        key=lambda item: (
            0 if item.get("metric") else 1,
            str(item.get("metric") or ""),
            str(item.get("sk") or ""),
        )
    )

    return {
        "symbol": symbol,
        "metric": metric,
        "record_count": len(filtered_items),
        "records": _json_ready(filtered_items),
    }


def _get_analytics_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(event)
    symbol = str(params.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError("El parametro `symbol` es obligatorio para consultar analytics.")

    captured_at = str(params.get("captured_at") or "").strip()
    if captured_at:
        response = CURRENT_SNAPSHOTS_TABLE.get_item(
            Key={
                "symbol": symbol,
                "captured_at": captured_at,
            }
        )
        snapshot = response.get("Item")
        previous_snapshots = []
        if snapshot:
            previous_snapshots = _query_snapshots_for_symbol(
                symbol,
                to_timestamp=_parse_snapshot_timestamp(captured_at),
                limit=2,
            )
    else:
        previous_snapshots = _query_snapshots_for_symbol(
            symbol,
            limit=2,
        )
        snapshot = previous_snapshots[0] if previous_snapshots else None

    if not snapshot:
        raise ValueError("No se encontro un snapshot para el simbolo solicitado.")

    current_snapshot = snapshot
    previous_snapshot = None
    if previous_snapshots:
        if captured_at:
            previous_snapshot = next(
                (
                    item
                    for item in previous_snapshots
                    if str(item.get("captured_at", "")).strip() != captured_at
                ),
                None,
            )
        elif len(previous_snapshots) > 1:
            previous_snapshot = previous_snapshots[1]

    snapshots = [_json_ready(current_snapshot)]
    if previous_snapshot is not None:
        snapshots.append(_json_ready(previous_snapshot))

    return {
        "symbol": symbol,
        "record_count": len(snapshots),
        "from_timestamp": str((previous_snapshot or current_snapshot).get("captured_at", "")),
        "to_timestamp": str(current_snapshot.get("captured_at", "")),
        "current_snapshot": _json_ready(current_snapshot),
        "previous_snapshot": None if previous_snapshot is None else _json_ready(previous_snapshot),
        "snapshots": snapshots,
    }


def _get_historic_stats(event: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(event)
    symbol = str(params.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError("El parametro `symbol` es obligatorio para consultar historic stats.")

    metric = str(params.get("metric") or "").strip()
    if not metric:
        metric = None

    return _load_historic_stats(symbol, metric=metric)


def _parse_spanish_datetime(raw_value: str) -> str:
    normalized = " ".join(raw_value.replace(",", " ").split()).lower()
    parts = normalized.split()
    if len(parts) < 6:
        raise ValueError(f"Fecha y hora inválida: {raw_value}")

    day = int(parts[0])
    month = SPANISH_MONTHS.get(parts[1][:3])
    year = int(parts[2])
    hour, minute = [int(value) for value in parts[3].split(":")]
    meridiem = f"{parts[4]} {parts[5]}"

    if month is None:
        raise ValueError(f"Mes no soportado en fecha: {raw_value}")
    if meridiem == "p. m." and hour != 12:
        hour += 12
    if meridiem == "a. m." and hour == 12:
        hour = 0

    return datetime(year, month, day, hour, minute).isoformat() + "-05:00"


def _parse_decimal(raw_value: str) -> Decimal:
    value = raw_value.strip().replace("$", "").replace(" ", "")
    if not value:
        return Decimal("0")
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    return Decimal(value)


def _parse_quantity(raw_value: str) -> int:
    value = raw_value.strip()
    if not value:
        return 0
    return int(value.split("/")[0])


def _parse_requested_quantity(completed_value: str, pending_value: str) -> int:
    pending_quantity = _parse_quantity(pending_value)
    completed_clean = completed_value.strip()
    requested_hint = None

    if "/" in completed_clean:
        requested_hint = int(completed_clean.split("/", maxsplit=1)[1])

    filled_quantity = _parse_quantity(completed_clean)
    requested_quantity = filled_quantity + pending_quantity
    if requested_hint is not None:
        requested_quantity = max(requested_quantity, requested_hint)
    return requested_quantity


def _normalize_status(raw_status: str) -> str:
    mapping = {
        "aprobado": "approved",
        "cancelado": "cancelled",
        "pendiente": "pending",
        "rechazado": "rejected",
    }
    return mapping.get(raw_status.strip().lower(), "unknown")


def _normalize_order_side(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    if normalized == "compra":
        return "buy"
    if normalized == "venta":
        return "sell"
    raise ValueError(f"Tipo de orden no soportado: {raw_value}")


def _order_record_checksum(record: dict[str, Any]) -> str:
    canonical_payload = {
        "ordered_at": record["ordered_at"],
        "symbol": record["symbol"],
        "order_side": record["order_side"],
        "raw_status": record["raw_status"],
        "requested_quantity": record["requested_quantity"],
        "filled_quantity": record["filled_quantity"],
        "pending_quantity": record["pending_quantity"],
        "price_per_share": str(record["price_per_share"]),
        "gross_amount": str(record["gross_amount"]),
        "commission_amount": str(record["commission_amount"]),
        "net_amount": str(record["net_amount"]),
        "currency": record["currency"],
    }
    return _json_checksum(canonical_payload)


def _load_csv_rows(raw_bytes: bytes) -> list[dict[str, str]]:
    text = raw_bytes.decode("utf-8-sig").strip()
    if not text:
        raise ValueError("El archivo CSV de movimientos está vacío.")

    reader = csv.DictReader(StringIO(text))
    columns = tuple(reader.fieldnames or ())
    if columns != EXPECTED_STOCK_ORDER_COLUMNS:
        missing = [column for column in EXPECTED_STOCK_ORDER_COLUMNS if column not in columns]
        unexpected = [column for column in columns if column not in EXPECTED_STOCK_ORDER_COLUMNS]
        details: list[str] = []
        if missing:
            details.append("faltan: " + ", ".join(missing))
        if unexpected:
            details.append("sobran: " + ", ".join(unexpected))
        raise ValueError(
            "El CSV de movimientos no coincide con la estructura esperada de Trii; "
            + "; ".join(details)
            + "."
        )

    rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    rows = [row for row in rows if any(value for value in row.values())]
    if not rows:
        raise ValueError("El archivo CSV de movimientos no contiene filas válidas.")
    return rows


def _normalize_order_records(raw_bytes: bytes) -> list[dict[str, Any]]:
    rows = _load_csv_rows(raw_bytes)
    imported_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    source_file_checksum = hashlib.sha256(raw_bytes).hexdigest()

    records: list[dict[str, Any]] = []
    seen_checksums: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        ordered_at = _parse_spanish_datetime(row["Fecha y hora"])
        symbol = row["Símbolo de la acción"].strip().upper()
        record = {
            "source_file_checksum": source_file_checksum,
            "source_line_number": line_number,
            "ordered_at": ordered_at,
            "ordered_month": ordered_at[:7],
            "ordered_at_symbol": f"{ordered_at}#{symbol}",
            "symbol": symbol,
            "order_side": _normalize_order_side(row["Tipo de orden"]),
            "raw_status": row["Estado"],
            "normalized_status": _normalize_status(row["Estado"]),
            "requested_quantity": _parse_requested_quantity(
                row["Acciones completadas"],
                row["Acciones pendientes"],
            ),
            "filled_quantity": _parse_quantity(row["Acciones completadas"]),
            "pending_quantity": _parse_quantity(row["Acciones pendientes"]),
            "price_per_share": _parse_decimal(row["Precio por acción"]),
            "gross_amount": _parse_decimal(row["Total invertido"]),
            "commission_amount": _parse_decimal(row["Valor comisión"]),
            "net_amount": _parse_decimal(row["Total estimado"]),
            "currency": "COP",
            "imported_at": imported_at,
        }
        record["record_checksum"] = _order_record_checksum(record)
        if record["record_checksum"] in seen_checksums:
            raise ValueError(
                "El CSV de movimientos contiene checksums duplicados dentro del mismo archivo; se rechaza el lote completo."
            )
        seen_checksums.add(record["record_checksum"])
        records.append(record)

    return records


def _persist_order_if_new(record: dict[str, Any]) -> bool:
    try:
        STOCK_ORDERS_TABLE.put_item(
            Item=_decimalize(record),
            ConditionExpression="attribute_not_exists(record_checksum)",
        )
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return False
        raise


def _persist_orders(body: dict[str, Any]) -> dict[str, Any]:
    file_name = str(body.get("file_name") or "").strip()
    if not file_name:
        raise ValueError("El payload de movimientos debe incluir `file_name`.")

    raw_bytes = _decode_base64_field(body, "file_content_base64")
    records = _normalize_order_records(raw_bytes)
    imported_records = 0
    duplicate_records = 0

    for new_record in records:
        if _persist_order_if_new(new_record):
            imported_records += 1
        else:
            duplicate_records += 1

    return {
        "table": os.environ["STOCK_ORDERS_TABLE"],
        "file_name": file_name,
        "source_file_checksum": records[0]["source_file_checksum"],
        "received_records": len(records),
        "imported_records": imported_records,
        "duplicate_records": duplicate_records,
        "symbols": sorted({record["symbol"] for record in records}),
    }


def _parse_spanish_datetime(raw_value: str) -> str:
    match = SPANISH_DATETIME_PATTERN.match(raw_value)
    if match is None:
        raise ValueError(f"Fecha y hora inválida: {raw_value}")

    month = SPANISH_MONTHS.get(match.group("month")[:3].lower())
    if month is None:
        raise ValueError(f"Mes no soportado en fecha: {raw_value}")

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    meridiem = match.group("meridiem").lower()
    if meridiem == "p" and hour != 12:
        hour += 12
    if meridiem == "a" and hour == 12:
        hour = 0

    return datetime(
        int(match.group("year")),
        month,
        int(match.group("day")),
        hour,
        minute,
        tzinfo=BOGOTA_TIMEZONE,
    ).isoformat()


def _parse_decimal(raw_value: Any) -> Decimal:
    value = str(raw_value).strip().replace("$", "").replace(" ", "")
    if not value:
        return Decimal("0")
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    return Decimal(value)


def _order_record_checksum(record: dict[str, Any]) -> str:
    canonical_payload = {
        "created_at": record["created_at"],
        "symbol": record["symbol"],
        "order_side": record["order_side"],
        "raw_status": record["raw_status"],
        "requested_quantity": record["requested_quantity"],
        "filled_quantity": record["filled_quantity"],
        "pending_quantity": record["pending_quantity"],
        "price_per_share": str(record["price_per_share"]),
        "gross_amount": str(record["gross_amount"]),
        "commission_amount": str(record["commission_amount"]),
        "net_amount": str(record["net_amount"]),
        "currency": record["currency"],
    }
    return _json_checksum(canonical_payload)


def _normalize_order_records(raw_bytes: bytes) -> list[dict[str, Any]]:
    rows = _load_csv_rows(raw_bytes)
    imported_at = datetime.now(BOGOTA_TIMEZONE).replace(microsecond=0).isoformat()
    source_file_checksum = hashlib.sha256(raw_bytes).hexdigest()

    records: list[dict[str, Any]] = []
    seen_checksums: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        created_at = _parse_spanish_datetime(row["Fecha y hora"])
        symbol = row["Símbolo de la acción"].strip().upper()
        record = {
            "source_file_checksum": source_file_checksum,
            "source_line_number": line_number,
            "created_at": created_at,
            "created_month": created_at[:7],
            "created_at_symbol": f"{created_at}#{symbol}",
            "symbol": symbol,
            "order_side": _normalize_order_side(row["Tipo de orden"]),
            "raw_status": row["Estado"],
            "normalized_status": _normalize_status(row["Estado"]),
            "requested_quantity": _parse_requested_quantity(
                row["Acciones completadas"],
                row["Acciones pendientes"],
            ),
            "filled_quantity": _parse_quantity(row["Acciones completadas"]),
            "pending_quantity": _parse_quantity(row["Acciones pendientes"]),
            "price_per_share": _parse_decimal(row["Precio por acción"]),
            "gross_amount": _parse_decimal(row["Total invertido"]),
            "commission_amount": _parse_decimal(row["Valor comisión"]),
            "net_amount": _parse_decimal(row["Total estimado"]),
            "currency": "COP",
            "imported_at": imported_at,
        }
        record["record_checksum"] = _order_record_checksum(record)
        if record["record_checksum"] in seen_checksums:
            raise ValueError(
                "El CSV de movimientos contiene checksums duplicados dentro del mismo archivo; se rechaza el lote completo."
            )
        seen_checksums.add(record["record_checksum"])
        records.append(record)

    return records


def _normalize_iso_timestamp(raw_value: Any) -> str:
    normalized = str(raw_value).strip()
    if not normalized:
        raise ValueError("Cada orden debe incluir `created_at`.")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
    return timestamp.astimezone(BOGOTA_TIMEZONE).isoformat()


def _normalize_payload_order_records(body: dict[str, Any]) -> list[dict[str, Any]]:
    payload_records = body.get("records")
    if not isinstance(payload_records, list) or not payload_records:
        raise ValueError("El payload de movimientos debe incluir una lista `records` no vacía.")

    source_file_checksum = str(body.get("source_file_checksum") or "").strip()
    if not source_file_checksum:
        source_file_checksum = _json_checksum(payload_records)

    imported_at = datetime.now(BOGOTA_TIMEZONE).replace(microsecond=0).isoformat()
    records: list[dict[str, Any]] = []
    seen_checksums: set[str] = set()

    for position, payload_record in enumerate(payload_records, start=1):
        if not isinstance(payload_record, dict):
            raise ValueError("Cada item de `records` debe ser un objeto.")

        created_at = _normalize_iso_timestamp(payload_record.get("created_at"))
        symbol = str(payload_record.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("Cada orden debe incluir `symbol`.")

        raw_status = str(payload_record.get("raw_status") or "").strip()
        if not raw_status:
            raise ValueError("Cada orden debe incluir `raw_status`.")

        order_side = str(payload_record.get("order_side") or "").strip().lower()
        if order_side == "buy":
            normalized_order_side = "buy"
        elif order_side == "sell":
            normalized_order_side = "sell"
        else:
            normalized_order_side = _normalize_order_side(order_side)

        record = {
            "source_file_checksum": source_file_checksum,
            "source_line_number": int(payload_record.get("source_line_number") or position + 1),
            "created_at": created_at,
            "created_month": created_at[:7],
            "created_at_symbol": f"{created_at}#{symbol}",
            "symbol": symbol,
            "order_side": normalized_order_side,
            "raw_status": raw_status,
            "normalized_status": _normalize_status(raw_status),
            "requested_quantity": int(payload_record.get("requested_quantity") or 0),
            "filled_quantity": int(payload_record.get("filled_quantity") or 0),
            "pending_quantity": int(payload_record.get("pending_quantity") or 0),
            "price_per_share": _parse_decimal(payload_record.get("price_per_share", "0")),
            "gross_amount": _parse_decimal(payload_record.get("gross_amount", "0")),
            "commission_amount": _parse_decimal(payload_record.get("commission_amount", "0")),
            "net_amount": _parse_decimal(payload_record.get("net_amount", "0")),
            "currency": str(payload_record.get("currency") or "COP").strip().upper(),
            "imported_at": imported_at,
        }
        record["record_checksum"] = _order_record_checksum(record)
        if record["record_checksum"] in seen_checksums:
            raise ValueError(
                "El payload de movimientos contiene checksums duplicados dentro del mismo archivo; se rechaza el lote completo."
            )
        seen_checksums.add(record["record_checksum"])
        records.append(record)

    return records


def _persist_orders(body: dict[str, Any]) -> dict[str, Any]:
    file_name = str(body.get("file_name") or "").strip()
    if not file_name:
        raise ValueError("El payload de movimientos debe incluir `file_name`.")

    if body.get("records") is not None:
        records = _normalize_payload_order_records(body)
    else:
        raw_bytes = _decode_base64_field(body, "file_content_base64")
        records = _normalize_order_records(raw_bytes)
    imported_records = 0
    duplicate_records = 0

    for new_record in records:
        if _persist_order_if_new(new_record):
            imported_records += 1
        else:
            duplicate_records += 1

    return {
        "table": os.environ["STOCK_ORDERS_TABLE"],
        "file_name": file_name,
        "source_file_checksum": records[0]["source_file_checksum"],
        "received_records": len(records),
        "imported_records": imported_records,
        "duplicate_records": duplicate_records,
        "symbols": sorted({record["symbol"] for record in records}),
    }


def _persist_invoices(body: dict[str, Any]) -> dict[str, Any]:
    documents = body.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError(
            "El payload de facturas debe incluir una lista `documents` con XML y PDF por factura."
        )

    captured_at = datetime.utcnow().replace(microsecond=0)
    persisted_documents = []
    for document_payload in documents:
        archive_name = str(document_payload.get("archive_name") or "").strip()
        archive_stem = str(document_payload.get("archive_stem") or "").strip()
        xml_file_name = str(document_payload.get("xml_file_name") or "").strip()
        pdf_file_name = str(document_payload.get("pdf_file_name") or "").strip()

        if not archive_name:
            raise ValueError("Cada factura debe incluir `archive_name`.")
        if not archive_stem:
            raise ValueError("Cada factura debe incluir `archive_stem`.")
        if not xml_file_name.lower().endswith(".xml"):
            raise ValueError(f"La factura `{archive_name}` debe incluir un `xml_file_name` válido.")
        if not pdf_file_name.lower().endswith(".pdf"):
            raise ValueError(f"La factura `{archive_name}` debe incluir un `pdf_file_name` válido.")

        xml_bytes = _decode_base64_field(document_payload, "xml_content_base64")
        pdf_bytes = _decode_base64_field(document_payload, "pdf_content_base64")
        if not xml_bytes:
            raise ValueError(f"La factura `{archive_name}` tiene un XML vacío.")
        if not pdf_bytes:
            raise ValueError(f"La factura `{archive_name}` tiene un PDF vacío.")

        base_prefix = f"invoices/{captured_at.strftime('%Y/%m/%d')}/{archive_stem}"
        xml_s3_key = f"{base_prefix}/{xml_file_name}"
        pdf_s3_key = f"{base_prefix}/{pdf_file_name}"

        S3_CLIENT.put_object(
            Bucket=os.environ["SOURCE_DOCUMENTS_BUCKET"],
            Key=xml_s3_key,
            Body=xml_bytes,
            ContentType="application/xml",
            Metadata={
                "archive-name": archive_name,
                "document-type": "xml",
            },
        )
        S3_CLIENT.put_object(
            Bucket=os.environ["SOURCE_DOCUMENTS_BUCKET"],
            Key=pdf_s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            Metadata={
                "archive-name": archive_name,
                "document-type": "pdf",
            },
        )
        persisted_documents.append(
            {
                "archive_name": archive_name,
                "xml_s3_key": xml_s3_key,
                "pdf_s3_key": pdf_s3_key,
            }
        )

    return {
        "bucket": os.environ["SOURCE_DOCUMENTS_BUCKET"],
        "uploaded_files": len(persisted_documents) * 2,
        "documents": persisted_documents,
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    route_key = event.get("routeKey", "")

    if route_key == "GET /health":
        return _response(
            200,
            {
                "status": "ok",
                "service": "api_handler",
            },
        )

    if not _is_authorized(event):
        return _response(
            401,
            {
                "status": "error",
                "message": "Unauthorized",
            },
        )

    try:
        if route_key == "GET /snapshots":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _list_recent_snapshots(event),
                },
            )

        if route_key == "GET /orders":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _list_orders(event),
                },
            )

        if route_key == "GET /analytics/snapshot":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _get_analytics_snapshot(event),
                },
            )

        if route_key == "GET /analytics/historic-stats":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _get_historic_stats(event),
                },
            )

        if route_key == "GET /analytics/catalog":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _list_analytics_catalog(event),
                },
            )

        if route_key == "GET /analytics/zscore-opportunities":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _list_zscore_opportunities(event),
                },
            )

        if route_key == "GET /analytics/daily-closing":
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _list_daily_closing_snapshots(event),
                },
            )

        body = _parse_body(event)

        if route_key == "POST /snapshots":
            return _response(
                201,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _persist_snapshot(body),
                },
            )

        if route_key == "POST /orders":
            return _response(
                201,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _persist_orders(body),
                },
            )

        if route_key in {"POST /invoices", "POST /documents"}:
            return _response(
                201,
                {
                    "status": "ok",
                    "route": route_key,
                    "result": _persist_invoices(body),
                },
            )

        return _response(
            404,
            {
                "status": "error",
                "message": f"Unsupported route: {route_key}",
            },
        )
    except ValueError as exc:
        return _response(
            400,
            {
                "status": "error",
                "message": str(exc),
            },
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "TransactionCanceledException":
            return _response(
                409,
                {
                    "status": "error",
                    "message": "El snapshot fue rechazado porque ya existe un checksum o una llave primaria igual.",
                },
            )
        return _response(
            500,
            {
                "status": "error",
                "message": exc.response.get("Error", {}).get("Message", "AWS client error"),
            },
        )
    except Exception:
        return _response(
            500,
            {
                "status": "error",
                "message": "Internal server error",
            },
        )
