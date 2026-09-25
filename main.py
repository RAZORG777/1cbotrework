import os
import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from one_c_client import OneCClient
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import builtins
from collections import deque
import json

# --- ПЕРЕХВАТЧИК ЛОГОВ ---
log_buffer = deque(maxlen=100)
original_print = builtins.print

def custom_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    log_buffer.append(log_line)
    original_print(*args, **kwargs)

builtins.print = custom_print
# -------------------------

# --- НАСТРОЙКИ БАЗЫ ДАННЫХ (SQLAlchemy) ---
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

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

# --- ЛОГИКА ЖИЗНЕННОГО ЦИКЛА ПРИЛОЖЕНИЯ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.start() 
    print("🚀 Планировщик запущен (с поддержкой базы данных)")

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
                    msg = f"{fio_short}\n🔔 Напоминание: ваш визит в клинику «ЯСНО ВИЖУ» через {delta} ч. в {appt.time}!"
                    scheduler.add_job(send_telegram_reminder, 'date', run_date=rem_time, args=[appt.tg_id, msg], id=job_id, replace_existing=True)
                    restored_count += 1
        except Exception as e:
            print(f"⚠️ Ошибка восстановления задачи {appt.tg_id}: {e}")
    db.close()
    
    if restored_count > 0:
        print(f"✅ Восстановлено {restored_count} задач напоминаний из БД")

    yield
    scheduler.shutdown()
    print("🛑 Планировщик остановлен")

app = FastAPI(lifespan=lifespan)

jobstores = { 'default': SQLAlchemyJobStore(url='sqlite:///appointments.db') }
scheduler = AsyncIOScheduler(jobstores=jobstores)

client = OneCClient(
    base_url=os.getenv("ONEC_URL"), 
    auth=(os.getenv("ONEC_USER"), os.getenv("ONEC_PASSWORD"))
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

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
    old_appointment_id: str = None # ДЛЯ ПЕРЕНОСА ЗАПИСИ

class CancelRequest(BaseModel):
    tg_id: str

# --- ФУНКЦИЯ ОТПРАВКИ В ТЕЛЕГРАМ ---
async def send_telegram_reminder(tg_id: str, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(url, json={
                "chat_id": tg_id, 
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True 
            })
            resp_data = response.json()
            if response.status_code == 200 and resp_data.get("ok"):
                print(f"✅ DEBUG: Сообщение успешно доставлено пользователю {tg_id}")
            else:
                print(f"❌ DEBUG: Telegram API отказал в отправке! Ошибка: {resp_data}")
        except Exception as e:
            print(f"❌ DEBUG: Сетевая ошибка при отправке сообщения: {e}")

# --- ЭНДПОИНТЫ ---
@app.get("/")
async def read_index(): return FileResponse("index.html")

@app.get("/Логотип.png")
async def get_logo(): return FileResponse("Логотип.png")

@app.get("/doctors")
async def get_doctors(branch: str = None, date: str = None):
    return await client.get_doctors(branch, date)

@app.get("/services")
async def get_services(doctor_id: str = None): 
    return await client.get_services(doctor_id)

@app.get("/schedule")
async def get_schedule(doctor_id: str, date: str, branch: str = None):
    # 1. Получаем сырое расписание от 1С (шаг 15 минут)
    response = await client.get_schedule(doctor_id, date, branch)
    
    # 2. Если 1С вернула успешный ответ и список слотов
    if response.get("status") == "success" and "free_slots" in response:
        original_slots = response["free_slots"]
        valid_slots = set(original_slots) # Превращаем в множество для быстрого поиска
        filtered_slots = []
        
        for slot in original_slots:
            try:
                # Превращаем строку "10:00" в объект времени
                time_obj = datetime.strptime(slot, "%H:%M")
                
                # Вычисляем время следующего 15-минутного слота ("10:15")
                next_time_obj = time_obj + timedelta(minutes=15)
                next_slot_str = next_time_obj.strftime("%H:%M")
                
                # Если следующий 15-минутный кусок ТОЖЕ свободен, 
                # значит у нас есть полноценные 30 минут для диагностики!
                if next_slot_str in valid_slots:
                    filtered_slots.append(slot)
            except Exception as e:
                print(f"⚠️ Ошибка при фильтрации слота {slot}: {e}")
                pass
                
        # 3. Подменяем список слотов на отфильтрованный
        response["free_slots"] = filtered_slots
        
    return response

# НОВАЯ ЗАПИСЬ
@app.post("/book")
async def book_appointment(req: BookingRequest, send_notifications: bool = False, db: Session = Depends(get_db)):
    existing_appt = db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first()
    if existing_appt:
        return {"status": "error", "error": "SECOND_BOOKING_ERROR"}

    try:
        data_to_send = req.model_dump() 
        print(f"▶️ DEBUG: Попытка записи пациента {req.patient.last_name} {req.patient.first_name}...")
        
        response = await client.create_booking(data_to_send)
        
        if response.get("status") == "success":
            appointment_id = response.get("appointment_id", "ID_NOT_FOUND")
            print(f"✅ DEBUG: Успешная запись в 1С. ID: {appointment_id}")
            
            new_appt = DBAppointment(
                tg_id=req.tg_id, appointment_id=appointment_id, branch=req.branch, doctor_id=req.doctor_id,
                doctor_name=req.doctor_name, service_id=req.service_id, service_name=req.service_name,
                date=req.date, time=req.time, first_name=req.patient.first_name, last_name=req.patient.last_name,
                middle_name=req.patient.middle_name, phone=req.patient.phone, birth_date=req.patient.birth_date
            )
            db.add(new_appt)
            db.commit()
            print("💾 DEBUG: Данные пациента сохранены в SQLite.")
            
            fio_short = f"{req.patient.first_name} {req.patient.middle_name}".strip()
            formatted_date = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            if req.branch == "Профсоюзная":
                branch_name = "Профсоюзная"
                link_branch = "https://yasno-vizhu.com/contacts/"
                link_map = "https://yandex.ru/maps/213/moscow/?ll=37.469009%2C55.554740&mode=routes&rtext=~55.660637%2C37.543529&rtt=auto&ruri=~&z=14"
            else:
                branch_name = "Новые Ватутинки"
                link_branch = "https://yasno-vizhu.com/contacts/"
                link_map = "https://yandex.ru/maps/213/moscow/?ll=37.469699%2C55.555274&mode=routes&rtext=~55.518290%2C37.345203&rtt=auto&ruri=~&z=14"
            
            confirm_msg = (
                f"{fio_short}\n"
                f"<b>{formatted_date}</b> вы записаны в клинику Ясно вижу.\n\n"
                f"<b>{req.time}</b> <a href='{link_branch}'>{branch_name}</a> 📍\n"
                f"Проложить маршрут - <a href='{link_map}'>тут 🏥</a>\n\n"
                f"Ждем вас в назначенное время!"
            )
            await send_telegram_reminder(req.tg_id, confirm_msg)

            if send_notifications:
                schedule_notifications(req, fio_short, formatted_date, branch_name, link_branch, link_map)
                
        return response
    except Exception as e:
        print(f"❌ DEBUG: Критическая ошибка при бронировании: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ПЕРЕНОС ЗАПИСИ
@app.post("/reschedule")
async def reschedule_appointment(req: BookingRequest, send_notifications: bool = False, db: Session = Depends(get_db)):
    if not req.old_appointment_id:
        return {"status": "error", "error": "Не передан ID старой записи"}
        
    existing_appt = db.query(DBAppointment).filter(DBAppointment.tg_id == req.tg_id).first()
    if not existing_appt:
        return {"status": "error", "error": "Активная запись не найдена в базе бота"}

    try:
        data_to_send = req.model_dump() 
        print(f"▶️ DEBUG: Попытка ПЕРЕНОСА записи для {req.patient.last_name} {req.patient.first_name}...")
        
        # Используем внутренний метод клиента для отправки на новый URL
        response = await client._make_request("POST", "reschedule", json=data_to_send)
        
        if response.get("status") == "success":
            new_appointment_id = response.get("appointment_id", req.old_appointment_id)
            print(f"✅ DEBUG: Успешный перенос в 1С. ID: {new_appointment_id}")
            
            # Обновляем старую запись новыми данными
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
            print("💾 DEBUG: Новые данные сохранены в SQLite.")
            
            # Удаляем старые будильники
            for prefix in ["rem24h_", "rem2h_", "remsmart_", "feedback_"]:
                job_id = f"{prefix}{req.tg_id}"
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
            
            fio_short = f"{req.patient.first_name} {req.patient.middle_name}".strip()
            formatted_date = datetime.strptime(req.date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            if req.branch == "Профсоюзная":
                branch_name = "Профсоюзная"
                link_branch = "https://yasno-vizhu.com/contacts/"
                link_map = "https://yandex.ru/maps/213/moscow/?ll=37.469009%2C55.554740&mode=routes&rtext=~55.660637%2C37.543529&rtt=auto&ruri=~&z=14"
            else:
                branch_name = "Новые Ватутинки"
                link_branch = "https://yasno-vizhu.com/contacts/"
                link_map = "https://yandex.ru/maps/213/moscow/?ll=37.469699%2C55.555274&mode=routes&rtext=~55.518290%2C37.345203&rtt=auto&ruri=~&z=14"
            
            confirm_msg = (
                f"🔄 {fio_short}\n"
                f"Ваша запись успешно <b>перенесена</b>!\n\n"
                f"Новая дата: <b>{formatted_date}</b>\n"
                f"Время: <b>{req.time}</b>\n"
                f"Врач: {req.doctor_name}\n"
                f"Филиал: <a href='{link_branch}'>{branch_name}</a> 📍\n\n"
                f"Ждем вас!"
            )
            await send_telegram_reminder(req.tg_id, confirm_msg)

            if send_notifications:
                schedule_notifications(req, fio_short, formatted_date, branch_name, link_branch, link_map)
                
        return response
    except Exception as e:
        print(f"❌ DEBUG: Критическая ошибка при переносе: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def schedule_notifications(req, fio_short, formatted_date, branch_name, link_branch, link_map):
    try:
        appt_dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        time_until_appt = appt_dt - now

        rem_2h = appt_dt - timedelta(hours=2)
        if rem_2h > now:
            msg_2h = (
                f"{fio_short}\n"
                f"<b>{formatted_date}</b> вы записаны в клинику Ясно вижу.\n\n"
                f"<b>{req.time}</b> <a href='{link_branch}'>{branch_name}</a> 📍\n"
                f"Проложить маршрут - <a href='{link_map}'>тут 🏥</a>\n\n"
                f"Напоминаем: ваш визит через 2 часа!"
            )
            scheduler.add_job(send_telegram_reminder, 'date', run_date=rem_2h, args=[req.tg_id, msg_2h], id=f"rem2h_{req.tg_id}", replace_existing=True)

        rem_24h = appt_dt - timedelta(hours=24)
        if rem_24h > now:
            msg_24h = (
                f"{fio_short}\n"
                f"<b>{formatted_date}</b> вы записаны в клинику Ясно вижу.\n\n"
                f"<b>{req.time}</b> <a href='{link_branch}'>{branch_name}</a> 📍\n"
                f"Проложить маршрут - <a href='{link_map}'>тут 🏥</a>\n\n"
                f"Пожалуйста, подтвердите ваши завтрашние приемы."
            )
            scheduler.add_job(send_telegram_reminder, 'date', run_date=rem_24h, args=[req.tg_id, msg_24h], id=f"rem24h_{req.tg_id}", replace_existing=True)
        
        elif time_until_appt > timedelta(hours=5):
            smart_rem_time = now + timedelta(hours=2)
            if smart_rem_time < rem_2h:
                msg_smart = (
                    f"{fio_short}\n"
                    f"💡 Напоминаем: вы успешно записаны на визит в <b>{req.time}</b>.\n"
                    f"Филиал: <a href='{link_branch}'>{branch_name}</a>. Ждем вас!"
                )
                scheduler.add_job(send_telegram_reminder, 'date', run_date=smart_rem_time, args=[req.tg_id, msg_smart], id=f"remsmart_{req.tg_id}", replace_existing=True)
    except Exception as ex:
        print(f"❌ DEBUG: Ошибка при расчете времени уведомлений: {ex}")

@app.get("/my_appointment")
async def get_my_appointment(tg_id: str, db: Session = Depends(get_db)):
    appt = db.query(DBAppointment).filter(DBAppointment.tg_id == tg_id).first()
    if appt:
        # ВАЖНО: Добавили appointment_id в ответ для переноса
        data = { 
            "appointment_id": appt.appointment_id,
            "branch": appt.branch, 
            "date": appt.date, 
            "time": appt.time, 
            "doctor_name": appt.doctor_name, 
            "service_name": appt.service_name 
        }
        return {"status": "success", "has_appointment": True, "data": data}
    return {"status": "success", "has_appointment": False}

@app.post("/cancel")
async def cancel_appointment(request: CancelRequest, db: Session = Depends(get_db)):
    tg_id = request.tg_id
    print(f"\n▶️ DEBUG [cancel]: Запрос на отмену записи от tg_id: {tg_id}...")
    
    appt = db.query(DBAppointment).filter(DBAppointment.tg_id == tg_id).first()
    if appt:
        try:
            # 1. Отменяем в 1С
            res_1c = await client.cancel_booking(appt.appointment_id)
            if res_1c.get("status") == "success":
                # 2. Удаляем из базы бота
                db.delete(appt)
                db.commit()
                
                # 3. Чистим все таймеры
                for prefix in ["rem24h_", "rem2h_", "remsmart_", "feedback_"]:
                    job_id = f"{prefix}{tg_id}"
                    if scheduler.get_job(job_id):
                        scheduler.remove_job(job_id)
                        
                print(f"✅ DEBUG [cancel]: УСПЕХ! Запись {appt.appointment_id} отменена в 1С.")
                
                # === 4. ОТПРАВЛЯЕМ ПОДТВЕРЖДЕНИЕ В ЧАТ ПАЦИЕНТУ ===
                try:
                    текст_отмены = (
                        "✅ <b>Ваша запись успешно отменена.</b>\n\n"
                        "Если вы захотите выбрать другое удобное время, "
                        "просто нажмите кнопку записи в меню. Будем рады видеть вас снова! 🏥"
                    )
                    await send_telegram_reminder(tg_id, текст_отмены)
                    print(f"✉️ [cancel]: Пациенту {tg_id} отправлено подтверждение отмены в чат!")
                except Exception as e:
                    print(f"❌ [cancel]: Ошибка при отправке сообщения в чат: {e}")
                # ====================================================

                return {"status": "success"}
            else:
                return {"status": "error", "error": res_1c.get("error")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
    return {"status": "error", "error": "Запись не найдена"}
    
@app.post("/api/v1/internal/cancel-visit")
async def cancel_visit_from_1c(data: dict, db: Session = Depends(get_db)):
    print(f"🗑 [CANCEL] ВХОДЯЩИЙ СИГНАЛ ОТМЕНЫ ОТ 1С: {data}")
    
    appt_id = data.get("appointment_id")
    
    # 1. Ищем заявку в базе бота
    appt = db.query(DBAppointment).filter(DBAppointment.appointment_id == appt_id).first()
    
    if appt:
        tg_id = appt.tg_id 
        
        # === 2. ОЧИСТКА ПЛАНИРОВЩИКА (APScheduler) ===
        jobs_removed = 0
        for job in scheduler.get_jobs():
            # Ищем задачи, в ID которых есть либо tg_id пациента, либо appt_id заявки
            if str(tg_id) in job.id or str(appt_id) in job.id:
                scheduler.remove_job(job.id)
                jobs_removed += 1
        print(f"🧹 [CANCEL] Очищено таймеров в планировщике: {jobs_removed}")
        
        # 3. Удаляем саму заявку из базы
        print(f"✅ [CANCEL] Удаляем запись {appt_id} из базы бота")
        db.delete(appt)
        db.commit()
        
        # === 4. ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ ПАЦИЕНТУ ===
        try:
            текст_отмены = (
                "😔 <b>Ваша запись была отменена нашими администраторами.</b>\n\n"
                "Если ваши планы изменились или вы хотите подобрать другое удобное время, "
                "вы всегда можете записаться заново через меню! 🏥"
            )
            # ИСПОЛЬЗУЕМ ТВОЮ ФУНКЦИЮ ВМЕСТО bot.send_message
            await send_telegram_reminder(tg_id, текст_отмены)
            print(f"✉️ [CANCEL] Пациенту {tg_id} отправлено сообщение об отмене!")
        except Exception as e:
            print(f"❌ [CANCEL] Ошибка при отправке сообщения пациенту: {e}")
            
        return {"status": "success"}
        
    print(f"⚠️ [CANCEL] Запись {appt_id} не найдена в боте (возможно, уже удалена).")
    return {"status": "not_found"}
    
@app.post("/api/v1/internal/finish-visit")
async def finish_visit(data: dict, db: Session = Depends(get_db)):
    print(f"📥 ВХОДЯЩИЙ СИГНАЛ ОТЗЫВА: {data}")
    
    appt_id = data.get("appointment_id")
    appt = db.query(DBAppointment).filter(DBAppointment.appointment_id == appt_id).first()
    
    if appt:
        # 1. Формируем персональное обращение и ссылку по филиалу
        fio = f"{appt.first_name} {appt.middle_name}".strip()
        
        # Берем ссылку для филиала (если не найдет, возьмет Профсоюзную по умолчанию)
        link = REVIEWS_LINKS.get(appt.branch, REVIEWS_LINKS.get("Профсоюзная", "https://yandex.ru/maps/"))
        
        msg_feedback = (
            f"🌟 {fio}, надеемся, вам понравилось у нас!\n\n"
            f"Мы стараемся быть лучше для вас. Будем очень благодарны, если вы уделите минутку и оставите отзыв о нашей работе:\n"
            f"👉 <a href='{link}'>Оставить отзыв на Яндекс.Картах</a>"
        )

        # 2. Ставим таймер (сейчас 1 минута для теста)
        run_at = datetime.now() + timedelta(minutes=20)
        
        # 3. Планируем задачу
        # ВАЖНО: id=f"feedback_{appt_id}" предотвращает ошибку ConflictingIdError!
        scheduler.add_job(
            send_telegram_reminder, 
            'date', 
            run_date=run_at, 
            args=[appt.tg_id, msg_feedback], 
            id=f"feedback_{appt_id}", 
            replace_existing=True
        )
        
        print(f"✅ Отзыв для '{fio}' запланирован на {run_at.strftime('%H:%M:%S')}")
        return {"status": "success"}
        
    print(f"❌ ОШИБКА: Запись {appt_id} не найдена в базе.")
    return {"status": "error", "message": "Not found"}

# --- ЗАЩИТА АДМИНКИ ---
security = HTTPBasic()

def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_correct_username = secrets.compare_digest(credentials.username, "admin")
    is_correct_password = secrets.compare_digest(credentials.password, "5069522709") 
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
    
# --- ПРИЕМ СООБЩЕНИЙ ИЗ TELEGRAM (WEBHOOK) ---
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
                webapp_url = os.getenv("WEBAPP_URL2")
                keyboard = { "keyboard": [[ { "text": "🌐 Наш сайт", "web_app": {"url": webapp_url} } ]], "resize_keyboard": True }
                
                welcome_text = (
                    f"Здравствуйте, {first_name}! 👋\n\n"
                    "Добро пожаловать в бота клиники «ЯСНО ВИЖУ». "
                    "Нажмите кнопку ниже, чтобы выбрать врача, посмотреть свободное время и записаться на прием."
                )
                
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                async with httpx.AsyncClient() as http_client:
                    await http_client.post(url, json={ "chat_id": chat_id, "text": welcome_text, "reply_markup": keyboard, "parse_mode": "HTML" })

            elif text == "/stats":
                if chat_id in ADMIN_IDS:
                    total_appts = db.query(DBAppointment).count()
                    jobs = scheduler.get_jobs()
                    stats_msg = f"⚙️ <b>Панель управления (Telegram)</b>\n\n👥 Пациентов в базе: <b>{total_appts}</b>\n🕒 Запланированных задач: <b>{len(jobs)}</b>"
                    await send_telegram_reminder(chat_id, stats_msg)

    except Exception as e:
        print(f"❌ Ошибка при обработке вебхука: {e}")
        
    return {"status": "ok"}

@app.get("/admin/logs", response_class=PlainTextResponse)
async def get_admin_logs(admin: str = Depends(get_current_admin)):
    logs_text = "\n".join(reversed(log_buffer))
    if not logs_text: return "Логи пока пусты. Бот только что запущен..."
    return logs_text

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    appts = db.query(DBAppointment).all()
    total_appts = len(appts)
    jobs = scheduler.get_jobs()
    
    jobs_html = ""
    now = datetime.now()

    for job in jobs:
        run_time_str = "Пауза"
        countdown = ""
        if job.next_run_time:
            run_time_str = job.next_run_time.strftime('%d.%m.%Y %H:%M:%S')
            diff = job.next_run_time - now.astimezone(job.next_run_time.tzinfo)
            total_sec = diff.total_seconds()
            if total_sec > 0:
                countdown = f" (через {int(total_sec//60)}м {int(total_sec%60)}с)"

        style = "color: #e67e22;" if "feedback" in job.id else ""
        jobs_html += f"<li style='{style}'><b>ID:</b> {job.id} <br> <b>Сработает:</b> {run_time_str} <b style='color:red'>{countdown}</b></li><hr>"
        
    logs_text = "\n".join(reversed(log_buffer))
    if not logs_text: logs_text = "Логи пока пусты..."
        
    html_content = f"""
    <html>
        <head><title>Админ-панель</title><meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background-color: #f4f7f6; padding: 20px; }}
            .card {{ background: white; padding: 25px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }}
            .stat {{ font-size: 24px; color: #3498db; font-weight: bold; }}
            .log-console {{ width: 100%; height: 350px; background-color: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 8px; }}
        </style>
        </head>
        <body>
            <div style="max-width: 900px; margin: auto;">
                <h1>⚙️ Панель управления ботом</h1>
                <div class="card">
                    <h3>📊 Статистика базы данных</h3>
                    <p>Пациентов в очереди: <span class="stat">{total_appts}</span></p>
                </div>
                <div class="card">
                    <h3>🖥️ Логи сервера</h3>
                    <textarea id="log-console" class="log-console" readonly>{logs_text}</textarea>
                </div>
                <div class="card">
                    <h3>🕒 Очередь сообщений ({len(jobs)})</h3>
                    <ul>{jobs_html if jobs_html else "<li>Очередь сообщений пуста</li>"}</ul>
                </div>
            </div>
            <script>
                async function fetchLogs() {{
                    try {{
                        let response = await fetch('/admin/logs');
                        if (response.ok) {{
                            let text = await response.text();
                            document.getElementById('log-console').value = text;
                        }}
                    }} catch (e) {{ console.error(e); }}
                }}
                setInterval(fetchLogs, 2000);
            </script>
        </body>
    </html>
    """
    return html_content
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)