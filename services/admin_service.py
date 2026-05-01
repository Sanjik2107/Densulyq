from fastapi import HTTPException

from app_helpers import (
    get_user_or_404,
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
from schemas import AdminUserCreate, AdminUserUpdate, model_dump
from security import hash_password


def list_users(db, actor, *, limit: int = 50, offset: int = 0):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Админ панель доступна только администраторам")
    require_permission(db, actor, "users:read")
    limit, offset = parse_pagination(limit, offset)
    rows = db.execute(
        """
        SELECT *
        FROM users
        ORDER BY CASE
            WHEN role='admin' THEN 0
            WHEN role='doctor' THEN 1
            ELSE 2
        END, created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """
        ,
        (limit, offset),
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
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    created = get_user_or_404(db, user_id)
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
        if not password.strip():
            raise HTTPException(status_code=400, detail="Пароль не может быть пустым")
        fields["password_hash"] = hash_password(password)
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
