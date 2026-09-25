import sys
import os
import asyncio
import uvicorn
import httpx
import secrets
import json
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks, APIRouter
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from collections import deque
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# --- НАСТРОЙКА ПУТЕЙ ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

load_dotenv(os.path.join(parent_dir, '.env'))

from one_c_client import OneCClient
from max_doctors_enricher import enrich_doctors_data, DOCTORS_EXTRA_INFO

# --- НАСТРОЙКА ЛОГИРОВАНИЯ (loguru) ---
from loguru import logger

log_buffer = deque(maxlen=100)
def web_log_sink(message):
    log_buffer.append(message.strip())

logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
logger.add("logs/max_bot.log", rotation="10 MB", retention="10 days", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", encoding="utf-8")
logger.add(web_log_sink, format="[{time:HH:mm:ss}] {message}")
# -------------------------

# --- НАСТРОЙКИ БАЗЫ ДАННЫХ ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./max_appointments.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ССЫЛКИ НА ОТЗЫВЫ ---
REVIEWS_LINKS = {
    "Профсоюзная": "https://yandex.ru/maps/213/moscow/?ll=37.543560%2C55.660760&mode=poi&poi%5Bpoint%5D=37.543529%2C55.660638&poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D196039112145&z=17",
    "Новые Ватутинки": "https://yandex.ru/maps/213/moscow/?indoorLevel=1&ll=37.345203%2C55.518301&mode=poi&poi%5Bpoint%5D=37.344904%2C55.518219&poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D200998099919&z=17"
}

class DBAppointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(String, unique=True, index=True)
    platform = Column(String, default="max") 
    source = Column(String, default="MAX бот")
    appointment_id = Column(String)
    branch = Column(String)
    doctor_id = Column(String)
    doctor_name = Column(String)
    service_id = Column(String)
    service_name = Column(String)
    date = Column(String)
    time = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    middle_name = Column(String)
    phone = Column(String)
    birth_date = Column(String)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- PYDANTIC МОДЕЛИ ДАННЫХ ---
class Patient(BaseModel):
    first_name: str
    last_name: str
    middle_name: str = ""
    phone: str
    birth_date: str

class BookingRequest(BaseModel):
    tg_id: str
    branch: str
    doctor_id: str
    doctor_name: str = ""
    service_id: str
    service_name: str = ""
    date: str
    time: str
    patient: Patient
    source: str = "MAX бот"
    platform: str = "max"
    old_appointment_id: str = None 

class CancelRequest(BaseModel):
    tg_id: str

# --- ЛОГИКА АВТОРИЗАЦИИ АДМИНКИ ---
security = HTTPBasic()

def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "5069522709")
    if not (secrets.compare_digest(credentials.username, expected_username) and secrets.compare_digest(credentials.password, expected_password)):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

# --- ФУНКЦИИ ОТПРАВКИ СООБЩЕНИЙ В MAX ---
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
MAX_API_URL = os.getenv("MAX_API_URL", "https://platform-api.max.ru")

async def send_max_reminder(user_id: str, text: str, inline_keyboard: list = None):
    base_url = MAX_API_URL.rstrip('/')
    url = f"{base_url}/messages?user_id={user_id}"
    
    headers = {"Authorization": f"{MAX_BOT_TOKEN}", "Content-Type": "application/json"}
    
    payload = {
        "text": text,
        "format": "html"
    }
    
    if inline_keyboard:
        payload["attachments"] = [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": inline_keyboard}
            }
        ]
    
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.success(f"✅ MAX API Send: {user_id} | Успешно (попытка {attempt})")
                    return True
                else:
                    logger.error(f"⚠️ Ошибка MAX API ({response.status_code}): {response.text}")
                    return False
        except Exception as e:
            logger.warning(f"⚠️ Сетевая ошибка MAX (попытка {attempt}/3): {repr(e)}")
            if attempt < 3:
                await asyncio.sleep(2)
            else:
                logger.error(f"❌ Критическая ошибка: сообщение для {user_id} не доставлено.")
    return False

async def send_max_welcome(user_id: str):
    webapp_url = f"https://1cmed.one-two.online/max/?user_id={user_id}"
    kb = [[{"type": "link", "text": "Записаться ✅", "url": webapp_url}]]
    welcome_text = (
        "<b>Добро пожаловать в клинику «ЯСНО ВИЖУ»!</b> 👋\n\n"
        "Нажмите кнопку ниже, чтобы выбрать врача и время для записи. "
        "Кнопка-ссылка всегда будет здесь, просто напишите мне любое слово, если потеряете её!"
    )
    return await send_max_reminder(user_id, welcome_text, inline_keyboard=kb)

# --- ПЛАНИРОВЩИК НАПОМИНАНИЙ (с кнопками) ---
def schedule_notifications(req: BookingRequest, fio: str):
    try:
        appt_dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        
        rem_24h = appt_dt - timedelta(hours=24)
        if rem_24h > now:
            msg_24h = (
                f"<b>{fio}</b>,\n🔔 Напоминаем: завтра в <b>{req.time}</b> вы записаны в клинику «ЯСНО ВИЖУ».\n"
                f"🏥 Филиал: {req.branch}\n👨‍⚕️ Врач: {req.doctor_name}\n\nПожалуйста, подтвердите визит 👇"
            )
            # Добавлена клавиатура подтверждения
            kb = [
                [{"type": "callback", "text": "✅ Подтверждаю", "payload": "confirm_visit"}],
                [{"type": "callback", "text": "❌ Отменить", "payload": "cancel_visit_btn"}]
            ]
            scheduler.add_job(send_max_reminder, 'date', run_date=rem_24h, args=[req.tg_id, msg_24h, kb], id=f"rem24h_{req.tg_id}", replace_existing=True)

        rem_2h = appt_dt - timedelta(hours=2)
        if rem_2h > now:
            msg_2h = f"<b>{fio}</b>,\n🔔 Напоминаем: через 2 часа у вас прием в клинике «ЯСНО ВИЖУ».\n🏥 Филиал: {req.branch}\n👨‍⚕️ Врач: {req.doctor_name}"
            scheduler.add_job(send_max_reminder, 'date', run_date=rem_2h, args=[req.tg_id, msg_2h], id=f"rem2h_{req.tg_id}", replace_existing=True)
    except Exception as ex: 
        logger.error(f"❌ Ошибка при планировании напоминаний: {ex}")

# --- ЛОГИКА ЖИЗНЕННОГО ЦИКЛА ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.start() 
    logger.info("🚀 Планировщик MAX запущен")
    
    db = SessionLocal()
    appts = db.query(DBAppointment).all()
    for appt in appts:
        try:
            appt_dt = datetime.strptime(f"{appt.date} {appt.time}", "%Y-%m-%d %H:%M")
            fio = f"{appt.first_name} {appt.middle_name}".strip()
            
            for rem_type, delta in [("rem24h", 24), ("rem2h", 2)]:
                rem_time = appt_dt - timedelta(hours=delta)
                if rem_time > datetime.now():
                    job_id = f"{rem_type}_{appt.tg_id}"
                    if delta == 24:
                        msg = f"<b>{fio}</b>,\n🔔 Напоминаем: завтра в <b>{appt.time}</b> у вас прием в клинике «ЯСНО ВИЖУ».\n🏥 Филиал: {appt.branch}\n👨‍⚕️ Врач: {appt.doctor_name}\n\nПожалуйста, подтвердите визит 👇"
                        kb = [
                            [{"type": "callback", "text": "✅ Подтверждаю", "payload": "confirm_visit"}],
                            [{"type": "callback", "text": "❌ Отменить", "payload": "cancel_visit_btn"}]
                        ]
                        scheduler.add_job(send_max_reminder, 'date', run_date=rem_time, args=[appt.tg_id, msg, kb], id=job_id, replace_existing=True)
                    else:
                        msg = f"<b>{fio}</b>,\n🔔 Напоминаем: через 2 часа в <b>{appt.time}</b> у вас прием в клинике «ЯСНО ВИЖУ».\n🏥 Филиал: {appt.branch}\n👨‍⚕️ Врач: {appt.doctor_name}"
                        scheduler.add_job(send_max_reminder, 'date', run_date=rem_time, args=[appt.tg_id, msg], id=job_id, replace_existing=True)
        except Exception as e: pass
    db.close()
    
    yield
    scheduler.shutdown()
    logger.info("🛑 Планировщик MAX остановлен")

app = FastAPI(lifespan=lifespan)
jobstores = { 'default': SQLAlchemyJobStore(url='sqlite:///max_appointments.db') }
scheduler = AsyncIOScheduler(jobstores=jobstores)
client_1c = OneCClient(base_url=os.getenv("ONEC_URL"), auth=(os.getenv("ONEC_USER"), os.getenv("ONEC_PASSWORD")))

router = APIRouter(prefix="/max", redirect_slashes=False)

# --- ЭНДПОИНТЫ ПРИЛОЖЕНИЯ ---
@router.get("/")
@router.get("") 
async def read_index(): 
    return FileResponse(os.path.join(current_dir, "max_index.html"))

@router.get("/Логотип.png")
async def get_logo():
    path = os.path.join(current_dir, "Логотип.png")
    if not os.path.exists(path): path = os.path.join(parent_dir, "Логотип.png")
    return FileResponse(path)

@router.get("/doctors")
async def get_doctors(branch: str = None, date: str = None):
    raw_docs = await client_1c.get_doctors(branch, date)
    
    # Обогащаем результат фотографиями и стажем + ФИЛЬТРУЕМ ПО ФИЛИАЛУ
    if isinstance(raw_docs, dict) and "data" in raw_docs:
        raw_docs["data"] = enrich_doctors_data(raw_docs["data"], target_branch=branch) # ✅ Исправлено
        return raw_docs
    elif isinstance(raw_docs, list):
        return enrich_doctors_data(raw_docs, target_branch=branch) # ✅ Исправлено
        
    return raw_docs

@router.get("/services")
async def get_services(doctor_id: str = None): return await client_1c.get_services(doctor_id)

@router.get("/schedule")
async def get_schedule(doctor_id: str, branch: str = None, date: str = None, start_date: str = None, end_date: str = None): 
    return await client_1c.get_schedule(doctor_id=doctor_id, date=date, branch=branch, start_date=start_date, end_date=end_date)

@router.post("/book")
async def book_appointment(req: BookingRequest, background_tasks: BackgroundTasks, send_notifications: bool = False, db: Session = Depends(get_db)):
    if db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first():
        return {"status": "error", "error": "SECOND_BOOKING_ERROR"}

    try:
        response = await client_1c.create_booking(req.model_dump())
        if response.get("status") == "success":
            new_appt = DBAppointment(
                **req.model_dump(exclude={'patient', 'old_appointment_id'}), 
                **req.patient.model_dump(),
                appointment_id=response.get("appointment_id")
            )
            db.add(new_appt)
            try:
                db.commit() 
            except Exception as db_err:
                db.rollback() 
                logger.error(f"❌ Ошибка БД: {db_err}")
                return {"status": "error", "error": "Ошибка сохранения в БД"}
            
            fio = f"{req.patient.first_name} {req.patient.middle_name}".strip()
            formatted_date = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            msg = (
                f"<b>{fio}</b>,\n"
                f"✅ Вы успешно записаны!\n\n"
                f"🏥 Филиал: <b>{req.branch}</b>\n"
                f"📅 Дата: <b>{formatted_date}</b>\n"
                f"⏰ Время: <b>{req.time}</b>\n"
                f"👨‍⚕️ Врач: {req.doctor_name}"
            )
            background_tasks.add_task(send_max_reminder, req.tg_id, msg)
            
            if send_notifications:
                schedule_notifications(req, fio)
                
        return response
    except Exception as e:
        db.rollback() 
        logger.error(f"❌ Ошибка записи 1С: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reschedule")
async def reschedule_appointment(req: BookingRequest, background_tasks: BackgroundTasks, send_notifications: bool = False, db: Session = Depends(get_db)):
    if not req.old_appointment_id:
        return {"status": "error", "error": "Не передан ID старой записи"}
        
    existing_appt = db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first()
    if not existing_appt:
        return {"status": "error", "error": "Активная запись не найдена"}

    try:
        data_to_send = req.model_dump() 
        response = await client_1c._make_request("POST", "reschedule", json=data_to_send)
        
        if response.get("status") == "success":
            new_appointment_id = response.get("appointment_id", req.old_appointment_id)
            
            existing_appt.platform = req.platform
            existing_appt.source = req.source
            existing_appt.appointment_id = new_appointment_id
            existing_appt.branch = req.branch
            existing_appt.doctor_id = req.doctor_id
            existing_appt.doctor_name = req.doctor_name
            existing_appt.service_id = req.service_id
            existing_appt.service_name = req.service_name
            existing_appt.date = req.date
            existing_appt.time = req.time
            existing_appt.first_name = req.patient.first_name
            existing_appt.last_name = req.patient.last_name
            existing_appt.middle_name = req.patient.middle_name
            existing_appt.phone = req.patient.phone
            existing_appt.birth_date = req.patient.birth_date
            
            try:
                db.commit()
            except Exception as db_err:
                db.rollback()
                return {"status": "error", "error": "Ошибка БД при переносе"}
            
            for prefix in ["rem24h_", "rem2h_", "remsmart_", "feedback_"]:
                job_id = f"{prefix}{req.tg_id}"
                if scheduler.get_job(job_id): scheduler.remove_job(job_id)
            
            fio = f"{req.patient.first_name} {req.patient.middle_name}".strip()
            formatted_date = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            confirm_msg = (
                f"🔄 <b>{fio}</b>,\nВаша запись успешно перенесена!\n\n"
                f"🏥 Филиал: <b>{req.branch}</b>\n"
                f"📅 Новая дата: <b>{formatted_date}</b>\n"
                f"⏰ Время: <b>{req.time}</b>\n"
                f"👨‍⚕️ Врач: {req.doctor_name}\n\nЖдем вас!"
            )
            background_tasks.add_task(send_max_reminder, req.tg_id, confirm_msg)
            
            if send_notifications:
                schedule_notifications(req, fio)
                
        return response
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Критическая ошибка при переносе: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/my_appointment")
async def get_my_appointment(tg_id: str, db: Session = Depends(get_db)):
    appt = db.query(DBAppointment).filter(DBAppointment.tg_id == tg_id).first()
    return {"has_appointment": bool(appt), "data": appt}

@router.post("/cancel")
async def cancel_appointment(req: CancelRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    appt = db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first()
    if appt:
        try:
            res = await client_1c.cancel_booking(appt.appointment_id)
            if res.get("status") == "success":
                db.delete(appt)
                db.commit()
                
                fio = f"{appt.first_name} {appt.middle_name}".strip()
                background_tasks.add_task(send_max_reminder, req.tg_id, f"<b>{fio}</b>,\n🚫 Ваша запись была успешно отменена.")
                
                for prefix in ["rem24h_", "rem2h_"]:
                    job_id = f"{prefix}{req.tg_id}"
                    if scheduler.get_job(job_id): scheduler.remove_job(job_id)
                    
                return {"status": "success"}
            return {"status": "error", "error": res.get("error", "Ошибка отмены 1С")}
        except Exception as e:
            db.rollback()
            return {"status": "error", "error": str(e)}
    return {"status": "error", "error": "Запись не найдена"}
    
@router.post("/api/v1/internal/finish-visit")
async def finish_visit(data: dict, db: Session = Depends(get_db)):
    appt_id = data.get("appointment_id")
    appt = db.query(DBAppointment).filter(DBAppointment.appointment_id == appt_id).first()
    
    if appt:
        fio = f"{appt.first_name} {appt.middle_name}".strip()
        doctor_name = appt.doctor_name.strip() if appt.doctor_name else ""
        
        # 1. Пытаемся найти ссылку на ПроДокторов для этого врача
        prodoctorov_link = None
        for key, info in DOCTORS_EXTRA_INFO.items():
            # Ищем совпадение имени, игнорируя разницу между 'е' и 'ё'
            if key.replace("ё", "е").lower() in doctor_name.replace("ё", "е").lower():
                prodoctorov_link = info.get("prodoctorov_url")
                break
                
        # 2. Формируем сообщение в зависимости от того, нашли ссылку или нет
        if prodoctorov_link:
            # У врача есть профиль на ПроДокторов
            msg_feedback = (
                f"🌟 <b>{fio}</b>, надеемся, вам понравилось на приеме у специалиста <b>{doctor_name}</b>!\n\n"
                f"Будем очень благодарны, если вы уделите минуту и оставите отзыв о работе врача:\n"
                f"👉 <a href='{prodoctorov_link}'>Оставить отзыв на ПроДокторов</a>"
            )
        else:
            # Врача нет в списке или у него нет ссылки -> просим отзыв на филиал в Яндекс.Картах
            branch_key = "Новые Ватутинки" if "Ватутинки" in appt.branch else "Профсоюзная"
            link = REVIEWS_LINKS.get(branch_key, REVIEWS_LINKS["Профсоюзная"])
            
            msg_feedback = (
                f"🌟 <b>{fio}</b>, надеемся, вам понравилось в нашей клинике!\n\n"
                f"Будем очень благодарны за ваш отзыв:\n"
                f"👉 <a href='{link}'>Оставить отзыв на Яндекс.Картах</a>"
            )
        
        # 3. Отправляем через 20 минут после сигнала
        run_at = datetime.now() + timedelta(minutes=20)
        
        scheduler.add_job(
            send_max_reminder, 
            'date', 
            run_date=run_at, 
            args=[appt.tg_id, msg_feedback], 
            id=f"feedback_{appt_id}", 
            replace_existing=True
        )
        return {"status": "success"}
        
    return {"status": "error", "message": "Not found"}
    
@router.post("/api/v1/internal/cancel-visit")
async def cancel_visit_from_1c(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logger.info(f"📥 ВХОДЯЩИЙ СИГНАЛ 1С (Отмена): {data}")
    
    appt_id = data.get("appointment_id")
    appt = db.query(DBAppointment).filter(DBAppointment.appointment_id == appt_id).first()
    
    if appt:
        logger.success(f"✅ Пациент найден в базе MAX! tg_id: {appt.tg_id}. Удаляем...")
        tg_id = appt.tg_id 
        fio = f"{appt.first_name} {appt.middle_name}".strip()
        
        for job in scheduler.get_jobs():
            if str(tg_id) in job.id or str(appt_id) in job.id: 
                scheduler.remove_job(job.id)
                
        db.delete(appt)
        db.commit()
        
        текст_отмены = (
            f"😔 <b>{fio}</b>,\n"
            f"Ваша запись была отменена нашими администраторами.\n\n"
            f"Вы всегда можете записаться заново, нажав на кнопку меню! 🏥"
        )
        
        background_tasks.add_task(send_max_reminder, tg_id, текст_отмены)
        return {"status": "success"}
        
    logger.warning(f"⚠️ Пациент с ID {appt_id} НЕ НАЙДЕН в базе MAX (возможно, он из Telegram)")
    return {"status": "not_found"}

# --- ДОБАВЛЕНА ОБРАБОТКА КНОПОК В ВЕБХУКЕ ---
@router.api_route("/webhook", methods=["GET", "POST"])
async def max_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if request.method == "GET": 
        return {"status": "ok", "message": "Webhook active"}
    
    try:
        update = await request.json()
        logger.info(f"📥 MAX Webhook Incoming: {update}")
        
        update_type = update.get("update_type")
        user_id = None
        
        if update_type == "bot_started":
            user_id = str(update.get("user_id", update.get("user", {}).get("user_id", "")))
            if user_id:
                asyncio.create_task(send_max_welcome(user_id))
            
        elif update_type == "message_created" or "message" in update:
            message = update.get("message", {})
            user_id = str(message.get("sender", {}).get("user_id", ""))
            is_bot = message.get("sender", {}).get("is_bot", False)
            payload = message.get("payload", "") # Ловим скрытый payload кнопки
            
            # --- ЛОГИКА КНОПОК ПОДТВЕРЖДЕНИЯ ---
            if payload == "confirm_visit":
                appt = db.query(DBAppointment).filter(DBAppointment.tg_id == user_id).first()
                if appt:
                    try:
                        # Отправляем в 1С обновление примечания
                        await client_1c._make_request("POST", "update_note", json={
                            "appointment_id": appt.appointment_id,
                            "note": "✅ Визит подтвержден пациентом (MAX)"
                        })
                        await send_max_reminder(user_id, "✅ <b>Спасибо! Ваш визит подтвержден.</b> Ждем вас в клинике!")
                    except Exception as e:
                        logger.error(f"Ошибка подтверждения в 1С: {e}")
                        await send_max_reminder(user_id, "⚠️ Произошла ошибка связи с клиникой, но мы зафиксировали ваше подтверждение.")
                return {"status": "ok"}
                
            elif payload == "cancel_visit_btn":
                cancel_req = CancelRequest(tg_id=user_id)
                await cancel_appointment(cancel_req, background_tasks, db)
                return {"status": "ok"}
                
            # Если это просто текстовое сообщение от юзера (не кнопка) - присылаем меню
            elif not is_bot and user_id:
                asyncio.create_task(send_max_welcome(user_id))
                
    except Exception as e:
        logger.error(f"❌ Ошибка разбора вебхука: {repr(e)}")
        
    return {"status": "ok"}

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    # 1. Собираем данные из базы для аналитики
    appointments = db.query(DBAppointment).all()
    total_appts = len(appointments)
    
    branch_stats = {"Профсоюзная": 0, "Ватутинки": 0, "Другие": 0}
    doctor_counter = {}
    
    for appt in appointments:
        # Считаем филиалы
        b_name = appt.branch or "Не указан"
        if "профсоюзная" in b_name.lower():
            branch_stats["Профсоюзная"] += 1
        elif "ватутинки" in b_name.lower():
            branch_stats["Ватутинки"] += 1
        else:
            branch_stats["Другие"] += 1
            
        # Считаем популярность врачей
        doc = appt.doctor_name or "Неизвестный врач"
        doctor_counter[doc] = doctor_counter.get(doc, 0) + 1

    # Вычисляем ТОП-5 врачей
    top_doctors = sorted(doctor_counter.items(), key=lambda x: x[1], reverse=True)[:5]
    doc_labels = [x[0] for x in top_doctors]
    doc_counts = [x[1] for x in top_doctors]
    
    # 2. Формируем красивый список задач планировщика
    jobs_list_html = ""
    now = datetime.now()
    active_jobs_count = len(scheduler.get_jobs())
    
    for j in scheduler.get_jobs():
        run_time_str = j.next_run_time.strftime('%d.%m %H:%M:%S') if j.next_run_time else "Пауза"
        # Вычисляем статус задачи
        is_feedback = "feedback" in j.id
        badge_color = "bg-purple-100 text-purple-700" if is_feedback else "bg-amber-100 text-amber-700"
        badge_text = "Отзыв" if is_feedback else "Напоминание"
        
        jobs_list_html += f"""
        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-100 mb-2">
            <div class="truncate pr-2">
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider {badge_color}">{badge_text}</span>
                <div class="text-xs font-mono font-bold text-gray-700 mt-1 truncate">{j.id}</div>
            </div>
            <div class="text-right flex-shrink-0">
                <div class="text-[10px] uppercase font-bold text-gray-400">План запуска</div>
                <div class="text-xs font-black text-gray-900">{run_time_str}</div>
            </div>
        </div>
        """
    if not jobs_list_html:
        jobs_list_html = "<div class='text-center py-6 text-sm text-gray-400 font-medium'>Активных задач в очереди нет</div>"

    # 3. Умное раскрашивание логов под терминал
    formatted_logs = []
    for log in reversed(log_buffer):
        log_str = str(log)
        color_class = "text-gray-300"
        if "❌" in log_str or "ERROR" in log_str or "Exception" in log_str:
            color_class = "text-red-400 font-bold bg-red-500/10 px-1 rounded"
        elif "✅" in log_str or "SUCCESS" in log_str:
            color_class = "text-green-400 font-bold bg-green-500/10 px-1 rounded"
        elif "⚠️" in log_str or "WARNING" in log_str:
            color_class = "text-yellow-400"
        elif "🚀" in log_str or "INFO" in log_str:
            color_class = "text-sky-400"
            
        formatted_logs.append(f"<div class='py-1 border-b border-gray-800/40 font-mono text-xs {color_class}'>{log_str}</div>")
    logs_html = "".join(formatted_logs) if formatted_logs else "<div class='text-gray-500 text-xs italic p-4'>Логи пока пусты...</div>"

    # Превращаем данные в JSON строки для безопасной интеграции в JavaScript графиков
    js_doc_labels = json.dumps(doc_labels)
    js_doc_counts = json.dumps(doc_counts)
    js_branch_counts = json.dumps([branch_stats["Профсоюзная"], branch_stats["Ватутинки"], branch_stats["Другие"]])

    # Возвращаем премиальный HTML-шаблон
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Клиника «ЯСНО ВИЖУ» — Панель управления</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background-color: #f8fafc; }}
            .custom-scrollbar::-webkit-scrollbar {{ width: 6px; }}
            .custom-scrollbar::-webkit-scrollbar-track {{ background: transparent; }}
            .custom-scrollbar::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 3px; }}
        </style>
    </head>
    <body class="text-slate-800 min-h-screen flex flex-col">
        
        <header class="bg-gradient-to-r from-teal-600 to-cyan-700 text-white shadow-lg px-6 py-4 flex-shrink-0">
            <div class="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
                <div class="flex items-center gap-4">
                    <div class="w-10 h-10 bg-white rounded-full flex items-center justify-center font-black text-teal-700 shadow-md">ЯВ</div>
                    <div>
                        <h1 class="text-lg font-black uppercase tracking-tight leading-none">ЯСНО ВИЖУ</h1>
                    </div>
                </div>
                <div class="flex items-center gap-3 bg-black/10 px-4 py-2 rounded-full border border-white/10">
                    <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                    <span class="text-xs font-bold text-teal-50">Администратор: <span class="underline font-black">{admin}</span></span>
                </div>
            </div>
        </header>

        <main class="max-w-7xl w-full mx-auto p-4 md:p-6 lg:p-8 flex-grow flex flex-col gap-6">
            
            <section class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col justify-between">
                    <span class="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Всего записей в БД</span>
                    <div class="flex items-baseline gap-2 mt-2">
                        <span class="text-3xl font-black text-slate-900">{total_appts}</span>
                        <span class="text-xs font-bold text-teal-600">пациентов</span>
                    </div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col justify-between">
                    <span class="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Напоминания в очереди</span>
                    <div class="flex items-baseline gap-2 mt-2">
                        <span class="text-3xl font-black text-slate-900">{active_jobs_count}</span>
                        <span class="text-xs font-bold text-amber-600">задач</span>
                    </div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col justify-between">
                    <span class="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Филиал Профсоюзная</span>
                    <div class="flex items-baseline gap-2 mt-2">
                        <span class="text-3xl font-black text-teal-600">{branch_stats["Профсоюзная"]}</span>
                        <span class="text-xs font-bold text-slate-400">визитов</span>
                    </div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col justify-between">
                    <span class="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Новые Ватутинки</span>
                    <div class="flex items-baseline gap-2 mt-2">
                        <span class="text-3xl font-black text-cyan-600">{branch_stats["Ватутинки"]}</span>
                        <span class="text-xs font-bold text-slate-400">визитов</span>
                    </div>
                </div>
            </section>

            <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm lg:col-span-2 flex flex-col justify-between min-h-[320px]">
                    <h3 class="text-xs font-black uppercase text-slate-400 tracking-widest mb-4">📊 ТОП-5 Врачей по записи</h3>
                    <div class="relative flex-grow h-full max-h-[240px]">
                        <canvas id="doctorsChart"></canvas>
                    </div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col justify-between min-h-[320px]">
                    <h3 class="text-xs font-black uppercase text-slate-400 tracking-widest mb-4">🏥 Нагрузка на филиалы</h3>
                    <div class="relative flex-grow h-full max-h-[220px] flex items-center justify-center">
                        <canvas id="branchesChart"></canvas>
                    </div>
                </div>
            </section>

            <section class="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start flex-grow">
                <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col max-h-[500px]">
                    <h3 class="text-xs font-black uppercase text-slate-400 tracking-widest mb-4 flex items-center justify-between">
                        <span>⏰ Очередь уведомлений</span>
                        <span class="bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full text-[11px] font-black">{active_jobs_count}</span>
                    </h3>
                    <div class="overflow-y-auto custom-scrollbar flex-grow pr-1">
                        {jobs_list_html}
                    </div>
                </div>
                
                <div class="bg-slate-900 p-5 rounded-2xl border border-slate-950 shadow-xl lg:col-span-2 flex flex-col h-[500px]">
                    <h3 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-3 flex items-center justify-between">
                        <span>📟 Консоль логов приложения (Последние 100 действий)</span>
                        <div class="flex gap-1.5">
                            <span class="w-2.5 h-2.5 rounded-full bg-red-500/30"></span>
                            <span class="w-2.5 h-2.5 rounded-full bg-yellow-500/30"></span>
                            <span class="w-2.5 h-2.5 rounded-full bg-green-500/30"></span>
                        </div>
                    </h3>
                    <div class="bg-slate-950 p-4 rounded-xl flex-grow overflow-y-auto custom-scrollbar border border-slate-800/60 shadow-inner">
                        {logs_html}
                    </div>
                </div>
            </section>

        </main>

        <script>
            // График ТОП-Врачей
            const ctxDocs = document.getElementById('doctorsChart').getContext('2d');
            new Chart(ctxDocs, {{
                type: 'bar',
                data: {{
                    labels: {js_doc_labels},
                    datasets: [{{
                        label: 'Количество записей к врачу ',
                        data: {js_doc_counts},
                        backgroundColor: 'rgba(50, 163, 150, 0.85)',
                        borderColor: '#32a396',
                        borderWidth: 1.5,
                        borderRadius: 8,
                        barThickness: 24
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{ beginAtZero: true, grid: {{ color: '#f1f5f9' }}, ticks: {{ font: {{ weight: 'bold', family: 'Inter' }} }} }},
                        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ weight: '700', family: 'Inter', size: 10 }} }} }}
                    }},
                    plugins: {{ legend: {{ display: false }} }}
                }}
            }});

            // График филиалов
            const ctxBranch = document.getElementById('branchesChart').getContext('2d');
            new Chart(ctxBranch, {{
                type: 'doughnut',
                data: {{
                    labels: ['Профсоюзная', 'Новые Ватутинки', 'Другие'],
                    datasets: [{{
                        data: {js_branch_counts},
                        backgroundColor: ['#32a396', '#06b6d4', '#cbd5e1'],
                        borderWidth: 3,
                        borderColor: '#ffffff'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ font: {{ weight: '700', family: 'Inter', size: 11 }}, boxWidth: 12, padding: 15 }} }}
                    }},
                    cutout: '65%'
                }}
            }});
        </script>
    </body>
    </html>
    """

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)