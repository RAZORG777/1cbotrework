"""API рассылок в админке (specs/007-broadcasts/contracts/broadcasts.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from .. import broadcasts, metrics, subscribers
from ..auth import require_admin, require_admin_action
from ..db import MSK, session_scope
from ..models import Broadcast

router = APIRouter(prefix="/admin/api/broadcasts")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(MSK).replace(tzinfo=None)
    return value.isoformat(timespec="seconds")


def _error(status: int, code: str, message: str | None = None) -> HTTPException:
    detail = {"error": code}
    if message:
        detail["message"] = message
    return HTTPException(status_code=status, detail=detail)


class ButtonIn(BaseModel):
    type: Literal["none", "book", "url"] = "none"
    text: str = ""
    url: str = ""


class DraftIn(BaseModel):
    kind: Literal["service", "promo"]
    audience: Literal["all", "active", "branch"] = "all"
    branch: str = ""
    text: str
    image: str = ""
    button: ButtonIn = ButtonIn()


class TestIn(DraftIn):
    chat_id: str


def _draft(body: DraftIn) -> broadcasts.Draft:
    markup, error = broadcasts.normalize_text(body.text)
    draft = broadcasts.Draft(
        kind=body.kind,
        audience=body.audience,
        branch=body.branch,
        text=markup,
        image=body.image,
        button_type=body.button.type,
        button_text=body.button.text,
        button_url=body.button.url,
    )
    error = error or broadcasts.check_draft(draft)
    if error:
        raise _error(422, "BAD_DRAFT", error)
    return draft


def _view(state, bc: Broadcast, full: bool = False) -> dict:
    data = {
        "id": bc.id,
        "created_at": _iso(bc.created_at),
        "created_by": bc.created_by,
        "kind": bc.kind,
        "audience": bc.audience,
        "branch": bc.branch,
        "image": bc.image,
        "button_type": bc.button_type,
        "button_text": bc.button_text,
        "button_url": bc.button_url,
        "status": bc.status,
        "total": bc.total,
        "sent": bc.sent,
        "failed": bc.failed,
        "blocked": bc.blocked,
        "started_at": _iso(bc.started_at),
        "finished_at": _iso(bc.finished_at),
        "running": broadcasts.is_running(state, bc.id),
    }
    plain = broadcasts.html.unescape(broadcasts.TAG_RE.sub("", bc.text))
    data["text" if full else "preview"] = bc.text if full else plain[:140]
    return data


@router.get("")
async def list_broadcasts(request: Request, admin: str = Depends(require_admin)) -> dict:
    state = request.app.state
    with session_scope(state.session_factory) as session:
        items = session.scalars(select(Broadcast).order_by(Broadcast.id.desc()).limit(50)).all()
        return {
            "items": [_view(state, bc) for bc in items],
            "subscribers": subscribers.stats(session),
            "branches": list(broadcasts.BRANCHES),
            "limits": {
                "text": broadcasts.TEXT_LIMIT,
                "caption": broadcasts.CAPTION_LIMIT,
                "button": broadcasts.BUTTON_TEXT_LIMIT,
            },
            "platform": broadcasts.PLATFORM,
            "recipients": sorted(state.settings.admin_ids),
        }


@router.get("/audience")
async def audience(
    request: Request,
    kind: Literal["service", "promo"] = "service",
    audience: Literal["all", "active", "branch"] = "all",
    branch: str = "",
    admin: str = Depends(require_admin),
) -> dict:
    with session_scope(request.app.state.session_factory) as session:
        return {"count": broadcasts.count_recipients(session, kind, audience, branch)}


@router.post("/image")
async def upload_image(request: Request, admin: str = Depends(require_admin_action)) -> dict:
    length = int(request.headers.get("content-length") or 0)
    if length > broadcasts.IMAGE_LIMIT:
        raise _error(422, "BAD_IMAGE", "Картинка больше 5 МБ.")
    name = broadcasts.save_image(await request.body())
    if name is None:
        raise _error(422, "BAD_IMAGE", "Нужна картинка JPEG или PNG до 5 МБ.")
    return {"image": name}


@router.get("/image/{name}")
async def get_image(name: str, admin: str = Depends(require_admin)):
    path = broadcasts.image_path(name)
    if path is None:
        raise _error(404, "NOT_FOUND")
    return FileResponse(path, media_type="image/png" if name.endswith(".png") else "image/jpeg")


@router.post("/test")
async def send_test(body: TestIn, request: Request, admin: str = Depends(require_admin_action)):
    state = request.app.state
    if body.chat_id not in state.settings.admin_ids:
        raise _error(403, "NOT_ADMIN_RECIPIENT")
    ok, detail = await broadcasts.send_test(state, _draft(body), body.chat_id)
    metrics.inc("admin_actions")
    logger.info("Админка: пробная рассылка в {} ({})", body.chat_id, admin)
    if not ok:
        raise _error(502, "SEND_FAILED", detail)
    return {"status": "ok"}


@router.post("")
async def create_broadcast(
    body: DraftIn, request: Request, admin: str = Depends(require_admin_action)
) -> dict:
    state = request.app.state
    bc = broadcasts.create(state, _draft(body), admin)
    if bc is None:
        raise _error(409, "NO_RECIPIENTS", "Нет получателей для этой аудитории.")
    metrics.inc("admin_actions")
    logger.info(
        "Админка: запущена рассылка {} ({}, {}), получателей {} ({})",
        bc.id,
        bc.kind,
        bc.audience,
        bc.total,
        admin,
    )
    return {"id": bc.id, "total": bc.total}


@router.get("/{broadcast_id}")
async def get_broadcast(
    broadcast_id: int, request: Request, admin: str = Depends(require_admin)
) -> dict:
    state = request.app.state
    with session_scope(state.session_factory) as session:
        bc = session.get(Broadcast, broadcast_id)
        if bc is None:
            raise _error(404, "NOT_FOUND")
        return _view(state, bc, full=True)


@router.post("/{broadcast_id}/stop")
async def stop_broadcast(
    broadcast_id: int, request: Request, admin: str = Depends(require_admin_action)
) -> dict:
    if not broadcasts.stop(request.app.state, broadcast_id):
        raise _error(404, "NOT_FOUND")
    metrics.inc("admin_actions")
    logger.info("Админка: рассылка {} остановлена ({})", broadcast_id, admin)
    return {"status": "ok"}
