import base64
import json
import os
from typing import Any

import boto3


LAMBDA_CLIENT = boto3.client("lambda")


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body")
    if not raw_body:
        return {}

    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    if isinstance(raw_body, str):
        return json.loads(raw_body)

    return raw_body


def _invoke_ai_handler(payload: dict[str, Any]) -> dict[str, Any]:
    response = LAMBDA_CLIENT.invoke(
        FunctionName=os.environ["AI_HANDLER_FUNCTION"],
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    body = response["Payload"].read().decode("utf-8")
    return json.loads(body or "{}")


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

    accepted_routes = {
        "POST /snapshots": "snapshot",
        "POST /orders": "orders",
        "POST /invoices": "invoice",
        "POST /documents": "document",
    }

    if route_key in accepted_routes:
        return _response(
            202,
            {
                "status": "accepted",
                "route": route_key,
                "resource_type": accepted_routes[route_key],
                "message": "Placeholder handler deployed. Persistence logic will be implemented on top of this contract.",
                "received_keys": sorted(body.keys()),
            },
        )

    return _response(
        404,
        {
            "status": "error",
            "message": f"Unsupported route: {route_key}",
        },
    )
