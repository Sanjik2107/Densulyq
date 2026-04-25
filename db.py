import json
import sqlite3
from datetime import datetime
from typing import Optional

from config import (
    ANALYSIS_STATUS_ORDERED,
    ANALYSIS_STATUS_READY,
    ANALYSIS_STATUS_REVIEWED,
    DB_PATH,
    DEMO_CREDENTIALS,
    ROLE_PERMISSIONS,
)
from security import hash_password


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


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


def try_normalize_slot_time(raw_value: Optional[str]):
    cleaned = (raw_value or "").strip()
    if not cleaned:
        return None
    try:
        slot = datetime.strptime(cleaned, "%H:%M")
    except ValueError:
        return None
    return slot.strftime("%H:%M")


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
