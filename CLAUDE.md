# Job Tracker

Personal job application tracker. React + TypeScript frontend (`frontend/`), FastAPI backend (`backend/`), PostgreSQL in Docker.

## Commands

- Start everything: `start.bat`
- DB: `docker compose up -d --wait` (Postgres on host port 5433; DB files live in the `pgdata` named volume, not in OneDrive)
- Backend (from `backend/`): `uv run uvicorn app.main:app --reload --port 8000`, `uv run pytest`, `uv run alembic upgrade head`
- New migration: `uv run alembic revision --autogenerate -m "..."`, then review the generated file
- Frontend (from `frontend/`): `npm run dev`, `npm run build` (runs `tsc -b`, so it's the type check), `npm run lint`
- API types: `npm run gen:api` exports `backend/openapi.json` and regenerates `frontend/src/api/schema.d.ts`. Run it after any schema or route change; never hand-edit `schema.d.ts`.

## Conventions

- Backend: routers in `app/routers/`, SQLAlchemy models in `app/models.py`, Pydantic schemas in `app/schemas.py`. Status and job type are `StrEnum`s stored as Postgres enums using their lowercase values.
- Every status change must write a `StatusEvent` (the PATCH route does it). Stats count interviews and responses from event history, not just the current status.
- Tests use the `jobtracker_test` database and rebuild the schema for each test (`tests/conftest.py`).
- Frontend: server state goes through the TanStack Query hooks in `src/hooks/useApplications.ts`; components don't call `api` directly. Vite proxies `/api` to port 8000.
- `tsconfig` has `erasableSyntaxOnly` and `verbatimModuleSyntax`: no TS `enum`s, and use `import type` for types.
- Styling: Tailwind utilities with a stone palette; stage colours live in `src/lib/status.ts`.
