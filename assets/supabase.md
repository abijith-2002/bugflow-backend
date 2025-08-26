# Supabase Integration for BugFlow API (FastAPI)

This backend uses Supabase for authentication (email/password).

Required environment variables (configure in `.env`):
- SUPABASE_URL: The project URL (e.g., https://your-project.supabase.co)
- SUPABASE_ANON_KEY: The anon public key from the Supabase project
- SITE_URL: The frontend/site public URL for email verification redirects (e.g., http://localhost:5173)
- FRONTEND_ORIGIN: The origin allowed by CORS (e.g., http://localhost:5173)

Endpoints:
- POST /auth/signup
  - Body: { "email": string, "password": string, "redirect_to"?: string }
  - Creates a user via Supabase. If email confirmations are enabled, the `access_token` will be null and `requires_verification` will be true.
- POST /auth/login
  - Body: { "email": string, "password": string }
  - Returns access token and user_id on success.

Notes:
- The signup endpoint passes `email_redirect_to` to Supabase using `SITE_URL` when provided.
- Frontend should store the token (e.g., in memory or secure storage) and include it in subsequent API requests if required by protected routes (to be added in future tasks).
- To regenerate OpenAPI spec, run the OpenAPI generator script (e.g., via Python) which writes to `interfaces/openapi.json`.
