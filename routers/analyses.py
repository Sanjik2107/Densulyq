from typing import Optional

from fastapi import APIRouter, Header, Query, Response

from app_helpers import get_current_user
from db import get_db
from schemas import AnalysisLabUpdate, AnalysisOrderCreate, AnalysisReviewUpdate
from services import analyses_service


router = APIRouter(tags=["analyses"])


@router.get("/analyses/{user_id}")
def get_analyses(user_id: int, authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.get_user_analyses(db, actor, user_id)
    finally:
        db.close()


@router.post("/doctor/patients/{user_id}/analyses")
def doctor_create_analysis(
    user_id: int,
    data: AnalysisOrderCreate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.doctor_create_analysis(db, actor, user_id, data)
    finally:
        db.close()


@router.put("/doctor/analyses/{analysis_id}/review")
def doctor_review_analysis(
    analysis_id: int,
    data: AnalysisReviewUpdate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.doctor_review(db, actor, analysis_id, data)
    finally:
        db.close()


@router.get("/lab/analyses")
def lab_list_analyses(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str = "",
    status: str = "",
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.list_lab_analyses(db, actor, limit=limit, offset=offset, query=query, status=status)
    finally:
        db.close()


@router.put("/lab/analyses/{analysis_id}")
def lab_update_analysis(
    analysis_id: int,
    data: AnalysisLabUpdate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.update_lab_analysis(db, actor, analysis_id, data)
    finally:
        db.close()


@router.get("/lab/analyses/export")
def lab_export_analyses(authorization: Optional[str] = Header(default=None)):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        csv_text = analyses_service.export_lab_analyses_csv(db, actor)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=densaulyq-analyses.csv"},
        )
    finally:
        db.close()


@router.get("/admin/analyses")
def deprecated_admin_list_analyses(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.list_lab_analyses(db, actor, limit=limit, offset=offset)
    finally:
        db.close()


@router.put("/admin/analyses/{analysis_id}")
def deprecated_admin_update_analysis(
    analysis_id: int,
    data: AnalysisLabUpdate,
    authorization: Optional[str] = Header(default=None),
):
    db = get_db()
    try:
        actor = get_current_user(db, authorization)
        return analyses_service.update_lab_analysis(db, actor, analysis_id, data)
    finally:
        db.close()
