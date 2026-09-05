from __future__ import annotations

import importlib.util
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus

import pytest
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_SRC = ROOT_DIR / "infra" / "prod" / "services" / "lambda" / "parsed-invoices-processor" / "src"
if str(LAMBDA_SRC) not in sys.path:
    sys.path.insert(0, str(LAMBDA_SRC))

os.environ.setdefault("SOURCE_DOCUMENTS_BUCKET", "test-source-documents")
os.environ.setdefault("PARSED_INVOICES_TABLE", "test-parsed-invoices")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

HANDLER_SPEC = importlib.util.spec_from_file_location(
    "parsed_invoices_processor_handler",
    LAMBDA_SRC / "handler.py",
)
if HANDLER_SPEC is None or HANDLER_SPEC.loader is None:
    raise RuntimeError("Could not load parsed invoices processor handler module.")

handler = importlib.util.module_from_spec(HANDLER_SPEC)
HANDLER_SPEC.loader.exec_module(handler)
DESERIALIZER = TypeDeserializer()
SAMPLE_XML = (ROOT_DIR / "nuco-factura.xml").read_bytes()


class FakeS3Client:
    def __init__(self) -> None:
        self.bucket = "test-source-documents"
        self.prefix = "invoices/daniel-muner/2026/08/14/invoice-001/"
        self.xml_key = f"{self.prefix}invoice.xml"
        self.pdf_key = f"{self.prefix}invoice.pdf"

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict:
        assert Bucket == self.bucket
        assert Prefix == self.prefix
        return {
            "Contents": [
                {"Key": self.xml_key},
                {"Key": self.pdf_key},
            ]
        }

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        assert Bucket == self.bucket
        assert Key == self.xml_key
        return {"Body": BytesIO(SAMPLE_XML)}


class FakeDynamoClient:
    def __init__(self) -> None:
        self.query_calls: list[dict] = []
        self.put_calls: list[dict] = []
        self.duplicate_on_query = False
        self.duplicate_on_put = False

    def query(self, **kwargs) -> dict:
        self.query_calls.append(kwargs)
        if self.duplicate_on_query:
            return {
                "Items": [
                    {
                        "invoice_uuid": {"S": "existing-invoice"},
                        "source_xml_checksum": {"S": "existing-checksum"},
                    }
                ]
            }
        return {"Items": []}

    def put_item(self, **kwargs) -> dict:
        if self.duplicate_on_put:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.put_calls.append(kwargs)
        return {}


def _deserialize_item(item: dict[str, dict]) -> dict[str, object]:
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def _pdf_event(key: str) -> dict:
    return {
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {
            "bucket": {"name": "test-source-documents"},
            "object": {"key": quote_plus(key)},
        },
    }


def test_parse_invoice_xml_extracts_relevant_fields() -> None:
    result = handler._parse_invoice_xml(
        SAMPLE_XML,
        source_xml_s3_key="invoices/daniel-muner/2026/08/14/invoice-001/invoice.xml",
        source_pdf_s3_key="invoices/daniel-muner/2026/08/14/invoice-001/invoice.pdf",
        source_folder_s3_prefix="invoices/daniel-muner/2026/08/14/invoice-001/",
    )

    assert result["invoice_uuid"].startswith("1df6bcd2")
    assert result["invoice_number"] == "LIBO1861696"
    assert result["user_name"] == "daniel-muner"
    assert result["order_reference_id"] == "1862128"
    assert result["user_order_reference_id"] == "daniel-muner#1862128"
    assert result["user_issued_month"] == "daniel-muner#2026-08"
    assert str(result["payable_amount"]) == "7436.16"
    assert str(result["tax_amount"]) == "1187.28"
    assert result["extracted_order_side"] == "sell"
    assert result["source_xml_s3_key"].endswith("invoice.xml")
    assert result["source_pdf_s3_key"].endswith("invoice.pdf")


def test_handler_ignores_xml_event_until_pdf_arrives() -> None:
    response = handler.handler(
        _pdf_event("invoices/daniel-muner/2026/08/14/invoice-001/invoice.xml"),
        None,
    )

    assert response["status"] == "ignored"
    assert response["reason"] == "waiting_for_pdf_event"


def test_handler_processes_pdf_event_and_persists_invoice_and_checksum() -> None:
    fake_s3 = FakeS3Client()
    fake_dynamo = FakeDynamoClient()
    handler.S3_CLIENT = fake_s3
    handler.DYNAMODB_CLIENT = fake_dynamo

    response = handler.handler(_pdf_event(fake_s3.pdf_key), None)

    assert response["status"] == "stored"
    assert response["invoice_number"] == "LIBO1861696"
    assert response["bucket"] == "test-source-documents"
    assert len(fake_dynamo.query_calls) == 1
    assert len(fake_dynamo.put_calls) == 1

    query_call = fake_dynamo.query_calls[0]
    put_call = fake_dynamo.put_calls[0]
    invoice_item = _deserialize_item(put_call["Item"])

    assert query_call["TableName"] == "test-parsed-invoices"
    assert query_call["IndexName"] == "source-xml-checksum-index"
    assert put_call["TableName"] == "test-parsed-invoices"
    assert invoice_item["user_name"] == "daniel-muner"
    assert invoice_item["source_folder_s3_prefix"] == fake_s3.prefix
    assert invoice_item["source_xml_s3_key"] == fake_s3.xml_key
    assert invoice_item["source_pdf_s3_key"] == fake_s3.pdf_key


def test_handler_returns_duplicate_when_checksum_or_invoice_already_exists() -> None:
    fake_s3 = FakeS3Client()
    fake_dynamo = FakeDynamoClient()
    fake_dynamo.duplicate_on_query = True
    handler.S3_CLIENT = fake_s3
    handler.DYNAMODB_CLIENT = fake_dynamo

    response = handler.handler(_pdf_event(fake_s3.pdf_key), None)

    assert response["status"] == "duplicate"
    assert response["source_xml_s3_key"] == fake_s3.xml_key
    assert response["bucket"] == "test-source-documents"


def test_handler_returns_duplicate_when_invoice_uuid_already_exists_during_put() -> None:
    fake_s3 = FakeS3Client()
    fake_dynamo = FakeDynamoClient()
    fake_dynamo.duplicate_on_put = True
    handler.S3_CLIENT = fake_s3
    handler.DYNAMODB_CLIENT = fake_dynamo

    response = handler.handler(_pdf_event(fake_s3.pdf_key), None)

    assert response["status"] == "duplicate"
    assert response["source_xml_s3_key"] == fake_s3.xml_key
