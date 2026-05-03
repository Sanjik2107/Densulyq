from typing import Optional

from fastapi import APIRouter, Header, Request, Response

from app_helpers import extract_token, get_current_user
from db import get_db
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
from services import auth_service


router = APIRouter(tags=["auth"])


def set_auth_cookies(response: Response, payload: dict):
    token = payload.get("token")
    csrf_token = payload.get("csrf_token")
    if token:
        response.set_cookie(
            "session_token",
            token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=60 * 60 * 24,
        )
    if csrf_token:
        response.set_cookie(
            "csrf_token",
            csrf_token,
            httponly=False,
            samesite="lax",
            secure=False,
            max_age=60 * 60 * 24,
        )
    return payload


def clear_auth_cookies(response: Response):
    response.delete_cookie("session_token")
    response.delete_cookie("csrf_token")


@router.post("/auth/login")
def auth_login(data: AuthLogin, request: Request, response: Response):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
    if not client_ip:
        client_ip = request.client.host if request.client else ""
    db = get_db()
    try:
        payload = auth_service.login(db, data, client_ip=client_ip)
        return set_auth_cookies(response, payload)
    finally:
        db.close()


@router.post("/auth/2fa/verify")
def auth_mfa_verify(data: AuthMfaVerify, response: Response):
    db = get_db()
    try:
        payload = auth_service.verify_mfa(db, data)
        return set_auth_cookies(response, payload)
    finally:
        db.close()


@router.post("/auth/register")
def auth_register(data: AuthRegister, response: Response):
    db = get_db()
    try:
        payload = auth_service.register(db, data)
        return set_auth_cookies(response, payload)
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
def auth_logout(response: Response, authorization: Optional[str] = Header(default=None)):
    token = extract_token(authorization)
    db = get_db()
    try:
        result = auth_service.logout(db, token)
        clear_auth_cookies(response)
        return result
    finally:
        db.close()


@router.post("/auth/logout-all")
def auth_logout_all(response: Response, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        result = auth_service.logout_all(db, actor)
        clear_auth_cookies(response)
        return result
    finally:
        db.close()


@router.post("/auth/password-reset/request")
def auth_password_reset_request(data: PasswordResetRequest):
    db = get_db()
    try:
        return auth_service.request_password_reset(db, data)
    finally:
        db.close()


@router.post("/auth/password-reset/confirm")
def auth_password_reset_confirm(data: PasswordResetConfirm):
    db = get_db()
    try:
        return auth_service.confirm_password_reset(db, data)
    finally:
        db.close()


@router.post("/auth/verification/request")
def auth_verification_request(data: VerificationRequest, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return auth_service.request_verification(db, actor, data)
    finally:
        db.close()


@router.post("/auth/verification/confirm")
def auth_verification_confirm(data: VerificationConfirm, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return auth_service.confirm_verification(db, actor, data)
    finally:
        db.close()


@router.put("/auth/2fa")
def auth_set_two_factor(data: TwoFactorToggle, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return auth_service.set_two_factor(db, actor, data)
    finally:
        db.close()
