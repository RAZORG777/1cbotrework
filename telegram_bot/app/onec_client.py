"""Клиент HTTP-сервиса 1С УМЦ. Единственный путь к 1С (принцип II).

Контракт — docs/onec-contract.md (источник истины — onec/http-service.bsl).
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger


class OneCError(Exception):
    """1С ответила, но ответ ошибочный или неожиданного формата."""


class OneCUnavailable(OneCError):
    """1С недоступна (сеть, таймаут, HTTP 5xx)."""


class OneCClient:
    def __init__(
        self,
        base_url: str,
        auth: tuple[str, str],
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self._transport = transport

    async def _request(
        self, method: str, endpoint: str, params: dict | None = None, json: dict | None = None
    ) -> Any:
        url = f"{self.base_url}/{endpoint}"
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(
                    auth=self.auth, timeout=self.timeout, transport=self._transport
                ) as client:
                    response = await client.request(method, url, params=params, json=json)
                break
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                # Запрос не ушёл — безопасно повторить один раз.
                if attempt == 2:
                    logger.error("1С недоступна: {} {} ({})", method, endpoint, type(exc).__name__)
                    raise OneCUnavailable(endpoint) from exc
            except httpx.TransportError as exc:
                logger.error("1С: сетевая ошибка {} {} ({})", method, endpoint, type(exc).__name__)
                raise OneCUnavailable(endpoint) from exc
        if response.status_code >= 500:
            logger.error("1С: HTTP {} на {} {}", response.status_code, method, endpoint)
            raise OneCUnavailable(f"{endpoint}: HTTP {response.status_code}")
        if response.status_code >= 400:
            logger.error("1С: HTTP {} на {} {}", response.status_code, method, endpoint)
            raise OneCError(f"{endpoint}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            logger.error("1С: ответ не JSON на {} {}", method, endpoint)
            raise OneCError(f"{endpoint}: invalid JSON") from exc

    @staticmethod
    def _expect(value: Any, kind: type, endpoint: str) -> Any:
        if not isinstance(value, kind):
            raise OneCError(f"{endpoint}: неожиданный формат ответа")
        return value

    async def get_doctors(self, branch: str | None = None, date: str | None = None) -> list:
        params = {k: v for k, v in {"branch": branch, "date": date}.items() if v}
        data = await self._request("GET", "doctors", params=params)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            data = data["data"]
        return self._expect(data, list, "doctors")

    async def get_services(self, doctor_id: str | None = None) -> list:
        params = {"doctor_id": doctor_id} if doctor_id else {}
        data = await self._request("GET", "services", params=params)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            data = data["data"]
        return self._expect(data, list, "services")

    async def get_schedule(
        self,
        doctor_id: str,
        date: str | None = None,
        branch: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        params: dict[str, str] = {"doctor_id": doctor_id}
        if branch:
            params["branch"] = branch
        if start_date and end_date:
            params["start_date"] = start_date
            params["end_date"] = end_date
        elif date:
            params["date"] = date
        data = await self._request("GET", "schedule", params=params)
        return self._expect(data, dict, "schedule")

    async def create_booking(self, payload: dict) -> dict:
        return self._expect(await self._request("POST", "book", json=payload), dict, "book")

    async def reschedule(self, payload: dict) -> dict:
        return self._expect(
            await self._request("POST", "reschedule", json=payload), dict, "reschedule"
        )

    async def cancel_booking(self, appointment_id: str) -> dict:
        data = await self._request("POST", "cancel", json={"appointment_id": appointment_id})
        return self._expect(data, dict, "cancel")
