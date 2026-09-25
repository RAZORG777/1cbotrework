"""Регистрирует вебхук Telegram с secret_token (contracts/messenger-webhooks.md).

Запуск из каталога telegram_bot:  python -m scripts.register_webhook
"""

from __future__ import annotations

import sys

import httpx

from app.config import load_settings


def main() -> int:
    settings = load_settings()
    url = f"{settings.TELEGRAM_API_BASE}/bot{settings.BOT_TOKEN}/setWebhook"
    payload = {
        "url": f"{settings.WEBAPP_URL}/admin/webhook",
        "secret_token": settings.TG_WEBHOOK_SECRET,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False,
    }
    response = httpx.post(url, json=payload, timeout=15)
    data = response.json()
    # Токен в вывод не попадает.
    print(
        f"setWebhook → HTTP {response.status_code}: ok={data.get('ok')} {data.get('description', '')}"
    )
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
