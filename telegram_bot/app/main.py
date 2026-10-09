"""Точка входа Telegram-бота: `python -m app.main` из каталога telegram_bot."""

from __future__ import annotations

import asyncio
import logging as std_logging
import traceback
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import select

from . import broadcasts, keyboards, metrics
from .config import Settings, load_settings
from .db import init_db, make_engine, make_session_factory, now_msk, session_scope
from .logging import mask_pii, setup_logging
from .messenger import TelegramMessenger
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
from .routes import admin, admin_api, broadcasts_api, health, internal, webapp, webhook

ADMIN_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


class InterceptHandler(std_logging.Handler):
    """Ошибки uvicorn — в общий журнал (с маской ПДн), чтобы их было видно в админке."""

    def emit(self, record: std_logging.LogRecord) -> None:
        text = record.getMessage()
        if record.exc_info:
            text += "\n" + "".join(traceback.format_exception(*record.exc_info)).rstrip()
        logger.opt(depth=6).log(record.levelname if record.levelno >= 30 else "INFO", text)


def intercept_uvicorn() -> None:
    for name in ("uvicorn.error",):
        std = std_logging.getLogger(name)
        std.handlers = [InterceptHandler()]
        std.setLevel(std_logging.WARNING)
        std.propagate = False


async def set_menu_button(messenger, settings) -> None:
    """Кнопка меню «Записаться» со ссылкой на текущую сборку формы (вместо старой из BotFather)."""
    button = keyboards.menu_button(settings.WEBAPP_URL)
    if await messenger.call("setChatMenuButton", {"menu_button": button}) is not None:
        logger.info("Кнопка меню: {}", button["web_app"]["url"])


def create_app(
    settings: Settings,
    onec_transport: httpx.AsyncBaseTransport | None = None,
    tg_transport: httpx.AsyncBaseTransport | None = None,
    retry_pause: float = 2.0,
) -> FastAPI:
    setup_logging(settings.log_dir, "telegram_bot")
    engine = make_engine(settings.db_file)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine, settings.db_file)
        metrics.mark_started()
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
        broadcasts.resume(app.state)
        if settings.TG_SET_MENU_BUTTON:
            # В фоне: если Telegram недоступен, запуск бота не ждёт повторов.
            app.state.menu_task = asyncio.create_task(
                set_menu_button(app.state.messenger, settings)
            )
        try:
            yield
        finally:
            await broadcasts.shutdown(app.state)
            scheduler.shutdown(wait=False)
            engine.dispose()
            logger.info("Бот остановлен")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.stop_process = admin_api.stop_process
    app.state.session_factory = session_factory
    app.state.onec = OneCClient(
        settings.ONEC_URL, (settings.ONEC_USER, settings.ONEC_PASSWORD), transport=onec_transport
    )
    app.state.messenger = TelegramMessenger(
        settings.TELEGRAM_API_BASE,
        settings.BOT_TOKEN,
        transport=tg_transport,
        retry_pause=retry_pause,
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        body = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.middleware("http")
    async def admin_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if "/admin" in path and not path.endswith("/webhook"):
            for key, value in ADMIN_HEADERS.items():
                response.headers.setdefault(key, value)
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        metrics.inc("http_errors")
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
        logger.error(
            "Необработанная ошибка {} {}: {}\n{}",
            request.method,
            request.url.path,
            type(exc).__name__,
            mask_pii(trace),
        )
        return JSONResponse({"status": "error", "error": "INTERNAL"}, status_code=500)

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

    # Ассеты сборки формы (имена с хэшем). Без сборки бот стартует, GET / отвечает 503.
    app.mount(
        "/assets",
        StaticFiles(directory=webapp.APP_DIR / "assets", check_dir=False),
        name="webapp-assets",
    )
    for module in (health, webapp, internal, webhook, admin, admin_api, broadcasts_api):
        app.include_router(module.router)
    return app


def run() -> None:
    settings = load_settings()
    intercept_uvicorn()
    uvicorn.run(create_app(settings), host=settings.HOST, port=settings.PORT, log_level="warning")


if __name__ == "__main__":
    run()
