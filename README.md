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

- Backend: Python 3.10+, FastAPI, Uvicorn, PostgreSQL/SQLite, Pydantic, HTTPX
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
4. Configure environment variables:
   ```bash
   # Production/Vercel PostgreSQL. Use the URL from your Postgres provider.
   export DATABASE_URL="postgresql://user:password@host:5432/database?sslmode=require"

   # Optional AI integration.
   export GEMINI_API_KEY="your_api_key_here"
   ```

If `DATABASE_URL` is not set, the backend uses local SQLite at `medportal.db`.
For Vercel Postgres/Neon/Supabase, set `DATABASE_URL` or `POSTGRES_URL` in the Vercel project environment.

## Run (Recommended)

### Docker, one command

```bash
docker compose up --build
```

Then open:

- App: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

Docker Compose starts:

- `app`: FastAPI backend with the built React frontend
- `postgres`: PostgreSQL 16 with a persistent `postgres_data` volume

### Local Python/Node

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

## Database

- Production data should live in PostgreSQL via `DATABASE_URL`/`POSTGRES_URL`.
- Tables and indexes are created idempotently on startup with `CREATE TABLE IF NOT EXISTS`.
- Demo accounts are seeded only when missing; existing application data is not wiped on deploy.
- Local fallback DB file is `medportal.db` and is ignored by git.
- This is an educational prototype and should be hardened before production use.

Full architecture and module documentation: [`PROJECT.md`](PROJECT.md).
