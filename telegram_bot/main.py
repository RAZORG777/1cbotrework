import sys
import os
import asyncio
import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from collections import deque
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# --- НАСТРОЙКА ПУТЕЙ ---
# Добавляем родительскую папку в пути Python, чтобы импортировать one_c_client
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, '.env')) # Загружаем .env из корня проекта

from one_c_client import OneCClient
from doctors_enricher import DOCTORS_EXTRA_INFO, enrich_doctors_data

# --- НАСТРОЙКА ЛОГИРОВАНИЯ (loguru) ---
from loguru import logger

log_buffer = deque(maxlen=100)
def web_log_sink(message):
    log_buffer.append(message.strip())

logger.remove() # Убираем стандартный вывод, чтобы настроить свой
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
logger.add("logs/telegram_bot.log", rotation="10 MB", retention="10 days", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", encoding="utf-8")
logger.add(web_log_sink, format="[{time:HH:mm:ss}] {message}")
# -------------------------

# --- НАСТРОЙКИ БАЗЫ ДАННЫХ (SQLAlchemy) ---
ADMIN_IDS = os.getenv("ADMIN_IDS", "5069522709").split(",")

REVIEWS_LINKS = {
    "Профсоюзная": "https://yandex.ru/maps/213/moscow/?ll=37.543560%2C55.660760&mode=poi&poi%5Bpoint%5D=37.543529%2C55.660638&poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D196039112145&z=17",
    "Новые Ватутинки": "https://yandex.ru/maps/213/moscow/?indoorLevel=1&ll=37.345203%2C55.518301&mode=poi&poi%5Bpoint%5D=37.344904%2C55.518219&poi%5Buri%5D=ymapsbm1%3A%2F%2Forg%3Foid%3D200998099919&z=17"
}

SQLALCHEMY_DATABASE_URL = "sqlite:///./appointments.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBAppointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(String, unique=True, index=True)
    platform = Column(String, default="telegram") 
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

# --- ФУНКЦИИ ОТПРАВКИ СООБЩЕНИЙ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def send_telegram_reminder(tg_id: str, text: str):
    # Используем твой новый прокси Cloudflare!
    url = f"https://tg-proxy-yasno.danicimo08.workers.dev/bot{BOT_TOKEN}/sendMessage"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(url, json={
                "chat_id": tg_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True 
            })
            resp_data = response.json()
            if response.status_code == 200 and resp_data.get("ok"):
                logger.success(f"📩 DEBUG: Сообщение доставлено в Telegram пациенту {tg_id}!")
                return
            else:
                logger.error(f"❌ DEBUG: Telegram API ошибка: {resp_data}")
                return
    except Exception as e:
        logger.warning(f"⚠️ DEBUG: Сетевая ошибка Telegram: {repr(e)}")
        logger.error(f"❌ DEBUG: Сообщение для {tg_id} не отправлено.")

# --- ЛОГИКА ЖИЗНЕННОГО ЦИКЛА ПРИЛОЖЕНИЯ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.start() 
    logger.info("🚀 Планировщик запущен")

    db = SessionLocal()
    appts = db.query(DBAppointment).all()
    restored_count = 0
    for appt in appts:
        try:
            appt_dt = datetime.strptime(f"{appt.date} {appt.time}", "%Y-%m-%d %H:%M")
            fio_short = f"{appt.first_name} {appt.middle_name}".strip()
            
            for rem_type, delta in [("rem24h", 24), ("rem2h", 2)]:
                rem_time = appt_dt - timedelta(hours=delta)
                if rem_time > datetime.now():
                    job_id = f"{rem_type}_{appt.tg_id}"
                    msg = f"{fio_short}\n🔔 Напоминаем, что ваш визит в клинику «ЯСНО ВИЖУ» состоится через {delta} ч. {appt.date} в {appt.time}"
                    scheduler.add_job(send_telegram_reminder, 'date', run_date=rem_time, args=[appt.tg_id, msg], id=job_id, replace_existing=True)
                    restored_count += 1
        except Exception as e: pass
    db.close()
    if restored_count > 0: logger.success(f"✅ Восстановлено {restored_count} задач напоминаний")

    yield
    scheduler.shutdown()
    logger.info("🛑 Планировщик остановлен")

app = FastAPI(lifespan=lifespan)

jobstores = { 'default': SQLAlchemyJobStore(url='sqlite:///appointments.db') }
scheduler = AsyncIOScheduler(jobstores=jobstores)

client = OneCClient(base_url=os.getenv("ONEC_URL"), auth=(os.getenv("ONEC_USER"), os.getenv("ONEC_PASSWORD")))

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
    platform: str = "telegram"
    old_appointment_id: str = None 

class CancelRequest(BaseModel):
    tg_id: str

# --- ЭНДПОИНТЫ ---
@app.get("/")
async def read_index(): return FileResponse("index.html")

@app.get("/Логотип.png")
async def get_logo(): return FileResponse("Логотип.png")

@app.get("/doctors")
async def get_doctors(branch: str = None, date: str = None):
    # Получаем сухие данные из 1С
    response = await client.get_doctors(branch, date)
    
    # ✅ ИСПРАВЛЕНО: Передаем target_branch=branch для фильтрации
    if isinstance(response, dict) and "data" in response:
        response["data"] = enrich_doctors_data(response["data"], target_branch=branch)
    elif isinstance(response, list):
        response = enrich_doctors_data(response, target_branch=branch)
        
    return response

@app.get("/services")
async def get_services(doctor_id: str = None): return await client.get_services(doctor_id)

# ✅ ИСПРАВЛЕНО: Эндпоинт теперь принимает start_date и end_date
@app.get("/schedule")
async def get_schedule(doctor_id: str, branch: str = None, date: str = None, start_date: str = None, end_date: str = None): 
    return await client.get_schedule(doctor_id=doctor_id, date=date, branch=branch, start_date=start_date, end_date=end_date)

@app.get("/schedule")
async def get_schedule(doctor_id: str, date: str, branch: str = None): return await client.get_schedule(doctor_id, date, branch)

@app.post("/book")
async def book_appointment(req: BookingRequest, background_tasks: BackgroundTasks, send_notifications: bool = False, db: Session = Depends(get_db)):
    existing_appt = db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first()
    if existing_appt: return {"status": "error", "error": "SECOND_BOOKING_ERROR"}

    try:
        data_to_send = req.model_dump()
        logger.info(f"▶️ DEBUG: Попытка записи {req.patient.last_name} {req.patient.first_name} (telegram)...")
        
        response = await client.create_booking(data_to_send)
        
        if response.get("status") == "success":
            appointment_id = response.get("appointment_id", "ID_NOT_FOUND")
            logger.success(f"✅ DEBUG: Успешная запись в 1С. ID: {appointment_id}")
            
            new_appt = DBAppointment(
                tg_id=req.tg_id, platform="telegram", appointment_id=appointment_id, branch=req.branch, doctor_id=req.doctor_id,
                doctor_name=req.doctor_name, service_id=req.service_id, service_name=req.service_name,
                date=req.date, time=req.time, first_name=req.patient.first_name, last_name=req.patient.last_name,
                middle_name=req.patient.middle_name, phone=req.patient.phone, birth_date=req.patient.birth_date
            )
            db.add(new_appt)
            db.commit()
            
            fio_short = f"{req.patient.first_name} {req.patient.middle_name}".strip()
            formatted_date = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            branch_name = "Профсоюзная" if req.branch == "Профсоюзная" else "Новые Ватутинки"
            link_branch = "https://yasno-vizhu.com/contacts/"
            link_map = "https://yandex.ru/maps/" 
            
            confirm_msg = (
                f"{fio_short}\n"
                f"<b>{formatted_date}</b> вы записаны в клинику Ясно вижу.\n\n"
                f"<b>{req.time}</b> <a href='{link_branch}'>{branch_name}</a> 📍\n"
                f"Проложить маршрут - <a href='{link_map}'>тут 🏥</a>\n\n"
                f"Ждем вас в назначенное время!"
            )
            
            background_tasks.add_task(send_telegram_reminder, req.tg_id, confirm_msg)

            if send_notifications:
                schedule_notifications(req, fio_short, formatted_date, branch_name, link_branch, link_map)
                
        return response
    except Exception as e:
        logger.error(f"❌ DEBUG: Ошибка при бронировании: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reschedule")
async def reschedule_appointment(req: BookingRequest, background_tasks: BackgroundTasks, send_notifications: bool = False, db: Session = Depends(get_db)):
    if not req.old_appointment_id: return {"status": "error", "error": "Не передан ID старой записи"}
        
    existing_appt = db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first()
    if not existing_appt: return {"status": "error", "error": "Активная запись не найдена"}

    try:
        data_to_send = req.model_dump() 
        response = await client._make_request("POST", "reschedule", json=data_to_send)
        
        if response.get("status") == "success":
            new_appointment_id = response.get("appointment_id", req.old_appointment_id)
            
            existing_appt.platform = "telegram"
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
            
            db.commit()
            
            for prefix in ["rem24h_", "rem2h_", "remsmart_", "feedback_"]:
                job_id = f"{prefix}{req.tg_id}"
                if scheduler.get_job(job_id): scheduler.remove_job(job_id)
            
            fio_short = f"{req.patient.first_name} {req.patient.middle_name}".strip()
            formatted_date = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
            branch_name = "Профсоюзная" if req.branch == "Профсоюзная" else "Новые Ватутинки"
            link_branch = "https://yasno-vizhu.com/contacts/"
            
            confirm_msg = (
                f"🔄 {fio_short}\nВаша запись успешно <b>перенесена</b>!\n\n"
                f"Новая дата: <b>{formatted_date}</b>\nВремя: <b>{req.time}</b>\n"
                f"Врач: {req.doctor_name}\nФилиал: <a href='{link_branch}'>{branch_name}</a> 📍\n\nЖдем вас!"
            )
            
            background_tasks.add_task(send_telegram_reminder, req.tg_id, confirm_msg)

            if send_notifications:
                schedule_notifications(req, fio_short, formatted_date, branch_name, link_branch, "https://yandex.ru/maps/")
                
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def schedule_notifications(req, fio_short, formatted_date, branch_name, link_branch, link_map):
    try:
        appt_dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        rem_2h = appt_dt - timedelta(hours=2)
        if rem_2h > now:
            msg_2h = f"{fio_short}\n<b>{formatted_date}</b> вы записаны...\nНапоминаем: ваш визит через 2 часа!"
            scheduler.add_job(send_telegram_reminder, 'date', run_date=rem_2h, args=[req.tg_id, msg_2h], id=f"rem2h_{req.tg_id}", replace_existing=True)

        rem_24h = appt_dt - timedelta(hours=24)
        if rem_24h > now:
            msg_24h = f"{fio_short}\n<b>{formatted_date}</b> вы записаны...\nОператор Call-Центра свяжется с вами для подтверждения записи."
            scheduler.add_job(send_telegram_reminder, 'date', run_date=rem_24h, args=[req.tg_id, msg_24h], id=f"rem24h_{req.tg_id}", replace_existing=True)
    except Exception as ex: logger.error(f"❌ DEBUG: Ошибка при расчете времени: {ex}")

@app.get("/my_appointment")
async def get_my_appointment(tg_id: str, db: Session = Depends(get_db)):
    appt = db.query(DBAppointment).filter(DBAppointment.tg_id == tg_id).first()
    if appt:
        return {"status": "success", "has_appointment": True, "data": { "appointment_id": appt.appointment_id, "branch": appt.branch, "date": appt.date, "time": appt.time, "doctor_name": appt.doctor_name, "service_name": appt.service_name }}
    return {"status": "success", "has_appointment": False}

@app.post("/cancel")
async def cancel_appointment(request: CancelRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    tg_id = request.tg_id
    appt = db.query(DBAppointment).filter(DBAppointment.tg_id == tg_id).first()
    if appt:
        try:
            res_1c = await client.cancel_booking(appt.appointment_id)
            if res_1c.get("status") == "success":
                db.delete(appt)
                db.commit()
                for prefix in ["rem24h_", "rem2h_", "remsmart_", "feedback_"]:
                    job_id = f"{prefix}{tg_id}"
                    if scheduler.get_job(job_id): scheduler.remove_job(job_id)
                        
                текст_отмены = "✅ <b>Ваша запись успешно отменена.</b>\n\nБудем рады видеть вас снова! 🏥"
                background_tasks.add_task(send_telegram_reminder, tg_id, текст_отмены)
                return {"status": "success"}
            else:
                return {"status": "error", "error": res_1c.get("error")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return {"status": "error", "error": "Запись не найдена"}
    
@app.post("/api/v1/internal/cancel-visit")
async def cancel_visit_from_1c(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    appt_id = data.get("appointment_id")
    appt = db.query(DBAppointment).filter(DBAppointment.appointment_id == appt_id).first()
    if appt:
        tg_id = appt.tg_id 
        for job in scheduler.get_jobs():
            if str(tg_id) in job.id or str(appt_id) in job.id: scheduler.remove_job(job.id)
        db.delete(appt)
        db.commit()
        
        текст_отмены = "😔 <b>Ваша запись была отменена нашими администраторами.</b>\n\nВы всегда можете записаться заново через меню! 🏥"
        background_tasks.add_task(send_telegram_reminder, tg_id, текст_отмены)
        return {"status": "success"}
    return {"status": "not_found"}
    
@app.post("/api/v1/internal/finish-visit")
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
            link = REVIEWS_LINKS.get(branch_key, REVIEWS_LINKS.get("Профсоюзная", "https://yandex.ru/maps/"))
            
            msg_feedback = (
                f"🌟 <b>{fio}</b>, надеемся, вам понравилось в нашей клинике!\n\n"
                f"Будем очень благодарны за ваш отзыв:\n"
                f"👉 <a href='{link}'>Оставить отзыв на Яндекс.Картах</a>"
            )
        
        # 3. Отправляем через 20 минут после сигнала (используем send_telegram_reminder)
        run_at = datetime.now() + timedelta(minutes=20)
        
        scheduler.add_job(
            send_telegram_reminder, 
            'date', 
            run_date=run_at, 
            args=[appt.tg_id, msg_feedback], 
            id=f"feedback_{appt_id}", 
            replace_existing=True
        )
        return {"status": "success"}
        
    return {"status": "error", "message": "Not found"}

# --- ЗАЩИТА АДМИНКИ ---
security = HTTPBasic()
def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not (secrets.compare_digest(credentials.username, "admin") and secrets.compare_digest(credentials.password, "5069522709")):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

@app.post("/admin/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        update = await request.json()
        if "message" in update:
            msg = update["message"]
            chat_id = str(msg.get("chat", {}).get("id"))
            text = msg.get("text", "")
            first_name = msg.get("from", {}).get("first_name", "Гость")

            if text == "/start":
                webapp_url_record = os.getenv("WEBAPP_URL")
                webapp_url_site = os.getenv("WEBAPP_URL2")
                inline_keyboard = { "inline_keyboard": [ [ { "text": "Записаться ✅", "web_app": {"url": webapp_url_record} } ], [ { "text": "🌐 Наш сайт", "web_app": {"url": webapp_url_site} } ] ] }
                welcome_text = f"Здравствуйте, {first_name}! 👋\n\nДобро пожаловать в бота клиники «ЯСНО ВИЖУ»."
                
                # ---> ЗДЕСЬ ТЕПЕРЬ ТОЖЕ СТОИТ CLOUDFLARE <---
                url = f"https://tg-proxy-yasno.danicimo08.workers.dev/bot{BOT_TOKEN}/sendMessage"
                
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    await http_client.post(url, json={ "chat_id": chat_id, "text": "<i>Обновление меню...</i>", "reply_markup": {"remove_keyboard": True}, "parse_mode": "HTML" })
                    await http_client.post(url, json={ "chat_id": chat_id, "text": welcome_text, "reply_markup": inline_keyboard, "parse_mode": "HTML" })
            elif text == "/stats" and chat_id in ADMIN_IDS:
                stats_msg = f"⚙️ <b>Панель управления (Telegram)</b>\n\n👥 Пациентов в базе: <b>{db.query(DBAppointment).count()}</b>\n🕒 Запланированных задач: <b>{len(scheduler.get_jobs())}</b>"
                await send_telegram_reminder(chat_id, stats_msg)
    except Exception as e: 
        logger.error(f"❌ Ошибка при обработке вебхука: {e}")
    return {"status": "ok"}

@app.get("/admin/logs", response_class=PlainTextResponse)
async def get_admin_logs(admin: str = Depends(get_current_admin)): return "\n".join(reversed(log_buffer)) if log_buffer else "Логи пусты..."

# ОБНОВЛЕННАЯ АДМИН-ПАНЕЛЬ
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    jobs_html = ""
    now = datetime.now()
    for job in scheduler.get_jobs():
        run_time_str = job.next_run_time.strftime('%d.%m.%Y %H:%M:%S') if job.next_run_time else "Пауза"
        try:
            time_diff = (job.next_run_time - now.astimezone(job.next_run_time.tzinfo)).total_seconds()
            countdown = f" (через {int(time_diff // 60)}м)"
        except Exception:
            countdown = ""
        jobs_html += f"<li><b>ID:</b> {job.id} <br> <b>Сработает:</b> {run_time_str} <b style='color:teal'>{countdown}</b></li><hr>"
    
    logs_html = "".join(f"<div style='margin-bottom: 4px; border-bottom: 1px solid #ddd; padding-bottom: 2px;'>{log}</div>" for log in reversed(log_buffer))
    if not logs_html:
        logs_html = "<div>Логи пусты...</div>"

    return f"""
    <html>
    <head>
        <title>Админ-панель Telegram</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: sans-serif; padding: 20px; background-color: #f9fafb; }}
            h2 {{ color: #32a396; border-bottom: 2px solid #32a396; padding-bottom: 5px; }}
            .container {{ display: flex; gap: 20px; }}
            .panel {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); width: 50%; }}
            .logs-box {{ background: #1e1e1e; color: #00ff00; font-family: monospace; font-size: 13px; height: 500px; overflow-y: auto; padding: 15px; border-radius: 5px; line-height: 1.4; }}
            li {{ margin-bottom: 10px; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h2>Панель управления (Telegram) | Пользователь: {admin}</h2>
        <div class="container">
            <div class="panel">
                <h3>⚙️ Очередь напоминаний</h3>
                <ul>{jobs_html if jobs_html else "<li>Нет запланированных задач</li>"}</ul>
            </div>
            <div class="panel">
                <h3>📝 Логи приложения</h3>
                <div class="logs-box">
                    {logs_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)