# ForesightX-auth

Production-oriented authentication microservice for the ForesightX platform, built with FastAPI, PostgreSQL, Redis, JWT, and Google OAuth.

## Features

- Email/password registration and login
- JWT access tokens and rotating refresh tokens
- Redis-backed refresh session storage and token blacklist
- Google OAuth login with Authlib
- PostgreSQL user persistence with SQLAlchemy async ORM
- Alembic migrations for schema management
- Async integration with `ForesightX-profile`
- CORS support, structured logging, and role-ready user model

## Project Structure

```text
ForesightX-auth/
├── app/
│   ├── main.py
│   ├── core/
│   ├── db/
│   ├── schemas/
│   ├── api/
│   └── services/
├── alembic/
├── alembic.ini
├── requirements.txt
├── .env.example
├── docker-compose.yml
└── Dockerfile
```

## Environment

This service is independently configured from `ForesightX-auth/.env`.

Copy `.env.example` to `.env` and set real values:

```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/foresightx_auth
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8004/oauth/google/callback
PROFILE_SERVICE_URL=http://localhost:8002
PROFILE_CREATE_PATH=/profiles
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
LOG_LEVEL=INFO
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run database migrations:

```bash
alembic upgrade head
```

4. Start Redis locally, or use Docker Compose:

```bash
docker compose up redis -d
```

5. Start the service:

```bash
uvicorn app.main:app --reload --port 8004
```

## Docker

Run the service and Redis:

```bash
docker compose up --build
```

Neon/Postgres remains external. Point `DATABASE_URL` to the auth service's dedicated Neon database.

## API Endpoints

### Auth

- `POST /auth/sign-up`
- `POST /auth/sign-in`
- `POST /auth/token/refresh`
- `POST /auth/sign-out`
- `GET /auth/me`

### OAuth

- `GET /oauth/google/authorize`
- `GET /oauth/google/callback`

### Health

- `GET /health`

Interactive OpenAPI docs are available at `/docs`.

## Profile Service Integration

After a successful registration or first-time Google OAuth login, the service attempts to create a profile record by calling:

```http
POST {PROFILE_SERVICE_URL}{PROFILE_CREATE_PATH}
Content-Type: application/json

{
  "user_id": "<uuid>",
  "email": "user@example.com"
}
```

Failures are retried and logged, but they do not roll back auth user creation.

## Security Notes

- Passwords are hashed with bcrypt via Passlib.
- Access tokens expire in 15 minutes by default.
- Refresh tokens expire in 7 days by default.
- Refresh rotation invalidates the previous refresh token on use.
- Redis stores refresh sessions and revoked token JTIs.
- `is_verified` is present for email-verification flows; email delivery is intentionally left as a placeholder.

## Google OAuth Setup

1. Create OAuth credentials in Google Cloud.
2. Add `http://localhost:8004/oauth/google/callback` as an authorized redirect URI.
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and optionally `GOOGLE_REDIRECT_URI`.

## Notes

- The auth service expects the profile service to expose `POST /profiles` by default.
- If your profile service uses a different route, change `PROFILE_CREATE_PATH`.
