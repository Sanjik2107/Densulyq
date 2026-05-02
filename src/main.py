import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
