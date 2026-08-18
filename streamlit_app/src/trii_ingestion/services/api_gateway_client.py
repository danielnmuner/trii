from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class ApiGatewayClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiGatewayClient:
    base_url: str
    token: str
    timeout_seconds: int = 30

    def submit_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/snapshots", {"snapshot": snapshot})

    def submit_stock_orders(self, *, file_name: str, raw_bytes: bytes) -> dict[str, Any]:
        return self._post_json(
            "/orders",
            {
                "file_name": file_name,
                "file_content_base64": base64.b64encode(raw_bytes).decode("utf-8"),
            },
        )

    def submit_invoice_archives(self, *, files: list[tuple[str, bytes]]) -> dict[str, Any]:
        return self._post_json(
            "/invoices",
            {
                "files": [
                    {
                        "file_name": file_name,
                        "content_base64": base64.b64encode(raw_bytes).decode("utf-8"),
                    }
                    for file_name, raw_bytes in files
                ]
            },
        )

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._perform_request(
            request.Request(
                url=f"{self.base_url.rstrip('/')}{path}",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Token": self.token,
                },
                method="POST",
            )
        )
        return self._decode_response(response)

    def _perform_request(self, api_request: request.Request):
        try:
            return request.urlopen(api_request, timeout=self.timeout_seconds)
        except error.HTTPError as exc:
            raise ApiGatewayClientError(self._decode_error_payload(exc)) from exc
        except error.URLError as exc:
            raise ApiGatewayClientError(
                "No fue posible conectarse con el API Gateway configurado."
            ) from exc

    @staticmethod
    def _decode_response(http_response) -> dict[str, Any]:
        raw_payload = http_response.read().decode("utf-8")
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ApiGatewayClientError("El API Gateway devolvió una respuesta no válida.") from exc

    @staticmethod
    def _decode_error_payload(exc: error.HTTPError) -> str:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return f"El API Gateway respondió con error HTTP {exc.code}."
        return str(payload.get("message") or payload.get("status") or f"HTTP {exc.code}")
