# Sabuj Pran Business Management Platform

Sabuj Pran is a modular-monolith ERP-lite for a small manufacturing and trading business. It
combines purchasing, inventory, production, sales, money management, assets, employees, and
administration in one FastAPI API and Next.js web application backed by MySQL.

## Project status

Phases 0–12 are implemented, including authentication and administration, master data, parties,
inventory, purchasing, money workflows, sales, production, assets, attendance, payroll, approvals,
and reporting. Phase 13 hardening is in progress: the full business-cycle E2E test and reusable
demo-data seed are complete; performance, security, and delivery-documentation tasks remain.

See [the phased plan](./knowledge/05_PLAN.md), [the current checklist](./knowledge/06_TODO.md), and
[the implementation guide](./knowledge/10_DEVELOPMENT_GUIDE.md) for details. The business and
engineering requirements in [04_RULES.md](./knowledge/04_RULES.md) govern implementation.

## Included

- FastAPI backend with SQLAlchemy, Alembic, and MySQL 8
- Next.js App Router frontend with TypeScript, Tailwind CSS, and Zod validation
- Role-based permissions, authentication, audit logging, and administration
- Inventory and money ledgers with transactional posting services
- Purchasing, sales, production, assets, employee, attendance, and payroll workflows
- Ruff, Mypy, Pytest, Vitest, TypeScript checks, and CI

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
docker compose run --rm --no-deps api python -m app.demo_seed
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
The demo-data command adds reusable sample parties, products, a BOM, money accounts, an expense
category, and current-year document sequences. It is safe to rerun: existing demo records are
preserved. Demo money accounts have opening balances for payment workflows; the command does not
post purchases, sales, expenses, or other business transactions.

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

## Documentation

- [Project overview](./knowledge/01_PROJECT.md)
- [Product requirements](./knowledge/03_PRD.md)
- [Business and engineering rules](./knowledge/04_RULES.md)
- [Application workflows](./knowledge/08_APP_FLOW.md)
- [Database schema](./knowledge/09_SCHEMA.md)
- [Development guide](./knowledge/10_DEVELOPMENT_GUIDE.md)
