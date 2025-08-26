# Supabase Integration for APIBackend

This backend integrates with Supabase Auth using direct HTTP calls (no heavy SDK). Required env vars:

- SUPABASE_URL: e.g., https://your-project-id.supabase.co
- SUPABASE_ANON_KEY: Project anon public key
- SITE_URL: Public frontend URL for email confirmation redirect

Endpoints used:
- POST {SUPABASE_URL}/auth/v1/signup
- POST {SUPABASE_URL}/auth/v1/token?grant_type=password

Headers:
- apikey: SUPABASE_ANON_KEY
- Authorization: Bearer SUPABASE_ANON_KEY
- Content-Type: application/json

Signup payload includes email/password and forwards emailRedirectTo using SITE_URL (or the request-provided redirect_to).
