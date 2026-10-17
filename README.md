# Sabuj Pran Business Management Platform

Sabuj Pran is a modular-monolith ERP-lite for a small manufacturing and trading business. It
combines purchasing, inventory, production, sales, money management, assets, employees, and
administration in one FastAPI API and Next.js web application backed by MySQL.

## Project status

Phases 0–12 are implemented, including authentication and administration, master data, parties,
inventory, purchasing, money workflows, sales, production, assets, attendance, payroll, approvals,
and reporting. Phase 13 hardening is in progress: the full business-cycle E2E test, reusable
demo-data seed, report-query index review, and JWT signing-key hardening are complete; delivery
documentation remains.

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

## Deployment Guideline

This guide deploys the application locally or to a trusted development/test host with Docker
Compose. The repository's Compose configuration runs the Next.js development server and starts
Uvicorn with auto-reload; it is **not a production-hardened deployment configuration**. Before
internet-facing or production use, use production application servers, TLS through a reverse proxy,
private secret management, restricted network access, and a tested database backup/restore process.

### 1. Requirements

- Git and Docker Desktop (or Docker Engine) with the Docker Compose plugin.
- Ports `3000`, `8000`, and `3306` available for the web app, API, and MySQL respectively.
- For local frontend development without Docker: Node.js 20 and npm.

### 2. Get the application and configure the environment

From the repository root, copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` before starting the API. At minimum:

- Replace `SECRET_KEY` with a unique random value of at least 32 characters. Generate one with:

  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

  Keep the value private and stable for this installation. Changing it invalidates existing login
  sessions. The API refuses to start when it is missing, a known placeholder, or too short.
- Set unique `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` values. Set `DATABASE_URL` to use the same
  database username/password and database name as `MYSQL_USER`, `MYSQL_PASSWORD`, and
  `MYSQL_DATABASE`; the Compose default URL uses the Compose service hostname `db`.
- Set `NEXT_PUBLIC_API_URL` to the API URL reachable by the user's browser and set
  `FRONTEND_ORIGIN` to the exact web app origin (scheme, host, and port), for example
  `http://localhost:3000`. They must reflect the URLs used by your deployment.
- Configure `SMTP_HOST`, `SMTP_FROM_EMAIL`, and any required SMTP credentials if users need
  password-reset email. The default is STARTTLS on port 587. For implicit TLS, set
  `SMTP_USE_TLS=false` and `SMTP_USE_SSL=true`.
- Review company defaults such as `COMPANY_NAME`, `CURRENCY_CODE`, `TIMEZONE`,
  `CREDIT_LIMIT_MODE`, and `RECEIPT_TOLERANCE_PCT`.

Do not commit `.env` or use the example database credentials for a shared or production
installation. If a database password contains URL-reserved characters, percent-encode it in
`DATABASE_URL`. Compose initializes MySQL users and the database only when its data volume is
first created; changing the MySQL variables later does not update an existing database account.

### 3. Start MySQL and initialize the schema

Start the database and wait until its health check passes:

```powershell
docker compose up -d db
docker compose ps
```

Build the API image and apply all Alembic migrations to the configured database:

```powershell
docker compose build api
docker compose run --rm --no-deps api alembic upgrade head
```

Migrations create and update the schema; they do not create the initial administrator or demo
records. Run these seed commands from the repository root:

```powershell
docker compose run --rm --no-deps api python -c "import app.main; from app.modules.auth.seed import main; main()"
docker compose run --rm --no-deps api python -m app.modules.company_settings.seed
```

The auth seed creates the `admin` user, an active Administrator role, and the current permission
catalog. Its generated password is Argon2-hashed and printed only when the account is first
created; store it securely. Re-running the command does not reset an existing password. Re-run it
after application upgrades to synchronize newly introduced permissions.

Company settings are seeded from `.env.example`'s `COMPANY_*`, `CURRENCY_CODE`, `TIMEZONE`,
`INVOICE_FOOTER`, `CREDIT_LIMIT_MODE`, and `RECEIPT_TOLERANCE_PCT` values. Existing values are
preserved. Use the seed command's `--overwrite` option only when intentionally replacing saved
settings with environment defaults.

For a development or demo installation only, seed sample master data and current-year document
sequences:

```powershell
docker compose run --rm --no-deps api python -c "import app.main; from app.demo_seed import main; main()"
```

This command is idempotent and does not post purchases, sales, expenses, or stock/money ledger
transactions. Skip it for production data.

### 4. Start and verify the application

Start all services:

```powershell
docker compose up --build -d
docker compose ps
```

Open the sign-in page at <http://localhost:3000/login>. Confirm the API is responding at
<http://localhost:8000/health>; it should return HTTP 200 and `{"status":"ok",...}`. Use the
one-time password printed by the first admin seed. Change it after the first sign-in and add a
valid email to the administrator profile before relying on password recovery.

To inspect service startup errors:

```powershell
docker compose logs --tail 100 api
docker compose logs --tail 100 web
docker compose logs --tail 100 db
```

### 5. Data persistence, upgrades, and operations

- MySQL data is stored in the Compose-managed `mysql_data` volume. Uploaded company logos and
  favicons are stored in `backend/media`, which is mounted into the API container.
- Back up the database volume/data and `backend/media` according to your retention policy, and
  periodically test restoring those backups. A container rebuild does not replace the MySQL volume.
- To deploy an application update, build the new API image, apply migrations, then rebuild/restart
  services:

  ```powershell
  docker compose build api
  docker compose run --rm --no-deps api alembic upgrade head
  docker compose up --build -d
  ```

- Never edit an applied migration or change the database manually. Review the release's migrations
  and back up the database before applying schema changes.
- `docker compose down` stops and removes containers but preserves the named database volume.
  `docker compose down -v` removes the volume and permanently deletes its database contents; only
  use it when you deliberately intend to destroy the local database.
- The Compose file publishes MySQL on port 3306 and uses development servers. Do not expose these
  settings directly to the public internet. A production deployment must restrict database access,
  use TLS, production server commands, secure environment-secret storage, and a separately reviewed
  production deployment configuration.

Uploaded logo and favicon images persist through the Compose media mount. The default brand artwork
remains available when no custom file is uploaded. Logo uploads accept PNG, JPEG, or WebP (up to
2 MB); favicon uploads accept PNG, WebP, or ICO (up to 512 KB).

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
