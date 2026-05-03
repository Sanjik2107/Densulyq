 Densaulyq - README

## 1. Project Title

**Densulyq** — lightweight medical portal prototype for patient care workflows and role-based clinical access.

## 2. Topic Area

Healthcare / medical informatics — coordination of patients, clinicians, and administration in a single web system (appointments, referrals, lab analyses, role-based access).

## 3. Problem Statement

- Clinical and administrative tasks are often scattered across calls, paper, and ad hoc messages, which slows care and increases errors.
- Patients lack a single place to view their care path, book visits, and understand lab status without unnecessary back-and-forth.
- Doctors and lab admins need controlled visibility: who may see which record, and a clear workflow from order to reviewed result.
- A small unified portal reduces friction for education and pilot deployments where full hospital IT is unavailable.

## 4. Proposed Solution

A **single full-stack web application**: React (Vite) frontend and FastAPI backend with **session-based authentication**, **RBAC** (`user`, `doctor`, `admin`), **appointment booking** with slot rules, **analysis lifecycle** (ordered → processing → ready → reviewed), optional **AI assistant** (Google Gemini with safe fallback if no API key). Data is stored in **PostgreSQL** in production (e.g. Render + managed Postgres); **SQLite** is optional for local development without Docker.

## 5. Target Users

- **Patients (`user`)** — profile, appointments, referrals, visible analyses, AI chat (informational).
- **Doctors (`doctor`)** — dashboard for assigned patients, ordering and reviewing analyses, booking within scope.
- **Administrators (`admin`)** — user/role management, lab workflow updates, RBAC visibility.

## 6. Technology Stack

| Layer | Technologies |
|--------|----------------|
| **Frontend** | React 19, Vite, React Router, ESLint |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic, HTTPX |
| **Database** | PostgreSQL (production / Docker); SQLite fallback locally |
| **Cloud / Hosting** | Render (Docker web service + PostgreSQL); optional Docker Compose locally |
| **APIs / Integrations** | Google Generative Language API (Gemini 2.0 Flash) — optional via `GEMINI_API_KEY` |
| **Other tools** | Alembic (migrations), Playwright (e2e), `unittest` (backend tests), Docker |

## 7. Key Features

- Role-based authentication and permissions (`user` / `doctor` / `admin`) with session tokens and logout-all.
- Patient profile and **role-aware** data access (doctors see assigned patients only; patients see own records).
- **Doctor dashboard** with assigned-patient checks; **appointment booking** with working hours and 15-minute slot validation.
- **Analysis lifecycle** aligned with lab workflow: ordered → processing → ready → doctor-reviewed; admin can progress lab states.
- **AI chat** and health-score style endpoint with **fallback** when `GEMINI_API_KEY` is not set.

## 8. Team Members (with Email IDs)



| Name | Role | id |
|------|------|--------|
| Sanjar Yermuratov| Backend | 230103195 |
| Sanzhar Nabi |Frontend |220103075 |
| Aibar Barlykov | Backend| 230103147 |

**Student IDs:** 230103195, 220103075, 230103147

## 9. Expected Outcome

Deliverable: a **working web prototype** — deployable full-stack app (browser UI + REST API + database), with demo accounts, documented run instructions, and automated checks (unit + e2e). Suitable as an **educational / pilot** system; not a certified medical device.

**Public demo (when live):** `https://densulyq.onrender.com`  
*(Free tier may sleep after inactivity; first load after sleep can take ~30–60 seconds.)*

## 10. Git Repo Link (GitHub/GitLab)

**URL:** https://github.com/Sanjik2107/Densulyq  

---

## Appendix — Development & grading helpers

### Project layout

```text
Densulyq/
├── src/main.py          # FastAPI entrypoint
├── routers/             # API routers
├── services/            # Business logic
├── alembic/             # PostgreSQL migrations
├── frontend/            # React app (Vite)
├── tests/               # Backend tests
├── config.py, db.py, schemas.py, security.py, app_helpers.py
├── requirements.txt
├── Dockerfile, docker-compose.yml
└── PROJECT.md           # Deeper module / flow notes
```

### Demo accounts

- `patient-demo` / `patient123`
- `doctor-demo` / `doctor123`
- `admin-demo` / `admin123`

### Local setup

1. Backend: `python3 -m pip install -r requirements.txt`
2. Frontend: `cd frontend && npm install`
3. Env: `cp .env.example .env`. Leave `DATABASE_URL` empty to use local SQLite at `medportal.db`, or set it for Postgres. Add `GEMINI_API_KEY` only locally or in hosting secrets.
4. Optional Vite dev env: `cp frontend/.env.example frontend/.env.local` and set `VITE_API_BASE_URL=http://127.0.0.1:8000` when running frontend/backend separately.

### Run

**Docker:** `docker compose up --build` → http://localhost:8000  

**Local:** `cd frontend && npm run build && cd ..` then `python3 src/main.py` → http://localhost:8000  

API docs: http://localhost:8000/docs

### Quality checks

```bash
python3 -m unittest discover -s tests
python3 -m py_compile db.py config.py app_helpers.py security.py schemas.py src/main.py routers/*.py services/*.py alembic/env.py alembic/versions/*.py
cd frontend && npm run lint && npm run build && npm run e2e
```

More architecture detail: [`PROJECT.md`](PROJECT.md).
