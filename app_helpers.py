from datetime import datetime, timezone
import json
import secrets
import sqlite3
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException

from config import (
    ANALYSIS_ADMIN_EDITABLE_STATUSES,
    ANALYSIS_READY_STATUSES,
    ANALYSIS_STATUS_REVIEWED,
    BOOKING_DAY_START_HOUR,
    BOOKING_DAY_START_MINUTES,
    BOOKING_LAST_SLOT_MINUTES,
    BOOKING_SLOT_MINUTES,
    ROLE_PERMISSIONS,
    SESSION_TTL,
)


def serialize_user(row: sqlite3.Row):
    data = dict(row)
    data.pop("password_hash", None)
    data.pop("session_created_at", None)
    data.pop("session_last_seen_at", None)
    data.pop("session_csrf_token", None)
    data["is_active"] = bool(data.get("is_active"))
    data["email_verified"] = bool(data.get("email_verified", False))
    data["phone_verified"] = bool(data.get("phone_verified", False))
    data["two_factor_enabled"] = bool(data.get("two_factor_enabled", False))
    return data


def get_user_row(db: sqlite3.Connection, user_id: int):
    return db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def get_user_or_404(db: sqlite3.Connection, user_id: int):
    row = get_user_row(db, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return row


def get_permissions(db: sqlite3.Connection, role: str):
    rows = db.execute(
        "SELECT permission FROM role_permissions WHERE role=? ORDER BY permission",
        (role,),
    ).fetchall()
    return [row["permission"] for row in rows]


def parse_db_timestamp(value: Optional[str]):
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def try_normalize_calendar_date(raw_value: Optional[str]):
    cleaned = (raw_value or "").strip()
    if not cleaned:
        return None
    for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_calendar_date(raw_value: Optional[str]):
    normalized = try_normalize_calendar_date(raw_value)
    if not normalized:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    return normalized


def try_normalize_slot_time(raw_value: Optional[str]):
    cleaned = (raw_value or "").strip()
    if not cleaned:
        return None
    try:
        slot = datetime.strptime(cleaned, "%H:%M")
    except ValueError:
        return None
    return slot.strftime("%H:%M")


def normalize_slot_time(raw_value: Optional[str]):
    normalized = try_normalize_slot_time(raw_value)
    if not normalized:
        raise HTTPException(status_code=400, detail="Неверный формат времени. Используйте HH:MM")
    total_minutes = int(normalized[:2]) * 60 + int(normalized[3:])
    if total_minutes < BOOKING_DAY_START_MINUTES or total_minutes > BOOKING_LAST_SLOT_MINUTES:
        raise HTTPException(
            status_code=400,
            detail=f"Запись доступна только с {BOOKING_DAY_START_HOUR:02d}:00 до {BOOKING_LAST_SLOT_MINUTES // 60:02d}:{BOOKING_LAST_SLOT_MINUTES % 60:02d}",
        )
    if total_minutes % BOOKING_SLOT_MINUTES != 0:
        raise HTTPException(status_code=400, detail=f"Доступны только интервалы по {BOOKING_SLOT_MINUTES} минут")
    return normalized


def build_slot_datetime(date_iso: str, time_hhmm: str):
    return datetime.strptime(f"{date_iso} {time_hhmm}", "%Y-%m-%d %H:%M")


def generate_booking_slots():
    slots = []
    for total_minutes in range(
        BOOKING_DAY_START_MINUTES,
        BOOKING_LAST_SLOT_MINUTES + 1,
        BOOKING_SLOT_MINUTES,
    ):
        slots.append(f"{total_minutes // 60:02d}:{total_minutes % 60:02d}")
    return slots


def get_doctor_booked_slots(db: sqlite3.Connection, doctor_user_id: int, date_iso: str):
    rows = db.execute(
        "SELECT date, time, status FROM appointments WHERE doctor_user_id=?",
        (doctor_user_id,),
    ).fetchall()
    occupied = set()
    for row in rows:
        if normalize_optional_string(row["status"]) == "отменено":
            continue
        normalized_date = try_normalize_calendar_date(row["date"])
        normalized_time = try_normalize_slot_time(row["time"])
        if normalized_date == date_iso and normalized_time:
            occupied.add(normalized_time)
    return occupied


def patient_has_slot_conflict(db: sqlite3.Connection, user_id: int, date_iso: str, time_hhmm: str):
    rows = db.execute("SELECT date, time, status FROM appointments WHERE user_id=?", (user_id,)).fetchall()
    for row in rows:
        if normalize_optional_string(row["status"]) == "отменено":
            continue
        if try_normalize_calendar_date(row["date"]) == date_iso and try_normalize_slot_time(row["time"]) == time_hhmm:
            return True
    return False


def get_available_doctor_slots(db: sqlite3.Connection, doctor_user_id: int, date_iso: str):
    now = datetime.now()
    occupied = get_doctor_booked_slots(db, doctor_user_id, date_iso)
    available = []
    blocked = []
    for slot in generate_booking_slots():
        if build_slot_datetime(date_iso, slot) <= now:
            continue
        if slot in occupied:
            blocked.append(slot)
        else:
            available.append(slot)
    return available, blocked


def ensure_active(row: sqlite3.Row):
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Пользователь деактивирован")


def require_permission(db: sqlite3.Connection, actor: sqlite3.Row, permission: str):
    ensure_active(actor)
    permissions = get_permissions(db, actor["role"])
    if permission not in permissions:
        raise HTTPException(status_code=403, detail="Недостаточно прав доступа")
    return actor


def is_doctor_assigned_to_patient(db: sqlite3.Connection, doctor_user_id: int, patient_user_id: int):
    row = db.execute(
        """
        SELECT 1
        FROM appointments
        WHERE doctor_user_id=? AND user_id=? AND COALESCE(status, '')!='отменено'
        LIMIT 1
        """,
        (doctor_user_id, patient_user_id),
    ).fetchone()
    return bool(row)


def parse_pagination(limit: int, offset: int, *, max_limit: int = 200):
    safe_limit = max(1, min(int(limit), max_limit))
    safe_offset = max(0, int(offset))
    return safe_limit, safe_offset


def require_user_scope(
    db: sqlite3.Connection,
    actor: sqlite3.Row,
    target_user_id: int,
    *,
    cross_user_permission: str,
):
    ensure_active(actor)
    target = get_user_or_404(db, target_user_id)
    if actor["id"] == target["id"]:
        return actor, target
    permissions = get_permissions(db, actor["role"])
    if cross_user_permission not in permissions:
        raise HTTPException(status_code=403, detail="Недостаточно прав доступа")
    if actor["role"] == "admin":
        return actor, target
    if actor["role"] == "doctor" and cross_user_permission == "users:read":
        if target["role"] != "user":
            raise HTTPException(status_code=403, detail="Доктор может просматривать только пациентов")
        if not is_doctor_assigned_to_patient(db, actor["id"], target["id"]):
            raise HTTPException(status_code=403, detail="Этот пациент не закреплен за доктором")
        return actor, target
    raise HTTPException(status_code=403, detail="Недостаточно прав доступа")


def extract_token(authorization: Optional[str]):
    if not authorization:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Неверный формат токена")
    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Пустой токен")
    return token


def get_current_user(db: sqlite3.Connection, authorization: Optional[str]):
    token = extract_token(authorization)
    row = db.execute(
        """
        SELECT
            users.*,
            auth_sessions.created_at AS session_created_at,
            auth_sessions.last_seen_at AS session_last_seen_at,
            auth_sessions.csrf_token AS session_csrf_token
        FROM auth_sessions
        JOIN users ON users.id = auth_sessions.user_id
        WHERE auth_sessions.token = ?
        """,
        (token,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Сессия не найдена или истекла")
    last_seen_at = parse_db_timestamp(row["session_last_seen_at"])
    now = datetime.now(timezone.utc)
    if last_seen_at and now - last_seen_at > SESSION_TTL:
        db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        db.commit()
        raise HTTPException(status_code=401, detail="Сессия истекла. Войдите снова.")
    ensure_active(row)
    db.execute(
        "UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE token=?",
        (token,),
    )
    db.commit()
    return row


def issue_session_token(db: sqlite3.Connection, user_id: int):
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    db.execute(
        """
        INSERT INTO auth_sessions (token, user_id, csrf_token)
        VALUES (?, ?, ?)
        """,
        (token, user_id, csrf_token),
    )
    return token, csrf_token


def validate_role(role: str):
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="Неизвестная роль")
    return role


def infer_portal(role: str):
    if role == "admin":
        return "admin"
    if role == "lab":
        return "lab"
    if role == "doctor":
        return "doctor"
    return "patient"


def validate_name(name: str):
    cleaned = name.strip()
    if len(cleaned) < 2:
        raise HTTPException(status_code=400, detail="Имя должно содержать минимум 2 символа")
    return cleaned


def validate_username(username: str):
    cleaned = username.strip()
    if len(cleaned) < 3:
        raise HTTPException(status_code=400, detail="Username должен содержать минимум 3 символа")
    if any(char.isspace() for char in cleaned):
        raise HTTPException(status_code=400, detail="Username не должен содержать пробелы")
    return cleaned


def validate_password(password: str):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")
    return password


def normalize_optional_string(value: Optional[str]):
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_optional_value(value: Any):
    if value is None:
        return None
    return normalize_optional_string(str(value))


def validate_iin(value: Optional[str]):
    cleaned = normalize_optional_string(value)
    if cleaned is None:
        return None
    if not cleaned.isdigit() or len(cleaned) != 12:
        raise HTTPException(status_code=400, detail="ИИН должен содержать 12 цифр")
    return cleaned


def normalize_analysis_status(value: Optional[str], *, allow_reviewed: bool = False):
    cleaned = normalize_optional_string(value)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Укажите статус анализа")
    allowed = set(ANALYSIS_ADMIN_EDITABLE_STATUSES)
    if allow_reviewed:
        allowed.add(ANALYSIS_STATUS_REVIEWED)
    if cleaned not in allowed:
        raise HTTPException(status_code=400, detail="Недопустимый статус анализа")
    return cleaned


def coerce_result_ok(value: Any):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "ok", "normal", "norm"}:
            return True
        if lowered in {"false", "0", "high", "low", "abnormal", "out"}:
            return False
    raise HTTPException(status_code=400, detail="Для каждого результата укажите ok=true/false")


def sanitize_analysis_results(results: Optional[list[dict[str, Any]]]):
    if results is None:
        return []
    if not isinstance(results, list):
        raise HTTPException(status_code=400, detail="Результаты анализа должны быть списком")
    cleaned_results = []
    for item in results:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Некорректный формат результата анализа")
        param = normalize_optional_value(item.get("param"))
        value = normalize_optional_value(item.get("val"))
        if not param or value is None:
            raise HTTPException(status_code=400, detail="У результата анализа обязательны param и val")
        cleaned_results.append(
            {
                "param": param,
                "val": value,
                "unit": normalize_optional_value(item.get("unit")) or "",
                "norm": normalize_optional_value(item.get("norm")) or "",
                "ok": coerce_result_ok(item.get("ok")),
            }
        )
    return cleaned_results


def parse_analysis_results(raw_results: Any):
    if not raw_results:
        return []
    if isinstance(raw_results, list):
        return raw_results
    try:
        parsed = json.loads(raw_results)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def normalize_analysis_date_for_display(row: Union[sqlite3.Row, Dict[str, Any]]):
    for key in ("ready_at", "scheduled_for", "date", "ordered_at"):
        value = row[key] if isinstance(row, sqlite3.Row) else row.get(key)
        if not value:
            continue
        normalized = try_normalize_calendar_date(str(value)[:10] if len(str(value)) >= 10 else value)
        if normalized:
            return normalized
    return None


def serialize_analysis_row(row: sqlite3.Row, *, actor_role: Optional[str] = None, is_self_patient: bool = False):
    data = dict(row)
    data["results"] = parse_analysis_results(data.get("results"))
    data["is_visible_to_patient"] = bool(data.get("is_visible_to_patient", 1))
    if not data.get("date"):
        data["date"] = normalize_analysis_date_for_display(data)
    if is_self_patient:
        if not data["is_visible_to_patient"]:
            return None
        if data.get("status") not in ANALYSIS_READY_STATUSES:
            data["results"] = []
            data["lab_note"] = None
    return data


def get_analysis_or_404(db: sqlite3.Connection, analysis_id: int):
    row = db.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    return row


def log_audit(
    db: sqlite3.Connection,
    actor: Optional[sqlite3.Row],
    action: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    actor_id = actor["id"] if actor else None
    db.execute(
        """
        INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            actor_id,
            action,
            entity_type,
            entity_id,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
