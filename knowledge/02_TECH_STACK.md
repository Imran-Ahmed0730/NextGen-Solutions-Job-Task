# TECH STACK

The stack is **fixed** (interview requirement). Do not substitute.

## Frontend
| Concern | Choice |
|---|---|
| Framework | Next.js (App Router) + React |
| Language | TypeScript (strict mode) |
| Styling | Tailwind CSS |
| Server state | TanStack Query (React Query) |
| Forms | React Hook Form |
| Validation | Zod |
| UI components | shadcn/ui (Radix + Tailwind) |
| Charts | Recharts |
| Dates | date-fns |
| Print/PDF | Browser print CSS + server-side PDF for invoices/reports |
| Tests | Vitest + React Testing Library; Playwright for key flows |

Frontend responsibilities: data entry, display, validation feedback, workflow, usability. **Business logic stays in the backend.**

## Backend
| Concern | Choice |
|---|---|
| Framework | FastAPI (Python 3.12) |
| Validation/schemas | Pydantic v2 |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Auth | JWT (access + refresh), password hashing with argon2/bcrypt |
| Tests | pytest, httpx TestClient, factory helpers |
| Lint/format/types | ruff, black (or ruff format), mypy |
| PDF | WeasyPrint or ReportLab |

## Database
- **MySQL 8** (InnoDB, utf8mb4).
- Money: `DECIMAL(18,2)`. Quantities: `DECIMAL(18,3)`. Never float.
- Business logic is in Python services, not triggers/stored procedures. Database enforces only FKs, unique indexes, CHECK constraints and read-only views.

## Infrastructure
- Docker + docker-compose: `api`, `web`, `db` (and optional `adminer`).
- `.env` files per environment; no secrets in git.
- CI (GitHub Actions): lint, type-check, test backend and frontend, build images.

## Repository layout (monorepo)
```
/
├─ docs/                  # these md files
├─ backend/
│  ├─ app/
│  │  ├─ core/            # config, db, security, errors, numbering, audit
│  │  ├─ modules/
│  │  │  ├─ auth/ company/ products/ customers/ suppliers/
│  │  │  ├─ sales/ purchase/ inventory/ production/ money/
│  │  │  ├─ assets/ employees/ approvals/ reports/ audit/
│  │  │  │   ├─ router.py  schemas.py  models.py
│  │  │  │   ├─ service.py repository.py  tests/
│  │  └─ main.py
│  ├─ alembic/
│  └─ pyproject.toml
├─ frontend/
│  ├─ src/
│  │  ├─ app/             # routes
│  │  ├─ features/<module>/ (pages, components, hooks, schemas, api)
│  │  ├─ components/ui/   # shared UI
│  │  └─ lib/             # api client, auth, utils
│  └─ package.json
├─ docker-compose.yml
└─ CLAUDE.md              # AI context file (copy of key rules)
```

## Layering (backend)
`router` (HTTP, validation, permission check) → `service` (business rules, transactions) → `repository` (queries) → `models`.
- Routers never contain business logic.
- Services own transactions (`with session.begin()`).
- Cross-module calls go through the other module's **service**, never its repository/tables.

## API conventions
- REST, JSON, prefix `/api/v1/<module>`.
- Plural nouns: `/api/v1/products`, `/api/v1/sales-orders`.
- Actions as sub-resources: `POST /sales-orders/{id}/reserve`, `POST /goods-receipts/{id}/post`.
- Pagination: `?page=1&page_size=20`; filtering by query params; sort `?sort=-created_at`.
- Error shape: `{ "error": { "code": "STOCK_INSUFFICIENT", "message": "...", "details": {} } }`.
- Auth: `Authorization: Bearer <token>`.
