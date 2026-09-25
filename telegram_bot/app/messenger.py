"""Отправка сообщений в Telegram через TELEGRAM_API_BASE (в проде — посредник Cloudflare)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger

RETRY_PAUSE = 2.0


class TelegramMessenger:
    def __init__(
        self,
        api_base: str,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_pause: float = RETRY_PAUSE,
    ):
        self.api_base = api_base.rstrip("/")
        self._token = token
        self._transport = transport
        self._retry_pause = retry_pause

    async def call(self, method: str, payload: dict) -> dict[str, Any] | None:
        url = f"{self.api_base}/bot{self._token}/{method}"
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                    response = await client.post(url, json=payload)
                data = response.json()
                if response.status_code == 200 and data.get("ok"):
                    return data
                logger.error(
                    "Telegram {}: HTTP {} {}", method, response.status_code, data.get("description")
                )
                return None
            except (httpx.TransportError, ValueError) as exc:
                logger.warning(
                    "Telegram {}: сетевая ошибка, попытка {}/3 ({})",
                    method,
                    attempt,
                    type(exc).__name__,
                )
                if attempt < 3:
                    await asyncio.sleep(self._retry_pause)
        logger.error("Telegram {}: не доставлено после 3 попыток", method)
        return None

    async def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        ok = await self.call("sendMessage", payload) is not None
        if ok:
            logger.info("Сообщение доставлено chat_id={}", chat_id)
        return ok

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self.call("answerCallbackQuery", payload)
