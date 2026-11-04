# Architecture overview

Start here. This page explains how the pieces of Job Tracker fit together and follows a few requests from click to database and back. The detailed guides are:

- [BACKEND.md](BACKEND.md): FastAPI app, data model, stats logic, AI features, tests
- [FRONTEND.md](FRONTEND.md): React app, components, data fetching and caching

## The big picture

Job Tracker is a single-user app with three running processes and one external service.

```mermaid
flowchart LR
    subgraph Browser
        UI["React app<br/>(localhost:5173)"]
    end

    subgraph Dev machine
        Vite["Vite dev server<br/>:5173"]
        API["FastAPI (uvicorn)<br/>:8000"]
        DB[("PostgreSQL 16<br/>Docker, host :5433")]
    end

    OR["OpenRouter<br/>(LLM API)"]

    UI -- "page + JS" --> Vite
    UI -- "fetch /api/*" --> Vite
    Vite -- "proxies /api/*" --> API
    API -- "SQLAlchemy async<br/>(asyncpg)" --> DB
    API -- "chat completions<br/>(openai SDK)" --> OR
```

| Process  | What it does | Started by |
| -------- | ------------ | ---------- |
| Postgres | Stores applications, timeline events, profile, reviews, cover letters. Data lives in the `pgdata` Docker volume (kept out of OneDrive on purpose). | `docker compose up -d --wait` |
| FastAPI  | The REST API under `/api`. All business rules live here. | `uv run uvicorn app.main:app --reload --port 8000` |
| Vite     | Serves the React app and forwards every `/api/*` request to port 8000, so the browser only ever talks to one origin. | `npm run dev` |

`start.bat` runs all three in order: start Postgres, apply migrations (`alembic upgrade head`), then open the API and the web app in their own windows.

OpenRouter is only called by the two AI features (resume review and cover letter). The rest of the app works without an API key.

## Repository map

```
job-tracker/
├── start.bat                 one-click start (Windows)
├── docker-compose.yml        Postgres container, port 5433, pgdata volume
├── docker/init-test-db.sql   creates the jobtracker_test database on first start
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app, CORS, mounts routers under /api
│   │   ├── config.py         settings from backend/.env
│   │   ├── db.py             async engine, session dependency
│   │   ├── models.py         SQLAlchemy tables + StrEnums
│   │   ├── schemas.py        Pydantic request/response models
│   │   ├── routers/          applications, stats, profile, ai
│   │   ├── llm/              OpenRouter client, prompts, call logic
│   │   └── export_openapi.py writes openapi.json for the frontend
│   ├── alembic/versions/     database migrations
│   └── tests/                pytest, against jobtracker_test
└── frontend/
    └── src/
        ├── main.tsx          React root + TanStack QueryClient
        ├── App.tsx           page shell, view switch, shortcuts
        ├── api/              typed fetch client + generated schema
        ├── hooks/            every query and mutation
        ├── components/       Board, Table, Drawer, modals, AI panels
        └── lib/              status colours, dates, form helpers
```

## The contract between frontend and backend

The frontend never hand-writes API types. The backend's Pydantic schemas are the single source of truth, and a script turns them into TypeScript:

```mermaid
flowchart LR
    S["backend/app/schemas.py<br/>+ routers"] --> F["FastAPI builds<br/>OpenAPI spec"]
    F -- "npm run gen:api<br/>(app.export_openapi)" --> J["backend/openapi.json"]
    J -- "openapi-typescript" --> D["frontend/src/api/schema.d.ts<br/>(generated, never edit)"]
    D --> T["src/api/types.ts<br/>friendly aliases"]
    D --> C["src/api/client.ts<br/>openapi-fetch client"]
    T --> H["hooks + components"]
    C --> H
```

Because `openapi-fetch` is typed from `schema.d.ts`, a wrong path, a missing parameter or a misspelt field is a compile error in the frontend. **After changing a schema or a route, run `npm run gen:api` and then `npm run build`** to see what broke.

## Domain in one minute

- An **Application** is one job you're tracking: company, role, optional details, and a **status** (stage).
- Stages: `wishlist → applied → assessment → interview → offer`, plus two closed stages `rejected` and `withdrawn`.
- Every status change writes a **StatusEvent**. Plain notes ("Recruiter called") are also StatusEvents, just without a `to_status`. Together they form the application's **timeline**.
- **Stats** (interviews, response rate) are computed by replaying the event history, so an application that reached Interview and was then Rejected still counts as an interview.
- The **Profile** is a single row holding your resume PDF and an "about me" note. The AI features send these, plus an application's job description, to the model.
- A **ResumeReview** is a stored ATS-style score for one application (you can run it many times; the latest is shown). A **CoverLetter** is one editable letter per application.

```mermaid
erDiagram
    APPLICATION ||--o{ STATUS_EVENT : "timeline"
    APPLICATION ||--o{ RESUME_REVIEW : "reviews"
    APPLICATION ||--o| COVER_LETTER : "letter"
    PROFILE {
        int id "always 1"
        bytes resume_pdf
        text about_me
    }
```

Deleting an application deletes its events, reviews and letter (`ON DELETE CASCADE`).

## Request walkthroughs

### 1. Dragging a card to a new column

This is the most important flow: it shows the optimistic update on the frontend and the event logging on the backend.

```mermaid
sequenceDiagram
    actor User
    participant Board as Board.tsx (dnd-kit)
    participant Hook as useUpdateApplication
    participant Cache as TanStack Query cache
    participant API as PATCH /api/applications/{id}
    participant DB as Postgres

    User->>Board: drop card on "Interview"
    Board->>Hook: mutate({id, body: {status: "interview"}})
    Hook->>Cache: onMutate: move the card in ['applications'] now
    Note over Board: card already shows in the new column
    Hook->>API: PATCH {status: "interview"}
    API->>DB: load application + events
    API->>DB: append StatusEvent(from=applied, to=interview)<br/>set status, fill applied_at if empty
    API->>DB: COMMIT
    API-->>Hook: 200 ApplicationDetail (with timeline)
    Hook->>Cache: onSuccess: store detail under ['applications', id]
    Hook->>Cache: onSettled: invalidate ['applications'] and ['stats']
    Cache->>API: refetch list and stats in the background
    alt request failed
        Hook->>Cache: onError: restore the previous list (card jumps back)
    end
```

### 2. Running a resume review

```mermaid
sequenceDiagram
    actor User
    participant Panel as ResumeReviewPanel
    participant Router as routers/ai.py
    participant Service as llm/service.py
    participant OR as OpenRouter
    participant DB as Postgres

    User->>Panel: "Review my resume"
    Panel->>Router: POST /api/applications/{id}/review
    Router->>DB: load application + profile
    alt no job description or no resume
        Router-->>Panel: 400 "Add a job description first" / "Upload your resume..."
    end
    Router->>Service: review_resume(llm, profile, application)
    Service->>OR: chat.completions.create<br/>system prompt + resume PDF (base64) + job description<br/>response_format = ATSReview JSON schema
    OR-->>Service: JSON text
    Service->>Service: validate against ATSReview<br/>(one retry if invalid)
    Service-->>Router: ATSReview
    Router->>DB: INSERT resume_reviews (score, result JSONB)
    Router-->>Panel: 201 ResumeReviewRead
    Panel->>Panel: setQueryData(review) and render the score
```

The frontend also guards this: `AiGate` shows a checklist instead of the panel until a resume is uploaded and the job description is saved.

### 3. Loading the page

1. `main.tsx` creates a `QueryClient` and renders `App`.
2. `App` calls `useApplications()` → `GET /api/applications` (everything, no filters).
3. `StatsStrip` calls `useStats()` → `GET /api/stats`.
4. The board/table and the search box work on the already-loaded list in the browser; search does not hit the server.
5. Clicking a card opens `DetailDrawer`, which fetches `GET /api/applications/{id}` for the full record and its timeline.

## Where to make common changes

| I want to... | Touch these |
| ------------ | ----------- |
| Add a field to applications | `models.py`, new Alembic migration, `schemas.py` (`ApplicationFields`), `npm run gen:api`, `lib/form.ts`, `FormFields.tsx` |
| Add a new stage | `ApplicationStatus` in `models.py`, a migration that alters the Postgres enum, `RANK`/sets in `routers/stats.py`, `lib/status.ts` |
| Add an endpoint | a router in `app/routers/` (include it in `main.py` if new), schemas, tests, `npm run gen:api`, a hook in `useApplications.ts` |
| Change an AI prompt | `app/llm/prompts.py` (keep it byte-stable between calls; see BACKEND.md) |
| Change stage colours | `frontend/src/lib/status.ts` |

## Ports and environment

| Thing | Value |
| ----- | ----- |
| Web app | http://localhost:5173 |
| API + Swagger docs | http://localhost:8000/docs |
| Postgres | `localhost:5433`, user/password/db `jobtracker` |
| Test database | `jobtracker_test` (same server) |
| Config file | `backend/.env` (copy from `.env.example`) |
| AI settings | `OPENROUTER_API_KEY`, `LLM_MODEL` (default `anthropic/claude-sonnet-5.5`) |
