"""T049: ежедневная очистка по PD_RETENTION_DAYS."""

from datetime import datetime, timedelta

from app.db import init_db, make_engine, make_session_factory, session_scope
from app.models import Appointment, ProcessedEvent
from app.reminders import run_retention

NOW = datetime(2030, 6, 15, 3, 30)


def appt(appointment_id, visit_at, status="active", closed_at=None):
    return Appointment(
        user_id=appointment_id,
        appointment_id=appointment_id,
        visit_at=visit_at,
        status=status,
        closed_at=closed_at,
        created_at=NOW - timedelta(days=60),
    )


def test_retention(tmp_path):
    db = tmp_path / "r.db"
    engine = make_engine(db)
    init_db(engine, db)
    factory = make_session_factory(engine)
    with session_scope(factory) as s:
        s.add_all(
            [
                appt("future", NOW + timedelta(days=1)),
                appt("yesterday", NOW - timedelta(days=2)),
                appt("fresh-closed", NOW - timedelta(days=5), "finished", NOW - timedelta(days=5)),
                appt("old-closed", NOW - timedelta(days=40), "cancelled", NOW - timedelta(days=31)),
                appt("custom", NOW - timedelta(days=12), "finished", NOW - timedelta(days=11)),
            ]
        )
        s.add(ProcessedEvent(key="old", created_at=NOW - timedelta(days=8)))
        s.add(ProcessedEvent(key="new", created_at=NOW - timedelta(days=1)))

    with session_scope(factory) as s:
        result = run_retention(s, 30, NOW)
    assert result == {"finished": 1, "deleted": 1, "events": 1}
    with session_scope(factory) as s:
        rows = {a.appointment_id: a for a in s.query(Appointment)}
        assert set(rows) == {"future", "yesterday", "fresh-closed", "custom"}
        assert rows["yesterday"].status == "finished"
        assert rows["future"].status == "active"
        assert {e.key for e in s.query(ProcessedEvent)} == {"new"}

    with session_scope(factory) as s:  # срок берётся из настройки
        run_retention(s, 10, NOW)
    with session_scope(factory) as s:
        assert "custom" not in {a.appointment_id for a in s.query(Appointment)}
