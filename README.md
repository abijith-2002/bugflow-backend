# BugFlow Backend (FastAPI) + Supabase

This backend uses Supabase Auth (email/password) for signup and login.

Quick start:
1. Copy `.env.example` to `.env` and set:
   - SUPABASE_URL
   - SUPABASE_ANON_KEY
   - FRONTEND_ORIGIN (http://localhost:3000)
   - SITE_URL (http://localhost:3000/)
2. Ensure Supabase SQL is applied (see assets/supabase.md).
3. Install deps and run:
   - pip install -r APIBackend/requirements.txt
   - uvicorn src.api.main:app --host 0.0.0.0 --port 3001

Endpoints:
- GET / (health)
- POST /auth/signup
- POST /auth/login

Note: Automated SupabaseTools could not run due to missing RPC public.run_sql. Apply the SQL in assets/supabase.md via Supabase SQL editor.