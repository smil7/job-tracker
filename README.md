# Job Tracker

A simple personal tracker for job applications (graduate programs and junior roles). Add an application in a few seconds, drag it through the stages on a Kanban board, and every stage change is logged on its timeline.

- **Board**: Wishlist → Applied → Assessment → Interview → Offer, plus Rejected / Withdrawn (collapsed, still droppable)
- **Table**: sortable list of everything
- **Detail drawer**: edit fields, keep the job description, add timeline notes ("Recruiter called")
- **Stats**: applied, this week, active, interviews, offers, response rate
- **Profile**: upload your resume (PDF) and an "About me" note, used by the AI tools below
- **Resume review**: scores your resume against an application's job description the way an ATS would (keywords, section scores, formatting risks, suggested edits)
- **Cover letter**: drafts a letter for the role from your resume and profile; edit it in the app and download it as `.docx`
- Shortcuts: `N` new application · `/` search · `Esc` close

New to the codebase? Start with [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), then [docs/BACKEND.md](docs/BACKEND.md) and [docs/FRONTEND.md](docs/FRONTEND.md).

## Stack

| Layer    | Tech                                                              |
| -------- | ----------------------------------------------------------------- |
| Frontend | React 19 + TypeScript, Vite, Tailwind CSS 4, TanStack Query, dnd-kit |
| Backend  | Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic, uv            |
| Database | PostgreSQL 16 (Docker Compose, host port **5433**)                 |
| AI       | [OpenRouter](https://openrouter.ai) via the `openai` SDK (default model `anthropic/claude-sonnet-5.5`) |

## Prerequisites

Docker Desktop, [uv](https://docs.astral.sh/uv/), Node 22+ and, optionally, [Task](https://taskfile.dev) for the shortcuts below:

```bash
winget install Task.Task      # Windows
brew install go-task          # macOS
npm install -g @go-task/cli   # anywhere with Node
```

## Run it

```bash
task setup   # first time: installs dependencies, creates backend/.env
task dev     # starts Postgres, applies migrations, runs the API and web app (Ctrl+C stops both)
```

Run `task` on its own to list every command. The ones you'll use most:

| Command | What it does |
| ------- | ------------ |
| `task dev` | Everything, in one terminal |
| `task api` / `task web` | Just the backend or the frontend |
| `task db` / `task db:stop` | Start or stop Postgres |
| `task db:shell` | psql in the database container |
| `task migrate` | Apply migrations |
| `task migration -- "message"` | New migration from model changes |
| `task test` | Backend tests (pass pytest args after `--`, e.g. `task test -- -k stats`) |
| `task gen:api` | Regenerate the frontend API types |
| `task check` | Same checks as CI: migrations, tests, lint, build |

Without Task, double-click `start.bat` on Windows, or run the steps by hand:

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

Copy `.env.example` to `backend/.env` to change the database URL or configure the AI features:

- `OPENROUTER_API_KEY`: required for resume review and cover letters (the rest of the app works without it)
- `LLM_MODEL`: any OpenRouter model id, default `anthropic/claude-sonnet-5.5`

Each review or letter is one model call, billed to your OpenRouter credits.

## Tests

```bash
task test                     # or: cd backend && uv run pytest
```

Tests run against a separate `jobtracker_test` database, which Docker creates on first start. The AI tests use a fake model, so they never call OpenRouter.

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request. It applies the migrations, runs the backend tests, lints and builds the frontend, and fails if `openapi.json` or `schema.d.ts` is out of date (fix that with `npm run gen:api`).

## API

All routes live under `/api`. Every route except `/health` needs a login (`Authorization: Bearer <token>`). Locally, `AUTH_DISABLED=true` in `backend/.env` skips it.

See `docs/features/` for how login and per-user data work.

| Method | Path                              | Purpose                                         |
| ------ | --------------------------------- | ----------------------------------------------- |
| GET    | `/applications?status=&q=&sort=`  | List (filter by stage, search, sort)            |
| POST   | `/applications`                   | Create (only `company` and `role` are required) |
| GET    | `/applications/{id}`              | One application with its timeline               |
| PATCH  | `/applications/{id}`              | Update; a stage change is logged automatically  |
| DELETE | `/applications/{id}`              | Delete                                          |
| POST   | `/applications/{id}/events`       | Add a timeline note                             |
| GET    | `/stats`                          | Dashboard numbers                               |
| GET    | `/me`                             | The logged-in user                              |
| DELETE | `/me`                             | Delete your account and all your data           |
| GET    | `/profile`                        | Your about-me text and resume status            |
| PUT    | `/profile`                        | Update the about-me text                        |
| PUT    | `/profile/resume`                 | Upload the resume (PDF, up to 5 MB)             |
| GET    | `/profile/resume`                 | Download the stored resume                      |
| POST   | `/applications/{id}/review`       | Run an ATS-style resume review                  |
| GET    | `/applications/{id}/review`       | Latest review (404 if none)                     |
| POST   | `/applications/{id}/cover-letter` | Generate a letter (optional `instructions`)     |
| GET    | `/applications/{id}/cover-letter` | Read the saved letter                           |
| PUT    | `/applications/{id}/cover-letter` | Save your edits                                 |
| GET    | `/applications/{id}/cover-letter.docx` | Download the letter as Word                |

The review and cover letter calls return 400 until a resume is uploaded and the application has a job description.

After changing the API, regenerate the frontend types:

```bash
cd frontend && npm run gen:api
```

## Ideas for later

- Paste a job link and have an LLM fill in company, role and description
- Follow-up and deadline reminders
- Keep several cover letter versions per application
- An agent that applies for you, using this API as its tools
