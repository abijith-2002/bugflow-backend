# BugFlow Backend (APIBackend)

FastAPI backend for the BugFlow application. This service exposes REST APIs and integrates with Supabase for authentication.

## Endpoints
- GET / — Health check
- POST /signup — User signup via Supabase
- POST /login — User login via Supabase

## Environment Variables
Copy `.env.example` to `.env` and set values:
- SUPABASE_URL
- SUPABASE_ANON_KEY
- FRONTEND_ORIGIN (optional; defaults to "*")
- SITE_URL (optional; used for signup email redirect)

## Run locally
1. Create and fill .env
2. Install dependencies: `pip install -r APIBackend/requirements.txt`
3. Start server (from APIBackend root):
   `uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload`

OpenAPI docs: `/docs`