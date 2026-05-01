from typing import Optional

from fastapi import APIRouter, Header, Request

from app_helpers import extract_token, get_current_user
from db import get_db
from schemas import AuthLogin, AuthRegister
from services import auth_service


router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def auth_login(data: AuthLogin, request: Request):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
    if not client_ip:
        client_ip = request.client.host if request.client else ""
    db = get_db()
    try:
        return auth_service.login(db, data, client_ip=client_ip)
    finally:
        db.close()


@router.post("/auth/register")
def auth_register(data: AuthRegister):
    db = get_db()
    try:
        return auth_service.register(db, data)
    finally:
        db.close()


@router.get("/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        user = get_current_user(db, authorization)
        return auth_service.get_session_context(db, user)
    finally:
        db.close()


@router.post("/auth/logout")
def auth_logout(authorization: Optional[str] = Header(default=None)):
    token = extract_token(authorization)
    db = get_db()
    try:
        return auth_service.logout(db, token)
    finally:
        db.close()


@router.post("/auth/logout-all")
def auth_logout_all(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return auth_service.logout_all(db, actor)
    finally:
        db.close()
