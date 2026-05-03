"""lab role, auth hardening, and audit log

Revision ID: 0002_lab_auth_audit
Revises: 0001_initial_schema
Create Date: 2026-05-03
"""

from alembic import op

revision = "0002_lab_auth_audit"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled INTEGER DEFAULT 0")
    op.execute("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS csrf_token TEXT")

    op.execute(
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
    op.execute(
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
    op.execute(
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
    op.execute(
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
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS two_factor_challenges")
    op.execute("DROP TABLE IF EXISTS verification_codes")
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")
    op.execute("ALTER TABLE auth_sessions DROP COLUMN IF EXISTS csrf_token")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS two_factor_enabled")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS phone_verified")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verified")
