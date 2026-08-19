import base64
import csv
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from zoneinfo import ZoneInfo


LAMBDA_CLIENT = boto3.client("lambda")
DYNAMODB_CLIENT = boto3.client("dynamodb")
DYNAMODB_RESOURCE = boto3.resource("dynamodb")
S3_CLIENT = boto3.client("s3")

CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
STOCK_ORDERS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["STOCK_ORDERS_TABLE"])
API_SHARED_TOKEN = os.environ["API_SHARED_TOKEN"]
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")

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


def _invoke_ai_handler(payload: dict[str, Any]) -> dict[str, Any]:
    response = LAMBDA_CLIENT.invoke(
        FunctionName=os.environ["AI_HANDLER_FUNCTION"],
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    body = response["Payload"].read().decode("utf-8")
    return json.loads(body or "{}")


def _json_checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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
        "spread",
        "mid_price",
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

    symbol = str(snapshot["symbol"]).upper()
    captured_at = str(snapshot["captured_at"])
    item = dict(snapshot)
    item["symbol"] = symbol
    item["captured_at"] = captured_at
    item["captured_date"] = captured_at[:10]
    item["snapshot_checksum"] = _json_checksum(snapshot)
    item["symbol_captured_at"] = f"{symbol}#{captured_at}"

    CURRENT_SNAPSHOTS_TABLE.put_item(
        Item=_decimalize(item),
        ConditionExpression="attribute_not_exists(symbol) AND attribute_not_exists(captured_at)",
    )

    return {
        "table": os.environ["CURRENT_SNAPSHOTS_TABLE"],
        "symbol": symbol,
        "captured_at": captured_at,
    }


def _parse_positive_int(raw_value: str | None, *, default: int) -> int:
    if raw_value is None or raw_value == "":
        return default
    parsed = int(raw_value)
    if parsed <= 0:
        raise ValueError("El parámetro `days` debe ser un entero positivo.")
    return parsed


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


def _find_existing_order_duplicates(record_checksums: list[str]) -> list[str]:
    duplicates: list[str] = []
    for chunk_start in range(0, len(record_checksums), 100):
        chunk = record_checksums[chunk_start : chunk_start + 100]
        response = DYNAMODB_CLIENT.batch_get_item(
            RequestItems={
                os.environ["STOCK_ORDERS_TABLE"]: {
                    "Keys": [{"record_checksum": {"S": checksum}} for checksum in chunk],
                    "ProjectionExpression": "record_checksum",
                }
            }
        )
        items = response.get("Responses", {}).get(os.environ["STOCK_ORDERS_TABLE"], [])
        duplicates.extend(item["record_checksum"]["S"] for item in items)
    return duplicates


def _persist_orders(body: dict[str, Any]) -> dict[str, Any]:
    file_name = str(body.get("file_name") or "").strip()
    if not file_name:
        raise ValueError("El payload de movimientos debe incluir `file_name`.")

    raw_bytes = _decode_base64_field(body, "file_content_base64")
    records = _normalize_order_records(raw_bytes)
    duplicates = _find_existing_order_duplicates([record["record_checksum"] for record in records])
    if duplicates:
        raise ValueError("El lote fue rechazado porque uno o más movimientos ya existen en DynamoDB.")

    with STOCK_ORDERS_TABLE.batch_writer() as batch:
        for record in records:
            batch.put_item(Item=_decimalize(record))

    return {
        "table": os.environ["STOCK_ORDERS_TABLE"],
        "file_name": file_name,
        "imported_records": len(records),
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

        body = _parse_body(event)

        if route_key == "POST /ai/query":
            ai_result = _invoke_ai_handler(
                {
                    "prompt": body.get("prompt"),
                    "context": body.get("context", {}),
                    "invoke_model": body.get("invoke_model", False),
                }
            )
            return _response(
                200,
                {
                    "status": "ok",
                    "route": route_key,
                    "ai_result": ai_result,
                },
            )

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
