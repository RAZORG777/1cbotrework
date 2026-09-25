"""API формы записи (contracts/webapp-api.md). Пользователь — только из подписанного initData."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..auth import WebAppUser, current_user
from ..config import BASE_DIR
from ..db import now_msk, session_scope
from ..doctors_enricher import enrich_doctors_data
from ..models import STATUS_ACTIVE, STATUS_CANCELLED, STATUS_FINISHED, Appointment
from ..onec_client import OneCError
from ..patient import MESSAGES as PATIENT_MESSAGES
from ..patient import normalize_birth_date, normalize_phone
from ..reminders import remove_reminders, schedule_reminders

router = APIRouter()
STATIC_DIR = BASE_DIR / "static"
BRANCH_LINK = "https://yasno-vizhu.com/contacts/"
MAP_LINK = "https://yandex.ru/maps/"


class Patient(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    middle_name: str = Field("", max_length=100)
    phone: str = Field(min_length=1, max_length=32)
    birth_date: str = Field(min_length=1, max_length=10)

    # Нормализация до 1С (contracts/onec-book.md): +7XXXXXXXXXX и YYYY-MM-DD.
    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, value: str) -> str:
        return normalize_birth_date(value)


class BookingRequest(BaseModel):
    branch: str = Field(min_length=1)
    doctor_id: str = Field(min_length=1)
    doctor_name: str = ""
    service_id: str = ""
    service_name: str = ""
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    patient: Patient
    send_notifications: bool = True
    pd_consent: bool = False
    old_appointment_id: str | None = None


def error(code: str, message: str, status: int = 200) -> JSONResponse:
    return JSONResponse({"status": "error", "error": code, "message": message}, status_code=status)


def unavailable() -> JSONResponse:
    return error(
        "SERVICE_UNAVAILABLE",
        "Сервис записи временно недоступен. Попробуйте позже или позвоните в клинику.",
        502,
    )


# Коды 1С, которые пациент может исправить сам; остальные — общая ошибка записи.
FIXABLE_CODES = {
    "SLOT_TAKEN": "Извините, это время уже занято. Выберите другое.",
    **PATIENT_MESSAGES,
}
GENERIC_REFUSAL = "Не удалось выполнить запись. Попробуйте позже или позвоните в клинику."


def onec_refusal(response: dict, user_id: str) -> JSONResponse:
    onec_code = str(response.get("code") or "")
    if onec_code in FIXABLE_CODES:
        code, message = onec_code, FIXABLE_CODES[onec_code]
    elif not onec_code and "занят" in str(response.get("error") or "").lower():
        # 1С без поля code (до этапа 1) — прежняя эвристика по тексту.
        code, message = "SLOT_TAKEN", FIXABLE_CODES["SLOT_TAKEN"]
    else:
        code, message = "ONEC_ERROR", GENERIC_REFUSAL
    logger.warning("1С отказала: user_id={} код={} код_1С={}", user_id, code, onec_code or "-")
    return error(code, message)


def log_patient_result(response: dict, appointment_id: str) -> None:
    """Итог поиска пациента и медкарты в 1С — без ПДн (FR-006, FR-015)."""
    patient = response.get("patient") or "-"
    card = response.get("medical_card") or "-"
    logger.info("1С: appointment_id={} пациент={} медкарта={}", appointment_id, patient, card)
    if card == "missing":
        logger.warning("1С не создала медкарту: appointment_id={}", appointment_id)


def branch_name(branch: str) -> str:
    return "Профсоюзная" if branch == "Профсоюзная" else "Новые Ватутинки"


PAST_GRACE = timedelta(hours=1)


def active_for(session, user_id: str) -> Appointment | None:
    """Активная запись пользователя. Прошедшая по дате сразу закрывается и не блокирует (FR-005)."""
    appt = session.scalar(
        select(Appointment).where(
            Appointment.user_id == user_id, Appointment.status == STATUS_ACTIVE
        )
    )
    if appt is not None and appt.visit_at < now_msk() - PAST_GRACE:
        appt.status = STATUS_FINISHED
        appt.closed_at = appt.visit_at
        session.flush()
        return None
    return appt


def onec_payload(req: BookingRequest) -> dict:
    payload = {
        "branch": req.branch,
        "doctor_id": req.doctor_id,
        "doctor_name": req.doctor_name,
        "service_id": req.service_id,
        "service_name": req.service_name,
        "date": req.date,
        "time": req.time,
        "patient": req.patient.model_dump(),
        "platform": "telegram",
    }
    if req.old_appointment_id:
        payload["old_appointment_id"] = req.old_appointment_id
    return payload


def fill(appt: Appointment, req: BookingRequest, appointment_id: str) -> None:
    appt.appointment_id = appointment_id
    appt.branch = req.branch
    appt.doctor_id = req.doctor_id
    appt.doctor_name = req.doctor_name
    appt.service_id = req.service_id
    appt.service_name = req.service_name
    appt.visit_at = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
    appt.first_name = req.patient.first_name
    appt.last_name = req.patient.last_name
    appt.middle_name = req.patient.middle_name
    appt.phone = req.patient.phone
    appt.birth_date = req.patient.birth_date
    appt.notify = req.send_notifications


def consent_required() -> JSONResponse:
    return error(
        "PD_CONSENT_REQUIRED", "Подтвердите согласие на обработку персональных данных.", 422
    )


# --- Статика и публичные данные ---


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/Логотип.png", include_in_schema=False)
async def logo() -> FileResponse:
    return FileResponse(STATIC_DIR / "Логотип.png")


@router.get("/config")
async def config(request: Request) -> dict:
    return {"pd_policy_url": request.app.state.settings.PD_POLICY_URL}


# --- Справочники 1С ---


@router.get("/doctors")
async def doctors(
    request: Request,
    branch: str | None = None,
    date: str | None = None,
    user: WebAppUser = Depends(current_user),
):
    try:
        data = await request.app.state.onec.get_doctors(branch, date)
    except OneCError:
        return unavailable()
    return enrich_doctors_data(data, target_branch=branch)


@router.get("/services")
async def services(
    request: Request, doctor_id: str | None = None, user: WebAppUser = Depends(current_user)
):
    try:
        return await request.app.state.onec.get_services(doctor_id)
    except OneCError:
        return unavailable()


@router.get("/schedule")
async def schedule(
    request: Request,
    doctor_id: str,
    branch: str | None = None,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user: WebAppUser = Depends(current_user),
):
    try:
        return await request.app.state.onec.get_schedule(
            doctor_id=doctor_id, date=date, branch=branch, start_date=start_date, end_date=end_date
        )
    except OneCError:
        return unavailable()


# --- Запись пациента ---


@router.get("/my_appointment")
async def my_appointment(request: Request, user: WebAppUser = Depends(current_user)) -> dict:
    with session_scope(request.app.state.session_factory) as session:
        appt = active_for(session, user.id)
        if appt is None:
            return {"status": "success", "has_appointment": False}
        return {
            "status": "success",
            "has_appointment": True,
            "data": {
                "appointment_id": appt.appointment_id,
                "branch": appt.branch,
                "date": appt.date_str,
                "time": appt.time_str,
                "doctor_name": appt.doctor_name,
                "service_name": appt.service_name,
            },
        }


@router.post("/book")
async def book(
    req: BookingRequest,
    request: Request,
    background: BackgroundTasks,
    user: WebAppUser = Depends(current_user),
):
    if not req.pd_consent:
        return consent_required()
    state = request.app.state
    with session_scope(state.session_factory) as session:
        if active_for(session, user.id):
            return {"status": "error", "error": "SECOND_BOOKING_ERROR"}

    logger.info("Запись: user_id={} врач={} {} {}", user.id, req.doctor_id, req.date, req.time)
    try:
        response = await state.onec.create_booking(onec_payload(req))
    except OneCError:
        return unavailable()
    if response.get("status") != "success":
        return onec_refusal(response, user.id)

    appointment_id = str(response.get("appointment_id") or "")
    now = now_msk()
    try:
        with session_scope(state.session_factory) as session:
            appt = Appointment(user_id=user.id, platform="telegram", created_at=now)
            fill(appt, req, appointment_id)
            session.add(appt)
    except IntegrityError:
        logger.error(
            "Параллельная вторая запись: user_id={} appointment_id={}", user.id, appointment_id
        )
        return {"status": "error", "error": "SECOND_BOOKING_ERROR"}
    # Задания пишутся в ту же SQLite — только после фиксации транзакции.
    schedule_reminders(state.scheduler, appt, now)
    logger.info("Записан: user_id={} appointment_id={}", user.id, appointment_id)
    log_patient_result(response, appointment_id)

    date_s = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
    fio = f"{req.patient.first_name} {req.patient.middle_name}".strip()
    text = (
        f"{fio}\n<b>{date_s}</b> вы записаны в клинику Ясно вижу.\n\n"
        f"<b>{req.time}</b> <a href='{BRANCH_LINK}'>{branch_name(req.branch)}</a> 📍\n"
        f"Проложить маршрут - <a href='{MAP_LINK}'>тут 🏥</a>\n\nЖдем вас в назначенное время!"
    )
    background.add_task(state.messenger.send_message, user.id, text)
    return {"status": "success", "appointment_id": appointment_id}


@router.post("/reschedule")
async def reschedule(
    req: BookingRequest,
    request: Request,
    background: BackgroundTasks,
    user: WebAppUser = Depends(current_user),
):
    if not req.pd_consent:
        return consent_required()
    state = request.app.state
    with session_scope(state.session_factory) as session:
        appt = active_for(session, user.id)
        if (
            appt is None
            or not req.old_appointment_id
            or appt.appointment_id != req.old_appointment_id
        ):
            return error("NOT_FOUND", "Активная запись не найдена.", 404)
        old_id = appt.appointment_id

    logger.info("Перенос: user_id={} appointment_id={}", user.id, old_id)
    try:
        response = await state.onec.reschedule(onec_payload(req))
    except OneCError:
        return unavailable()
    if response.get("status") != "success":
        return onec_refusal(response, user.id)

    new_id = str(response.get("appointment_id") or old_id)
    log_patient_result(response, new_id)
    now = now_msk()
    with session_scope(state.session_factory) as session:
        appt = active_for(session, user.id)
        if appt is None:
            return error("NOT_FOUND", "Активная запись не найдена.", 404)
        fill(appt, req, new_id)
    remove_reminders(state.scheduler, old_id)
    schedule_reminders(state.scheduler, appt, now)

    date_s = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
    fio = f"{req.patient.first_name} {req.patient.middle_name}".strip()
    text = (
        f"🔄 {fio}\nВаша запись успешно <b>перенесена</b>!\n\n"
        f"Новая дата: <b>{date_s}</b>\nВремя: <b>{req.time}</b>\n"
        f"Врач: {req.doctor_name}\nФилиал: <a href='{BRANCH_LINK}'>{branch_name(req.branch)}</a> 📍\n\n"
        "Ждем вас!"
    )
    background.add_task(state.messenger.send_message, user.id, text)
    return {"status": "success", "appointment_id": new_id}


async def cancel_for_user(state, user_id: str) -> JSONResponse | dict:
    """Отмена активной записи пользователя (используется формой и кнопками)."""
    with session_scope(state.session_factory) as session:
        appt = active_for(session, user_id)
        if appt is None:
            return error("NOT_FOUND", "Запись не найдена.", 404)
        appointment_id = appt.appointment_id
    try:
        response = await state.onec.cancel_booking(appointment_id)
    except OneCError:
        return unavailable()
    if response.get("status") != "success":
        return onec_refusal(response, user_id)
    with session_scope(state.session_factory) as session:
        appt = active_for(session, user_id)
        if appt is not None:
            appt.status = STATUS_CANCELLED
            appt.closed_at = now_msk()
    remove_reminders(state.scheduler, appointment_id)
    logger.info("Отменена пациентом: user_id={} appointment_id={}", user_id, appointment_id)
    return {"status": "success", "appointment_id": appointment_id}


@router.post("/cancel")
async def cancel(
    request: Request, background: BackgroundTasks, user: WebAppUser = Depends(current_user)
):
    result = await cancel_for_user(request.app.state, user.id)
    if isinstance(result, dict):
        text = "✅ <b>Ваша запись успешно отменена.</b>\n\nБудем рады видеть вас снова! 🏥"
        background.add_task(request.app.state.messenger.send_message, user.id, text)
        return {"status": "success"}
    return result
