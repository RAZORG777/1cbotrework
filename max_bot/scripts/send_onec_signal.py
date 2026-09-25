"""Имитирует сигнал 1С (только для тестового стенда).

Запуск из каталога max_bot:  python -m scripts.send_onec_signal cancel|finish <appointment_id>
"""

from __future__ import annotations

import sys

import httpx

from app.config import load_settings

KINDS = {"cancel": "cancel-visit", "finish": "finish-visit"}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in KINDS:
        print(__doc__)
        return 2
    settings = load_settings()
    url = f"http://127.0.0.1:{settings.PORT}/max/api/v1/internal/{KINDS[argv[0]]}"
    response = httpx.post(
        url,
        json={"appointment_id": argv[1]},
        headers={"X-Bot-Secret": settings.ONEC_WEBHOOK_SECRET},
        timeout=10,
    )
    print(f"{KINDS[argv[0]]} → HTTP {response.status_code}: {response.text}")
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
