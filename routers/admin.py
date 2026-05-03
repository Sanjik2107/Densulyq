from typing import Optional

from fastapi import APIRouter, Header, Query, Response

from app_helpers import get_current_user
from db import get_db
from schemas import AdminUserCreate, AdminUserUpdate
from services import admin_service


router = APIRouter(tags=["admin"])


@router.get("/admin/users")
def admin_list_users(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str = "",
    role: str = "",
    is_active: Optional[bool] = None,
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return admin_service.list_users(db, actor, limit=limit, offset=offset, query=query, role=role, is_active=is_active)
    finally:
        db.close()


@router.post("/admin/users")
def admin_create_user(data: AdminUserCreate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return admin_service.create_user(db, actor, data)
    finally:
        db.close()


@router.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, data: AdminUserUpdate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return admin_service.update_user(db, actor, user_id, data)
    finally:
        db.close()


@router.get("/rbac/model")
def get_rbac_model(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return admin_service.get_rbac_model(db, actor)
    finally:
        db.close()


@router.get("/admin/audit-log")
def admin_audit_log(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str = "",
    actor_user_id: int = 0,
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return admin_service.list_audit_log(db, actor, limit=limit, offset=offset, action=action, actor_user_id=actor_user_id)
    finally:
        db.close()


@router.get("/admin/users/export")
def admin_export_users(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        csv_text = admin_service.export_users_csv(db, actor)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=densaulyq-users.csv"},
        )
    finally:
        db.close()
