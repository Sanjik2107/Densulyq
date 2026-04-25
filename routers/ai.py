from typing import Optional

from fastapi import APIRouter, Header

from app_helpers import get_current_user
from db import get_db
from schemas import ChatRequest
from services import ai_service


router = APIRouter(tags=["ai"])


@router.post("/ai/chat")
async def ai_chat(data: ChatRequest, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return await ai_service.chat(db, actor, data)
    finally:
        db.close()


@router.get("/ai/health-score/{user_id}")
async def ai_health_score(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return await ai_service.health_score(db, actor, user_id)
    finally:
        db.close()
