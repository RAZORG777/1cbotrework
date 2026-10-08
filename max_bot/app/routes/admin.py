"""Админка: страница интерфейса и прежние адреса (specs/006-admin-devtool).

Интерфейс — статические файлы app/admin_ui/ без сборки и без CDN; данные — JSON API
app/routes/admin_api.py. Всё под Basic-авторизацией администратора.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from ..auth import require_admin
from ..logging import log_buffer
from ..reminders import send_reminder

router = APIRouter(prefix="/admin")
UI_DIR = Path(__file__).resolve().parent.parent / "admin_ui"
UI_FILES = {"admin.css": "text/css", "admin.js": "text/javascript"}
PAGE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
}


@router.get("/logs", response_class=PlainTextResponse)
async def admin_logs(admin: str = Depends(require_admin)) -> str:
    return "\n".join(reversed(log_buffer)) if log_buffer else "Логи пусты..."


@router.get("", include_in_schema=False)
async def admin_page(admin: str = Depends(require_admin)):
    return FileResponse(
        UI_DIR / "index.html", media_type="text/html; charset=utf-8", headers=PAGE_HEADERS
    )


@router.get("/ui/{name}", include_in_schema=False)
async def admin_asset(name: str, admin: str = Depends(require_admin)):
    if name not in UI_FILES:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    return FileResponse(UI_DIR / name, media_type=f"{UI_FILES[name]}; charset=utf-8")


@router.post("/send-reminder")
async def admin_send_reminder(
    appointment_id: str, kind: str = "24h", admin: str = Depends(require_admin)
) -> dict:
    """Отправить напоминание сейчас — для проверки кнопок на тестовом стенде (этап 2)."""
    await send_reminder(appointment_id, "2h" if kind == "2h" else "24h")
    return {"status": "ok"}
