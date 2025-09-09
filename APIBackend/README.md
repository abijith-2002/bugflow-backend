# APIBackend

FastAPI backend for BugFlow.

Environment loading
- The application automatically loads environment variables from APIBackend/.env on startup using python-dotenv.
- Default .env path: bugflow-backend/APIBackend/.env
- To override, set ENV_PATH before starting the server:
  ENV_PATH=/custom/path/.env uvicorn src.api.main:app --reload

Required environment variables
- SUPABASE_URL
- SUPABASE_ANON_KEY
Optional (for JWT validation of bearer tokens used by protected endpoints):
- JWT_SECRET_KEY (secret used to verify tokens)
- JWT_ALGORITHM (e.g., HS256)

Quick start
- Copy .env.example to .env in this directory and set SUPABASE_URL and SUPABASE_ANON_KEY.
- Start the server (example): uvicorn src.api.main:app --reload
- See SUPABASE_SETUP.md for Supabase dashboard configuration and SQL scripts to run.

Database/Auth SDK
- This backend uses the official supabase-py client for:
  - Authentication (signup/login)
  - Database CRUD (projects, work_items)

Notes
- See SUPABASE_SETUP.md for dashboard configuration.
- See AUTH_USAGE.md for endpoint usage and troubleshooting tips.
- User profile endpoints:
  - GET /users/me: fetch current user's display_name from public.profiles (via Authorization Bearer token)
  - POST /users/me: accepts {"user_id": "<uuid>"} and returns [{"display_name":"<name or Anonymous>"}] like a direct SQL select would
- See PROJECTS_USAGE.md for projects table and endpoints (/projects GET, POST).
