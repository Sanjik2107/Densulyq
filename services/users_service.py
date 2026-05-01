import sqlite3

from fastapi import HTTPException

from app_helpers import (
    ensure_active,
    get_available_doctor_slots,
    get_permissions,
    normalize_calendar_date,
    normalize_optional_string,
    parse_pagination,
    require_permission,
    require_user_scope,
    serialize_user,
    validate_iin,
    validate_name,
)
from config import (
    ANALYSIS_STATUS_READY,
    ANALYSIS_STATUS_REVIEWED,
    BOOKING_DAY_END_HOUR,
    BOOKING_DAY_START_HOUR,
    BOOKING_SLOT_MINUTES,
)
from schemas import ProfileUpdate, model_dump


def list_doctors(db, actor):
    ensure_active(actor)
    rows = db.execute(
        """
        SELECT id, name, username, department, email, phone
        FROM users
        WHERE role='doctor' AND is_active=1
        ORDER BY name COLLATE NOCASE, id
        """
    ).fetchall()
    return {"doctors": [dict(row) for row in rows]}


def get_doctor_availability(db, actor, doctor_user_id: int, date: str):
    ensure_active(actor)
    doctor = db.execute(
        "SELECT id, name, department, is_active FROM users WHERE id=? AND role='doctor'",
        (doctor_user_id,),
    ).fetchone()
    if not doctor:
        raise HTTPException(status_code=404, detail="Доктор не найден")
    ensure_active(doctor)
    date_iso = normalize_calendar_date(date)
    available_slots, booked_slots = get_available_doctor_slots(db, doctor_user_id, date_iso)
    return {
        "doctor_id": doctor["id"],
        "doctor_name": doctor["name"],
        "department": doctor["department"],
        "date": date_iso,
        "working_hours": {
            "start": f"{BOOKING_DAY_START_HOUR:02d}:00",
            "end": f"{BOOKING_DAY_END_HOUR:02d}:00",
            "slot_minutes": BOOKING_SLOT_MINUTES,
        },
        "available_slots": available_slots,
        "booked_slots": booked_slots,
    }


def get_directory_users(db, actor):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Справочник пользователей доступен только администратору")
    require_permission(db, actor, "users:read")
    rows = db.execute(
        """
        SELECT id, name, username, role, is_active, email, department
        FROM users
        ORDER BY CASE WHEN role='admin' THEN 0 ELSE 1 END, id
        """
    ).fetchall()
    return {"users": [serialize_user(row) for row in rows]}


def get_user_context(db, actor, user_id: int):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Контекст пользователя доступен только администратору")
    _, user = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    return {
        "user": serialize_user(user),
        "permissions": get_permissions(db, user["role"]),
    }


def get_user_profile(db, actor, user_id: int):
    _, user = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    return serialize_user(user)


def update_user_profile(db, actor, user_id: int, data: ProfileUpdate):
    _, target = require_user_scope(db, actor, user_id, cross_user_permission="users:update")
    fields = model_dump(data)
    if not fields:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    if "name" in fields:
        fields["name"] = validate_name(fields["name"])
    if "dob" in fields:
        fields["dob"] = normalize_optional_string(fields["dob"])
    if "phone" in fields:
        fields["phone"] = normalize_optional_string(fields["phone"])
    if "email" in fields:
        fields["email"] = normalize_optional_string(fields["email"])
    if "address" in fields:
        fields["address"] = normalize_optional_string(fields["address"])
    if "blood_type" in fields:
        fields["blood_type"] = normalize_optional_string(fields["blood_type"])
    if "iin" in fields:
        fields["iin"] = validate_iin(fields["iin"])
    if "department" in fields:
        fields["department"] = normalize_optional_string(fields["department"])
    if "height" in fields and fields["height"] is not None and fields["height"] <= 0:
        raise HTTPException(status_code=400, detail="Рост должен быть положительным числом")
    if "weight" in fields and fields["weight"] is not None and fields["weight"] <= 0:
        raise HTTPException(status_code=400, detail="Вес должен быть положительным числом")
    set_clause = ", ".join(f"{key}=?" for key in fields)
    try:
        db.execute(f"UPDATE users SET {set_clause} WHERE id=?", (*fields.values(), target["id"]))
        db.commit()
        return {"status": "updated"}
    except sqlite3.IntegrityError as error:
        if "iin" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=400, detail="Такой ИИН уже используется")
        raise


def get_referrals(db, actor, user_id: int):
    require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    rows = db.execute("SELECT * FROM referrals WHERE user_id=?", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def list_doctor_patients(db, actor, *, limit: int = 50, offset: int = 0):
    require_permission(db, actor, "users:read")
    limit, offset = parse_pagination(limit, offset)
    if actor["role"] == "admin":
        patient_rows = db.execute(
            """
            SELECT *
            FROM users
            WHERE role='user'
            ORDER BY name COLLATE NOCASE, id
            LIMIT ? OFFSET ?
            """
            ,
            (limit, offset),
        ).fetchall()
    elif actor["role"] == "doctor":
        patient_rows = db.execute(
            """
            SELECT DISTINCT users.*
            FROM users
            JOIN appointments ON appointments.user_id = users.id
            WHERE users.role='user' AND appointments.doctor_user_id=? AND COALESCE(appointments.status, '')!='отменено'
            ORDER BY users.name COLLATE NOCASE, users.id
            LIMIT ? OFFSET ?
            """,
            (actor["id"], limit, offset),
        ).fetchall()
    else:
        raise HTTPException(status_code=403, detail="Доступ только для doctor или admin")

    patients = []
    total_ready_analyses = 0
    total_active_referrals = 0
    total_appointments = 0

    for row in patient_rows:
        user_id = row["id"]
        ready_analyses = db.execute(
            "SELECT COUNT(*) FROM analyses WHERE user_id=? AND status IN (?, ?)",
            (user_id, ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED),
        ).fetchone()[0]
        appointment_count = db.execute(
            "SELECT COUNT(*) FROM appointments WHERE user_id=?",
            (user_id,),
        ).fetchone()[0]
        active_referrals = db.execute(
            "SELECT COUNT(*) FROM referrals WHERE user_id=? AND status='активно'",
            (user_id,),
        ).fetchone()[0]
        latest_analysis = db.execute(
            "SELECT date FROM analyses WHERE user_id=? ORDER BY date DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        next_appointment = db.execute(
            "SELECT date, time, doctor FROM appointments WHERE user_id=? ORDER BY date, time LIMIT 1",
            (user_id,),
        ).fetchone()

        patient = serialize_user(row)
        patient["ready_analyses"] = ready_analyses
        patient["appointment_count"] = appointment_count
        patient["active_referrals"] = active_referrals
        patient["latest_analysis_date"] = latest_analysis["date"] if latest_analysis else None
        patient["next_appointment"] = dict(next_appointment) if next_appointment else None
        patients.append(patient)

        total_ready_analyses += ready_analyses
        total_active_referrals += active_referrals
        total_appointments += appointment_count

    return {
        "patients": patients,
        "limit": limit,
        "offset": offset,
        "stats": {
            "total_patients": len(patients),
            "ready_analyses": total_ready_analyses,
            "active_referrals": total_active_referrals,
            "appointments": total_appointments,
        },
    }
