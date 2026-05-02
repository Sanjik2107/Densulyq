from datetime import timedelta
import os


APP_VERSION = "1.2.0"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DB_PATH = "medportal.db"
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_PRISMA_URL")
    or os.getenv("POSTGRES_URL_NON_POOLING")
    or ""
).strip()
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST_PATH = os.path.join(BASE_DIR, "frontend", "dist", "index.html")
FRONTEND_DIST_DIR = os.path.dirname(FRONTEND_DIST_PATH)
FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")
FRONTEND_DEV_PATH = os.path.join(BASE_DIR, "frontend", "index.html")
if os.path.exists(FRONTEND_DIST_PATH):
    FRONTEND_PATH = FRONTEND_DIST_PATH
elif os.path.exists(FRONTEND_DEV_PATH):
    FRONTEND_PATH = FRONTEND_DEV_PATH
else:
    FRONTEND_PATH = ""
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390000
SESSION_TTL_HOURS = max(1, int(os.getenv("SESSION_TTL_HOURS", "24")))
SESSION_TTL = timedelta(hours=SESSION_TTL_HOURS)
BOOKING_DAY_START_HOUR = 9
BOOKING_DAY_END_HOUR = 18
BOOKING_SLOT_MINUTES = 15
BOOKING_DAY_START_MINUTES = BOOKING_DAY_START_HOUR * 60
BOOKING_DAY_END_MINUTES = BOOKING_DAY_END_HOUR * 60
BOOKING_LAST_SLOT_MINUTES = BOOKING_DAY_END_MINUTES - BOOKING_SLOT_MINUTES
ROLE_PERMISSIONS = {
    "admin": [
        ("users:read", "Просмотр всех пользователей"),
        ("users:create", "Создание пользователей"),
        ("users:update", "Изменение ролей и статусов"),
        ("analyses:manage", "Управление лабораторными результатами"),
        ("rbac:read", "Просмотр role-based модели"),
        ("records:read", "Просмотр медицинских записей"),
    ],
    "doctor": [
        ("self:read", "Просмотр собственного профиля"),
        ("self:update", "Редактирование собственного профиля"),
        ("users:read", "Просмотр пациентов"),
        ("analyses:create", "Назначение анализов пациентам"),
        ("analyses:review", "Проверка готовых анализов"),
        ("records:read", "Просмотр медицинских записей пациентов"),
    ],
    "user": [
        ("self:read", "Просмотр собственного профиля"),
        ("self:update", "Редактирование собственного профиля"),
        ("appointments:create", "Создание собственных записей"),
        ("records:read", "Просмотр собственных медицинских записей"),
    ],
}
ANALYSIS_STATUS_ORDERED = "назначен"
ANALYSIS_STATUS_PROCESSING = "в обработке"
ANALYSIS_STATUS_READY = "готово"
ANALYSIS_STATUS_REVIEWED = "проверено"
ANALYSIS_READY_STATUSES = (ANALYSIS_STATUS_READY, ANALYSIS_STATUS_REVIEWED)
ANALYSIS_ADMIN_EDITABLE_STATUSES = (
    ANALYSIS_STATUS_ORDERED,
    ANALYSIS_STATUS_PROCESSING,
    ANALYSIS_STATUS_READY,
)
DEMO_CREDENTIALS = {
    "patient-demo": "patient123",
    "admin-demo": "admin123",
    "doctor-demo": "doctor123",
}
