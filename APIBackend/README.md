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
- New endpoint: GET /users/me to fetch current user's display_name from public.profiles.
- See PROJECTS_USAGE.md for projects table and endpoints (/projects GET, POST).
