# Sabuj Pran Business Management Platform

This repository is the foundation for the Sabuj Pran modular monolith described in the product blueprint.

## Included foundation

- Monorepo structure and Docker Compose development setup
- FastAPI backend with Alembic and a health endpoint
- Next.js frontend with TypeScript, Tailwind CSS, and shared UI primitives
- Ruff, Mypy, Pytest, Vitest, and CI checks
- Phase 1 authentication, role-based permissions, audit logging, and administration screens
- Phase 2 Units and hierarchical product-category master-data modules

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + MySQL 8
- Frontend: Next.js + TypeScript + Tailwind CSS + shadcn-style UI primitives
- Tooling: Ruff, Mypy, Pytest, Vitest, GitHub Actions

## Quick start

1. Copy `.env.example` to `.env`.
2. Replace the example `SECRET_KEY` with a private random value.
3. Start infrastructure: `docker compose up --build`
4. API: http://localhost:8000/health
5. Web: http://localhost:3000/login

## Initial administrator seed

Start the database, apply migrations, and seed the initial administrator:

```powershell
docker compose up -d db
docker compose run --build --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m app.modules.auth.seed
docker compose run --rm --no-deps api python -m app.modules.company_settings.seed
```

The initial-admin command creates `admin` with a randomly generated Argon2-hashed password and an
Administrator role. The company-settings command seeds defaults for the Company Settings screen,
using the `COMPANY_*`, `CURRENCY_CODE`, `TIMEZONE`, `INVOICE_FOOTER`, `CREDIT_LIMIT_MODE`, and
`RECEIPT_TOLERANCE_PCT` environment variables from `.env.example`. Existing settings are preserved
by default; run the company-settings command with `--overwrite` only when you intend to replace
saved values with environment defaults.
Uploaded logo and favicon images are saved under `backend/media` and persist through the Compose
media mount; the default brand artwork remains available if no custom file is uploaded. The
Company Settings screen previews current assets and provides a **Use default** action. Logo uploads
accept PNG, JPEG, or WebP (up to 2 MB); favicon uploads accept PNG, WebP, or ICO (up to 512 KB).

The admin plaintext password is printed only when the account is first created; save it securely.
Running the command again does not reset an existing password. Sign in at `/login`; the
Administrator role is assigned the seeded auth and master-data permissions, including
`master_data.units.*` and `master_data.product_categories.*`. Run the seed again after upgrading
the database to add newly introduced permissions; this does not change the existing admin password.

## Run the web app locally

Start the API and database using the connection configured in `.env`, then run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

The frontend calls the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Set
`FRONTEND_ORIGIN` to the frontend origin if it differs.

## Password reset email

Set the SMTP values in `.env` before using Forgot Password. `SMTP_HOST` and `SMTP_FROM_EMAIL`
are required; configure `SMTP_USERNAME` and `SMTP_PASSWORD` together when the relay requires
authentication. The default is STARTTLS on port 587. For implicit TLS (commonly port 465), set
`SMTP_USE_TLS=false` and `SMTP_USE_SSL=true`. Reset links expire after 30 minutes by default and
can be used once. The seed-created admin has no email address, so add a valid email to the admin
profile before attempting recovery. Missing SMTP configuration or delivery failure is reported by
the API; reset tokens are never displayed in the Users screen or written to the audit log.

## Phase 1 auth behavior

- Access JWTs are tied to persisted refresh sessions; refresh rotates the session token and logout
  revokes it. Password changes/resets and user deactivation also revoke existing refresh sessions.
- An account locks for 15 minutes after 5 consecutive failed login attempts.
- Password recovery emails a one-time reset link to the registered email address. Tokens are stored
  hashed and expire after 30 minutes.
- Passwords must be at least 8 characters. A stronger minimum length/complexity policy remains an
  open requirement decision.
- User and role deactivation is soft; audit entries are append-only. Role and endpoint access is
  controlled by granular `module.resource.action` permissions.
- The sign-out action is available to roles granted `auth.session.logout`; role managers should
  assign it to every role that needs to sign out through the UI.

## Phase 2 progress

The Units master-data slice is implemented at `/units`. Product categories are managed at
`/categories`, including parent-child hierarchies. Both support create, update, soft-delete, restore,
permission checks, and audit logging. Other Phase 2 master-data modules remain in the project plan
and are not yet implemented.
