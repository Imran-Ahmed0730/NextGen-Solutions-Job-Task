# API and OpenAPI Guide

## Interactive API documentation

The FastAPI application generates its OpenAPI specification from the live routes and Pydantic
schemas. When the API is running locally, use:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Health check: <http://localhost:8000/health>

For another environment, replace `localhost:8000` with that environment's API origin. Do not
publish interactive documentation on a public production API unless that exposure is intentional
and protected by the deployment's access policy.

## API conventions

- Business endpoints are versioned under `/api/v1`.
- Authentication is bearer-token based. Call `POST /api/v1/auth/login` with a username and
  password; use the returned `access_token` as
  `Authorization: Bearer <access_token>` for protected endpoints.
- Login, token refresh, forgotten-password request, and password-reset endpoints do not require an
  access token. Other endpoints declare authentication in OpenAPI and may also require the relevant
  role permission.
- A successful login returns an access token and a refresh token. Access-token expiration is
  configured with `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`; refresh-session lifetime is configured with
  `REFRESH_TOKEN_EXPIRE_DAYS`. `POST /api/v1/auth/refresh` rotates the refresh token.
- Endpoint authorization is checked by the backend. The frontend hiding a navigation item is not
  an authorization boundary.
- Amounts and quantities are represented as decimal strings in request/response schemas where
  precision matters. Follow the OpenAPI schema and examples instead of using binary floating-point
  values in client-side financial calculations.
- Validation errors are returned as HTTP 422. Authentication failures use HTTP 401; authenticated
  users missing the required permission receive HTTP 403 with the `PERMISSION_DENIED` error code.

## First requests

Use an administrator account created by the deployment's initial-admin seed. The generated
password is printed only on first creation; do not put it in source control or share it in an
insecure channel.

Login:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "<the securely delivered initial password>"
}
```

Use the returned access token in Swagger UI's **Authorize** dialog as a bearer token, or in a
request header:

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

## Main endpoint groups

The generated OpenAPI document is the authoritative list of paths, HTTP methods, schemas, query
filters, and response types. The following groups provide a navigation starting point:

| Area | API path prefix | Typical permission |
| --- | --- | --- |
| Authentication, users, roles, permissions | `/api/v1/auth` | `auth.*` |
| Master data and company settings | Module-specific `/api/v1` paths | `master_data.*` |
| Purchase orders, receipts, returns | `/api/v1/purchase` | `purchase.*` |
| Sales quotations, orders, delivery, invoices, returns | `/api/v1/sales` | `sales.*` |
| Inventory and stock movements | `/api/v1/inventory`, `/api/v1/stock-*` | `inventory.*` |
| Production BOMs and orders | `/api/v1/production` | `production.*` |
| Collections, payments, expenses, transfers | `/api/v1/money`, `/api/v1/expenses` | `money.*` |
| Management dashboard and reports | `/api/v1/reports` | `reports.dashboard.read`, `reports.read` |
| Approval rules and requests | `/api/v1/approvals` | `approvals.*` |
| Employees, attendance, and payroll | Module-specific `/api/v1` paths | `employees.*` |

Posting endpoints enforce business rules and perform ledger effects transactionally. Do not bypass
these APIs to write stock balances, account balances, due totals, document statuses, or ledger rows
directly in the database.

## Keeping API documentation accurate

The OpenAPI document is generated from the API code at runtime, not maintained as a separate static
copy. When an endpoint, permission, schema, or response changes:

1. Update the route/schema and its service/API tests.
2. Confirm the route appears correctly in `/openapi.json` and `/docs`.
3. Keep business rules, permission behavior, and error responses consistent with
   `knowledge/04_RULES.md`.
4. Run the backend tests, Ruff, and mypy listed in the README.

Use the application's OpenAPI JSON to generate client SDKs only after checking that generated
clients preserve decimal precision and send the required bearer token.
