# Plan: write `docs/IMPLEMENTATION_GUIDE_AWS.md`

**Status:** Done. The guide is written in `docs/IMPLEMENTATION_GUIDE_AWS.md`.

## Context

`docs/DEPLOYMENT_PLAN_AWS.md` says *what* to build. The user wants a second document that says *how*. It needs:

- a clear diagram of the system (the ASCII one is messy),
- a checklist of the steps that make the app deployable and usable,
- an answer to the question "are login and sign-up missing?"

**Findings from the code (the answer is yes):**

| Missing piece | Evidence |
|---|---|
| Login / sign-up / users | No auth code in `backend/app` or `frontend/src`. No `users` table. `Profile` is a single row (`models.py:96`). Every route returns all rows to anyone. |
| User-scoped data | `applications`, `resume_reviews`, `cover_letters` have no `user_id`. |
| Application logging | No `logging` setup in `backend/app`. Uvicorn access logs are the only output. |
| Container image | No `backend/Dockerfile`, no `.dockerignore`, no prod compose file. |
| Real health check | `/api/health` returns `{"status":"ok"}` without touching the DB (`main.py:22`). |
| Prod config | `config.py` has no Cognito, environment or git SHA settings. |
| AI cost guard | No per-user quota. Anyone with the URL could spend OpenRouter credit. |
| Infra + CD | No `infra/`, only `ci.yml` (no deploy workflow). |

Things that are already fine: CI (`ci.yml`), Alembic migrations, `alembic check`, same-origin `/api` client (`frontend/src/api/client.ts`), env-based settings (`config.py`).

## The document

**File:** `docs/IMPLEMENTATION_GUIDE_AWS.md`. Written in ASD-STE100 style, like the plan. Do **not** open it in VS Code.

**Decisions from the user:**

- **Sign-up is invite-only.** Cognito self-signup stays off. The admin creates users (`aws cognito-idp admin-create-user`), and Cognito emails a temporary password. The guide has an "Invite a user" step and a "first login / change password" note. No public sign-up page.
- **Diagrams are Mermaid** inside the `.md` file.


**Sections:**

1. **Short answer.** "Yes, you are right." List the missing pieces from the table above. Split them into *blockers* (must do before anyone else uses it) and *nice to have*.
2. **System diagrams (Mermaid).** Three small diagrams instead of one large one:
   - *Request path*: browser → Route 53 → CloudFront → (S3 | ALB → ECS → RDS / S3 / OpenRouter). Subgraphs for VPC, public subnet, private subnet.
   - *Login sequence*: browser → Cognito hosted UI → code + PKCE → tokens → API checks JWT with JWKS → `users` row.
   - *Deploy pipeline*: push → CI → build image → ECR → migrate task → ECS deploy → S3 sync → invalidation → smoke test.
3. **Where you are now vs. where you go.** A small "today" diagram (laptop: Vite → uvicorn → Docker Postgres) next to the target.
4. **Step-by-step checklist.** Each step has: goal, files to touch, exact commands, and a "done when" check. Order:
   - Step 0: AWS account safety + budget (console clicks, listed).
   - Step 1: Users and login in the code (blocker). `users` table + migration, `app/auth.py` with `current_user`, `user_id` filters in each router, per-user `Profile`, `AUTH_DISABLED` dev bypass, isolation tests, frontend login with `oidc-client-ts`, bearer token in `client.ts`, `npm run gen:api`.
   - Step 2: Logging and health (blocker). JSON logging to stdout with request id + user id, DB-backed `/api/health` with `version`.
   - Step 3: AI quota (blocker for others). `ai_usage` table, 429 over limit.
   - Step 4: Container. `Dockerfile`, `.dockerignore`, `docker-compose.prod.yml`, test locally.
   - Step 5: Terraform, in the order from the plan, one `apply` at a time.
   - Step 6: Deploy workflow.
   - Step 7: First real deploy + invite users.
   - Step 8: Operate (backups drill, alarms, runbook).
5. **"Minimum to use it" path.** A short box: which steps you must finish before you yourself can use it on AWS (Steps 0, 1, 2, 4, 5, 7), and which can wait (3 if only you, 6, 8).
6. **Links back** to the matching sections of `DEPLOYMENT_PLAN_AWS.md`, so the guide does not repeat the "why".

The guide does not contain full code. It names functions, files and commands, with short snippets only where a step is hard to understand without one (for example the `current_user` signature and the token check).

## Verification

- Check each Mermaid block for valid syntax (node ids without spaces, quoted labels with special characters). GitHub renders Mermaid natively.
- Make sure each step names real files that exist today, or files that the plan creates.
- Make sure the sentences follow the same short STE style as the plan.
