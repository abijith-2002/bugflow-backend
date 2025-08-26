# APIBackend Supabase Setup

Follow these steps to run the backend with Supabase Auth:

1) Configure environment
   - Copy .env.example to .env
   - Set SUPABASE_URL, SUPABASE_ANON_KEY, SITE_URL

2) Configure Supabase Authentication
   - In Supabase Dashboard > Authentication > URL Configuration:
     * Site URL: your frontend URL (e.g., http://localhost:3000/)
     * Add Redirect URLs: http://localhost:3000/** and your production domain /**
   - Optionally update Email Templates.

3) (Optional) Create profiles table and RLS policies
   - Create a `profiles` table keyed by user_id (references auth.users(id))
   - Enable RLS with row-level policies so each user can read/write only their own row.

4) Endpoints
   - POST /auth/signup
   - POST /auth/login

5) Notes
   - Backend uses httpx to call Supabase Auth, no client SDK needed.
   - Do not use REACT_APP_* vars in the backend.
   - The backend no longer accepts a redirect_to field on signup; configure redirect behavior in Supabase (Site URL and Redirect URLs). SITE_URL remains required for general configuration.

Troubleshooting
- If POST /auth/signup returns a 500 with "Configuration error: Missing required environment variables...", ensure APIBackend/.env is present and contains values for:
  SUPABASE_URL, SUPABASE_ANON_KEY, SITE_URL.
- If signup/login returns a 4xx with a JSON/text body, that is a direct Supabase error (e.g., weak password, email already registered, URL config). Review the response body and adjust inputs/settings accordingly.
