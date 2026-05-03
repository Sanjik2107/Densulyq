import json
import sqlite3
from datetime import datetime
from typing import Optional

from config import (
    ANALYSIS_STATUS_ORDERED,
    ANALYSIS_STATUS_READY,
    ANALYSIS_STATUS_REVIEWED,
    DATABASE_URL,
    DB_PATH,
    DEMO_CREDENTIALS,
    PASSWORD_SCHEME,
    ROLE_PERMISSIONS,
)
from security import hash_password

try:
    import psycopg
    from psycopg import errors as psycopg_errors
except ImportError:  # pragma: no cover - only used when PostgreSQL is configured.
    psycopg = None
    psycopg_errors = None


class DatabaseIntegrityError(Exception):
    pass


class DbRow(dict):
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class PgCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self._columns = [column.name for column in cursor.description] if cursor.description else []

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return DbRow(self._columns, row)

    def fetchall(self):
        return [DbRow(self._columns, row) for row in self.cursor.fetchall()]


class PgConnection:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        sql = _translate_sqlite_sql_to_postgres(sql)
        try:
            cursor = self.conn.execute(sql, params)
            return PgCursor(cursor)
        except psycopg_errors.IntegrityError as error:
            self.conn.rollback()
            raise DatabaseIntegrityError(str(error)) from error

    def executemany(self, sql, params_seq):
        sql = _translate_sqlite_sql_to_postgres(sql)
        try:
            with self.conn.cursor() as cursor:
                cursor.executemany(sql, params_seq)
        except psycopg_errors.IntegrityError as error:
            self.conn.rollback()
            raise DatabaseIntegrityError(str(error)) from error

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def _translate_sqlite_sql_to_postgres(sql: str):
    translated = (
        sql.replace("?", "%s")
        .replace("COLLATE NOCASE", "")
        .replace("SELECT last_insert_rowid()", "SELECT LASTVAL()")
    )
    if "INSERT OR IGNORE INTO role_permissions" in translated:
        translated = translated.replace("INSERT OR IGNORE INTO role_permissions", "INSERT INTO role_permissions")
        translated = translated.replace(
            "VALUES (%s, %s, %s)",
            "VALUES (%s, %s, %s) ON CONFLICT (role, permission) DO NOTHING",
        )
    return translated


def get_db():
    if DATABASE_URL:
        if psycopg is None:
            raise RuntimeError("PostgreSQL is configured, but psycopg is not installed")
        conn = psycopg.connect(DATABASE_URL)
        return PgConnection(conn)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def is_postgres_connection(conn):
    return isinstance(conn, PgConnection)


def get_last_insert_id(conn):
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def ensure_column(conn, table_name: str, column_name: str, column_sql: str):
    if is_postgres_connection(conn):
        column = column_sql.split()[0]
        column_type = " ".join(column_sql.split()[1:])
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column} {column_type}")
        return
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


def seed_role_permissions(cursor):
    for role, permissions in ROLE_PERMISSIONS.items():
        for permission, description in permissions:
            cursor.execute(
                """
                INSERT OR IGNORE INTO role_permissions (role, permission, description)
                VALUES (?, ?, ?)
                """,
                (role, permission, description),
            )


def seed_demo_password(cursor, username: str):
    password = DEMO_CREDENTIALS[username]
    cursor.execute(
        "UPDATE users SET password_hash=? WHERE username=?",
        (hash_password(password), username),
    )


def has_supported_password_hash(encoded: Optional[str]):
    if not encoded:
        return False
    try:
        scheme, iterations_raw, salt, digest = encoded.split("$", 3)
        return scheme == PASSWORD_SCHEME and int(iterations_raw) > 0 and bool(salt) and bool(digest)
    except Exception:
        return False


def seed_demo_password_if_needed(cursor, user_row, username: str):
    password_hash = None
    if user_row:
        try:
            password_hash = user_row["password_hash"]
        except (KeyError, IndexError):
            password_hash = None
    if not has_supported_password_hash(password_hash):
        seed_demo_password(cursor, username)


def init_postgres_db(conn):
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
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
            email_verified INTEGER DEFAULT 0,
            phone_verified INTEGER DEFAULT 0,
            two_factor_enabled INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_column(conn, "users", "email_verified", "email_verified INTEGER DEFAULT 0")
    ensure_column(conn, "users", "phone_verified", "phone_verified INTEGER DEFAULT 0")
    ensure_column(conn, "users", "two_factor_enabled", "two_factor_enabled INTEGER DEFAULT 0")
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
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            doctor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_analyses_doctor_user_id ON analyses(doctor_user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status)")

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            doctor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            doctor TEXT,
            speciality TEXT,
            date TEXT,
            time TEXT,
            place TEXT,
            reason TEXT,
            status TEXT DEFAULT 'ожидание',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_appointments_doctor_user_id ON appointments(doctor_user_id)")
    c.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_doctor_slot_active
        ON appointments(doctor_user_id, date, time)
        WHERE COALESCE(status, '') != 'отменено'
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT,
            from_doctor TEXT,
            issue_date TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'активно'
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            csrf_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_column(conn, "auth_sessions", "csrf_token", "csrf_token TEXT")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_codes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS two_factor_challenges (
            challenge_token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)")

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
            SET username='patient-demo', role='user', is_active=1, department=COALESCE(department, 'Пациент')
            WHERE id=1
            """
        )
        seed_demo_password_if_needed(c, demo_user, "patient-demo")

    c.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1))")

    demo_accounts = [
        (
            "admin-demo",
            "Администратор Densaulyq",
            "880101400001",
            "01.01.1988",
            "I+",
            "+7 700 000 00 01",
            "admin@densaulyq.local",
            "г. Алматы, центр администрирования",
            175,
            74,
            "admin",
            "Администрация",
            1,
        ),
        (
            "doctor-demo",
            "Иванова Н.С.",
            "870212400002",
            "12.02.1987",
            "I+",
            "+7 700 000 00 02",
            "doctor@densaulyq.local",
            "г. Алматы, клиника Densaulyq",
            168,
            62,
            "doctor",
            "Терапия",
            0,
        ),
        (
            "lab-demo",
            "Лаборант Densaulyq",
            "890303400003",
            "03.03.1989",
            "III+",
            "+7 700 000 00 03",
            "lab@densaulyq.local",
            "г. Алматы, лаборатория Densaulyq",
            170,
            65,
            "lab",
            "Лаборатория",
            0,
        ),
    ]
    for username, name, iin, dob, blood_type, phone, email, address, height, weight, role, department, two_factor_enabled in demo_accounts:
        user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            c.execute(
                """
                INSERT INTO users (
                    name, username, password_hash, iin, dob, blood_type, phone,
                    email, address, height, weight, role, is_active, department,
                    email_verified, phone_verified, two_factor_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 1, 1, ?)
                """,
                (
                    name,
                    username,
                    hash_password(DEMO_CREDENTIALS[username]),
                    iin,
                    dob,
                    blood_type,
                    phone,
                    email,
                    address,
                    height,
                    weight,
                    role,
                    department,
                    two_factor_enabled,
                ),
            )
        else:
            c.execute(
                """
                UPDATE users
                SET role=?, is_active=1, department=COALESCE(department, ?), two_factor_enabled=?
                WHERE username=?
                """,
                (role, department, two_factor_enabled, username),
            )
            seed_demo_password_if_needed(c, user, username)

    doctor_demo = c.execute("SELECT id, name, department FROM users WHERE username='doctor-demo'").fetchone()

    analyses_exists = c.execute("SELECT 1 FROM analyses WHERE user_id=1 LIMIT 1").fetchone()
    if not analyses_exists and doctor_demo:
        c.executemany(
            """
            INSERT INTO analyses (
                user_id, doctor_user_id, name, date, doctor, status, results,
                ordered_at, scheduled_for, ready_at, reviewed_at, doctor_note, lab_note, is_visible_to_patient
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    doctor_demo["id"],
                    "Общий анализ крови",
                    "2025-03-12",
                    doctor_demo["name"],
                    ANALYSIS_STATUS_READY,
                    json.dumps(
                        [
                            {"param": "Гемоглобин", "val": 145, "unit": "г/л", "norm": "120-160", "ok": True},
                            {"param": "Лейкоциты", "val": 9.1, "unit": "x10^9/л", "norm": "4.0-9.0", "ok": False},
                        ],
                        ensure_ascii=False,
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
                    doctor_demo["name"],
                    ANALYSIS_STATUS_REVIEWED,
                    json.dumps(
                        [
                            {"param": "Глюкоза", "val": 5.2, "unit": "ммоль/л", "norm": "3.9-6.1", "ok": True},
                            {"param": "Холестерин общий", "val": 5.8, "unit": "ммоль/л", "norm": "< 5.2", "ok": False},
                        ],
                        ensure_ascii=False,
                    ),
                    "2025-03-10",
                    "2025-03-12",
                    "2025-03-12",
                    "2025-03-13",
                    "Повторить липидный профиль через 6-8 недель и обсудить рацион.",
                    "Показатели готовы и проверены лабораторией.",
                    1,
                ),
            ],
        )

    appointments_exist = c.execute("SELECT 1 FROM appointments WHERE user_id=1 LIMIT 1").fetchone()
    if not appointments_exist and doctor_demo:
        c.executemany(
            """
            INSERT INTO appointments (user_id, doctor_user_id, doctor, speciality, date, time, place, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, doctor_demo["id"], doctor_demo["name"], doctor_demo["department"], "2025-04-25", "14:00", "Кабинет 105", "Контроль давления", "подтверждено"),
            ],
        )

    referrals_exist = c.execute("SELECT 1 FROM referrals WHERE user_id=1 LIMIT 1").fetchone()
    if not referrals_exist:
        c.executemany(
            """
            INSERT INTO referrals (user_id, name, from_doctor, issue_date, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Общий анализ крови", "Иванова Н.С.", "2025-04-10", "2025-04-30", "активно"),
                (1, "УЗИ брюшной полости", "Карпова В.М.", "2025-04-05", "2025-05-05", "активно"),
            ],
        )

    c.execute("DELETE FROM auth_sessions WHERE user_id NOT IN (SELECT id FROM users)")
    c.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1))")
    c.execute("SELECT setval(pg_get_serial_sequence('analyses', 'id'), COALESCE((SELECT MAX(id) FROM analyses), 1))")
    c.execute("SELECT setval(pg_get_serial_sequence('appointments', 'id'), COALESCE((SELECT MAX(id) FROM appointments), 1))")
    c.execute("SELECT setval(pg_get_serial_sequence('referrals', 'id'), COALESCE((SELECT MAX(id) FROM referrals), 1))")
    c.execute("SELECT setval(pg_get_serial_sequence('chat_history', 'id'), COALESCE((SELECT MAX(id) FROM chat_history), 1))")
    c.execute("SELECT setval(pg_get_serial_sequence('verification_codes', 'id'), COALESCE((SELECT MAX(id) FROM verification_codes), 1))")
    c.execute("SELECT setval(pg_get_serial_sequence('audit_log', 'id'), COALESCE((SELECT MAX(id) FROM audit_log), 1))")
    conn.commit()
    conn.close()


def init_db():
    conn = get_db()
    c = conn.cursor()

    if is_postgres_connection(conn):
        init_postgres_db(conn)
        return

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
            email_verified INTEGER DEFAULT 0,
            phone_verified INTEGER DEFAULT 0,
            two_factor_enabled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    ensure_column(conn, "users", "username", "username TEXT")
    ensure_column(conn, "users", "password_hash", "password_hash TEXT")
    ensure_column(conn, "users", "role", "role TEXT DEFAULT 'user'")
    ensure_column(conn, "users", "is_active", "is_active INTEGER DEFAULT 1")
    ensure_column(conn, "users", "department", "department TEXT")
    ensure_column(conn, "users", "email_verified", "email_verified INTEGER DEFAULT 0")
    ensure_column(conn, "users", "phone_verified", "phone_verified INTEGER DEFAULT 0")
    ensure_column(conn, "users", "two_factor_enabled", "two_factor_enabled INTEGER DEFAULT 0")

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
            csrf_token TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    ensure_column(conn, "auth_sessions", "csrf_token", "csrf_token TEXT")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS two_factor_challenges (
            challenge_token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)")

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
        seed_demo_password_if_needed(c, demo_user, "patient-demo")

    admin_user = c.execute("SELECT * FROM users WHERE username='admin-demo'").fetchone()
    if not admin_user:
        c.execute(
            """
            INSERT INTO users (
                name, username, password_hash, iin, dob, blood_type, phone,
                email, address, height, weight, role, is_active, department,
                email_verified, phone_verified, two_factor_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1)
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
                department=COALESCE(department, 'Администрация'),
                two_factor_enabled=1
            WHERE username='admin-demo'
            """
        )
        seed_demo_password_if_needed(c, admin_user, "admin-demo")

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
        seed_demo_password_if_needed(c, doctor_user, "doctor-demo")

    lab_user = c.execute("SELECT * FROM users WHERE username='lab-demo'").fetchone()
    if not lab_user:
        c.execute(
            """
            INSERT INTO users (
                name, username, password_hash, iin, dob, blood_type, phone,
                email, address, height, weight, role, is_active, department,
                email_verified, phone_verified, two_factor_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
            """,
            (
                "Лаборант Densaulyq",
                "lab-demo",
                hash_password(DEMO_CREDENTIALS["lab-demo"]),
                "890303400003",
                "03.03.1989",
                "III+",
                "+7 700 000 00 03",
                "lab@densaulyq.local",
                "г. Алматы, лаборатория Densaulyq",
                170,
                65,
                "lab",
                1,
                "Лаборатория",
            ),
        )
    else:
        c.execute(
            """
            UPDATE users
            SET role='lab',
                is_active=1,
                department=COALESCE(department, 'Лаборатория')
            WHERE username='lab-demo'
            """
        )
        seed_demo_password_if_needed(c, lab_user, "lab-demo")

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
