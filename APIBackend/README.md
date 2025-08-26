# BugFlow APIBackend (FastAPI)

FastAPI backend for the BugFlow application. Exposes REST APIs and integrates with Supabase for authentication.

## Quick start

1) Create your environment file
- Copy .env.example to .env and set values:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY
  - FRONTEND_ORIGIN (optional; defaults to "*")
  - SITE_URL (optional; used for signup email redirect)

2) Install dependencies
- pip install -r requirements.txt

3) Start the server
- Option A (recommended local): python run.py
- Option B: uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload
  Ensure your working directory is this APIBackend folder so the 'src' package is importable.

OpenAPI docs: /docs

## Endpoints
- GET / — Health check
- POST /signup — User signup via Supabase
- POST /login — User login via Supabase

## Notes
- The application starts without Supabase variables present, but authentication endpoints will return HTTP 500 if SUPABASE_URL or SUPABASE_ANON_KEY are missing. This is by design to allow the service to boot and serve health checks in all environments.
- If you run from a different CWD, imports are hardened in src/api/main.py, and run.py also adds the correct path to avoid ModuleNotFoundError.

## Supabase setup (optional features)
See ../../assets/supabase.md for database schema and project configuration tips.
