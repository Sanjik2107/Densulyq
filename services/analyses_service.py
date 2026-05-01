from datetime import datetime
import json

from fastapi import HTTPException

from app_helpers import (
    get_analysis_or_404,
    normalize_analysis_status,
    normalize_calendar_date,
    normalize_optional_string,
    parse_pagination,
    parse_analysis_results,
    require_permission,
    require_user_scope,
    sanitize_analysis_results,
    serialize_analysis_row,
    validate_name,
)
from config import ANALYSIS_READY_STATUSES, ANALYSIS_STATUS_ORDERED, ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED
from schemas import AnalysisLabUpdate, AnalysisOrderCreate, AnalysisReviewUpdate

ALLOWED_ANALYSIS_TRANSITIONS = {
    "назначен": {"назначен", "в обработке"},
    "в обработке": {"в обработке", "готово"},
    "готово": {"готово", "проверено"},
    "проверено": {"проверено"},
}


def get_user_analyses(db, actor, user_id: int):
    require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    rows = db.execute(
        """
        SELECT *
        FROM analyses
        WHERE user_id=?
        ORDER BY COALESCE(ready_at, scheduled_for, date, ordered_at, created_at) DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    result = []
    is_self_patient = actor["role"] == "user" and actor["id"] == user_id
    for row in rows:
        data = serialize_analysis_row(row, actor_role=actor["role"], is_self_patient=is_self_patient)
        if data is not None:
            result.append(data)
    return result


def doctor_create_analysis(db, actor, user_id: int, data: AnalysisOrderCreate):
    if actor["role"] != "doctor":
        raise HTTPException(status_code=403, detail="Назначать анализы может только doctor")
    require_permission(db, actor, "analyses:create")
    _, patient = require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    if patient["role"] != "user":
        raise HTTPException(status_code=400, detail="Анализы можно назначать только пациенту")
    analysis_name = validate_name(data.name)
    scheduled_for = normalize_calendar_date(data.scheduled_for) if data.scheduled_for else None
    if scheduled_for and scheduled_for < datetime.now().date().isoformat():
        raise HTTPException(status_code=400, detail="Нельзя назначить анализ на прошедшую дату")
    ordered_at = datetime.now().date().isoformat()
    display_date = scheduled_for or ordered_at
    db.execute(
        """
        INSERT INTO analyses (
            user_id, doctor_user_id, name, date, doctor, status, results,
            ordered_at, scheduled_for, doctor_note, is_visible_to_patient
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            patient["id"],
            actor["id"],
            analysis_name,
            display_date,
            actor["name"],
            ANALYSIS_STATUS_ORDERED,
            json.dumps([], ensure_ascii=False),
            ordered_at,
            scheduled_for,
            normalize_optional_string(data.doctor_note),
            1 if data.is_visible_to_patient is not False else 0,
        ),
    )
    db.commit()
    created = get_analysis_or_404(db, db.execute("SELECT last_insert_rowid()").fetchone()[0])
    return {"status": "created", "analysis": serialize_analysis_row(created)}


def doctor_review(db, actor, analysis_id: int, data: AnalysisReviewUpdate):
    if actor["role"] != "doctor":
        raise HTTPException(status_code=403, detail="Проверять анализы может только doctor")
    require_permission(db, actor, "analyses:review")
    analysis = get_analysis_or_404(db, analysis_id)
    if analysis["doctor_user_id"] and analysis["doctor_user_id"] != actor["id"]:
        raise HTTPException(status_code=403, detail="Этот анализ назначен другим доктором")
    require_user_scope(db, actor, analysis["user_id"], cross_user_permission="users:read")
    if analysis["status"] == ANALYSIS_STATUS_REVIEWED:
        raise HTTPException(status_code=400, detail="Анализ уже проверен доктором")
    if analysis["status"] not in ANALYSIS_READY_STATUSES:
        raise HTTPException(status_code=400, detail="Доктор может проверять только готовый анализ")
    reviewed_at = datetime.now().date().isoformat()
    db.execute(
        """
        UPDATE analyses
        SET doctor_note=?, reviewed_at=?, status=?, is_visible_to_patient=1
        WHERE id=?
        """,
        (
            normalize_optional_string(data.doctor_note),
            reviewed_at,
            ANALYSIS_STATUS_REVIEWED,
            analysis_id,
        ),
    )
    db.commit()
    updated = get_analysis_or_404(db, analysis_id)
    return {"status": "reviewed", "analysis": serialize_analysis_row(updated)}


def list_admin_analyses(db, actor, *, limit: int = 50, offset: int = 0):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Очередь анализов доступна только администратору")
    require_permission(db, actor, "analyses:manage")
    limit, offset = parse_pagination(limit, offset)
    rows = db.execute(
        """
        SELECT
            analyses.*,
            users.name AS patient_name,
            users.username AS patient_username
        FROM analyses
        JOIN users ON users.id = analyses.user_id
        ORDER BY
            CASE analyses.status
                WHEN 'назначен' THEN 0
                WHEN 'в обработке' THEN 1
                WHEN 'готово' THEN 2
                ELSE 3
            END,
            COALESCE(analyses.ready_at, analyses.scheduled_for, analyses.date, analyses.ordered_at, analyses.created_at) DESC,
            analyses.id DESC
        LIMIT ? OFFSET ?
        """
        ,
        (limit, offset),
    ).fetchall()
    analyses = []
    for row in rows:
        analysis = serialize_analysis_row(row)
        analysis["patient_name"] = row["patient_name"]
        analysis["patient_username"] = row["patient_username"]
        analyses.append(analysis)
    return {"analyses": analyses, "limit": limit, "offset": offset}


def update_admin_analysis(db, actor, analysis_id: int, data: AnalysisLabUpdate):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Обновлять анализы может только администратор")
    require_permission(db, actor, "analyses:manage")
    analysis = get_analysis_or_404(db, analysis_id)
    status = normalize_analysis_status(data.status)
    current_status = analysis["status"]
    allowed_statuses = ALLOWED_ANALYSIS_TRANSITIONS.get(current_status, {current_status})
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Недопустимый переход статуса анализа")
    existing_results = parse_analysis_results(analysis["results"])
    incoming_results = sanitize_analysis_results(data.results) if data.results is not None else existing_results
    updates = {
        "status": status,
        "lab_note": normalize_optional_string(data.lab_note),
        "is_visible_to_patient": 1 if data.is_visible_to_patient is not False else 0,
    }
    if data.results is not None:
        updates["results"] = json.dumps(incoming_results, ensure_ascii=False)
    if status == ANALYSIS_STATUS_READY:
        if not incoming_results:
            raise HTTPException(status_code=400, detail="Для готового анализа нужно заполнить результаты")
        ready_at = normalize_calendar_date(data.ready_at) if data.ready_at else datetime.now().date().isoformat()
        updates["ready_at"] = ready_at
        updates["date"] = ready_at
        updates["is_visible_to_patient"] = 1
    else:
        updates["ready_at"] = None
    set_clause = ", ".join(f"{column}=?" for column in updates)
    db.execute(f"UPDATE analyses SET {set_clause} WHERE id=?", (*updates.values(), analysis_id))
    db.commit()
    updated = get_analysis_or_404(db, analysis_id)
    return {"status": "updated", "analysis": serialize_analysis_row(updated)}
