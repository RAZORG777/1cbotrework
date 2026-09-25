"""T030: миграция старой схемы (tg_id UNIQUE, date/time строками) без потерь."""

import sqlite3
from datetime import timedelta

from app.db import init_db, make_engine, make_session_factory, now_msk, session_scope
from app.models import Appointment
from app.reminders import make_scheduler, restore_reminders, run_retention

OLD_SCHEMA = """
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY, tg_id VARCHAR UNIQUE, platform VARCHAR, appointment_id VARCHAR,
    branch VARCHAR, doctor_id VARCHAR, doctor_name VARCHAR, service_id VARCHAR,
    service_name VARCHAR, date VARCHAR, time VARCHAR, first_name VARCHAR, last_name VARCHAR,
    middle_name VARCHAR, phone VARCHAR, birth_date VARCHAR);
CREATE TABLE apscheduler_jobs (id VARCHAR(191) PRIMARY KEY, next_run_time FLOAT, job_state BLOB);
"""


def make_old_db(path):
    now = now_msk()
    rows = [
        ("111", "future-1", now + timedelta(days=3)),
        ("222", "past-1", now - timedelta(days=1)),
        ("333", "old-1", now - timedelta(days=40)),
    ]
    con = sqlite3.connect(path)
    con.executescript(OLD_SCHEMA)
    for tg_id, appt_id, dt in rows:
        con.execute(
            "INSERT INTO appointments (tg_id, platform, appointment_id, branch, doctor_id,"
            " doctor_name, service_id, service_name, date, time, first_name, last_name,"
            " middle_name, phone, birth_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tg_id,
                "telegram",
                appt_id,
                "Профсоюзная",
                "d",
                "Доктор",
                "s",
                "Услуга",
                dt.strftime("%Y-%m-%d"),
                dt.strftime("%H:%M"),
                "Имя",
                "Фам",
                "Отч",
                "+7",
                "01.01.1990",
            ),
        )
    con.execute("INSERT INTO apscheduler_jobs VALUES ('rem24h_111', 1.0, x'00')")
    con.commit()
    con.close()


def test_migration_v0_to_v1(tmp_path):
    db = tmp_path / "appointments.db"
    make_old_db(db)
    engine = make_engine(db)
    init_db(engine, db)

    assert (tmp_path / "appointments.db.bak-v0").exists()
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM apscheduler_jobs").fetchone()[0] == 0
    con.close()

    factory = make_session_factory(engine)
    with session_scope(factory) as s:
        by_id = {a.appointment_id: a for a in s.query(Appointment)}
        assert by_id["future-1"].status == "active" and by_id["future-1"].user_id == "111"
        assert by_id["past-1"].status == "finished" and by_id["past-1"].closed_at is not None
        assert by_id["old-1"].status == "finished"

        scheduler = make_scheduler(f"sqlite:///{db}")
        assert restore_reminders(scheduler, s, now_msk()) == 2
        assert scheduler.get_job("rem24h_future-1") is not None

        run_retention(s, 30, now_msk())
    with session_scope(factory) as s:
        ids = {a.appointment_id for a in s.query(Appointment)}
    assert ids == {"future-1", "past-1"}


def test_new_db_gets_version(tmp_path):
    db = tmp_path / "new.db"
    engine = make_engine(db)
    init_db(engine, db)
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1
