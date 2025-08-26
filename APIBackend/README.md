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
  The app now auto-loads environment variables from APIBackend/.env on import, so uvicorn works the same as run.py.
  Ensure your working directory is this APIBackend folder so the 'src' package is importable.

OpenAPI docs: /docs

## Endpoints
- GET / — Health check
- POST /signup — User signup via Supabase
- POST /login — User login via Supabase

## Diagnostics for environment loading

We added detailed logging to verify .env detection and environment propagation:

- On app startup (import of src.api.main), the service logs:
  - Whether python-dotenv successfully loaded APIBackend/.env and whether the file exists.
  - Current working directory and whether sys.path includes APIBackend.
  - Presence (boolean) of SUPABASE_URL and SUPABASE_ANON_KEY.

- Health endpoint (GET /) now responds with:
  - env_loaded flag and booleans for SUPABASE variables (non-sensitive).

- Auth dependency (get_supabase_client in src/api/auth.py) logs presence of SUPABASE_URL and SUPABASE_ANON_KEY right before building the client. If missing, endpoints return HTTP 500 with a clear message.

You should see log lines like:
```
INFO bugflow.api: Env load attempt: path=/.../APIBackend/.env loaded=True exists=True
INFO bugflow.api: Startup env snapshot: SUPABASE_URL_present=True SUPABASE_ANON_KEY_present=True FRONTEND_ORIGIN=http://localhost:3000
```

## Common causes when SUPABASE_* are not detected

Even with a correct APIBackend/.env file, these contexts can prevent the variables from being present at runtime:

1) Different working directory (CWD) when starting uvicorn
- If uvicorn is started from a parent folder or another container, python-dotenv may not find APIBackend/.env depending on import path.
- Fix: Run from APIBackend root or use run.py (it explicitly loads APIBackend/.env).

2) Process managers or containers ignoring .env files
- Docker/Kubernetes/PM2-like systems do not read repo .env by default. The .env must be injected into the container environment (ENV, env_file, or secrets).
- Fix: For Docker, use:
  - docker run --env-file ./APIBackend/.env ...
  - or in docker-compose.yml → env_file: - ./APIBackend/.env
  For Kubernetes, create a Secret/ConfigMap and mount or export as env.

3) Multi-process reloaders
- When using --reload, the reloader child process may have a different CWD than the launcher.
- Fix: Prefer python run.py for local dev, or set DOTENV_PATH env variable pointing to an absolute path of the .env.

4) Wrong file path or filename
- Ensure the file is exactly at bugflow-backend/APIBackend/.env.
- Health check and startup logs show which path was attempted.

## Robust usage patterns

- Local development (recommended):
  - cd bugflow-backend/APIBackend
  - python run.py

- Alternative with uvicorn:
  - cd bugflow-backend/APIBackend
  - uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload

- Containerized:
  - Ensure variables are provided by the container orchestrator:
    - docker run --env-file bugflow-backend/APIBackend/.env -p 3001:3001 yourimage
    - docker-compose:
      ```
      services:
        api:
          env_file:
            - ./bugflow-backend/APIBackend/.env
      ```

- Force a specific .env path (if needed):
  - Export DOTENV_PATH=/absolute/path/to/bugflow-backend/APIBackend/.env
  - Or set environment variables directly (recommended for production).

## Notes
- The application starts without Supabase variables present, but authentication endpoints will return HTTP 500 if SUPABASE_URL or SUPABASE_ANON_KEY are missing. This is by design to allow the service to boot and serve health checks in all environments.
- If you run from a different CWD, imports are hardened in src/api/main.py, and run.py also adds the correct path to avoid ModuleNotFoundError.

## Supabase setup (optional features)
See ../../assets/supabase.md for database schema and project configuration tips.
