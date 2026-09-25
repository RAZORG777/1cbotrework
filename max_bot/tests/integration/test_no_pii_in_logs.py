"""T075: после полного сценария в журналах и админке нет ФИО, телефона и даты рождения."""

from tests.helpers import MAX_SECRET, ONEC_SECRET, PATIENT, auth, booking

SIG = {"X-Bot-Secret": ONEC_SECRET}
PII = [
    PATIENT["last_name"],
    PATIENT["first_name"],
    PATIENT["middle_name"],
    PATIENT["phone"],
    PATIENT["birth_date"],
    "999) 123-45-67",
    "+79991234567",  # нормализованные формы (этап 1)
    "9991234567",
    "1990-02-01",
]


async def test_no_pii(client, settings, mocks):
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post(
        "/max/reschedule", json=booking(time_="11:00", old_id="appt-1"), headers=auth(5)
    )
    await client.post("/max/cancel", headers=auth(5))
    mocks["book"].respond(
        json={"status": "error", "error": f"ОШИБКА 1С: клиент {PATIENT['last_name']}"}
    )
    await client.post("/max/book", json=booking(), headers=auth(5))
    mocks["book"].respond(json={"status": "success", "appointment_id": "appt-3"})
    await client.post("/max/book", json=booking(), headers=auth(5))
    await client.post(
        "/max/api/v1/internal/finish-visit", json={"appointment_id": "appt-3"}, headers=SIG
    )
    await client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": MAX_SECRET},
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "user_id": 5,
            "user": {"user_id": 5, "name": PATIENT["first_name"] + " " + PATIENT["last_name"]},
        },
    )
    bad = booking()
    bad["patient"]["phone"] = ""
    r = await client.post("/max/book", json=bad, headers=auth(5))
    assert PATIENT["last_name"] not in r.text  # ошибка валидации без эха данных

    log_text = "".join(p.read_text(encoding="utf-8") for p in settings.log_dir.glob("*.log"))
    admin = (await client.get("/max/admin", auth=("admin", "admin-pass"))).text
    logs = (await client.get("/max/admin/logs", auth=("admin", "admin-pass"))).text
    for blob in (log_text, admin, logs):
        for value in PII:
            assert value not in blob, value
