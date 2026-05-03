from datetime import datetime, timedelta, timezone
import secrets
from threading import Lock

from fastapi import HTTPException

from app_helpers import (
    ensure_active,
    get_permissions,
    get_user_or_404,
    infer_portal,
    issue_session_token,
    log_audit,
    parse_db_timestamp,
    serialize_user,
    validate_name,
    validate_password,
    validate_username,
)
from db import get_last_insert_id
from schemas import (
    AuthLogin,
    AuthMfaVerify,
    AuthRegister,
    PasswordResetConfirm,
    PasswordResetRequest,
    TwoFactorToggle,
    VerificationConfirm,
    VerificationRequest,
)
from security import hash_password, verify_password

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 6
MFA_TTL_MINUTES = 5
RESET_TTL_MINUTES = 30
VERIFICATION_TTL_MINUTES = 10
_LOGIN_ATTEMPTS = {}
_LOGIN_LOCK = Lock()


def _utc_expiry(minutes: int):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def _session_payload(db, user):
    token, csrf_token = issue_session_token(db, user["id"])
    log_audit(db, user, "auth.login", entity_type="user", entity_id=user["id"])
    db.commit()
    return {
        "token": token,
        "csrf_token": csrf_token,
        "portal": infer_portal(user["role"]),
        "user": serialize_user(user),
        "permissions": get_permissions(db, user["role"]),
    }


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
    if user["role"] == "admin" and user["two_factor_enabled"]:
        challenge_token = secrets.token_urlsafe(24)
        code = f"{secrets.randbelow(1000000):06d}"
        db.execute(
            """
            INSERT INTO two_factor_challenges (challenge_token, user_id, code, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (challenge_token, user["id"], code, _utc_expiry(MFA_TTL_MINUTES)),
        )
        db.commit()
        return {
            "mfa_required": True,
            "challenge_token": challenge_token,
            "dev_code": code,
            "detail": "Введите 2FA-код администратора",
        }

    return _session_payload(db, user)


def verify_mfa(db, data: AuthMfaVerify):
    challenge = db.execute(
        """
        SELECT two_factor_challenges.*, users.*
        FROM two_factor_challenges
        JOIN users ON users.id = two_factor_challenges.user_id
        WHERE challenge_token=?
        """,
        (data.challenge_token.strip(),),
    ).fetchone()
    if not challenge:
        raise HTTPException(status_code=401, detail="2FA challenge не найден")
    expires_at = parse_db_timestamp(challenge["expires_at"])
    if not expires_at or expires_at < datetime.now(timezone.utc):
        db.execute("DELETE FROM two_factor_challenges WHERE challenge_token=?", (data.challenge_token.strip(),))
        db.commit()
        raise HTTPException(status_code=401, detail="2FA-код истек")
    if data.code.strip() != challenge["code"]:
        raise HTTPException(status_code=401, detail="Неверный 2FA-код")
    user = db.execute("SELECT * FROM users WHERE id=?", (challenge["user_id"],)).fetchone()
    ensure_active(user)
    db.execute("DELETE FROM two_factor_challenges WHERE challenge_token=?", (data.challenge_token.strip(),))
    return _session_payload(db, user)


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
    log_audit(db, user, "auth.register", entity_type="user", entity_id=user_id)
    payload = _session_payload(db, user)
    return {
        "status": "registered",
        **payload,
    }


def request_password_reset(db, data: PasswordResetRequest):
    username = data.username.strip() if data.username else None
    email = data.email.strip() if data.email else None
    if not username and not email:
        raise HTTPException(status_code=400, detail="Укажите username или email")
    user = db.execute(
        "SELECT * FROM users WHERE username=? OR email=?",
        (username or "", email or ""),
    ).fetchone()
    if not user:
        return {"status": "ok", "detail": "Если аккаунт найден, reset-token создан"}
    token = secrets.token_urlsafe(32)
    db.execute(
        """
        INSERT INTO password_reset_tokens (token, user_id, expires_at)
        VALUES (?, ?, ?)
        """,
        (token, user["id"], _utc_expiry(RESET_TTL_MINUTES)),
    )
    log_audit(db, user, "auth.password_reset_requested", entity_type="user", entity_id=user["id"])
    db.commit()
    return {"status": "ok", "dev_token": token, "expires_in_minutes": RESET_TTL_MINUTES}


def confirm_password_reset(db, data: PasswordResetConfirm):
    password = validate_password(data.password.strip())
    token = data.token.strip()
    row = db.execute(
        """
        SELECT password_reset_tokens.*, users.id AS target_user_id
        FROM password_reset_tokens
        JOIN users ON users.id = password_reset_tokens.user_id
        WHERE token=? AND used_at IS NULL
        """,
        (token,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Reset-token не найден")
    expires_at = parse_db_timestamp(row["expires_at"])
    if not expires_at or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset-token истек")
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["target_user_id"]))
    db.execute("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE token=?", (token,))
    db.execute("DELETE FROM auth_sessions WHERE user_id=?", (row["target_user_id"],))
    log_audit(db, None, "auth.password_reset_completed", entity_type="user", entity_id=row["target_user_id"])
    db.commit()
    return {"status": "password_updated"}


def request_verification(db, actor, data: VerificationRequest):
    channel = data.channel.strip().lower()
    if channel not in {"email", "phone"}:
        raise HTTPException(status_code=400, detail="channel должен быть email или phone")
    if channel == "email" and not actor["email"]:
        raise HTTPException(status_code=400, detail="Сначала укажите email")
    if channel == "phone" and not actor["phone"]:
        raise HTTPException(status_code=400, detail="Сначала укажите phone")
    code = f"{secrets.randbelow(1000000):06d}"
    db.execute(
        """
        INSERT INTO verification_codes (user_id, channel, code, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (actor["id"], channel, code, _utc_expiry(VERIFICATION_TTL_MINUTES)),
    )
    log_audit(db, actor, f"auth.{channel}_verification_requested", entity_type="user", entity_id=actor["id"])
    db.commit()
    return {"status": "sent", "channel": channel, "dev_code": code, "expires_in_minutes": VERIFICATION_TTL_MINUTES}


def confirm_verification(db, actor, data: VerificationConfirm):
    channel = data.channel.strip().lower()
    if channel not in {"email", "phone"}:
        raise HTTPException(status_code=400, detail="channel должен быть email или phone")
    row = db.execute(
        """
        SELECT *
        FROM verification_codes
        WHERE user_id=? AND channel=? AND code=? AND used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (actor["id"], channel, data.code.strip()),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Код подтверждения неверный")
    expires_at = parse_db_timestamp(row["expires_at"])
    if not expires_at or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Код подтверждения истек")
    column = "email_verified" if channel == "email" else "phone_verified"
    db.execute(f"UPDATE users SET {column}=1 WHERE id=?", (actor["id"],))
    db.execute("UPDATE verification_codes SET used_at=CURRENT_TIMESTAMP WHERE id=?", (row["id"],))
    log_audit(db, actor, f"auth.{channel}_verified", entity_type="user", entity_id=actor["id"])
    db.commit()
    return {"status": "verified", "channel": channel}


def set_two_factor(db, actor, data: TwoFactorToggle):
    db.execute(
        "UPDATE users SET two_factor_enabled=? WHERE id=?",
        (1 if data.enabled else 0, actor["id"]),
    )
    log_audit(db, actor, "auth.2fa_updated", entity_type="user", entity_id=actor["id"], metadata={"enabled": data.enabled})
    db.commit()
    return {"status": "updated", "two_factor_enabled": data.enabled}


def get_session_context(db, user):
    return {
        "user": serialize_user(user),
        "permissions": get_permissions(db, user["role"]),
        "portal": infer_portal(user["role"]),
    }


def logout(db, token: str):
    row = db.execute("SELECT user_id FROM auth_sessions WHERE token=?", (token,)).fetchone()
    db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
    if row:
        log_audit(db, None, "auth.logout", entity_type="user", entity_id=row["user_id"])
    db.commit()
    return {"status": "logged_out"}


def logout_all(db, actor):
    db.execute("DELETE FROM auth_sessions WHERE user_id=?", (actor["id"],))
    log_audit(db, actor, "auth.logout_all", entity_type="user", entity_id=actor["id"])
    db.commit()
    return {"status": "logged_out_all"}
