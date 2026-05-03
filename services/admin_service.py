import csv
import io
import json
import sqlite3

from fastapi import HTTPException

from app_helpers import (
    get_user_or_404,
    log_audit,
    normalize_optional_string,
    parse_pagination,
    require_permission,
    serialize_user,
    validate_iin,
    validate_name,
    validate_password,
    validate_role,
    validate_username,
)
from db import DatabaseIntegrityError, get_last_insert_id
from schemas import AdminUserCreate, AdminUserUpdate, model_dump
from security import hash_password


def list_users(db, actor, *, limit: int = 50, offset: int = 0, query: str = "", role: str = "", is_active=None):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Админ панель доступна только администраторам")
    require_permission(db, actor, "users:read")
    limit, offset = parse_pagination(limit, offset)
    filters = []
    params = []
    if query:
        like = f"%{query.strip()}%"
        filters.append("(name LIKE ? OR username LIKE ? OR email LIKE ? OR phone LIKE ?)")
        params.extend([like, like, like, like])
    if role:
        filters.append("role=?")
        params.append(validate_role(role.strip()))
    if is_active is not None:
        filters.append("is_active=?")
        params.append(1 if is_active else 0)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    rows = db.execute(
        f"""
        SELECT *
        FROM users
        {where_clause}
        ORDER BY CASE
            WHEN role='admin' THEN 0
            WHEN role='doctor' THEN 1
            WHEN role='lab' THEN 2
            ELSE 3
        END, created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """
        ,
        (*params, limit, offset),
    ).fetchall()
    stats = db.execute(
        """
        SELECT
            COUNT(*) AS total_users,
            SUM(CASE WHEN role='admin' THEN 1 ELSE 0 END) AS admins,
            SUM(CASE WHEN role='doctor' THEN 1 ELSE 0 END) AS doctors,
            SUM(CASE WHEN role='lab' THEN 1 ELSE 0 END) AS labs,
            SUM(CASE WHEN role='user' THEN 1 ELSE 0 END) AS users,
            SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active_users
        FROM users
        """
    ).fetchone()
    return {"users": [serialize_user(row) for row in rows], "stats": dict(stats), "limit": limit, "offset": offset}


def create_user(db, actor, data: AdminUserCreate):
    require_permission(db, actor, "users:create")
    name = validate_name(data.name)
    username = validate_username(data.username)
    password = validate_password(data.password)
    role = validate_role(data.role)
    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Username уже используется")
    if data.height is not None and data.height <= 0:
        raise HTTPException(status_code=400, detail="Рост должен быть положительным числом")
    if data.weight is not None and data.weight <= 0:
        raise HTTPException(status_code=400, detail="Вес должен быть положительным числом")
    try:
        db.execute(
            """
            INSERT INTO users (
                name, username, password_hash, iin, dob, blood_type, phone, email, address,
                height, weight, role, is_active, department
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                name,
                username,
                hash_password(password),
                validate_iin(data.iin),
                normalize_optional_string(data.dob),
                normalize_optional_string(data.blood_type),
                normalize_optional_string(data.phone),
                normalize_optional_string(data.email),
                normalize_optional_string(data.address),
                data.height,
                data.weight,
                role,
                normalize_optional_string(data.department),
            ),
        )
    except (sqlite3.IntegrityError, DatabaseIntegrityError) as error:
        message = str(error).lower()
        if "iin" in message:
            raise HTTPException(status_code=400, detail="Такой ИИН уже используется")
        if "username" in message or "unique" in message:
            raise HTTPException(status_code=400, detail="Username уже используется")
        raise
    db.commit()
    user_id = get_last_insert_id(db)
    created = get_user_or_404(db, user_id)
    log_audit(db, actor, "admin.user_created", entity_type="user", entity_id=user_id, metadata={"role": role})
    db.commit()
    return {"status": "created", "user": serialize_user(created)}


def update_user(db, actor, user_id: int, data: AdminUserUpdate):
    require_permission(db, actor, "users:update")
    current = get_user_or_404(db, user_id)
    fields = model_dump(data)
    if "role" in fields:
        fields["role"] = validate_role(fields["role"])
    if "is_active" in fields:
        fields["is_active"] = 1 if fields["is_active"] else 0
    if "password" in fields:
        password = fields.pop("password")
        password = validate_password(password.strip())
        fields["password_hash"] = hash_password(password)
    if "two_factor_enabled" in fields:
        fields["two_factor_enabled"] = 1 if fields["two_factor_enabled"] else 0
    for key in ("department", "email", "phone", "address"):
        if key in fields:
            fields[key] = normalize_optional_string(fields[key])
    if not fields:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    if current["role"] == "admin":
        next_role = fields.get("role", current["role"])
        next_active = fields.get("is_active", current["is_active"])
        if next_role != "admin" or int(next_active) == 0:
            active_admins = db.execute(
                "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1 AND id<>?",
                (user_id,),
            ).fetchone()[0]
            if active_admins == 0:
                raise HTTPException(status_code=400, detail="Нельзя деактивировать или понизить последнего активного администратора")
    set_clause = ", ".join(f"{column}=?" for column in fields)
    db.execute(f"UPDATE users SET {set_clause} WHERE id=?", (*fields.values(), user_id))
    log_audit(db, actor, "admin.user_updated", entity_type="user", entity_id=user_id, metadata={"fields": sorted(fields)})
    db.commit()
    updated = get_user_or_404(db, user_id)
    return {"status": "updated", "user": serialize_user(updated)}


def get_rbac_model(db, actor):
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


def list_audit_log(db, actor, *, limit: int = 50, offset: int = 0, action: str = "", actor_user_id: int = 0):
    require_permission(db, actor, "audit:read")
    limit, offset = parse_pagination(limit, offset)
    filters = []
    params = []
    if action:
        filters.append("audit_log.action LIKE ?")
        params.append(f"%{action.strip()}%")
    if actor_user_id:
        filters.append("audit_log.actor_user_id=?")
        params.append(actor_user_id)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    rows = db.execute(
        f"""
        SELECT audit_log.*, users.username AS actor_username, users.name AS actor_name
        FROM audit_log
        LEFT JOIN users ON users.id = audit_log.actor_user_id
        {where_clause}
        ORDER BY audit_log.created_at DESC, audit_log.id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.get("metadata") or "{}")
        except Exception:
            item["metadata"] = {}
        items.append(item)
    return {"audit": items, "limit": limit, "offset": offset}


def export_users_csv(db, actor):
    require_permission(db, actor, "users:read")
    rows = db.execute(
        """
        SELECT id, name, username, role, is_active, email, email_verified, phone, phone_verified, department, created_at
        FROM users
        ORDER BY id
        """
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "username", "role", "is_active", "email", "email_verified", "phone", "phone_verified", "department", "created_at"])
    for row in rows:
        writer.writerow([row[key] for key in row.keys()])
    log_audit(db, actor, "admin.users_exported", entity_type="user")
    db.commit()
    return output.getvalue()
