# Sabuj Pran Business Management Platform

This repository is the initial foundation for the Sabuj Pran modular monolith described in the product blueprint.

## Phase 0 included

- Monorepo structure
- FastAPI backend skeleton
- Next.js frontend skeleton
- MySQL 8 + Docker Compose setup
- Alembic initialization
- Lint, type-check, test, and CI configuration
- Health endpoint and app shell

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + MySQL 8
- Frontend: Next.js + TypeScript + Tailwind CSS + shadcn-style UI primitives
- Tooling: Ruff, Mypy, Pytest, Vitest, GitHub Actions

## Quick start

1. Copy `.env.example` to `.env`.
2. Start infrastructure: `docker compose up --build`
3. API: http://localhost:8000/health
4. Web: http://localhost:3000
