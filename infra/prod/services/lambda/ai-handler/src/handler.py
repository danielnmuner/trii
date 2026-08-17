import json
import os
from typing import Any

import boto3


BEDROCK_CLIENT = boto3.client("bedrock-runtime")


def _text_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": 200,
        "body": json.dumps(payload),
    }


def _extract_text(response: dict[str, Any]) -> str | None:
    output = response.get("output", {})
    message = output.get("message", {})
    content = message.get("content", [])

    for item in content:
        if "text" in item:
            return item["text"]

    return None


def _invoke_bedrock(prompt: str) -> dict[str, Any]:
    response = BEDROCK_CLIENT.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
    )
    return {
        "model_id": os.environ["BEDROCK_MODEL_ID"],
        "text": _extract_text(response),
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    prompt = event.get("prompt")
    context = event.get("context", {})
    invoke_model = event.get("invoke_model", False)

    if not prompt:
        return _text_response(
            {
                "status": "error",
                "message": "prompt is required",
            }
        )

    requested_sources = sorted(
        key for key, enabled in context.items() if bool(enabled)
    )

    payload = {
        "status": "ok",
        "service": "ai_handler",
        "requested_sources": requested_sources,
        "tables": {
            "current_snapshots": os.environ["CURRENT_SNAPSHOTS_TABLE"],
            "stock_orders": os.environ["STOCK_ORDERS_TABLE"],
            "parsed_invoices": os.environ["PARSED_INVOICES_TABLE"],
        },
        "source_documents_bucket": os.environ["SOURCE_DOCUMENTS_BUCKET"],
    }

    if invoke_model:
        payload["model_result"] = _invoke_bedrock(prompt)
    else:
        payload["model_result"] = {
            "skipped": True,
            "reason": "Set invoke_model=true to call Bedrock from this placeholder implementation.",
            "model_id": os.environ["BEDROCK_MODEL_ID"],
        }

    return _text_response(payload)
