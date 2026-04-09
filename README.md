# Densulyq

Densulyq is a lightweight medical portal prototype built with FastAPI and SQLite.  
It includes patient profile management, doctor-specific patient access, appointment booking, referrals, AI-assisted health interactions through Gemini, and an admin panel with role-based access.

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- SQLite
- Pydantic
- HTTPX

## Features

- Patient profile retrieval and updates
- Patient/doctor/admin role separation with RBAC-style permissions
- Unified login/password authentication with automatic routing by role
- Patient self-registration with automatic login after account creation
- Doctor dashboard for viewing only assigned patients
- Admin panel for creating users and changing roles/statuses
- Doctor-assigned analyses with lab processing and doctor review
- Patient-to-doctor appointment booking with doctor directory lookup and 15-minute slots
- Referral tracking
- AI chat endpoint with patient context enrichment
- AI-based health score endpoint
- Session-token authentication with session expiry and logout-all support
- Built-in demo data for local testing

## Project Structure

- `main.py` - FastAPI app, database initialization, auth/RBAC helpers, routes, and AI integration
- `index1.html` - frontend served from `/`, with unified login, patient portal, doctor dashboard, and admin panel
- `medportal.db` - local SQLite database
- `requirements.txt` - Python dependencies

## Getting Started

1. Clone the repository and move into the project directory.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

4. Set your Gemini API key:

```bash
export GEMINI_API_KEY="your_api_key_here"
```

5. Start the server:

```bash
python3 main.py
```

The API will be available at:

- `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

## Authentication Flow

- Open `http://localhost:8000`
- Log in with one common `username/password` form
- For patients: you can either register a new account or log in with existing credentials
- For doctors and admins: accounts are created by an administrator, then they log in through the same form
- Users with role `user` are routed to the patient portal
- Users with role `doctor` are routed to the doctor dashboard
- Users with role `admin` are routed to the admin panel

## Main API Endpoints

- `GET /health` - service health check
- `POST /auth/login` - login with `username` and `password`, portal is inferred from role
- `POST /auth/register` - create a new patient account and open a patient session
- `GET /auth/me` - fetch current authenticated user session
- `POST /auth/logout` - close current session
- `POST /auth/logout-all` - close all sessions for the current account
- `GET /doctors` - list active doctor accounts for patient booking
- `GET /doctors/{doctor_id}/availability?date=YYYY-MM-DD` - list free 15-minute slots for a doctor
- `GET /user/{user_id}` - fetch user profile for the authenticated user, an assigned doctor, or admin
- `PUT /user/{user_id}` - update profile fields for the authenticated user or admin
- `GET /analyses/{user_id}` - list analyses for the authenticated user, assigned doctor, or admin
- `POST /doctor/patients/{user_id}/analyses` - doctor assigns a new analysis to an assigned patient
- `GET /admin/analyses` - admin queue of all analyses across patients
- `PUT /admin/analyses/{analysis_id}` - admin updates lab status, notes, and results
- `PUT /doctor/analyses/{analysis_id}/review` - doctor adds clinical review to a ready analysis
- `GET /appointments/{user_id}` - list appointments for the authenticated user, assigned doctor, or admin
- `POST /appointments` - create an appointment between a patient and a selected doctor
- `GET /referrals/{user_id}` - list referrals for the authenticated user, assigned doctor, or admin
- `GET /doctor/patients` - doctor sees only assigned patients; admin sees all patients
- `GET /admin/users` - admin-only user list with counts
- `POST /admin/users` - admin-only user creation
- `PUT /admin/users/{user_id}` - admin-only role/status/password update
- `GET /rbac/model` - admin-only RBAC model view
- `POST /ai/chat` - AI chat assistant
- `GET /ai/health-score/{user_id}` - AI-generated health score and recommendations

## Demo Accounts

- `patient-demo / patient123` - seeded standard user with medical records
- `doctor-demo / doctor123` - seeded doctor account for the doctor dashboard
- `admin-demo / admin123` - seeded administrator for the admin panel

## Notes

- On startup, the app initializes the database schema, creates auth session storage, seeds RBAC permissions, and creates demo patient/doctor/admin records when needed.
- CORS is currently open for all origins (`*`) to simplify local development.
- Authentication is session-token based; the browser stores the current session locally after successful login.
- Sessions expire automatically after `SESSION_TTL_HOURS` (default: 24 hours of inactivity).
- Appointment booking is limited to daily slots from `09:00` to `18:00` in 15-minute increments; past slots and occupied slots are rejected.
- Analysis lifecycle: `assigned -> processing -> ready -> reviewed`.
- AI endpoints use only ready/reviewed analyses as medical context.
- If `GEMINI_API_KEY` is not configured, AI endpoints fall back to a limited local response instead of crashing.
- This repository is a prototype and should be hardened before production use.
