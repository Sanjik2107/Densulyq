from typing import Optional

from fastapi import APIRouter, Header

from app_helpers import get_current_user
from db import get_db
from schemas import AppointmentCreate
from services import appointments_service


router = APIRouter(tags=["appointments"])


@router.get("/appointments/{user_id}")
def get_appointments(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return appointments_service.get_user_appointments(db, actor, user_id)
    finally:
        db.close()


@router.post("/appointments")
def create_appointment(data: AppointmentCreate, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return appointments_service.create_appointment(db, actor, data)
    finally:
        db.close()


@router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return appointments_service.cancel_appointment(db, actor, appointment_id)
    finally:
        db.close()
