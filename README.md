# Densulyq

Lightweight medical portal prototype for patient care workflows and role-based clinical access.

## Problem Statement

Many small healthcare teams need a simple internal portal to manage patient records, appointments, analyses, and staff access without setting up a complex enterprise system.  
This project demonstrates a compact, local-first solution using FastAPI + SQLite, including basic RBAC and AI-assisted health interactions.

## Features

- Unified authentication flow for `user`, `doctor`, and `admin` roles
- Patient profile management and role-aware access control
- Doctor dashboard with assigned-patient visibility
- Appointment booking with 15-minute slot validation
- Analysis lifecycle management (`assigned -> processing -> ready -> reviewed`)
- Referral tracking and patient-doctor workflows
- Session-based authentication with expiration and logout-all
- AI chat and health score endpoints with safe fallback when `GEMINI_API_KEY` is missing

## Technology Stack

- Python 3.10+
- FastAPI
- Uvicorn
- SQLite
- Pydantic
- HTTPX
- HTML/CSS/Vanilla JavaScript frontend

## Project Structure

```text
project-root/
├── src/            # FastAPI backend + frontend page
├── docs/           # Documentation artifacts
├── tests/          # Test suite (placeholder)
├── assets/         # Static assets (icons, images)
├── README.md
├── AUDIT.md
├── requirements.txt
├── .gitignore
└── LICENSE
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Sanjik2107/Densulyq.git
   cd Densulyq
   ```
2. (Optional) Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
4. Set your Gemini API key (optional but recommended for AI features):
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

1. Start the app:
   ```bash
   python3 src/main.py
   ```
2. Open:
   - App: `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`
3. Log in with demo accounts:
   - `patient-demo / patient123`
   - `doctor-demo / doctor123`
   - `admin-demo / admin123`

## Screenshots

- Main UI screenshot can be added under `docs/screenshots/` and referenced here for presentation/readability.
- Current repository includes UI asset files but does not yet include dedicated screenshot captures.

## Notes

- Database file is generated at runtime (`medportal.db`) and should not be version-controlled.
- This is a prototype for educational/demo purposes and should be hardened before production use.
