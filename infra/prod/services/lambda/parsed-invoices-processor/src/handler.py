import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import unquote_plus
import xml.etree.ElementTree as ET

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


S3_CLIENT = boto3.client("s3")
DYNAMODB_CLIENT = boto3.client("dynamodb")
SERIALIZER = TypeSerializer()

SOURCE_DOCUMENTS_BUCKET = os.environ["SOURCE_DOCUMENTS_BUCKET"]
PARSED_INVOICES_TABLE = os.environ["PARSED_INVOICES_TABLE"]
PARSED_INVOICES_CHECKSUM_INDEX = "source-xml-checksum-index"

ATTACHED_DOCUMENT_NS = {
    "ad": "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
INVOICE_NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in item.items() if value is not None}


def _to_decimal(raw_value: str | None) -> Decimal | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    return Decimal(normalized)


def _require_text(root: ET.Element, xpath: str, namespaces: dict[str, str]) -> str:
    value = root.findtext(xpath, namespaces=namespaces)
    if value is None or not str(value).strip():
        raise ValueError(f"Missing required XML field: {xpath}")
    return str(value).strip()


def _optional_text(root: ET.Element, xpath: str, namespaces: dict[str, str]) -> str | None:
    value = root.findtext(xpath, namespaces=namespaces)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_user_name(raw_value: str) -> str:
    normalized = "-".join(str(raw_value or "").strip().lower().split())
    if not normalized:
        raise ValueError("Could not derive user_name from S3 key.")
    return normalized


def _extract_order_side(line_description: str | None) -> str | None:
    if not line_description:
        return None
    description = line_description.upper()
    if "COMPRA" in description:
        return "buy"
    if "VENTA" in description:
        return "sell"
    return None


def _resolve_related_keys(bucket: str, object_key: str) -> tuple[str, str | None, str]:
    if not object_key.startswith("invoices/"):
        raise ValueError(f"Unsupported S3 key outside invoices/: {object_key}")
    if not object_key.lower().endswith(".pdf"):
        raise ValueError(f"Unsupported S3 key for invoice processing: {object_key}")

    prefix = object_key.rsplit("/", 1)[0] + "/"
    response = S3_CLIENT.list_objects_v2(Bucket=bucket, Prefix=prefix)
    contents = response.get("Contents", [])
    xml_candidates = sorted(
        str(item["Key"]) for item in contents if str(item.get("Key", "")).lower().endswith(".xml")
    )
    pdf_candidates = sorted(
        str(item["Key"]) for item in contents if str(item.get("Key", "")).lower().endswith(".pdf")
    )
    if not xml_candidates:
        raise ValueError(f"No XML sibling found for invoice prefix: {prefix}")

    return xml_candidates[0], (pdf_candidates[0] if pdf_candidates else None), prefix


def _load_object_bytes(bucket: str, key: str) -> bytes:
    response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _derive_user_name_from_key(key: str) -> str:
    parts = key.split("/")
    if len(parts) < 3:
        raise ValueError(f"Unsupported invoice key structure: {key}")
    return _normalize_user_name(parts[1])


def _parse_invoice_xml(xml_bytes: bytes, *, source_xml_s3_key: str, source_pdf_s3_key: str | None, source_folder_s3_prefix: str) -> dict[str, Any]:
    outer_root = ET.fromstring(xml_bytes)
    inner_xml = _require_text(
        outer_root,
        "./cac:Attachment/cac:ExternalReference/cbc:Description",
        ATTACHED_DOCUMENT_NS,
    )
    invoice_root = ET.fromstring(inner_xml)

    issue_date = _require_text(invoice_root, "./cbc:IssueDate", INVOICE_NS)
    issue_time = _require_text(invoice_root, "./cbc:IssueTime", INVOICE_NS)
    issued_at = datetime.fromisoformat(f"{issue_date}T{issue_time}").isoformat()
    issued_month = issued_at[:7]
    invoice_number = _require_text(invoice_root, "./cbc:ID", INVOICE_NS)
    invoice_uuid = _require_text(invoice_root, "./cbc:UUID", INVOICE_NS)
    order_reference_id = _optional_text(invoice_root, "./cac:OrderReference/cbc:ID", INVOICE_NS)
    line_description = _optional_text(
        invoice_root,
        "./cac:InvoiceLine/cac:Item/cbc:Description",
        INVOICE_NS,
    )

    user_name = _derive_user_name_from_key(source_xml_s3_key)
    item = {
        "invoice_uuid": invoice_uuid,
        "invoice_number": invoice_number,
        "user_name": user_name,
        "order_reference_id": order_reference_id,
        "user_order_reference_id": None if order_reference_id is None else f"{user_name}#{order_reference_id}",
        "issued_at": issued_at,
        "issued_month": issued_month,
        "user_issued_month": f"{user_name}#{issued_month}",
        "issued_at_invoice_number": f"{issued_at}#{invoice_number}",
        "supplier_tax_id": _optional_text(
            invoice_root,
            "./cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID",
            INVOICE_NS,
        ),
        "supplier_name": _optional_text(
            invoice_root,
            "./cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName",
            INVOICE_NS,
        ),
        "customer_tax_id": _optional_text(
            invoice_root,
            "./cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID",
            INVOICE_NS,
        ),
        "customer_name": _optional_text(
            invoice_root,
            "./cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName",
            INVOICE_NS,
        ),
        "currency": _optional_text(invoice_root, "./cbc:DocumentCurrencyCode", INVOICE_NS),
        "invoice_type_code": _optional_text(invoice_root, "./cbc:InvoiceTypeCode", INVOICE_NS),
        "payable_amount": _to_decimal(
            _optional_text(invoice_root, "./cac:LegalMonetaryTotal/cbc:PayableAmount", INVOICE_NS)
        ),
        "tax_exclusive_amount": _to_decimal(
            _optional_text(invoice_root, "./cac:LegalMonetaryTotal/cbc:LineExtensionAmount", INVOICE_NS)
        ),
        "tax_inclusive_amount": _to_decimal(
            _optional_text(invoice_root, "./cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", INVOICE_NS)
        ),
        "tax_amount": _to_decimal(
            _optional_text(invoice_root, "./cac:TaxTotal/cbc:TaxAmount", INVOICE_NS)
        ),
        "line_description": line_description,
        "line_item_code": _optional_text(
            invoice_root,
            "./cac:InvoiceLine/cac:Item/cac:SellersItemIdentification/cbc:ID",
            INVOICE_NS,
        ),
        "extracted_symbol": None,
        "extracted_order_side": _extract_order_side(line_description),
        "dian_validation_status": None,
        "source_xml_checksum": hashlib.sha256(xml_bytes).hexdigest(),
        "source_folder_s3_prefix": source_folder_s3_prefix,
        "source_xml_s3_key": source_xml_s3_key,
        "source_pdf_s3_key": source_pdf_s3_key,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    return item


def _find_existing_invoice_by_checksum(source_xml_checksum: str) -> dict[str, Any] | None:
    response = DYNAMODB_CLIENT.query(
        TableName=PARSED_INVOICES_TABLE,
        IndexName=PARSED_INVOICES_CHECKSUM_INDEX,
        KeyConditionExpression="source_xml_checksum = :source_xml_checksum",
        ExpressionAttributeValues={
            ":source_xml_checksum": SERIALIZER.serialize(source_xml_checksum),
        },
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None
    return items[0]


def _persist_invoice(item: dict[str, Any]) -> dict[str, Any]:
    existing_item = _find_existing_invoice_by_checksum(item["source_xml_checksum"])
    if existing_item:
        return {
            "status": "duplicate",
            "invoice_uuid": item["invoice_uuid"],
            "source_xml_checksum": item["source_xml_checksum"],
            "source_xml_s3_key": item["source_xml_s3_key"],
        }

    try:
        DYNAMODB_CLIENT.put_item(
            TableName=PARSED_INVOICES_TABLE,
            Item=_serialize_item(item),
            ConditionExpression="attribute_not_exists(invoice_uuid)",
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return {
                "status": "duplicate",
                "invoice_uuid": item["invoice_uuid"],
                "source_xml_checksum": item["source_xml_checksum"],
                "source_xml_s3_key": item["source_xml_s3_key"],
            }
        raise

    return {
        "status": "stored",
        "invoice_uuid": item["invoice_uuid"],
        "invoice_number": item["invoice_number"],
        "source_xml_checksum": item["source_xml_checksum"],
        "source_xml_s3_key": item["source_xml_s3_key"],
        "source_pdf_s3_key": item["source_pdf_s3_key"],
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    detail = event.get("detail") or {}
    bucket = str(((detail.get("bucket") or {}).get("name")) or "")
    object_key = unquote_plus(str(((detail.get("object") or {}).get("key")) or ""))
    if bucket != SOURCE_DOCUMENTS_BUCKET:
        return {"status": "ignored", "reason": "unexpected_bucket", "bucket": bucket}
    if not object_key.startswith("invoices/"):
        return {"status": "ignored", "reason": "unexpected_key_prefix", "key": object_key}
    if not object_key.lower().endswith(".pdf"):
        return {"status": "ignored", "reason": "waiting_for_pdf_event", "key": object_key}

    source_xml_s3_key, source_pdf_s3_key, source_folder_s3_prefix = _resolve_related_keys(bucket, object_key)
    xml_bytes = _load_object_bytes(bucket, source_xml_s3_key)
    item = _parse_invoice_xml(
        xml_bytes,
        source_xml_s3_key=source_xml_s3_key,
        source_pdf_s3_key=source_pdf_s3_key,
        source_folder_s3_prefix=source_folder_s3_prefix,
    )
    result = _persist_invoice(item)
    result["bucket"] = bucket
    result["source_folder_s3_prefix"] = source_folder_s3_prefix
    print(json.dumps(result, sort_keys=True))
    return result
