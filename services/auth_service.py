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
from schemas import AuthLogin, AuthRegister
from security import hash_password, verify_password


def login(db, data: AuthLogin):
    username = data.username.strip()
    if not username or not data.password:
        raise HTTPException(status_code=400, detail="Введите username и пароль")

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
