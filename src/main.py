import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import APP_VERSION, CORS_ORIGINS, FRONTEND_ASSETS_DIR, FRONTEND_DIST_DIR, FRONTEND_PATH
from db import init_db
from routers.admin import router as admin_router
from routers.ai import router as ai_router
from routers.analyses import router as analyses_router
from routers.appointments import router as appointments_router
from routers.auth import router as auth_router
from routers.users import router as users_router


app = FastAPI(title="Densaulyq API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cookie_auth_and_csrf(request: Request, call_next):
    original_headers = dict(request.scope.get("headers") or [])
    has_authorization = b"authorization" in original_headers
    session_token = request.cookies.get("session_token")
    if session_token and not has_authorization:
        request.scope["headers"].append((b"authorization", f"Bearer {session_token}".encode("latin-1")))
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            public_paths = {
                "/auth/login",
                "/auth/register",
                "/auth/2fa/verify",
                "/auth/password-reset/request",
                "/auth/password-reset/confirm",
            }
            if request.url.path not in public_paths:
                csrf_header = request.headers.get("x-csrf-token", "")
                from db import get_db

                db = get_db()
                try:
                    row = db.execute(
                        "SELECT csrf_token FROM auth_sessions WHERE token=?",
                        (session_token,),
                    ).fetchone()
                finally:
                    db.close()
                if not row or not csrf_header or csrf_header != row["csrf_token"]:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF token is missing or invalid"},
                    )
    return await call_next(request)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(analyses_router)
app.include_router(appointments_router)
app.include_router(admin_router)
app.include_router(ai_router)

if os.path.isdir(FRONTEND_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="frontend-assets")


@app.get("/")
def root():
    if os.path.exists(FRONTEND_PATH):
        return FileResponse(FRONTEND_PATH)
    return {"status": "ok", "app": "Densaulyq API", "version": APP_VERSION}


@app.get("/favicon.svg")
def favicon():
    favicon_path = os.path.join(FRONTEND_DIST_DIR, "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="favicon not found")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    init_db()


if __name__ == "__main__":
    import uvicorn

    print("🔐 Demo patient login: patient-demo / patient123")
    print("🔐 Demo doctor login: doctor-demo / doctor123")
    print("🔐 Demo admin login: admin-demo / admin123")
    print("🚀 Запуск сервера на http://localhost:8000")
    print("📖 Документация API: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
