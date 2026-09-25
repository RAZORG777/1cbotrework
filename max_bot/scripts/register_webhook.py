"""Подписывает MAX-бота на вебхук с секретом (contracts/messenger-webhooks.md).

Запуск из каталога max_bot:  python -m scripts.register_webhook
URL вебхука — только HTTPS на 443 с доверенным сертификатом (требование MAX).
"""

from __future__ import annotations

import sys

import httpx

from app.config import load_settings


def main() -> int:
    settings = load_settings()
    payload = {
        "url": f"{settings.WEBAPP_URL}/max/webhook",
        "update_types": ["bot_started", "message_created", "message_callback"],
        "secret": settings.MAX_WEBHOOK_SECRET,
    }
    response = httpx.post(
        f"{settings.MAX_API_URL}/subscriptions",
        json=payload,
        headers={"Authorization": settings.MAX_BOT_TOKEN},
        timeout=15,
    )
    # Токен и секрет в вывод не попадают.
    print(f"POST /subscriptions → HTTP {response.status_code}: {response.text[:300]}")
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
