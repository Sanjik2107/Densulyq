from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException

from app_helpers import (
    ensure_active,
    get_permissions,
    get_user_or_404,
    infer_portal,
    issue_session_token,
    serialize_user,
    validate_name,
    validate_password,
    validate_username,
)
from db import get_last_insert_id
from schemas import AuthLogin, AuthRegister
from security import hash_password, verify_password

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 6
_LOGIN_ATTEMPTS = {}
_LOGIN_LOCK = Lock()


def _rate_limit_key(username: str, client_ip: str):
    return f"{username.lower()}|{client_ip or 'unknown'}"


def _enforce_login_rate_limit(username: str, client_ip: str):
    now = datetime.now(timezone.utc)
    key = _rate_limit_key(username, client_ip)
    with _LOGIN_LOCK:
        entry = _LOGIN_ATTEMPTS.get(key)
        if not entry:
            return
        if now - entry["first_attempt"] > timedelta(seconds=LOGIN_WINDOW_SECONDS):
            _LOGIN_ATTEMPTS.pop(key, None)
            return
        if entry["count"] >= LOGIN_MAX_ATTEMPTS:
            remaining = int(
                LOGIN_WINDOW_SECONDS - (now - entry["first_attempt"]).total_seconds()
            )
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много попыток входа. Повторите через {max(1, remaining)} сек.",
            )


def _register_failed_login(username: str, client_ip: str):
    now = datetime.now(timezone.utc)
    key = _rate_limit_key(username, client_ip)
    with _LOGIN_LOCK:
        entry = _LOGIN_ATTEMPTS.get(key)
        if not entry or now - entry["first_attempt"] > timedelta(seconds=LOGIN_WINDOW_SECONDS):
            _LOGIN_ATTEMPTS[key] = {"count": 1, "first_attempt": now}
            return
        entry["count"] += 1


def _clear_failed_logins(username: str, client_ip: str):
    key = _rate_limit_key(username, client_ip)
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(key, None)


def login(db, data: AuthLogin, *, client_ip: str = ""):
    username = data.username.strip()
    if not username or not data.password:
        raise HTTPException(status_code=400, detail="Введите username и пароль")
    _enforce_login_rate_limit(username, client_ip)

    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user or not verify_password(data.password, user["password_hash"]):
        _register_failed_login(username, client_ip)
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    _clear_failed_logins(username, client_ip)

    ensure_active(user)

    token = issue_session_token(db, user["id"])
    db.commit()
    return {
        "token": token,
        "portal": infer_portal(user["role"]),
        "user": serialize_user(user),
        "permissions": get_permissions(db, user["role"]),
    }


def register(db, data: AuthRegister):
    name = validate_name(data.name)
    username = validate_username(data.username)
    password = validate_password(data.password)
    email = data.email.strip() if data.email else None
    phone = data.phone.strip() if data.phone else None

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
    user_id = get_last_insert_id(db)
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


def get_session_context(db, user):
    return {
        "user": serialize_user(user),
        "permissions": get_permissions(db, user["role"]),
        "portal": infer_portal(user["role"]),
    }


def logout(db, token: str):
    db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
    db.commit()
    return {"status": "logged_out"}


def logout_all(db, actor):
    db.execute("DELETE FROM auth_sessions WHERE user_id=?", (actor["id"],))
    db.commit()
    return {"status": "logged_out_all"}
