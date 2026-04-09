
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
import httpx
import os
from datetime import datetime

app = FastAPI(title="Densaulyq API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC8UGrZUIlAyTtaNe_o5IKly6pd8n0I7ok")
DB_PATH = "medportal.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(BASE_DIR, "index1.html")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        iin TEXT UNIQUE,
        dob TEXT,
        blood_type TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        height REAL,
        weight REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        date TEXT,
        doctor TEXT,
        status TEXT DEFAULT 'в обработке',
        results TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        doctor TEXT,
        speciality TEXT,
        date TEXT,
        time TEXT,
        place TEXT,
        reason TEXT,
        status TEXT DEFAULT 'ожидание',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        from_doctor TEXT,
        issue_date TEXT,
        deadline TEXT,
        status TEXT DEFAULT 'активно',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        message TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    c.execute("SELECT id FROM users WHERE id=1")
    if not c.fetchone():
        c.execute("""INSERT INTO users (id, name, iin, dob, blood_type, phone, email, address, height, weight)
                     VALUES (1, 'Алибек Джаксыбеков', '900315300123', '15.03.1990', 'II+',
                             '+7 700 123 45 67', 'alibek@email.com',
                             'г. Алматы, ул. Абая 14, кв. 22', 178, 82)""")

        analyses_data = [
            (1, 'Общий анализ крови', '12.03.2025', 'Иванова Н.С.', 'готово',
             json.dumps([
                {"param": "Гемоглобин", "val": 145, "unit": "г/л", "norm": "120–160", "ok": True},
                {"param": "Лейкоциты", "val": 9.1, "unit": "×10⁹/л", "norm": "4.0–9.0", "ok": False},
                {"param": "Тромбоциты", "val": 210, "unit": "×10⁹/л", "norm": "150–400", "ok": True},
             ])),
            (1, 'Биохимия крови', '12.03.2025', 'Иванова Н.С.', 'готово',
             json.dumps([
                {"param": "Глюкоза", "val": 5.2, "unit": "ммоль/л", "norm": "3.9–6.1", "ok": True},
                {"param": "Холестерин общий", "val": 5.8, "unit": "ммоль/л", "norm": "< 5.2", "ok": False},
                {"param": "АЛТ", "val": 28, "unit": "Ед/л", "norm": "< 40", "ok": True},
             ])),
        ]
        c.executemany("""INSERT INTO analyses (user_id, name, date, doctor, status, results)
                         VALUES (?,?,?,?,?,?)""", analyses_data)

        apts = [
            (1, 'Смирнов Д.А.', 'Кардиолог', '18.04.2025', '09:30', 'Кабинет 215', 'Плановый осмотр', 'подтверждено'),
            (1, 'Иванова Н.С.', 'Терапевт', '25.04.2025', '14:00', 'Кабинет 105', 'Контроль давления', 'подтверждено'),
        ]
        c.executemany("""INSERT INTO appointments (user_id, doctor, speciality, date, time, place, reason, status)
                         VALUES (?,?,?,?,?,?,?,?)""", apts)

        refs = [
            (1, 'Общий анализ крови', 'Иванова Н.С.', '10.04.2025', '30.04.2025', 'активно'),
            (1, 'УЗИ брюшной полости', 'Карпова В.М.', '05.04.2025', '05.05.2025', 'активно'),
        ]
        c.executemany("""INSERT INTO referrals (user_id, name, from_doctor, issue_date, deadline, status)
                         VALUES (?,?,?,?,?,?)""", refs)

    conn.commit()
    conn.close()

class AppointmentCreate(BaseModel):
    user_id: int = 1
    doctor: str
    date: str
    time: str
    reason: Optional[str] = ""

class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = ""
    user_id: int = 1

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None

@app.get("/")
def root():
    if os.path.exists(FRONTEND_PATH):
        return FileResponse(FRONTEND_PATH)
    return {"status": "ok", "app": "Densaulyq API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/user/{user_id}")
def get_user(user_id: int = 1):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return dict(user)

@app.put("/user/{user_id}")
def update_user(user_id: int, data: ProfileUpdate):
    db = get_db()
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    set_clause = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE users SET {set_clause} WHERE id=?", (*fields.values(), user_id))
    db.commit()
    db.close()
    return {"status": "updated"}

@app.get("/analyses/{user_id}")
def get_analyses(user_id: int = 1):
    db = get_db()
    rows = db.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY date DESC", (user_id,)).fetchall()
    db.close()
    result = []
    for row in rows:
        d = dict(row)
        d['results'] = json.loads(d['results']) if d['results'] else []
        result.append(d)
    return result

@app.get("/appointments/{user_id}")
def get_appointments(user_id: int = 1):
    db = get_db()
    rows = db.execute("SELECT * FROM appointments WHERE user_id=? ORDER BY date", (user_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.post("/appointments")
def create_appointment(data: AppointmentCreate):
    db = get_db()
    db.execute("""INSERT INTO appointments (user_id, doctor, speciality, date, time, reason, status)
                  VALUES (?, ?, ?, ?, ?, ?, 'ожидание')""",
               (data.user_id, data.doctor, data.doctor, data.date, data.time, data.reason))
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return {"id": new_id, "status": "created"}

@app.get("/referrals/{user_id}")
def get_referrals(user_id: int = 1):
    db = get_db()
    rows = db.execute("SELECT * FROM referrals WHERE user_id=?", (user_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.post("/ai/chat")
async def ai_chat(data: ChatRequest):
    """Proxy для Gemini API — используется если ключ на бэкенде"""
    db = get_db()
    
    db.execute("INSERT INTO chat_history (user_id, role, message) VALUES (?,?,?)",
               (data.user_id, 'user', data.message))
    db.commit()

    system_prompt = data.context or """Ты — медицинский ИИ-ассистент. Отвечай кратко и по-дружески на русском языке."""

    user_row = db.execute(
        "SELECT name, dob, height, weight, blood_type FROM users WHERE id=?",
        (data.user_id,),
    ).fetchone()
    analyses_rows = db.execute(
        "SELECT name, date, status, results FROM analyses WHERE user_id=? ORDER BY date DESC LIMIT 10",
        (data.user_id,),
    ).fetchall()

    patient_context = ""
    if user_row:
        u = dict(user_row)
        patient_context += (
            f"Пациент: {u.get('name', 'Неизвестно')}, ДР: {u.get('dob', '-')}, "
            f"рост: {u.get('height', '-')}, вес: {u.get('weight', '-')}, "
            f"группа крови: {u.get('blood_type', '-')}\n"
        )

    analyses_context_lines = []
    all_results = []
    for row in analyses_rows:
        a = dict(row)
        line = f"- {a.get('name', 'Анализ')} ({a.get('date', '-')}) [{a.get('status', '-')}]"
        results = []
        if a.get("results"):
            try:
                results = json.loads(a["results"])
            except Exception:
                results = []
        if results:
            formatted = []
            for r in results:
                all_results.append(r)
                param = r.get("param", "показатель")
                val = r.get("val", "-")
                unit = r.get("unit", "")
                norm = r.get("norm", "-")
                marker = "норма" if r.get("ok") else "вне нормы"
                formatted.append(f"{param}={val}{unit} (норма: {norm}, {marker})")
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

    message_lower = data.message.lower()
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
            reply = (
                "I could not find your analyses in the database yet. "
                "Please upload or add at least one completed test result."
            )
        else:
            abnormal = [r for r in all_results if not r.get("ok")]
            top_items = []
            for r in abnormal[:5]:
                top_items.append(
                    f"- {r.get('param', 'Marker')}: {r.get('val', '-')}{r.get('unit', '')} "
                    f"(reference: {r.get('norm', '-')})"
                )

            if abnormal:
                overview = (
                    f"I analyzed your latest results. Found {len(abnormal)} parameter(s) outside "
                    f"the reference range."
                )
                recommendations = (
                    "Recommendations:\n"
                    "- Discuss these deviations with your therapist.\n"
                    "- Repeat key tests in 2-4 weeks if symptoms persist.\n"
                    "- Keep hydration, sleep, and nutrition consistent before retesting."
                )
                details = "Abnormal values:\n" + "\n".join(top_items)
                reply = f"{overview}\n\n{details}\n\n{recommendations}"
            else:
                reply = (
                    "I analyzed your latest results. All listed parameters are within the "
                    "reference ranges. Continue routine monitoring and preventive checkups."
                )

        db.execute(
            "INSERT INTO chat_history (user_id, role, message) VALUES (?,?,?)",
            (data.user_id, "ai", reply),
        )
        db.commit()
        db.close()
        return {"reply": reply}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{
                        "parts": [{"text": f"{enriched_prompt}\n\nВопрос: {data.message}"}]
                    }]
                }
            )
            result = response.json()
            reply = result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        reply = f"Ошибка подключения к ИИ: {str(e)}. Проверьте GEMINI_API_KEY."

    db.execute("INSERT INTO chat_history (user_id, role, message) VALUES (?,?,?)",
               (data.user_id, 'ai', reply))
    db.commit()
    db.close()

    return {"reply": reply}

@app.get("/ai/health-score/{user_id}")
async def ai_health_score(user_id: int = 1):
    """ИИ анализирует анализы и выдаёт общий показатель здоровья с рекомендациями"""
    db = get_db()
    user = dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    analyses_rows = db.execute("SELECT * FROM analyses WHERE user_id=? AND status='готово'", (user_id,)).fetchall()
    db.close()

    analyses_text = ""
    for row in analyses_rows:
        d = dict(row)
        results = json.loads(d['results']) if d['results'] else []
        bad = [r for r in results if not r.get('ok')]
        analyses_text += f"\n{d['name']} ({d['date']}): "
        if bad:
            analyses_text += f"Отклонения: {', '.join(r['param'] + '=' + str(r['val']) + r['unit'] for r in bad)}"
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

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip().strip("```json").strip("```").strip()
            return json.loads(text)
    except Exception as e:
        return {"score": 74, "status": "Хорошо", "recommendations": ["Снизить холестерин через диету", "Контроль АД"], "doctors": ["Кардиолог"], "error": str(e)}


@app.on_event("startup")
def on_startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    init_db()
    print("✅ БД инициализирована")
    print("🚀 Запуск сервера на http://localhost:8000")
    print("📖 Документация API: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
