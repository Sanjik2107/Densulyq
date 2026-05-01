# Densulyq

Lightweight medical portal prototype for patient care workflows and role-based clinical access.

## Features

- Authentication for `user`, `doctor`, and `admin` roles
- Patient profile and role-aware data access
- Doctor dashboard with assigned-patient scope checks
- Appointment booking with 15-minute slot validation
- Analysis lifecycle (`assigned -> processing -> ready -> reviewed`)
- Session-based auth with token persistence and logout-all
- AI chat and health score endpoints with fallback when `GEMINI_API_KEY` is not configured

## Technology Stack

- Backend: Python 3.10+, FastAPI, Uvicorn, SQLite, Pydantic, HTTPX
- Frontend: React + Vite

## Project Structure

```text
Densulyq/
├── src/main.py          # FastAPI entrypoint
├── routers/             # API routers
├── services/            # Business logic
├── frontend/            # React app (Vite)
├── tests/               # Backend tests
├── config.py            # Runtime config (DB, frontend path, auth settings)
├── db.py                # DB initialization and helpers
├── requirements.txt     # Python dependencies
└── README.md
```

## Installation

1. (Optional) Create and activate a virtual environment.
2. Install backend dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. Set your Gemini API key (optional):
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Run (Recommended)

1. Build frontend:
   ```bash
   cd frontend && npm run build && cd ..
   ```
2. Start backend:
   ```bash
   python3 src/main.py
   ```
3. Open:
   - App: `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`

`/` serves `frontend/dist/index.html` if it exists, otherwise falls back to `frontend/index.html`.

## Demo Accounts

- `patient-demo / patient123`
- `doctor-demo / doctor123`
- `admin-demo / admin123`

## Notes

- Local DB file is `medportal.db`.
- This is an educational prototype and should be hardened before production use.
