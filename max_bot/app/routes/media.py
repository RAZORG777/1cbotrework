"""Публичные картинки рассылок: MAX берёт вложение по ссылке (specs/007-broadcasts).

Имена — 32 случайных hex-символа, перечислить файлы нельзя. Другие файлы отсюда не раздаются.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import broadcasts

router = APIRouter()


@router.get("/media/broadcasts/{name}", include_in_schema=False)
async def broadcast_image(name: str):
    path = broadcasts.image_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    media_type = "image/png" if name.endswith(".png") else "image/jpeg"
    return FileResponse(
        path, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"}
    )
