import sqlite3
import unittest

from fastapi import HTTPException

from db import seed_role_permissions
from schemas import AuthLogin, AuthRegister
from security import hash_password, verify_password
from services import auth_service


def make_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE,
            password_hash TEXT,
            phone TEXT,
            email TEXT,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            department TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE role_permissions (
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            description TEXT,
            PRIMARY KEY (role, permission)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    seed_role_permissions(cursor)
    conn.commit()
    return conn


class SecurityTests(unittest.TestCase):
    def test_hash_and_verify_password(self):
        encoded = hash_password("secret123", salt="abc123")
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password("secret123", encoded))
        self.assertFalse(verify_password("wrong-pass", encoded))

    def test_verify_password_handles_invalid_hash(self):
        self.assertFalse(verify_password("secret123", None))
        self.assertFalse(verify_password("secret123", "broken"))


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = make_test_db()

    def tearDown(self):
        self.db.close()

    def test_register_creates_user_and_session(self):
        result = auth_service.register(
            self.db,
            AuthRegister(
                name="Test User",
                username="tester",
                password="secret123",
                email="tester@example.com",
                phone="+77001234567",
            ),
        )

        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["portal"], "patient")
        self.assertEqual(result["user"]["username"], "tester")
        self.assertNotIn("password_hash", result["user"])
        self.assertTrue(result["token"])
        self.assertIn("appointments:create", result["permissions"])

        user = self.db.execute("SELECT * FROM users WHERE username='tester'").fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "user")
        self.assertTrue(verify_password("secret123", user["password_hash"]))

        session = self.db.execute("SELECT * FROM auth_sessions WHERE user_id=?", (user["id"],)).fetchone()
        self.assertIsNotNone(session)

    def test_register_rejects_duplicate_username(self):
        auth_service.register(
            self.db,
            AuthRegister(name="First User", username="tester", password="secret123"),
        )

        with self.assertRaises(HTTPException) as context:
            auth_service.register(
                self.db,
                AuthRegister(name="Second User", username="tester", password="secret123"),
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Username уже используется")

    def test_login_returns_existing_user_context(self):
        auth_service.register(
            self.db,
            AuthRegister(name="Test User", username="tester", password="secret123"),
        )

        result = auth_service.login(
            self.db,
            AuthLogin(username="tester", password="secret123"),
        )

        self.assertEqual(result["user"]["username"], "tester")
        self.assertEqual(result["portal"], "patient")
        self.assertTrue(result["token"])

    def test_login_rejects_wrong_password(self):
        auth_service.register(
            self.db,
            AuthRegister(name="Test User", username="tester", password="secret123"),
        )

        with self.assertRaises(HTTPException) as context:
            auth_service.login(
                self.db,
                AuthLogin(username="tester", password="wrong-pass"),
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Неверный логин или пароль")

    def test_logout_all_removes_all_user_sessions(self):
        register_result = auth_service.register(
            self.db,
            AuthRegister(name="Test User", username="tester", password="secret123"),
        )
        user = self.db.execute("SELECT * FROM users WHERE username='tester'").fetchone()
        auth_service.login(self.db, AuthLogin(username="tester", password="secret123"))

        sessions_before = self.db.execute(
            "SELECT COUNT(*) FROM auth_sessions WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]
        self.assertGreaterEqual(sessions_before, 2)

        result = auth_service.logout_all(self.db, user)
        self.assertEqual(result["status"], "logged_out_all")

        sessions_after = self.db.execute(
            "SELECT COUNT(*) FROM auth_sessions WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]
        self.assertEqual(sessions_after, 0)
        self.assertTrue(register_result["token"])


if __name__ == "__main__":
    unittest.main()
