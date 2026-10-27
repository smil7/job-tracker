# Job Tracker

A simple personal tracker for job applications (graduate programs and junior roles). Add an application in a few seconds, drag it through the stages on a Kanban board, and every stage change is logged on its timeline.

- **Board**: Wishlist → Applied → Assessment → Interview → Offer, plus Rejected / Withdrawn (collapsed, still droppable)
- **Table**: sortable list of everything
- **Detail drawer**: edit fields, keep the job description, add timeline notes ("Recruiter called")
- **Stats**: applied, this week, active, interviews, offers, response rate
- Shortcuts: `N` new application · `/` search · `Esc` close

## Stack

| Layer    | Tech                                                              |
| -------- | ----------------------------------------------------------------- |
| Frontend | React 19 + TypeScript, Vite, Tailwind CSS 4, TanStack Query, dnd-kit |
| Backend  | Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic, uv            |
| Database | PostgreSQL 16 (Docker Compose, host port **5433**)                 |

## Prerequisites

Docker Desktop, [uv](https://docs.astral.sh/uv/) and Node 22+.

## Run it

Double-click `start.bat`, or step by step:

```bash
docker compose up -d --wait
```

```bash
cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

- App: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs

Copy `.env.example` to `backend/.env` if you need to change the database URL.

## Tests

```bash
cd backend && uv run pytest
```

Tests run against a separate `jobtracker_test` database, which Docker creates on first start.

## API

All routes live under `/api`:

| Method | Path                              | Purpose                                         |
| ------ | --------------------------------- | ----------------------------------------------- |
| GET    | `/applications?status=&q=&sort=`  | List (filter by stage, search, sort)            |
| POST   | `/applications`                   | Create (only `company` and `role` are required) |
| GET    | `/applications/{id}`              | One application with its timeline               |
| PATCH  | `/applications/{id}`              | Update; a stage change is logged automatically  |
| DELETE | `/applications/{id}`              | Delete                                          |
| POST   | `/applications/{id}/events`       | Add a timeline note                             |
| GET    | `/stats`                          | Dashboard numbers                               |

After changing the API, regenerate the frontend types:

```bash
cd frontend && npm run gen:api
```

## Ideas for later

- Paste a job link and have an LLM fill in company, role and description
- Follow-up and deadline reminders
- CV / cover letter versions per application
- An agent that applies for you, using this API as its tools
