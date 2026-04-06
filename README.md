# Densulyq

Densulyq is a lightweight medical portal prototype built with FastAPI and SQLite.  
It includes patient profile management, lab results, appointments, referrals, and AI-assisted health interactions through Gemini.

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- SQLite
- Pydantic
- HTTPX

## Features

- Patient profile retrieval and updates
- Lab analyses storage and structured result parsing
- Appointment creation and listing
- Referral tracking
- AI chat endpoint with patient context enrichment
- AI-based health score endpoint
- Built-in demo data for local testing

## Project Structure

- `main.py` - FastAPI app, database initialization, routes, and AI integration
- `index1.html` - simple frontend served from `/`
- `medportal.db` - local SQLite database
- `requirements.txt` - Python dependencies

## Getting Started

1. Clone the repository and move into the project directory.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set your Gemini API key:

```bash
export GEMINI_API_KEY="your_api_key_here"
```

5. Start the server:

```bash
python main.py
```

The API will be available at:

- `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

## Main API Endpoints

- `GET /health` - service health check
- `GET /user/{user_id}` - fetch user profile
- `PUT /user/{user_id}` - update profile fields
- `GET /analyses/{user_id}` - list analyses
- `GET /appointments/{user_id}` - list appointments
- `POST /appointments` - create appointment
- `GET /referrals/{user_id}` - list referrals
- `POST /ai/chat` - AI chat assistant
- `GET /ai/health-score/{user_id}` - AI-generated health score and recommendations

## Notes

- On startup, the app initializes the database schema and seeds demo records if they are missing.
- CORS is currently open for all origins (`*`) to simplify local development.
- This repository is a prototype and should be hardened before production use.
