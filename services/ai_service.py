import json

import httpx
from fastapi import HTTPException

from app_helpers import get_user_or_404, parse_analysis_results, require_user_scope, serialize_user
from config import ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED, GEMINI_API_KEY
from schemas import ChatRequest


async def chat(db, actor, data: ChatRequest):
    message = data.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Введите сообщение")
    user_id = data.user_id or actor["id"]
    require_user_scope(db, actor, user_id, cross_user_permission="users:read")

    db.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, "user", message),
    )
    db.commit()

    system_prompt = data.context or "Ты — медицинский ИИ-ассистент. Отвечай кратко и по-дружески на русском языке."
    user_row = db.execute(
        "SELECT name, dob, height, weight, blood_type FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    analyses_rows = db.execute(
        """
        SELECT name, date, status, results
        FROM analyses
        WHERE user_id=? AND status IN (?, ?)
        ORDER BY COALESCE(ready_at, date, ordered_at, CAST(created_at AS TEXT)) DESC
        LIMIT 10
        """,
        (user_id, ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED),
    ).fetchall()

    patient_context = ""
    if user_row:
        patient = dict(user_row)
        patient_context += (
            f"Пациент: {patient.get('name', 'Неизвестно')}, ДР: {patient.get('dob', '-')}, "
            f"рост: {patient.get('height', '-')}, вес: {patient.get('weight', '-')}, "
            f"группа крови: {patient.get('blood_type', '-')}\n"
        )

    analyses_context_lines = []
    all_results = []
    for row in analyses_rows:
        analysis = dict(row)
        line = f"- {analysis.get('name', 'Анализ')} ({analysis.get('date', '-')}) [{analysis.get('status', '-')}]"
        results = []
        if analysis.get("results"):
            try:
                results = json.loads(analysis["results"])
            except Exception:
                results = []
        if results:
            formatted = []
            for result in results:
                all_results.append(result)
                param = result.get("param", "показатель")
                value = result.get("val", "-")
                unit = result.get("unit", "")
                norm = result.get("norm", "-")
                marker = "норма" if result.get("ok") else "вне нормы"
                formatted.append(f"{param}={value}{unit} (норма: {norm}, {marker})")
            line += ": " + "; ".join(formatted)
        analyses_context_lines.append(line)

    analyses_context = "Анализы:\n" + ("\n".join(analyses_context_lines) if analyses_context_lines else "нет данных")
    enriched_prompt = (
        f"{system_prompt}\n\n"
        "Ниже медицинский контекст пациента из БД. "
        "Используй его по умолчанию в ответе, если вопрос связан с анализами/здоровьем.\n"
        f"{patient_context}{analyses_context}\n\n"
        "Если данных недостаточно, задай только 1-2 уточняющих вопроса."
    )

    message_lower = message.lower()
    direct_analysis_triggers = [
        "analyze my test results",
        "analyse my test results",
        "analyze my analyses",
        "analyze my labs",
        "анализ моих",
        "проанализируй мои анализы",
        "анализируй мои анализы",
    ]

    if any(trigger in message_lower for trigger in direct_analysis_triggers):
        if not analyses_rows:
            reply = "I could not find your analyses in the database yet. Please upload or add at least one completed test result."
        else:
            abnormal = [result for result in all_results if not result.get("ok")]
            top_items = []
            for result in abnormal[:5]:
                top_items.append(
                    f"- {result.get('param', 'Marker')}: {result.get('val', '-')}{result.get('unit', '')} "
                    f"(reference: {result.get('norm', '-')})"
                )
            if abnormal:
                overview = f"I analyzed your latest results. Found {len(abnormal)} parameter(s) outside the reference range."
                recommendations = (
                    "Recommendations:\n"
                    "- Discuss these deviations with your therapist.\n"
                    "- Repeat key tests in 2-4 weeks if symptoms persist.\n"
                    "- Keep hydration, sleep, and nutrition consistent before retesting."
                )
                details = "Abnormal values:\n" + "\n".join(top_items)
                reply = f"{overview}\n\n{details}\n\n{recommendations}"
            else:
                reply = "I analyzed your latest results. All listed parameters are within the reference ranges. Continue routine monitoring and preventive checkups."

        db.execute(
            "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, "ai", reply),
        )
        db.commit()
        return {"reply": reply}

    if not GEMINI_API_KEY:
        reply = "GEMINI_API_KEY не настроен. AI-ответы недоступны, но доступен локальный анализ результатов."
    else:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": f"{enriched_prompt}\n\nВопрос: {message}"}]}]},
                )
                result = response.json()
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as error:
            reply = f"Ошибка подключения к ИИ: {str(error)}. Проверьте GEMINI_API_KEY."

    db.execute(
        "INSERT INTO chat_history (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, "ai", reply),
    )
    db.commit()
    return {"reply": reply}


async def health_score(db, actor, user_id: int):
    require_user_scope(db, actor, user_id, cross_user_permission="users:read")
    user = serialize_user(get_user_or_404(db, user_id))
    analyses_rows = db.execute(
        "SELECT * FROM analyses WHERE user_id=? AND status IN (?, ?)",
        (user_id, ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED),
    ).fetchall()

    analyses_text = ""
    total_results = 0
    abnormal_results = 0
    for row in analyses_rows:
        analysis = dict(row)
        results = parse_analysis_results(analysis.get("results"))
        bad_results = [result for result in results if not result.get("ok")]
        total_results += len(results)
        abnormal_results += len(bad_results)
        analyses_text += f"\n{analysis['name']} ({analysis['date']}): "
        if bad_results:
            analyses_text += "Отклонения: " + ", ".join(
                result["param"] + "=" + str(result["val"]) + result["unit"] for result in bad_results
            )
        else:
            analyses_text += "Все в норме"

    prompt = f"""Пациент: {user['name']}, {user['dob']}, рост {user['height']}см, вес {user['weight']}кг

Анализы:{analyses_text}

Задачи:
1. Оцени общее здоровье по шкале 0-100
2. Дай 3-4 конкретные рекомендации
3. Укажи к каким врачам стоит обратиться

Отвечай в JSON формате:
{{"score": число, "status": "строка", "recommendations": ["...", "..."], "doctors": ["..."]}}"""

    if not GEMINI_API_KEY:
        penalty = round((abnormal_results / total_results) * 35) if total_results else 8
        score = max(45, min(92, 90 - penalty))
        status = "Хорошо" if score >= 75 else "Нужно внимание"
        recommendations = [
            "Обсудите отклонения с терапевтом, если они сохраняются или есть симптомы",
            "Повторите ключевые анализы по назначению врача",
            "Следите за сном, питанием, питьевым режимом и давлением",
        ]
        if not abnormal_results:
            recommendations = ["Продолжайте профилактические осмотры", "Поддерживайте стабильный режим сна и физической активности"]
        return {
            "score": score,
            "status": status,
            "recommendations": recommendations,
            "doctors": ["Терапевт"],
            "error": "GEMINI_API_KEY is not configured",
        }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip().strip("```json").strip("```").strip()
            return json.loads(text)
    except Exception as error:
        return {
            "score": 74,
            "status": "Хорошо",
            "recommendations": ["Снизить холестерин через диету", "Контроль АД"],
            "doctors": ["Кардиолог"],
            "error": str(error),
        }
