"""initial postgres schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-03
"""

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username) WHERE username IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

    op.execute(
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
    op.execute("CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_analyses_doctor_user_id ON analyses(doctor_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status)")

    op.execute(
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
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_doctor_user_id ON appointments(doctor_user_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_doctor_slot_active
        ON appointments(doctor_user_id, date, time)
        WHERE COALESCE(status, '') != 'отменено'
        """
    )

    op.execute(
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
    op.execute(
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
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (role, permission)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS auth_sessions")
    op.execute("DROP TABLE IF EXISTS role_permissions")
    op.execute("DROP TABLE IF EXISTS chat_history")
    op.execute("DROP TABLE IF EXISTS referrals")
    op.execute("DROP TABLE IF EXISTS appointments")
    op.execute("DROP TABLE IF EXISTS analyses")
    op.execute("DROP TABLE IF EXISTS users")
