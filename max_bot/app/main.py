"""Точка входа MAX-бота: `python -m app.main` из каталога max_bot. Все пути — под /max."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select

from .config import Settings, load_settings
from .db import init_db, make_engine, make_session_factory, now_msk, session_scope
from .logging import setup_logging
from .messenger import MaxMessenger
from .models import STATUS_ACTIVE, Appointment
from .onec_client import OneCClient
from .patient import BAD_BIRTH_DATE, BAD_PHONE
from .patient import MESSAGES as PATIENT_MESSAGES
from .reminders import (
    make_scheduler,
    register_retention,
    run_retention,
    schedule_reminders,
    set_runtime,
)
from .routes import admin, health, internal, webapp, webhook


def create_app(
    settings: Settings,
    onec_transport: httpx.AsyncBaseTransport | None = None,
    max_transport: httpx.AsyncBaseTransport | None = None,
    retry_pause: float = 2.0,
) -> FastAPI:
    setup_logging(settings.log_dir, "max_bot")
    engine = make_engine(settings.db_file)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine, settings.db_file)
        scheduler = make_scheduler(f"sqlite:///{settings.db_file}")
        app.state.scheduler = scheduler
        set_runtime(
            messenger=app.state.messenger, session_factory=session_factory, settings=settings
        )
        scheduler.start()
        register_retention(scheduler)
        with session_scope(session_factory) as session:
            run_retention(session, settings.PD_RETENTION_DAYS, now_msk())
        with session_scope(session_factory) as session:
            active = list(
                session.scalars(select(Appointment).where(Appointment.status == STATUS_ACTIVE))
            )
        restored = sum(schedule_reminders(scheduler, a, now_msk()) for a in active)
        logger.info("Бот запущен, восстановлено напоминаний: {}", restored)
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)
            engine.dispose()
            logger.info("Бот остановлен")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.onec = OneCClient(
        settings.ONEC_URL, (settings.ONEC_USER, settings.ONEC_PASSWORD), transport=onec_transport
    )
    app.state.messenger = MaxMessenger(
        settings.MAX_API_URL,
        settings.MAX_BOT_TOKEN,
        transport=max_transport,
        retry_pause=retry_pause,
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        body = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Без эха входных данных: в них могут быть ПДн.
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()})
        # Телефон и дату рождения пациент может исправить сам (contracts/onec-book.md).
        for field, code in (("patient.phone", BAD_PHONE), ("patient.birth_date", BAD_BIRTH_DATE)):
            if field in fields:
                return JSONResponse(
                    {"status": "error", "error": code, "message": PATIENT_MESSAGES[code]},
                    status_code=422,
                )
        return JSONResponse(
            {"status": "error", "error": "VALIDATION_ERROR", "fields": fields}, status_code=422
        )

    for module in (health, webapp, internal, webhook, admin):
        app.include_router(module.router, prefix="/max")
    return app


def run() -> None:
    settings = load_settings()
    uvicorn.run(create_app(settings), host=settings.HOST, port=settings.PORT, log_level="warning")


if __name__ == "__main__":
    run()
