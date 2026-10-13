# Sabuj Pran Project Work Documentation

This document explains what has been built in this repository, how the running application is
assembled, what happens in its current user workflows, and how to run and verify the project. It is
implementation documentation, not a second copy of the business-rule list.

## 1. Project at a glance

Sabuj Pran is a web-based ERP-lite for a small manufacturing and trading business. The intended
product brings purchasing, inventory, production, sales, money, party balances, administration,
and reporting into one auditable application.

The repository is a **modular monolith**: one API application and one web application backed by
MySQL. Business areas are separated into Python modules, but they are deployed together. Modules
are not independent services.

The target business cycle is:

```text
Supplier → Purchase → Inventory → Production → Sales → Customer due
          → Collection → Cash/Bank/MFS → Expenses → Management reports
```

The repository is under active phased development. The foundation and authentication/
administration slice are implemented. The complete purchase-to-dashboard ERP cycle is not yet
implemented; see [Section 10](#10-implementation-status).

## 2. Technology and runtime

| Layer | Current implementation |
|---|---|
| Web | Next.js 14 App Router, React 18, TypeScript, Tailwind CSS |
| Form validation | Zod in the frontend |
| Notifications | SweetAlert2 toast helper |
| API | FastAPI, Pydantic, SQLAlchemy 2 |
| Database | MySQL 8.4, InnoDB, `utf8mb4` |
| Authentication | JWT access tokens, rotating opaque refresh tokens, Argon2 passwords |
| Migrations | Alembic |
| Runtime/dev orchestration | Docker Compose |
| Backend tests and quality | pytest, Ruff, mypy |
| Frontend tests and quality | Vitest, React Testing Library, TypeScript, Next lint |

The web app runs at `http://localhost:3000`, the API at `http://localhost:8000`, and the default
Compose MySQL service listens on port 3306. API health is exposed at `/health`; the API root `/`
is protected.

## 3. Repository layout

```text
.
├── backend/
│   ├── app/
│   │   ├── api/                 # Health endpoint
│   │   ├── core/                # Configuration, DB, security, exceptions, email
│   │   ├── modules/auth/        # Authentication and user/role administration
│   │   ├── modules/units/       # Measurement-unit master-data reference module
│   │   ├── modules/product_categories/ # Hierarchical product categories
│   │   └── main.py              # FastAPI app and router registration
│   ├── alembic/versions/        # Versioned database changes
│   └── tests/                   # Backend service/API/model/mail tests
├── frontend/
│   └── src/
│       ├── app/                 # Routes and page components
│       ├── components/auth/     # Protected shell and user form
│       └── lib/                 # API client, validation, notifications
├── knowledge/                   # Product requirements, schema, flows and plans
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

`backend/app/modules/auth/` contains the auth and administration router, Pydantic schemas,
SQLAlchemy models, service logic, repository queries, audit helper, and initial-admin seed script.
`backend/app/modules/units/` is the first Phase 2 business module and follows the same
router/schema/model/service/repository split. `backend/app/modules/product_categories/` follows
that structure for hierarchical categories. `backend/app/core/` contains shared facilities such as
JWT/session validation, configuration, database access, and SMTP delivery.

The protected app shell uses a permission-filtered, grouped sidebar on desktop and a toggleable
drawer on smaller screens. The top bar shows the current route and signed-in account.

The frontend route tree currently includes:

| Route | Purpose |
|---|---|
| `/login` | Sign in using username, email, or mobile and password |
| `/forgot-password` | Request a reset link using the registered email address |
| `/reset-password` | Set a password using the one-time email link |
| `/` | Protected landing/dashboard foundation |
| `/profile` | View and update the signed-in user's contact details |
| `/change-password` | Change password while signed in |
| `/users` | List, activate, and deactivate user accounts |
| `/users/new` | Create a user and assign roles |
| `/users/[id]` | Edit user details and roles |
| `/roles` | Create/update roles and grant permissions |
| `/permissions` | Read-only permission catalog |
| `/units` | List, create, update, soft-delete, and restore measurement units |
| `/categories` | List, create, update, soft-delete, and restore product categories |

Routes are implemented under `frontend/src/app/`. Protected routes use the shared authentication
shell and permission-aware navigation.

## 4. Backend request and data flow

An HTTP request follows this general path:

```text
Next.js page
  → frontend apiRequest()
  → FastAPI router
  → Pydantic request schema
  → authentication/permission dependency (when required)
  → auth service
  → SQLAlchemy model/query
  → MySQL
```

The router maps HTTP operations and delegates application behavior to each module's `service.py`.
Pydantic schemas validate incoming payloads and document responses. Services own business
workflows, repositories hold reusable queries, and models map persisted data.
The HTTP interface is REST-style: collection reads/creates use `GET`/`POST`, resource updates use
`PATCH`, and soft deletion uses `DELETE`, with JSON request/response bodies. Category activation is
updated through `PATCH` on the category resource; restoration from soft deletion uses its explicit
restore action.

`backend/app/main.py` registers the health, authentication, units, and product-category routers,
configures CORS for `FRONTEND_ORIGIN`, and protects the API root. The auth router is mounted under
`/api/v1/auth`.

## 5. Authentication and account flows

### Sign in and protected requests

1. The login page validates the submitted credentials with Zod and posts them to
   `POST /api/v1/auth/login`.
2. The API verifies the Argon2 password hash. After repeated failures it locks the account for the
   configured duration (current project decision: five failures and 15 minutes).
3. On success, the API creates a persisted refresh session and returns an access token plus
   refresh token.
4. The frontend stores the tokens in the current browser tab's `sessionStorage`.
5. Protected pages request `/api/v1/auth/me`, then display navigation allowed by the profile's
   permissions.
6. If a request receives an expired-session 401, `apiRequest()` rotates the refresh token and
   retries. Concurrent 401 responses share a single refresh operation.

The API validates the access JWT's session ID against an active refresh-session record. Refresh
rotation revokes the old record and creates the next one. Logout revokes the current session.
Password changes/resets and account deactivation revoke sessions as appropriate.

### Password recovery by email

1. The user enters the account's registered email address on `/forgot-password`.
2. `POST /api/v1/auth/forgot-password` looks up an active account by email, case-insensitively.
3. For a matching account, the service invalidates earlier unused reset requests, creates a random
   one-time token, stores only its SHA-256 hash, and sends a link through the configured SMTP
   transport.
4. The link opens `/reset-password?token=...`. The user enters and confirms a new password.
5. `POST /api/v1/auth/reset-password` validates that the token exists, is unused, and has not
   expired. It hashes the new password, marks the token used, clears login lockout, and revokes
   existing sessions.

The API gives the same generic response for existing and unknown email addresses to avoid account
enumeration. It does **not** disclose the reset token in the response, user-management screen, or
audit record. SMTP delivery/configuration failures return an explicit service error. The initial
seeded administrator has no email, so assign the account a valid email from its profile before
using recovery.

For SMTP setup, use the `SMTP_*` keys in `.env`. The host and from-address are required; credentials
are optional only when the relay permits unauthenticated delivery. Port 587 normally uses STARTTLS
(`SMTP_USE_TLS=true`, `SMTP_USE_SSL=false`). Port 465 normally uses implicit SSL
(`SMTP_USE_TLS=false`, `SMTP_USE_SSL=true`). Set the reset-link lifetime with
`PASSWORD_RESET_EXPIRE_MINUTES`; the default is 30 minutes.

### User, role, and permission administration

- Users have unique usernames and optional unique email/mobile values. Administrators can create,
  update, list, activate, and deactivate user records according to their permissions.
- User and role deactivation is soft: it disables access without hard-deleting referenced records.
- Roles receive permissions from the application-owned permission catalog. Users receive access
  through their assigned active roles.
- Protected API operations use permissions named `module.resource.action`. Hiding a UI link is
  only a usability feature; the API independently denies unauthorized requests.
- Mutations write audit records. The audit endpoint is read-only to callers with
  `auth.audit_logs.read`.
- The system prevents removing or deactivating the last administrator access path.

The administrator seed creates the `Administrator` role, initial admin user, and current auth
permission catalog. A newly-created admin password is random and printed once by the seed command;
the seed does not reset an existing account's password.

## 6. Current API surface

The implemented auth API is:

| Method and path | Access/permission | Function |
|---|---|---|
| `POST /api/v1/auth/login` | Public credential flow | Start a session |
| `POST /api/v1/auth/refresh` | Public refresh-token flow | Rotate refresh session |
| `POST /api/v1/auth/logout` | `auth.session.logout` | Revoke current session |
| `POST /api/v1/auth/forgot-password` | Public email flow | Send reset link |
| `POST /api/v1/auth/reset-password` | Public reset-token flow | Consume reset link |
| `GET /api/v1/auth/me` | `auth.profile.read` | Read current profile and permissions |
| `PATCH /api/v1/auth/me` | `auth.profile.update` | Update profile |
| `POST /api/v1/auth/change-password` | `auth.password.change` | Change password |
| `GET /api/v1/auth/users` | `auth.users.read` | List users |
| `POST /api/v1/auth/users` | `auth.users.create` | Create user |
| `GET /api/v1/auth/users/{id}` | `auth.users.read` | Read one user |
| `PATCH /api/v1/auth/users/{id}` | `auth.users.update` | Update user |
| `POST /api/v1/auth/users/{id}/deactivate` | `auth.users.delete` | Deactivate user |
| `POST /api/v1/auth/users/{id}/activate` | `auth.users.update` | Reactivate user |
| `GET /api/v1/auth/roles` | `auth.roles.read` | List roles |
| `POST /api/v1/auth/roles` | `auth.roles.create` | Create role |
| `PATCH /api/v1/auth/roles/{id}` | `auth.roles.update` | Update role and permissions |
| `POST /api/v1/auth/roles/{id}/deactivate` | `auth.roles.delete` | Deactivate role |
| `POST /api/v1/auth/roles/{id}/activate` | `auth.roles.update` | Reactivate role |
| `GET /api/v1/auth/permissions` | `auth.permissions.read` | Read permission catalog |
| `GET /api/v1/auth/audit-logs` | `auth.audit_logs.read` | Read audit records |
| `GET /api/v1/units` | `master_data.units.read` | List active units; `include_inactive=true` includes deleted units |
| `POST /api/v1/units` | `master_data.units.create` | Create a unit |
| `PATCH /api/v1/units/{id}` | `master_data.units.update` | Update a unit |
| `DELETE /api/v1/units/{id}` | `master_data.units.delete` | Soft-delete a unit |
| `POST /api/v1/units/{id}/activate` | `master_data.units.update` | Restore a soft-deleted unit |
| `GET /api/v1/product-categories` | `master_data.product_categories.read` | List categories; `include_inactive=true` includes deleted categories |
| `POST /api/v1/product-categories` | `master_data.product_categories.create` | Create a category with an optional parent and active state |
| `PATCH /api/v1/product-categories/{id}` | `master_data.product_categories.update` | Update a category, parent, or active state |
| `DELETE /api/v1/product-categories/{id}` | `master_data.product_categories.delete` | Soft-delete a category |
| `POST /api/v1/product-categories/{id}/activate` | `master_data.product_categories.update` | Restore a soft-deleted category |

The public health endpoint is `GET /health`. The API root endpoint requires
`auth.profile.read`. Query pagination for user/audit/unit lists currently uses `offset` and
`limit`.

## 7. Database and migrations

Authentication currently persists:

- `users`: login identity, profile, password hash, active state, login-failure count and lock time.
- `roles` and `permissions`: named roles and the permission catalog.
- `user_roles` and `role_permissions`: many-to-many grants.
- `refresh_tokens`: hashed refresh token and session expiry/revocation state.
- `password_resets`: hashed one-time reset token, expiry, and used state.
- `audit_logs`: append-only event details and optional actor.

The first master-data migration adds `units` with its name, unique code, fractional-quantity flag,
active/deleted state, and timestamps. Unit changes are recorded in `audit_logs`; deleted units
remain stored and may be restored. The next migration adds `product_categories`, with an optional
self-referencing parent, active/deleted state, and timestamps. Category services reject missing or
inactive parents and parent changes that would create a cycle. Category create/update/delete/restore
operations write audit records. Active state can be switched with the screen's Active/Inactive
radio controls; deactivation hides a category from the default list without marking it deleted.
Deleting a category is a separate soft-delete action and preserves child references.
Products, price lists, warehouses, and the other Phase 2 setup data have not yet been implemented.

The current migration chain is:

1. `20261012_initial_empty` — initial empty migration.
2. `20261013_auth_models` — core auth/role/permission/session/reset tables.
3. `20261013_auth_audit` — role active flag and audit table.
4. `20261013_remove_reset_perm` — removes the obsolete operator-issued reset
   permission now that recovery is email-based.
5. `20261013_units` — creates the first master-data table.
6. `20261013_categories` — creates hierarchical product categories.

Do not edit a migration after it has been applied to an environment. Add a new Alembic revision for
subsequent schema changes. Offline SQL generation checks migration construction; applying a
migration to the configured database should be an intentional deployment operation.

## 8. Running the project

### Docker Compose

1. Copy `.env.example` to `.env`.
2. Set a private `SECRET_KEY`, database connection values, and SMTP values if password recovery is
   needed.
3. Start services:

   ```powershell
   docker compose up --build
   ```

4. Apply migrations:

   ```powershell
   docker compose run --build --rm --no-deps api alembic upgrade head
   ```

5. Create the initial admin if needed:

   ```powershell
   docker compose run --rm --no-deps api python -m app.modules.auth.seed
   ```

6. Open `http://localhost:3000/login`. API health is at `http://localhost:8000/health`.

Compose has `db`, `api`, and `web` services. The development web service runs `next dev`; the API
uses Uvicorn reload. The local MySQL data persists in the Compose-managed `mysql_data` volume.

### Local frontend

Run the API and database first, then:

```powershell
Set-Location frontend
npm install
npm run dev
```

The browser-facing API URL is controlled by `NEXT_PUBLIC_API_URL`. Configure `FRONTEND_ORIGIN` to
match the browser origin so the API's CORS policy permits requests.

## 9. Checks and tests

Run backend checks from `backend/` using the selected virtual environment:

```powershell
python -m pytest -q
python -m ruff check app tests
python -m mypy app
python -m alembic upgrade head --sql
```

Run frontend checks from `frontend/`:

```powershell
npm run typecheck
npm run test
npm run lint
npm run build
```

Tests use an isolated in-memory SQLite database for auth API behavior; migration SQL generation
uses the configured Alembic URL in offline mode. Neither operation applies schema changes to the
live MySQL database.

The Phase 1 checks previously run for this project passed: backend suite (34 tests), Ruff, mypy,
frontend typecheck/tests/lint/build, and offline migration generation. Subsequent notification and
email-reset UI adjustments also passed frontend typecheck, tests, lint, and production build.

## 10. Implementation status

### Implemented foundation

- Monorepo, Docker Compose services, environment configuration, API health endpoint, frontend
  foundation, migration framework, lint/type/test tooling, and CI.

### Implemented Phase 1 — Authentication and administration

- User, role, permission, refresh-session, password-reset, and audit models.
- Login/logout/refresh, revocable JWT sessions, Argon2 passwords, lockout, and granular permission
  dependencies.
- Email-based password recovery with configurable SMTP and one-time hashed reset tokens.
- Profile update and password change.
- User and role administration, permission catalog, audit API, administrator seeding.
- Login, forgot/reset password, protected shell, profile, change-password, users, roles, and
  permissions screens.
- SweetAlert2 toast feedback for frontend validation, success, and action errors.

### Implemented Phase 2 slices — Units and product categories

- Unit API, persistence model, schema validation, repository, and service.
- Permission-controlled unit list/create/update/delete/restore, with audit entries and soft-delete
  behavior.
- Administrator seed includes the `master_data.units.*` permissions.
- Units screen is available at `/units`.
- Product-category API and persistence model with optional self-referencing parent categories.
- Parent existence/active-state validation and cycle prevention for category hierarchy changes.
- Permission-controlled category list/create/update/delete/restore, with audit entries and
  soft-delete behavior.
- Administrator seed includes the `master_data.product_categories.*` permissions.
- Product-category screen is available at `/categories`.

### Planned, not yet implemented

The remaining roadmap is products, pricing, warehouses, other master data, customers/suppliers,
inventory, purchase, money, production, sales, assets, employees, approvals, reports/dashboard, and
full-cycle hardening. Consult
`06_TODO.md` for the current checklist and `05_PLAN.md` for ordering and exit criteria. Do not claim
these workflows work end-to-end until their modules, persistence, permissions, tests, and screens
are actually delivered.

## 11. Project documentation map

| File | What it documents |
|---|---|
| `01_PROJECT.md` | Product purpose, goals, boundaries, and module list |
| `02_TECH_STACK.md` | Fixed stack and architecture conventions |
| `03_PRD.md` | Product features and acceptance criteria |
| `04_RULES.md` | Binding business, engineering, and AI rules |
| `05_PLAN.md` | Phase dependencies and exit criteria |
| `06_TODO.md` | Delivered work, open questions, and decisions |
| `07_DESIGN.md` | UI/UX patterns and visual behavior |
| `08_APP_FLOW.md` | Navigation and process flows |
| `09_SCHEMA.md` | Planned database model |
| `10_DEVELOPMENT_GUIDE.md` | This repository's architecture, current features, operations, and implementation status |
| `CLAUDE.md` | Concise agent context that points to the source documents |
