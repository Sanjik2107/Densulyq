from fastapi import HTTPException

from app_helpers import get_user_or_404, require_permission, serialize_user, validate_role
from schemas import AdminUserCreate, AdminUserUpdate, model_dump
from security import hash_password


def list_users(db, actor):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Админ панель доступна только администраторам")
    require_permission(db, actor, "users:read")
    rows = db.execute(
        """
        SELECT *
        FROM users
        ORDER BY CASE
            WHEN role='admin' THEN 0
            WHEN role='doctor' THEN 1
            ELSE 2
        END, created_at DESC, id DESC
        """
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
    return {"users": [serialize_user(row) for row in rows], "stats": dict(stats)}


def create_user(db, actor, data: AdminUserCreate):
    require_permission(db, actor, "users:create")
    role = validate_role(data.role)
    if not data.password.strip():
        raise HTTPException(status_code=400, detail="Пароль обязателен")
    existing = db.execute("SELECT id FROM users WHERE username=?", (data.username,)).fetchone()
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
            data.name,
            data.username,
            hash_password(data.password),
            data.iin,
            data.dob,
            data.blood_type,
            data.phone,
            data.email,
            data.address,
            data.height,
            data.weight,
            role,
            data.department,
        ),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    created = get_user_or_404(db, user_id)
    return {"status": "created", "user": serialize_user(created)}


def update_user(db, actor, user_id: int, data: AdminUserUpdate):
    require_permission(db, actor, "users:update")
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
    if not fields:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    get_user_or_404(db, user_id)
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
