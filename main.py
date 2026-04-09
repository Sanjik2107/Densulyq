from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import httpx
import json
import os
import secrets
import sqlite3


app = FastAPI(title="Densaulyq API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DB_PATH = "medportal.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(BASE_DIR, "index1.html")
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390000
SESSION_TTL_HOURS = max(1, int(os.getenv("SESSION_TTL_HOURS", "24")))
SESSION_TTL = timedelta(hours=SESSION_TTL_HOURS)
BOOKING_DAY_START_HOUR = 9
BOOKING_DAY_END_HOUR = 18
BOOKING_SLOT_MINUTES = 15
BOOKING_DAY_START_MINUTES = BOOKING_DAY_START_HOUR * 60
BOOKING_DAY_END_MINUTES = BOOKING_DAY_END_HOUR * 60
BOOKING_LAST_SLOT_MINUTES = BOOKING_DAY_END_MINUTES - BOOKING_SLOT_MINUTES
ROLE_PERMISSIONS = {
    "admin": [
        ("users:read", "Просмотр всех пользователей"),
        ("users:create", "Создание пользователей"),
        ("users:update", "Изменение ролей и статусов"),
        ("analyses:manage", "Управление лабораторными результатами"),
        ("rbac:read", "Просмотр role-based модели"),
        ("records:read", "Просмотр медицинских записей"),
    ],
    "doctor": [
        ("self:read", "Просмотр собственного профиля"),
        ("self:update", "Редактирование собственного профиля"),
        ("users:read", "Просмотр пациентов"),
        ("analyses:create", "Назначение анализов пациентам"),
        ("analyses:review", "Проверка готовых анализов"),
        ("records:read", "Просмотр медицинских записей пациентов"),
    ],
    "user": [
        ("self:read", "Просмотр собственного профиля"),
        ("self:update", "Редактирование собственного профиля"),
        ("appointments:create", "Создание собственных записей"),
        ("records:read", "Просмотр собственных медицинских записей"),
    ],
}
ANALYSIS_STATUS_ORDERED = "назначен"
ANALYSIS_STATUS_PROCESSING = "в обработке"
ANALYSIS_STATUS_READY = "готово"
ANALYSIS_STATUS_REVIEWED = "проверено"
ANALYSIS_READY_STATUSES = (ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED)
ANALYSIS_ADMIN_EDITABLE_STATUSES = (
    ANALYSIS_STATUS_ORDERED,
    ANALYSIS_STATUS_PROCESSING,
    ANALYSIS_STATUS_READY,
)
DEMO_CREDENTIALS = {
    "patient-demo": "patient123",
    "admin-demo": "admin123",
    "doctor-demo": "doctor123",
}


def model_dump(data: BaseModel):
    if hasattr(data, "model_dump"):
        return data.model_dump(exclude_none=True)
    return data.dict(exclude_none=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def hash_password(password: str, *, salt: Optional[str] = None, iterations: int = PASSWORD_ITERATIONS):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"{PASSWORD_SCHEME}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, encoded: Optional[str]):
    if not encoded:
        return False
    try:
        scheme, iterations_raw, salt, stored_digest = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        candidate = hash_password(password, salt=salt, iterations=int(iterations_raw))
        return hmac.compare_digest(candidate, encoded)
    except Exception:
        return False


def serialize_user(row: sqlite3.Row):
    data = dict(row)
    data.pop("password_hash", None)
    data.pop("session_created_at", None)
    data.pop("session_last_seen_at", None)
    data["is_active"] = bool(data.get("is_active"))
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
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
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
        "SELECT date, time FROM appointments WHERE doctor_user_id=?",
        (doctor_user_id,),
    ).fetchall()
    occupied = set()
    for row in rows:
        normalized_date = try_normalize_calendar_date(row["date"])
        normalized_time = try_normalize_slot_time(row["time"])
        if normalized_date == date_iso and normalized_time:
            occupied.add(normalized_time)
    return occupied


def patient_has_slot_conflict(db: sqlite3.Connection, user_id: int, date_iso: str, time_hhmm: str):
    rows = db.execute("SELECT date, time FROM appointments WHERE user_id=?", (user_id,)).fetchall()
    for row in rows:
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
        WHERE doctor_user_id=? AND user_id=?
        LIMIT 1
        """,
        (doctor_user_id, patient_user_id),
    ).fetchone()
    return bool(row)


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
            auth_sessions.last_seen_at AS session_last_seen_at
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
    db.execute(
        """
        INSERT INTO auth_sessions (token, user_id)
        VALUES (?, ?)
        """,
        (token, user_id),
    )
    return token


def seed_role_permissions(cursor: sqlite3.Cursor):
    for role, permissions in ROLE_PERMISSIONS.items():
        for permission, description in permissions:
            cursor.execute(
                """
                INSERT OR IGNORE INTO role_permissions (role, permission, description)
                VALUES (?, ?, ?)
                """,
                (role, permission, description),
            )


def seed_demo_password(cursor: sqlite3.Cursor, username: str):
    password = DEMO_CREDENTIALS[username]
    cursor.execute(
        "UPDATE users SET password_hash=? WHERE username=?",
        (hash_password(password), username),
    )


def validate_role(role: str):
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="Неизвестная роль")
    return role


def infer_portal(role: str):
    if role == "admin":
        return "admin"
    if role == "doctor":
        return "doctor"
    return "patient"


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT,
            password_hash TEXT,
            iin TEXT UNIQUE,
            dob TEXT,
            blood_type TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            height REAL,
            weight REAL,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            department TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    ensure_column(conn, "users", "username", "username TEXT")
    ensure_column(conn, "users", "password_hash", "password_hash TEXT")
    ensure_column(conn, "users", "role", "role TEXT DEFAULT 'user'")
    ensure_column(conn, "users", "is_active", "is_active INTEGER DEFAULT 1")
    ensure_column(conn, "users", "department", "department TEXT")

    c.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique
        ON users(username) WHERE username IS NOT NULL
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doctor_user_id INTEGER,
            name TEXT NOT NULL,
            date TEXT,
            doctor TEXT,
            status TEXT DEFAULT 'в обработке',
            results TEXT,
            ordered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            scheduled_for TEXT,
            ready_at TEXT,
            reviewed_at TEXT,
            doctor_note TEXT,
            lab_note TEXT,
            is_visible_to_patient INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    ensure_column(conn, "analyses", "doctor_user_id", "doctor_user_id INTEGER")
    ensure_column(conn, "analyses", "ordered_at", "ordered_at TEXT")
    ensure_column(conn, "analyses", "scheduled_for", "scheduled_for TEXT")
    ensure_column(conn, "analyses", "ready_at", "ready_at TEXT")
    ensure_column(conn, "analyses", "reviewed_at", "reviewed_at TEXT")
    ensure_column(conn, "analyses", "doctor_note", "doctor_note TEXT")
    ensure_column(conn, "analyses", "lab_note", "lab_note TEXT")
    ensure_column(conn, "analyses", "is_visible_to_patient", "is_visible_to_patient INTEGER DEFAULT 1")
    c.execute("CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_analyses_doctor_user_id ON analyses(doctor_user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status)")

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doctor_user_id INTEGER,
            doctor TEXT,
            speciality TEXT,
            date TEXT,
            time TEXT,
            place TEXT,
            reason TEXT,
            status TEXT DEFAULT 'ожидание',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    ensure_column(conn, "appointments", "doctor_user_id", "doctor_user_id INTEGER")
    c.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_appointments_doctor_user_id ON appointments(doctor_user_id)")

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            from_doctor TEXT,
            issue_date TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'активно',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            message TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (role, permission)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    seed_role_permissions(c)
    c.execute("UPDATE users SET role='user' WHERE role IS NULL OR TRIM(role)=''")
    c.execute("UPDATE users SET is_active=1 WHERE is_active IS NULL")

    demo_user = c.execute("SELECT * FROM users WHERE id=1").fetchone()
    if not demo_user:
        c.execute(
            """
            INSERT INTO users (
                id, name, username, password_hash, iin, dob, blood_type, phone,
                email, address, height, weight, role, is_active, department
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "Алибек Джаксыбеков",
                "patient-demo",
                hash_password(DEMO_CREDENTIALS["patient-demo"]),
                "900315300123",
                "15.03.1990",
                "II+",
                "+7 700 123 45 67",
                "alibek@email.com",
                "г. Алматы, ул. Абая 14, кв. 22",
                178,
                82,
                "user",
                1,
                "Пациент",
            ),
        )
    else:
        c.execute(
            """
            UPDATE users
            SET username='patient-demo',
                role='user',
                is_active=1,
                department=COALESCE(department, 'Пациент')
            WHERE id=1
            """
        )
        seed_demo_password(c, "patient-demo")

    admin_user = c.execute("SELECT * FROM users WHERE username='admin-demo'").fetchone()
    if not admin_user:
        c.execute(
            """
            INSERT INTO users (
                name, username, password_hash, iin, dob, blood_type, phone,
                email, address, height, weight, role, is_active, department
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Администратор Densaulyq",
                "admin-demo",
                hash_password(DEMO_CREDENTIALS["admin-demo"]),
                "880101400001",
                "01.01.1988",
                "I+",
                "+7 700 000 00 01",
                "admin@densaulyq.local",
                "г. Алматы, центр администрирования",
                175,
                74,
                "admin",
                1,
                "Администрация",
            ),
        )
    else:
        c.execute(
            """
            UPDATE users
            SET role='admin',
                is_active=1,
                department=COALESCE(department, 'Администрация')
            WHERE username='admin-demo'
            """
        )
        seed_demo_password(c, "admin-demo")

    doctor_user = c.execute("SELECT * FROM users WHERE username='doctor-demo'").fetchone()
    if not doctor_user:
        c.execute(
            """
            INSERT INTO users (
                name, username, password_hash, iin, dob, blood_type, phone,
                email, address, height, weight, role, is_active, department
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Иванова Н.С.",
                "doctor-demo",
                hash_password(DEMO_CREDENTIALS["doctor-demo"]),
                "870212400002",
                "12.02.1987",
                "I+",
                "+7 700 000 00 02",
                "doctor@densaulyq.local",
                "г. Алматы, клиника Densaulyq",
                168,
                62,
                "doctor",
                1,
                "Терапия",
            ),
        )
    else:
        c.execute(
            """
            UPDATE users
            SET role='doctor',
                is_active=1,
                department=COALESCE(department, 'Терапия')
            WHERE username='doctor-demo'
            """
        )
        seed_demo_password(c, "doctor-demo")

    doctor_demo = c.execute("SELECT id, name, department FROM users WHERE username='doctor-demo'").fetchone()

    analyses_exists = c.execute("SELECT 1 FROM analyses WHERE user_id=1 LIMIT 1").fetchone()
    if not analyses_exists:
        analyses_data = [
            (
                1,
                doctor_demo["id"],
                "Общий анализ крови",
                "2025-03-12",
                "Иванова Н.С.",
                ANALYSIS_STATUS_READY,
                json.dumps(
                    [
                        {"param": "Гемоглобин", "val": 145, "unit": "г/л", "norm": "120–160", "ok": True},
                        {"param": "Лейкоциты", "val": 9.1, "unit": "×10⁹/л", "norm": "4.0–9.0", "ok": False},
                        {"param": "Тромбоциты", "val": 210, "unit": "×10⁹/л", "norm": "150–400", "ok": True},
                    ]
                ),
                "2025-03-10",
                "2025-03-12",
                "2025-03-12",
                None,
                "Соблюдайте обычный питьевой режим перед контрольным анализом.",
                "Незначительное повышение лейкоцитов, нужен контроль в динамике.",
                1,
            ),
            (
                1,
                doctor_demo["id"],
                "Биохимия крови",
                "2025-03-12",
                "Иванова Н.С.",
                ANALYSIS_STATUS_REVIEWED,
                json.dumps(
                    [
                        {"param": "Глюкоза", "val": 5.2, "unit": "ммоль/л", "norm": "3.9–6.1", "ok": True},
                        {"param": "Холестерин общий", "val": 5.8, "unit": "ммоль/л", "norm": "< 5.2", "ok": False},
                        {"param": "АЛТ", "val": 28, "unit": "Ед/л", "norm": "< 40", "ok": True},
                    ]
                ),
                "2025-03-10",
                "2025-03-12",
                "2025-03-12",
                "2025-03-13",
                "Повторить липидный профиль через 6-8 недель и обсудить рацион.",
                "Показатели готовы и проверены лабораторией.",
                1,
            ),
            (
                1,
                doctor_demo["id"],
                "Анализ мочи",
                "2025-04-20",
                doctor_demo["name"],
                ANALYSIS_STATUS_ORDERED,
                json.dumps([]),
                "2025-04-09",
                "2025-04-20",
                None,
                None,
                "Пациенту нужно сдать утреннюю порцию мочи.",
                None,
                1,
            ),
        ]
        c.executemany(
            """
            INSERT INTO analyses (
                user_id, doctor_user_id, name, date, doctor, status, results,
                ordered_at, scheduled_for, ready_at, reviewed_at, doctor_note, lab_note, is_visible_to_patient
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            analyses_data,
        )
    c.execute(
        """
        UPDATE analyses
        SET doctor_user_id=?
        WHERE doctor_user_id IS NULL AND doctor=?
        """,
        (doctor_demo["id"], doctor_demo["name"]),
    )
    c.execute(
        """
        UPDATE analyses
        SET is_visible_to_patient=1
        WHERE is_visible_to_patient IS NULL
        """
    )
    for row in c.execute("SELECT id, date, scheduled_for, ready_at, reviewed_at, ordered_at, status FROM analyses").fetchall():
        updates = {}
        normalized_date = try_normalize_calendar_date(row["date"]) or row["date"]
        normalized_scheduled = try_normalize_calendar_date(row["scheduled_for"]) or row["scheduled_for"]
        normalized_ready = try_normalize_calendar_date(row["ready_at"]) or row["ready_at"]
        ordered_value = row["ordered_at"]
        if ordered_value:
            ordered_text = str(ordered_value)
            if len(ordered_text) >= 10:
                normalized_ordered = try_normalize_calendar_date(ordered_text[:10])
                if normalized_ordered and normalized_ordered != ordered_text:
                    updates["ordered_at"] = normalized_ordered
        if normalized_date != row["date"]:
            updates["date"] = normalized_date
        if normalized_scheduled != row["scheduled_for"]:
            updates["scheduled_for"] = normalized_scheduled
        if normalized_ready != row["ready_at"]:
            updates["ready_at"] = normalized_ready
        if row["status"] == ANALYSIS_STATUS_READY and "ready_at" not in updates and not row["ready_at"]:
            updates["ready_at"] = normalized_date
        if row["status"] == ANALYSIS_STATUS_REVIEWED and not row["reviewed_at"]:
            updates["reviewed_at"] = normalized_date
        if updates:
            set_clause = ", ".join(f"{column}=?" for column in updates)
            c.execute(f"UPDATE analyses SET {set_clause} WHERE id=?", (*updates.values(), row["id"]))

    appointments_exist = c.execute("SELECT 1 FROM appointments WHERE user_id=1 LIMIT 1").fetchone()
    if not appointments_exist:
        appointments_data = [
            (1, None, "Смирнов Д.А.", "Кардиолог", "18.04.2025", "09:30", "Кабинет 215", "Плановый осмотр", "подтверждено"),
            (1, doctor_demo["id"], doctor_demo["name"], doctor_demo["department"], "25.04.2025", "14:00", "Кабинет 105", "Контроль давления", "подтверждено"),
        ]
        c.executemany(
            """
            INSERT INTO appointments (user_id, doctor_user_id, doctor, speciality, date, time, place, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            appointments_data,
        )
    c.execute(
        """
        UPDATE appointments
        SET doctor_user_id=?
        WHERE doctor_user_id IS NULL AND doctor=?
        """,
        (doctor_demo["id"], doctor_demo["name"]),
    )
    for row in c.execute("SELECT id, date, time FROM appointments").fetchall():
        normalized_date = try_normalize_calendar_date(row["date"]) or row["date"]
        normalized_time = try_normalize_slot_time(row["time"]) or row["time"]
        if normalized_date != row["date"] or normalized_time != row["time"]:
            c.execute(
                "UPDATE appointments SET date=?, time=? WHERE id=?",
                (normalized_date, normalized_time, row["id"]),
            )

    referrals_exist = c.execute("SELECT 1 FROM referrals WHERE user_id=1 LIMIT 1").fetchone()
    if not referrals_exist:
        referrals_data = [
            (1, "Общий анализ крови", "Иванова Н.С.", "10.04.2025", "30.04.2025", "активно"),
            (1, "УЗИ брюшной полости", "Карпова В.М.", "05.04.2025", "05.05.2025", "активно"),
        ]
        c.executemany(
            """
            INSERT INTO referrals (user_id, name, from_doctor, issue_date, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            referrals_data,
        )

    c.execute("DELETE FROM auth_sessions WHERE user_id NOT IN (SELECT id FROM users)")
    conn.commit()
    conn.close()


init_db()


class AuthLogin(BaseModel):
    username: str
    password: str


class AuthRegister(BaseModel):
    name: str
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None


class AppointmentCreate(BaseModel):
    user_id: Optional[int] = None
    doctor_user_id: Optional[int] = None
    doctor: Optional[str] = None
    date: str
    time: str
    reason: Optional[str] = ""


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = ""
    user_id: Optional[int] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    blood_type: Optional[str] = None
    iin: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    department: Optional[str] = None


class AnalysisOrderCreate(BaseModel):
    name: str
    scheduled_for: Optional[str] = None
    doctor_note: Optional[str] = None
    is_visible_to_patient: Optional[bool] = True


class AnalysisLabUpdate(BaseModel):
    status: str
    results: Optional[list[dict[str, Any]]] = None
    ready_at: Optional[str] = None
    lab_note: Optional[str] = None
    is_visible_to_patient: Optional[bool] = None


class AnalysisReviewUpdate(BaseModel):
    doctor_note: Optional[str] = None


class AdminUserCreate(BaseModel):
    name: str
    username: str
    password: str
    role: str = "user"
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    address: Optional[str] = None
    dob: Optional[str] = None
    blood_type: Optional[str] = None
    iin: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    password: Optional[str] = None


@app.get("/")
def root():
    if os.path.exists(FRONTEND_PATH):
        return FileResponse(FRONTEND_PATH)
    return {"status": "ok", "app": "Densaulyq API", "version": "1.2.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


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
        param = normalize_optional_string(str(item.get("param", "")))
        value = normalize_optional_string(str(item.get("val", "")))
        if not param or value is None:
            raise HTTPException(status_code=400, detail="У результата анализа обязательны param и val")
        cleaned_results.append(
            {
                "param": param,
                "val": value,
                "unit": normalize_optional_string(str(item.get("unit", ""))) or "",
                "norm": normalize_optional_string(str(item.get("norm", ""))) or "",
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


def normalize_analysis_date_for_display(row: sqlite3.Row | dict[str, Any]):
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


@app.post("/auth/login")
def auth_login(data: AuthLogin):
    username = data.username.strip()
    if not username or not data.password:
        raise HTTPException(status_code=400, detail="Введите username и пароль")

    db = get_db()
    try:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")

        ensure_active(user)

        token = issue_session_token(db, user["id"])
        db.commit()
        return {
            "token": token,
            "portal": infer_portal(user["role"]),
            "user": serialize_user(user),
            "permissions": get_permissions(db, user["role"]),
        }
    finally:
        db.close()


@app.post("/auth/register")
def auth_register(data: AuthRegister):
    name = validate_name(data.name)
    username = validate_username(data.username)
    password = validate_password(data.password)
    email = data.email.strip() if data.email else None
    phone = data.phone.strip() if data.phone else None

    db = get_db()
    try:
        existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username уже используется")

        db.execute(
            """
            INSERT INTO users (
                name, username, password_hash, phone, email, role, is_active, department
            )
            VALUES (?, ?, ?, ?, ?, 'user', 1, 'Пациент')
            """,
            (name, username, hash_password(password), phone, email),
        )
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        user = get_user_or_404(db, user_id)
        token = issue_session_token(db, user_id)
        db.commit()
        return {
            "status": "registered",
            "token": token,
            "portal": infer_portal("user"),
            "user": serialize_user(user),
            "permissions": get_permissions(db, "user"),
        }
    finally:
        db.close()


@app.get("/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        user = get_current_user(db, authorization)
        return {
            "user": serialize_user(user),
            "permissions": get_permissions(db, user["role"]),
            "portal": infer_portal(user["role"]),
        }
    finally:
        db.close()


@app.post("/auth/logout")
def auth_logout(authorization: Optional[str] = Header(default=None)):
    token = extract_token(authorization)
    db = get_db()
    try:
        db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        db.commit()
        return {"status": "logged_out"}
    finally:
        db.close()


@app.post("/auth/logout-all")
def auth_logout_all(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        db.execute("DELETE FROM auth_sessions WHERE user_id=?", (actor["id"],))
        db.commit()
        return {"status": "logged_out_all"}
    finally:
        db.close()


@app.get("/doctors")
def list_doctors(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
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
    finally:
        db.close()


@app.get("/doctors/{doctor_user_id}/availability")
def get_doctor_availability(doctor_user_id: int, date: str, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
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
    finally:
        db.close()


@app.get("/directory/users")
def get_directory_users(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
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
    finally:
        db.close()


@app.get("/context/{user_id}")
def get_user_context(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        if actor["role"] != "admin":
            raise HTTPException(status_code=403, detail="Контекст пользователя доступен только администратору")
        _, user = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        return {
            "user": serialize_user(user),
            "permissions": get_permissions(db, user["role"]),
        }
    finally:
        db.close()


@app.get("/user/{user_id}")
def get_user(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        _, user = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        return serialize_user(user)
    finally:
        db.close()


@app.put("/user/{user_id}")
def update_user(user_id: int, data: ProfileUpdate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
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
    finally:
        db.close()


@app.get("/analyses/{user_id}")
def get_analyses(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        rows = db.execute(
            """
            SELECT *
            FROM analyses
            WHERE user_id=?
            ORDER BY COALESCE(ready_at, scheduled_for, date, ordered_at, created_at) DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        result = []
        is_self_patient = actor["role"] == "user" and actor["id"] == user_id
        for row in rows:
            data = serialize_analysis_row(row, actor_role=actor["role"], is_self_patient=is_self_patient)
            if data is not None:
                result.append(data)
        return result
    finally:
        db.close()


@app.post("/doctor/patients/{user_id}/analyses")
def doctor_create_analysis(
    user_id: int,
    data: AnalysisOrderCreate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        if actor["role"] != "doctor":
            raise HTTPException(status_code=403, detail="Назначать анализы может только doctor")
        require_permission(db, actor, "analyses:create")
        _, patient = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        if patient["role"] != "user":
            raise HTTPException(status_code=400, detail="Анализы можно назначать только пациенту")
        analysis_name = validate_name(data.name)
        scheduled_for = normalize_calendar_date(data.scheduled_for) if data.scheduled_for else None
        if scheduled_for and scheduled_for < datetime.now().date().isoformat():
            raise HTTPException(status_code=400, detail="Нельзя назначить анализ на прошедшую дату")
        ordered_at = datetime.now().date().isoformat()
        display_date = scheduled_for or ordered_at
        db.execute(
            """
            INSERT INTO analyses (
                user_id, doctor_user_id, name, date, doctor, status, results,
                ordered_at, scheduled_for, doctor_note, is_visible_to_patient
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient["id"],
                actor["id"],
                analysis_name,
                display_date,
                actor["name"],
                ANALYSIS_STATUS_ORDERED,
                json.dumps([], ensure_ascii=False),
                ordered_at,
                scheduled_for,
                normalize_optional_string(data.doctor_note),
                1 if data.is_visible_to_patient is not False else 0,
            ),
        )
        db.commit()
        created = get_analysis_or_404(db, db.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {"status": "created", "analysis": serialize_analysis_row(created)}
    finally:
        db.close()


@app.put("/doctor/analyses/{analysis_id}/review")
def doctor_review_analysis(
    analysis_id: int,
    data: AnalysisReviewUpdate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        if actor["role"] != "doctor":
            raise HTTPException(status_code=403, detail="Проверять анализы может только doctor")
        require_permission(db, actor, "analyses:review")
        analysis = get_analysis_or_404(db, analysis_id)
        if analysis["doctor_user_id"] and analysis["doctor_user_id"] != actor["id"]:
            raise HTTPException(status_code=403, detail="Этот анализ назначен другим доктором")
        require_user_scope(db, actor, analysis["user_id"], cross_user_permission="users:read")
        if analysis["status"] not in ANALYSIS_READY_STATUSES:
            raise HTTPException(status_code=400, detail="Доктор может проверять только готовый анализ")
        reviewed_at = datetime.now().date().isoformat()
        db.execute(
            """
            UPDATE analyses
            SET doctor_note=?, reviewed_at=?, status=?, is_visible_to_patient=1
            WHERE id=?
            """,
            (
                normalize_optional_string(data.doctor_note),
                reviewed_at,
                ANALYSIS_STATUS_REVIEWED,
                analysis_id,
            ),
        )
        db.commit()
        updated = get_analysis_or_404(db, analysis_id)
        return {"status": "reviewed", "analysis": serialize_analysis_row(updated)}
    finally:
        db.close()


@app.get("/admin/analyses")
def admin_list_analyses(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        if actor["role"] != "admin":
            raise HTTPException(status_code=403, detail="Очередь анализов доступна только администратору")
        require_permission(db, actor, "analyses:manage")
        rows = db.execute(
            """
            SELECT
                analyses.*,
                users.name AS patient_name,
                users.username AS patient_username
            FROM analyses
            JOIN users ON users.id = analyses.user_id
            ORDER BY
                CASE analyses.status
                    WHEN 'назначен' THEN 0
                    WHEN 'в обработке' THEN 1
                    WHEN 'готово' THEN 2
                    ELSE 3
                END,
                COALESCE(analyses.ready_at, analyses.scheduled_for, analyses.date, analyses.ordered_at, analyses.created_at) DESC,
                analyses.id DESC
            """
        ).fetchall()
        analyses = []
        for row in rows:
            analysis = serialize_analysis_row(row)
            analysis["patient_name"] = row["patient_name"]
            analysis["patient_username"] = row["patient_username"]
            analyses.append(analysis)
        return {"analyses": analyses}
    finally:
        db.close()


@app.put("/admin/analyses/{analysis_id}")
def admin_update_analysis(
    analysis_id: int,
    data: AnalysisLabUpdate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        if actor["role"] != "admin":
            raise HTTPException(status_code=403, detail="Обновлять анализы может только администратор")
        require_permission(db, actor, "analyses:manage")
        analysis = get_analysis_or_404(db, analysis_id)
        status = normalize_analysis_status(data.status)
        existing_results = parse_analysis_results(analysis["results"])
        incoming_results = sanitize_analysis_results(data.results) if data.results is not None else existing_results
        updates = {
            "status": status,
            "lab_note": normalize_optional_string(data.lab_note),
            "is_visible_to_patient": 1 if data.is_visible_to_patient is not False else 0,
        }
        if data.results is not None:
            updates["results"] = json.dumps(incoming_results, ensure_ascii=False)
        if status == ANALYSIS_STATUS_READY:
            if not incoming_results:
                raise HTTPException(status_code=400, detail="Для готового анализа нужно заполнить результаты")
            ready_at = normalize_calendar_date(data.ready_at) if data.ready_at else datetime.now().date().isoformat()
            updates["ready_at"] = ready_at
            updates["date"] = ready_at
            updates["is_visible_to_patient"] = 1
        else:
            updates["ready_at"] = None
        set_clause = ", ".join(f"{column}=?" for column in updates)
        db.execute(f"UPDATE analyses SET {set_clause} WHERE id=?", (*updates.values(), analysis_id))
        db.commit()
        updated = get_analysis_or_404(db, analysis_id)
        return {"status": "updated", "analysis": serialize_analysis_row(updated)}
    finally:
        db.close()


@app.get("/appointments/{user_id}")
def get_appointments(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        rows = db.execute("SELECT * FROM appointments WHERE user_id=? ORDER BY date", (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@app.post("/appointments")
def create_appointment(data: AppointmentCreate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        user_id = data.user_id or actor["id"]
        _, target_user = require_user_scope(db, actor, user_id, cross_user_permission="users:update")
        if target_user["role"] != "user":
            raise HTTPException(status_code=400, detail="Запись к доктору доступна только пациенту")
        ensure_active(target_user)
        if not data.doctor_user_id:
            raise HTTPException(status_code=400, detail="Выберите доктора")
        date_iso = normalize_calendar_date(data.date)
        time_hhmm = normalize_slot_time(data.time)
        slot_datetime = build_slot_datetime(date_iso, time_hhmm)
        if slot_datetime <= datetime.now():
            raise HTTPException(status_code=400, detail="Нельзя записаться на прошедшее время")
        doctor = db.execute(
            "SELECT * FROM users WHERE id=? AND role='doctor'",
            (data.doctor_user_id,),
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
                data.reason,
            ),
        )
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": new_id, "status": "created"}
    finally:
        db.close()


@app.get("/referrals/{user_id}")
def get_referrals(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        rows = db.execute("SELECT * FROM referrals WHERE user_id=?", (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@app.get("/admin/users")
def admin_list_users(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        if actor["role"] != "admin":
            raise HTTPException(status_code=403, detail="Админ панель доступна только администраторам")
        require_permission(db, actor, "users:read")
        rows = db.execute(
            """
            SELECT *
            FROM users
            ORDER BY CASE
                WHEN role='admin' THEN 0
                WHEN role='doctor' THEN 1
                ELSE 2
            END, created_at DESC, id DESC
            """
        ).fetchall()
        stats = db.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                SUM(CASE WHEN role='admin' THEN 1 ELSE 0 END) AS admins,
                SUM(CASE WHEN role='doctor' THEN 1 ELSE 0 END) AS doctors,
                SUM(CASE WHEN role='user' THEN 1 ELSE 0 END) AS users,
                SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active_users
            FROM users
            """
        ).fetchone()
        return {"users": [serialize_user(row) for row in rows], "stats": dict(stats)}
    finally:
        db.close()


@app.get("/doctor/patients")
def doctor_list_patients(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_permission(db, actor, "users:read")
        if actor["role"] == "admin":
            patient_rows = db.execute(
                """
                SELECT *
                FROM users
                WHERE role='user'
                ORDER BY name COLLATE NOCASE, id
                """
            ).fetchall()
        elif actor["role"] == "doctor":
            patient_rows = db.execute(
                """
                SELECT DISTINCT users.*
                FROM users
                JOIN appointments ON appointments.user_id = users.id
                WHERE users.role='user' AND appointments.doctor_user_id=?
                ORDER BY users.name COLLATE NOCASE, users.id
                """,
                (actor["id"],),
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
            "stats": {
                "total_patients": len(patients),
                "ready_analyses": total_ready_analyses,
                "active_referrals": total_active_referrals,
                "appointments": total_appointments,
            },
        }
    finally:
        db.close()


@app.post("/admin/users")
def admin_create_user(data: AdminUserCreate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_permission(db, actor, "users:create")
        role = validate_role(data.role)
        if not data.password.strip():
            raise HTTPException(status_code=400, detail="Пароль обязателен")
        existing = db.execute("SELECT id FROM users WHERE username=?", (data.username,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username уже используется")
        db.execute(
            """
            INSERT INTO users (
                name, username, password_hash, iin, dob, blood_type, phone, email, address,
                height, weight, role, is_active, department
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                data.name,
                data.username,
                hash_password(data.password),
                data.iin,
                data.dob,
                data.blood_type,
                data.phone,
                data.email,
                data.address,
                data.height,
                data.weight,
                role,
                data.department,
            ),
        )
        db.commit()
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        created = get_user_or_404(db, user_id)
        return {"status": "created", "user": serialize_user(created)}
    finally:
        db.close()


@app.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, data: AdminUserUpdate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_permission(db, actor, "users:update")
        fields = model_dump(data)
        if "role" in fields:
            fields["role"] = validate_role(fields["role"])
        if "is_active" in fields:
            fields["is_active"] = 1 if fields["is_active"] else 0
        if "password" in fields:
            password = fields.pop("password")
            if not password.strip():
                raise HTTPException(status_code=400, detail="Пароль не может быть пустым")
            fields["password_hash"] = hash_password(password)
        if not fields:
            raise HTTPException(status_code=400, detail="Нет данных для обновления")
        get_user_or_404(db, user_id)
        set_clause = ", ".join(f"{column}=?" for column in fields)
        db.execute(f"UPDATE users SET {set_clause} WHERE id=?", (*fields.values(), user_id))
        db.commit()
        updated = get_user_or_404(db, user_id)
        return {"status": "updated", "user": serialize_user(updated)}
    finally:
        db.close()


@app.get("/rbac/model")
def get_rbac_model(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_permission(db, actor, "rbac:read")
        rows = db.execute(
            """
            SELECT role, permission, description
            FROM role_permissions
            ORDER BY role, permission
            """
        ).fetchall()
        grouped = {}
        for row in rows:
            role = row["role"]
            grouped.setdefault(role, []).append(
                {"permission": row["permission"], "description": row["description"]}
            )
        return {"roles": [{"role": role, "permissions": permissions} for role, permissions in grouped.items()]}
    finally:
        db.close()


@app.post("/ai/chat")
async def ai_chat(data: ChatRequest, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        user_id = data.user_id or actor["id"]
        require_user_scope(db, actor, user_id, cross_user_permission="users:read")

        db.execute(
            "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, "user", data.message),
        )
        db.commit()

        system_prompt = data.context or "Ты — медицинский ИИ-ассистент. Отвечай кратко и по-дружески на русском языке."
        user_row = db.execute(
            "SELECT name, dob, height, weight, blood_type FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        analyses_rows = db.execute(
            """
            SELECT name, date, status, results
            FROM analyses
            WHERE user_id=? AND status IN (?, ?)
            ORDER BY COALESCE(ready_at, date, ordered_at, created_at) DESC
            LIMIT 10
            """,
            (user_id, ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED),
        ).fetchall()

        patient_context = ""
        if user_row:
            patient = dict(user_row)
            patient_context += (
                f"Пациент: {patient.get('name', 'Неизвестно')}, ДР: {patient.get('dob', '-')}, "
                f"рост: {patient.get('height', '-')}, вес: {patient.get('weight', '-')}, "
                f"группа крови: {patient.get('blood_type', '-')}\n"
            )

        analyses_context_lines = []
        all_results = []
        for row in analyses_rows:
            analysis = dict(row)
            line = f"- {analysis.get('name', 'Анализ')} ({analysis.get('date', '-')}) [{analysis.get('status', '-')}]"
            results = []
            if analysis.get("results"):
                try:
                    results = json.loads(analysis["results"])
                except Exception:
                    results = []
            if results:
                formatted = []
                for result in results:
                    all_results.append(result)
                    param = result.get("param", "показатель")
                    value = result.get("val", "-")
                    unit = result.get("unit", "")
                    norm = result.get("norm", "-")
                    marker = "норма" if result.get("ok") else "вне нормы"
                    formatted.append(f"{param}={value}{unit} (норма: {norm}, {marker})")
                line += ": " + "; ".join(formatted)
            analyses_context_lines.append(line)

        analyses_context = "Анализы:\n" + ("\n".join(analyses_context_lines) if analyses_context_lines else "нет данных")
        enriched_prompt = (
            f"{system_prompt}\n\n"
            "Ниже медицинский контекст пациента из БД. "
            "Используй его по умолчанию в ответе, если вопрос связан с анализами/здоровьем.\n"
            f"{patient_context}{analyses_context}\n\n"
            "Если данных недостаточно, задай только 1-2 уточняющих вопроса."
        )

        message_lower = data.message.lower()
        direct_analysis_triggers = [
            "analyze my test results",
            "analyse my test results",
            "analyze my analyses",
            "analyze my labs",
            "анализ моих",
            "проанализируй мои анализы",
            "анализируй мои анализы",
        ]

        if any(trigger in message_lower for trigger in direct_analysis_triggers):
            if not analyses_rows:
                reply = "I could not find your analyses in the database yet. Please upload or add at least one completed test result."
            else:
                abnormal = [result for result in all_results if not result.get("ok")]
                top_items = []
                for result in abnormal[:5]:
                    top_items.append(
                        f"- {result.get('param', 'Marker')}: {result.get('val', '-')}{result.get('unit', '')} "
                        f"(reference: {result.get('norm', '-')})"
                    )
                if abnormal:
                    overview = f"I analyzed your latest results. Found {len(abnormal)} parameter(s) outside the reference range."
                    recommendations = (
                        "Recommendations:\n"
                        "- Discuss these deviations with your therapist.\n"
                        "- Repeat key tests in 2-4 weeks if symptoms persist.\n"
                        "- Keep hydration, sleep, and nutrition consistent before retesting."
                    )
                    details = "Abnormal values:\n" + "\n".join(top_items)
                    reply = f"{overview}\n\n{details}\n\n{recommendations}"
                else:
                    reply = "I analyzed your latest results. All listed parameters are within the reference ranges. Continue routine monitoring and preventive checkups."

            db.execute(
                "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
                (user_id, "ai", reply),
            )
            db.commit()
            return {"reply": reply}

        if not GEMINI_API_KEY:
            reply = "GEMINI_API_KEY не настроен. AI-ответы недоступны, но доступен локальный анализ результатов."
        else:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                        json={"contents": [{"parts": [{"text": f"{enriched_prompt}\n\nВопрос: {data.message}"}]}]},
                    )
                    result = response.json()
                    reply = result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as error:
                reply = f"Ошибка подключения к ИИ: {str(error)}. Проверьте GEMINI_API_KEY."

        db.execute(
            "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, "ai", reply),
        )
        db.commit()
        return {"reply": reply}
    finally:
        db.close()


@app.get("/ai/health-score/{user_id}")
async def ai_health_score(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        require_user_scope(db, actor, user_id, cross_user_permission="users:read")
        user = serialize_user(get_user_or_404(db, user_id))
        analyses_rows = db.execute(
            "SELECT * FROM analyses WHERE user_id=? AND status IN (?, ?)",
            (user_id, ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED),
        ).fetchall()

        analyses_text = ""
        for row in analyses_rows:
            analysis = dict(row)
            results = json.loads(analysis["results"]) if analysis["results"] else []
            bad_results = [result for result in results if not result.get("ok")]
            analyses_text += f"\n{analysis['name']} ({analysis['date']}): "
            if bad_results:
                analyses_text += "Отклонения: " + ", ".join(
                    result["param"] + "=" + str(result["val"]) + result["unit"] for result in bad_results
                )
            else:
                analyses_text += "Все в норме"

        prompt = f"""Пациент: {user['name']}, {user['dob']}, рост {user['height']}см, вес {user['weight']}кг

Анализы:{analyses_text}

Задачи:
1. Оцени общее здоровье по шкале 0-100
2. Дай 3-4 конкретные рекомендации
3. Укажи к каким врачам стоит обратиться

Отвечай в JSON формате:
{{"score": число, "status": "строка", "recommendations": ["...", "..."], "doctors": ["..."]}}"""

        if not GEMINI_API_KEY:
            return {
                "score": 74,
                "status": "Хорошо",
                "recommendations": ["Настройте GEMINI_API_KEY для AI-оценки", "Продолжайте наблюдение у врача"],
                "doctors": ["Терапевт"],
                "error": "GEMINI_API_KEY is not configured",
            }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                text = text.strip().strip("```json").strip("```").strip()
                return json.loads(text)
        except Exception as error:
            return {
                "score": 74,
                "status": "Хорошо",
                "recommendations": ["Снизить холестерин через диету", "Контроль АД"],
                "doctors": ["Кардиолог"],
                "error": str(error),
            }
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()


if __name__ == "__main__":
    import uvicorn

    init_db()
    print("✅ БД инициализирована")
    print("🔐 Demo patient login: patient-demo / patient123")
    print("🔐 Demo doctor login: doctor-demo / doctor123")
    print("🔐 Demo admin login: admin-demo / admin123")
    print("🚀 Запуск сервера на http://localhost:8000")
    print("📖 Документация API: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
