# Authentication API Usage

Base URL: /auth

## Sign Up
POST /auth/signup
Content-Type: application/json

Body:
{
  "email": "user@example.com",
  "password": "password123"
}

Response 201:
{
  "message": "User registration initiated",
  "user_id": "uuid-or-null",
  "needs_verification": true
}

## Login
POST /auth/login
Content-Type: application/json

Body:
{
  "email": "user@example.com",
  "password": "password123"
}

Response 200:
{
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "refresh",
  "user_id": "uuid"
}

Environment variables required (see .env.example):
- SUPABASE_URL
- SUPABASE_ANON_KEY

Troubleshooting:
- 500 Configuration error: Ensure the two env vars above are set in APIBackend/.env.
- 4xx errors on signup/login: These come from Supabase (e.g., password too weak, email taken, or auth URL config). The response body contains details.
