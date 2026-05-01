from typing import Optional

from fastapi import APIRouter, Header, Query

from app_helpers import get_current_user
from db import get_db
from schemas import ProfileUpdate
from services import users_service


router = APIRouter(tags=["users"])


@router.get("/doctors")
def list_doctors(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.list_doctors(db, actor)
    finally:
        db.close()


@router.get("/doctors/{doctor_user_id}/availability")
def get_doctor_availability(doctor_user_id: int, date: str, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.get_doctor_availability(db, actor, doctor_user_id, date)
    finally:
        db.close()


@router.get("/directory/users")
def get_directory_users(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.get_directory_users(db, actor)
    finally:
        db.close()


@router.get("/context/{user_id}")
def get_user_context(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.get_user_context(db, actor, user_id)
    finally:
        db.close()


@router.get("/user/{user_id}")
def get_user(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.get_user_profile(db, actor, user_id)
    finally:
        db.close()


@router.put("/user/{user_id}")
def update_user(user_id: int, data: ProfileUpdate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.update_user_profile(db, actor, user_id, data)
    finally:
        db.close()


@router.get("/referrals/{user_id}")
def get_referrals(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.get_referrals(db, actor, user_id)
    finally:
        db.close()


@router.get("/doctor/patients")
def doctor_list_patients(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return users_service.list_doctor_patients(db, actor, limit=limit, offset=offset)
    finally:
        db.close()
