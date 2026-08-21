from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from urllib.parse import urlencode

from trii_ingestion.services.invoice_archives import PreparedInvoiceDocument


class ApiGatewayClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiGatewayClient:
    base_url: str
    token: str
    timeout_seconds: int = 30

    def submit_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/snapshots", {"snapshot": snapshot})

    def get_recent_snapshots(self, *, days: int = 7) -> dict[str, Any]:
        return self._get_json("/snapshots", {"days": days})

    def get_analytics_catalog(self) -> dict[str, Any]:
        return self._get_json("/analytics/catalog", {})

    def get_analytics_snapshot(self, *, symbol: str) -> dict[str, Any]:
        return self._get_json("/analytics/snapshot", {"symbol": symbol})

    def get_analytics_zscore_opportunities(
        self,
        *,
        symbol: str,
        trading_date: str,
        limit: int = 250,
    ) -> dict[str, Any]:
        return self._get_json(
            "/analytics/zscore-opportunities",
            {
                "symbol": symbol,
                "trading_date": trading_date,
                "limit": limit,
            },
        )

    def get_analytics_daily_closing(
        self,
        *,
        symbol: str,
        limit: int = 500,
    ) -> dict[str, Any]:
        return self._get_json(
            "/analytics/daily-closing",
            {
                "symbol": symbol,
                "limit": limit,
            },
        )

    def submit_stock_orders(
        self,
        *,
        file_name: str,
        records: list[dict[str, Any]] | None = None,
        source_file_checksum: str | None = None,
        raw_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"file_name": file_name}
        if records is not None:
            payload["records"] = records
            if source_file_checksum:
                payload["source_file_checksum"] = source_file_checksum
        elif raw_bytes is not None:
            payload["file_content_base64"] = base64.b64encode(raw_bytes).decode("utf-8")
        else:
            raise ApiGatewayClientError("La carga de órdenes requiere `records` o `raw_bytes`.")
        return self._post_json("/orders", payload)

    def submit_invoice_archives(self, *, documents: list[PreparedInvoiceDocument]) -> dict[str, Any]:
        return self._post_json(
            "/invoices",
            {
                "documents": [
                    {
                        "archive_name": document.archive_name,
                        "archive_stem": document.archive_stem,
                        "xml_file_name": document.xml_file_name,
                        "xml_content_base64": base64.b64encode(document.xml_bytes).decode("utf-8"),
                        "pdf_file_name": document.pdf_file_name,
                        "pdf_content_base64": base64.b64encode(document.pdf_bytes).decode("utf-8"),
                    }
                    for document in documents
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

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        encoded_params = urlencode({key: value for key, value in params.items() if value is not None})
        query_suffix = f"?{encoded_params}" if encoded_params else ""
        response = self._perform_request(
            request.Request(
                url=f"{self.base_url.rstrip('/')}{path}{query_suffix}",
                headers={"X-Api-Token": self.token},
                method="GET",
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
