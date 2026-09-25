from __future__ import annotations

import httpx
import pytest
import respx

from app.config import Settings
from app.main import create_app
from tests.helpers import MAX, MAX_SECRET, ONEC, ONEC_SECRET, TOKEN


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        MAX_BOT_TOKEN=TOKEN,
        MAX_API_URL=MAX,
        MAX_WEBHOOK_SECRET=MAX_SECRET,
        MAX_MINIAPP="yasno_bot",
        ADMIN_IDS="100",
        WEBAPP_URL="https://app.test",
        PD_POLICY_URL="https://policy.test/consent.pdf",
        ONEC_URL=ONEC,
        ONEC_USER="bot",
        ONEC_PASSWORD="pwd",
        ONEC_WEBHOOK_SECRET=ONEC_SECRET,
        ADMIN_PASSWORD="admin-pass",
        DB_PATH=str(tmp_path / "bot.db"),
        LOG_DIR=str(tmp_path / "logs"),
    )


@pytest.fixture
def mocks():
    """Заглушки 1С и MAX Bot API. Любой неподменённый внешний запрос — ошибка теста."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        router.get(f"{ONEC}/doctors", name="doctors").respond(
            json=[
                {
                    "id": "doc-1",
                    "full_name": "Иванов Иван Иванович",
                    "specialty_name": "Офтальмолог",
                }
            ]
        )
        router.get(f"{ONEC}/services", name="services").respond(
            json=[{"id": "srv-1", "name": "Первичный прием", "price": 3000}]
        )
        router.get(f"{ONEC}/schedule", name="schedule").respond(
            json={"status": "success", "schedule": {"2030-01-10": ["10:00", "10:30"]}}
        )
        router.post(f"{ONEC}/book", name="book").respond(
            json={"status": "success", "appointment_id": "appt-1"}
        )
        router.post(f"{ONEC}/reschedule", name="reschedule").respond(
            json={"status": "success", "appointment_id": "appt-2"}
        )
        router.post(f"{ONEC}/cancel", name="cancel").respond(json={"status": "success"})
        router.post(f"{ONEC}/update_note", name="update_note").respond(json={"status": "success"})
        router.post(f"{MAX}/messages", name="msg").respond(json={"message": {}})
        router.post(f"{MAX}/answers", name="answers").respond(json={"success": True})
        yield router


@pytest.fixture
async def app(settings, mocks):
    application = create_app(settings, retry_pause=0)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bot.test") as c:
        yield c
