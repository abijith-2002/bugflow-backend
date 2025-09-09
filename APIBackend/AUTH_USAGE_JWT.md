# JWT Authentication for Protected Endpoints

This backend enforces Bearer JWT authentication on protected endpoints using PyJWT.

Environment variables (set in APIBackend/.env):
- JWT_SECRET_KEY: Secret key used to verify tokens
- JWT_ALGORITHM: Algorithm used to sign/verify tokens (e.g., HS256)

How it works:
- The dependency src/api/security.py provides:
  - get_current_user: decodes and validates the Bearer token and returns a CurrentUser model.
  - require_auth: enforces authentication without returning the user object.

Protected endpoints:
- Projects
  - POST /projects (create) -> requires auth
  - DELETE /projects/{id} -> requires auth
- Work Items
  - POST /work-items -> requires auth
  - PATCH /work-items/{project_id}/{id} -> requires auth
  - PATCH /work-items/{project_id}/{id}/status -> requires auth
  - DELETE /work-items/{project_id}/{id} -> requires auth
- Comments
  - POST /work-items/{project_id}/{id}/comments -> requires auth
- User Profile
  - GET /users/me
    - If user_id query param is provided: no auth required (direct lookup mode)
    - If user_id is omitted: requires auth to resolve current user

Client usage:
- Include Authorization header: Authorization: Bearer <your_jwt_token>
- Swagger UI now shows the HTTP Bearer security scheme. Use the "Authorize" button to set your token.

Notes:
- The token is validated using PyJWT with the configured secret (JWT_SECRET_KEY) and algorithm (JWT_ALGORITHM).
- The subject is read from "sub" claim by default; fallbacks: "user_id", "uid", or "id".
