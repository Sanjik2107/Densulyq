from datetime import datetime

from fastapi import HTTPException

from app_helpers import (
    build_slot_datetime,
    ensure_active,
    get_doctor_booked_slots,
    normalize_calendar_date,
    normalize_optional_string,
    normalize_slot_time,
    patient_has_slot_conflict,
    require_permission,
    require_user_scope,
)
from db import get_last_insert_id
from schemas import AppointmentCreate


def get_user_appointments(db, actor, user_id: int):
    require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    rows = db.execute(
        "SELECT * FROM appointments WHERE user_id=? ORDER BY date, time, id",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def create_appointment(db, actor, data: AppointmentCreate):
    user_id = data.user_id or actor["id"]
    doctor_user_id = data.doctor_user_id
    if actor["role"] == "doctor" and user_id != actor["id"]:
        require_permission(db, actor, "users:read")
        _, target_user = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        doctor_user_id = doctor_user_id or actor["id"]
        if doctor_user_id != actor["id"]:
            raise HTTPException(status_code=403, detail="Доктор может записывать пациента только к себе")
    else:
        _, target_user = require_user_scope(db, actor, user_id, cross_user_permission="users:update")
    if target_user["role"] != "user":
        raise HTTPException(status_code=400, detail="Запись к доктору доступна только пациенту")
    ensure_active(target_user)
    if not doctor_user_id:
        raise HTTPException(status_code=400, detail="Выберите доктора")
    date_iso = normalize_calendar_date(data.date)
    time_hhmm = normalize_slot_time(data.time)
    slot_datetime = build_slot_datetime(date_iso, time_hhmm)
    if slot_datetime <= datetime.now():
        raise HTTPException(status_code=400, detail="Нельзя записаться на прошедшее время")
    doctor = db.execute(
        "SELECT * FROM users WHERE id=? AND role='doctor'",
        (doctor_user_id,),
    ).fetchone()
    if not doctor:
        raise HTTPException(status_code=400, detail="Доктор не найден")
    ensure_active(doctor)
    if patient_has_slot_conflict(db, user_id, date_iso, time_hhmm):
        raise HTTPException(status_code=409, detail="У пациента уже есть запись на это время")
    doctor_booked_slots = get_doctor_booked_slots(db, doctor["id"], date_iso)
    if time_hhmm in doctor_booked_slots:
        raise HTTPException(status_code=409, detail="Это время у доктора уже занято")
    db.execute(
        """
        INSERT INTO appointments (user_id, doctor_user_id, doctor, speciality, date, time, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ожидание')
        """,
        (
            user_id,
            doctor["id"],
            doctor["name"],
            doctor["department"] or doctor["name"],
            date_iso,
            time_hhmm,
            normalize_optional_string(data.reason),
        ),
    )
    db.commit()
    new_id = get_last_insert_id(db)
    return {"id": new_id, "status": "created"}


def cancel_appointment(db, actor, appointment_id: int):
    appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,)).fetchone()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    status = (appointment["status"] or "").strip().lower()
    if status == "отменено":
        return {"status": "cancelled"}
    allowed = actor["role"] == "admin"
    if actor["role"] == "doctor":
        allowed = appointment["doctor_user_id"] == actor["id"]
        if not allowed:
            raise HTTPException(status_code=403, detail="Доктор может отменять только свои записи")
    if actor["id"] == appointment["user_id"]:
        allowed = True
    if not allowed:
        raise HTTPException(status_code=403, detail="Недостаточно прав для отмены записи")
    db.execute("UPDATE appointments SET status='отменено' WHERE id=?", (appointment_id,))
    db.commit()
    return {"status": "cancelled"}
