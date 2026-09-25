"""Отправка сообщений через MAX Bot API (токен только в заголовке Authorization, research R3)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger

RETRY_PAUSE = 2.0


class MaxMessenger:
    def __init__(
        self,
        api_url: str,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_pause: float = RETRY_PAUSE,
    ):
        self.api_url = api_url.rstrip("/")
        self._token = token
        self._transport = transport
        self._retry_pause = retry_pause

    async def _post(self, path: str, params: dict, payload: dict) -> bool:
        headers = {"Authorization": self._token, "Content-Type": "application/json"}
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                    response = await client.post(
                        f"{self.api_url}{path}", params=params, json=payload, headers=headers
                    )
                if response.status_code == 200:
                    return True
                logger.error("MAX {}: HTTP {}", path, response.status_code)
                return False
            except httpx.TransportError as exc:
                logger.warning(
                    "MAX {}: сетевая ошибка, попытка {}/3 ({})", path, attempt, type(exc).__name__
                )
                if attempt < 3:
                    await asyncio.sleep(self._retry_pause)
        logger.error("MAX {}: не доставлено после 3 попыток", path)
        return False

    async def send_message(self, user_id: str, text: str, keyboard: list | None = None) -> bool:
        payload: dict[str, Any] = {"text": text, "format": "html"}
        if keyboard:
            payload["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": keyboard}}]
        ok = await self._post("/messages", {"user_id": user_id}, payload)
        if ok:
            logger.info("Сообщение доставлено user_id={}", user_id)
        return ok

    async def answer_callback(self, callback_id: str, notification: str | None = None) -> None:
        payload: dict[str, Any] = {}
        if notification:
            payload["notification"] = notification
        await self._post("/answers", {"callback_id": callback_id}, payload)
