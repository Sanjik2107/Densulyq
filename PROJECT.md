# Densaulyq Project Documentation

## Overview

Densaulyq is a medical portal prototype with three role-based workspaces:

- Patient portal: profile, appointments, referrals, analyses, AI chat.
- Doctor dashboard: assigned patients, analysis ordering, analysis review.
- Admin panel: users, roles, lab analysis workflow, RBAC model.

The project is a single FastAPI backend that can also serve the built React frontend. In production-like runs, data is stored in PostgreSQL. For simple local development without env configuration, the backend falls back to a local SQLite file.

## Technology Stack

- Backend: Python, FastAPI, Uvicorn, Pydantic, HTTPX, Alembic.
- Database: PostgreSQL in Docker/production, SQLite as local fallback.
- PostgreSQL driver: `psycopg`.
- Frontend: React, Vite.
- Tests: Python `unittest`, frontend lint/build checks, Playwright e2e.
- Container runtime: Docker and Docker Compose.

## One-Command Run

```bash
docker compose up --build
```

This starts:

- `postgres`: PostgreSQL 16 with persistent Docker volume `postgres_data`.
- `app`: FastAPI app on `http://localhost:8000`.

The app container applies Alembic migrations before Uvicorn starts. The backend then runs idempotent compatibility checks and seeds demo accounts only when they are missing. Existing data is not wiped.

## Demo Accounts

- Patient: `patient-demo / patient123`
- Doctor: `doctor-demo / doctor123`
- Admin: `admin-demo / admin123`

## Runtime Configuration

Important environment variables:

- `DATABASE_URL`: PostgreSQL connection string. If omitted, SQLite `medportal.db` is used.
- `POSTGRES_URL`, `POSTGRES_PRISMA_URL`, `POSTGRES_URL_NON_POOLING`: accepted alternatives for hosted providers.
- `CORS_ORIGINS`: comma-separated allowed origins, defaults to `*`.
- `SESSION_TTL_HOURS`: auth session lifetime, defaults to `24`.
- `GEMINI_API_KEY`: optional key for AI responses. Without it, local fallback responses still work.
- `VITE_API_BASE_URL`: optional frontend build-time API URL. If omitted, frontend uses same-origin API.

## Backend Structure

- `src/main.py`: FastAPI app, middleware, router registration, health endpoint, frontend serving.
- `config.py`: environment configuration, app constants, frontend paths, role permissions.
- `db.py`: database connection layer, seed data, idempotent compatibility checks, PostgreSQL/SQLite helpers.
- `alembic/`: formal PostgreSQL migration history.
- `schemas.py`: Pydantic request models.
- `security.py`: password hashing and verification.
- `app_helpers.py`: shared validation, auth/session helpers, permission checks, serializers, date/time normalization.
- `routers/`: HTTP endpoints grouped by domain.
- `services/`: business logic grouped by domain.
- `tests/`: backend unit tests for auth, permissions, appointments, and analysis workflows.

## Backend Logic

Authentication:

- Login uses `username/password`.
- Passwords are stored as PBKDF2 hashes.
- Successful login creates an `auth_sessions` token.
- Protected endpoints read `Authorization: Bearer <token>`.
- Expired sessions are removed when used.

Roles and permissions:

- `admin`: manages users, roles, lab analysis workflow, RBAC view.
- `doctor`: reads assigned patients, orders analyses, reviews ready analyses.
- `user`: manages own profile, books own appointments, reads own records.
- Role permissions are stored in `role_permissions` and seeded idempotently.

Appointments:

- Patients book appointments with active doctors.
- Slots are validated by working hours and 15-minute interval rules.
- A doctor cannot have two active appointments at the same date/time.
- Cancelled appointments stop occupying the slot.

Analyses:

- Doctor creates an ordered analysis for an assigned patient.
- Admin/lab progresses status through `назначен -> в обработке -> готово`.
- Doctor reviews ready analyses and moves them to `проверено`.
- Patients see only visible analyses, and detailed results are hidden until ready/reviewed.

AI:

- Chat stores user and AI messages in `chat_history`.
- If `GEMINI_API_KEY` is missing, the app returns a clear fallback.
- Health score has a local fallback response.

## Database Tables

- `users`: patient, doctor, and admin accounts.
- `role_permissions`: role-to-permission mapping.
- `auth_sessions`: bearer-token sessions.
- `appointments`: appointment records and slot status.
- `analyses`: lab orders/results/review workflow.
- `referrals`: patient referrals.
- `chat_history`: AI chat messages.

PostgreSQL schema includes primary keys, foreign keys, indexes, and a unique active-slot index for doctor appointments.

## Frontend Structure

- `frontend/src/main.jsx`: React entrypoint.
- `frontend/src/App.jsx`: authenticated app shell and initial data loading.
- `frontend/src/pages/Login.jsx`: login and patient registration screen.
- `frontend/src/pages/Pages.jsx`: compatibility re-export for portal pages.
- `frontend/src/pages/portal/`: split patient, doctor, admin, profile, analyses, appointments, referrals, and AI views.
- `frontend/src/api.js`: fetch wrapper with auth token and 401 handling.
- `frontend/src/utils.jsx`: mapping, formatting, translations, frontend constants.
- `frontend/src/context/AuthContext.jsx`: auth state, login/register/logout, session restore.
- `frontend/src/context/ToastContext.jsx`: user notifications.
- `frontend/e2e/`: Playwright browser scenarios for patient booking, doctor patient selection, and admin analysis editing.

## Deployment Notes

For Docker deployment, use `docker compose up --build`.

For hosted deployment:

1. Create a PostgreSQL database with a persistent connection URL.
2. Set `DATABASE_URL` or provider-specific Postgres env variable.
3. Build the frontend with `npm run build`.
4. Run `python -m alembic upgrade head`.
5. Run the backend with `uvicorn src.main:app`.

The backend serves `frontend/dist/index.html` and `/assets/*` when the build exists.

## Quality Checks

Useful commands:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile db.py config.py app_helpers.py security.py schemas.py src/main.py routers/*.py services/*.py alembic/env.py alembic/versions/*.py
cd frontend && npm run lint && npm run build && npm run e2e
docker compose up -d --build
```

## Current Design Decisions

- SQLite remains only as a local fallback, not as production storage.
- Alembic is the formal PostgreSQL schema path.
- Idempotent startup compatibility checks remain as a safety net for local demos and older databases.
