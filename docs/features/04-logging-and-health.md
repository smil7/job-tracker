# Feature 4: Logs and health check

**Status:** Built and tested. Branch `feat/logging-and-health`.
**Files:** `backend/app/logging_config.py`, `backend/app/main.py`, `backend/app/auth.py`, `backend/app/llm/service.py`, `backend/tests/test_logging.py`, `backend/tests/test_health.py`.

## 1. What it does

1. Every log line is one **JSON object** on stdout.
2. Every request gets a **request id**. It is in each log line of the request and in the response header `X-Request-Id`.
3. Each request writes **one line** when it ends: method, path, status, duration, and the user id.
4. Each AI call writes a line at the start and a line at the end (or a warning when it fails).
5. An error that nobody handles is logged with its **stack trace**.
6. `GET /api/health` runs `SELECT 1` on the database. It answers `{"status":"ok","version":"<git sha>"}`. If the database does not answer in 3 seconds, it answers **503**.

Example line:

```json
{"time": "2026-11-15T19:00:22.537+00:00", "level": "INFO", "logger": "app.request", "message": "Request", "request_id": "146e7ad1...", "user_id": "5b0c...", "method": "GET", "path": "/api/applications", "status": 200, "duration_ms": 12.4}
```

## 2. Why this solution

### The problem

Without logs, you cannot find out why something failed on a server. Without a real health check, the load balancer thinks the API is fine when the database is down. Then it keeps sending users to a broken API.

### Choice 1: JSON lines on stdout

| Option | Reason |
|---|---|
| **JSON on stdout (chosen)** | A container must not write log files. ECS (`awslogs` driver) sends stdout to CloudWatch Logs. CloudWatch can search JSON fields, for example `{ $.request_id = "abc" }`. No agent, no file, no extra library. |
| Plain text lines | Hard to search by field. |
| A log library (structlog, loguru) | More code to learn. The Python `logging` module with a 20-line formatter is enough here. |
| Log files | Lost when the container stops. Need disk and rotation. |

### Choice 2: A request id in every line

When a user says "it failed at 10:05", you find the request line, copy its `request_id`, and see **all** lines of that request (the error, the AI call, the database problem). The id is also in the response header, so a user can send it to you. The id comes from a **context variable** (`request_context`), so the code that writes a log line does not need to pass the id around.

A client can send its own `X-Request-Id`. We accept it only if it matches `[A-Za-z0-9._-]{1,64}`. Otherwise we make a new one. This stops a client from putting strange text in your logs.

### Choice 3: A plain ASGI middleware

Starlette has `BaseHTTPMiddleware`, which is easier to write. It has a known problem with context variables: a value that a route sets is not always visible to the middleware afterwards. We need that for `user_id`. So `RequestLogMiddleware` is a plain ASGI middleware. The context holds a small dict that the middleware makes, and `current_user` fills in the `user_id`.

### Choice 4: `user_id` is the database id, not the email

`current_user` calls `set_user_id(user.id)`. The log has a random UUID. It has no email and no name. A log line can be seen by more people than the database (for example in a dashboard), so it holds the least personal data possible.

### Choice 5: What is not logged

| Never in a log | How it is enforced |
|---|---|
| Tokens | We log only the reason (`Signature has expired`), not the token. |
| Resume text, about-me, job description | The AI log has only `task`, `model`, duration and token counts. A test sends private text through a review and checks that it is not in the log. |
| Search text | The query string is not logged. A test checks this. |
| API keys | They are never passed to the logger. |

### Choice 6: Health checks are quiet

The load balancer calls `/api/health` every few seconds. If each call wrote an INFO line, the logs would fill with noise. A successful health check is logged at DEBUG. A failed one is logged at INFO with status 503, and an ERROR line with the reason.

### Choice 7: The health check tests the database

| | Old | New |
|---|---|---|
| Answer | Always `ok` | `ok` only when `SELECT 1` works |
| Database down | Still `ok` (wrong) | 503 |
| Version | None | `git_sha` (set by the deploy), so you can see which version runs |

The check has a **3 second limit**, so a slow database cannot hang the health check. The 503 answer has **no error text**: it can hold the database address.

**Trade-off:** if the load balancer marks the API "unhealthy" when the database is down, it restarts the task. A restart does not fix a database problem, and it can make it worse. So in Step 5 (Terraform) we decide which check the load balancer uses, and which check the uptime monitor and the smoke test use. Today one endpoint is enough.

### Choice 8: Uvicorn's own log is replaced

Uvicorn writes its own text lines. `setup_logging()` sends them through our JSON formatter. It turns off the access log, because our request line replaces it.

## 3. Settings

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `GIT_SHA` | `dev` | Shown by `/api/health`. The deploy workflow sets it to the commit. |

## 4. How it was checked

- 17 new tests (89 in total) pass. They cover: one line per request, the request id (kept when good, replaced when bad), the user id in the line, no search text in the log, the stack trace of an error, AI start, end and failure lines, no resume text in the log, the health answer, no login needed, and 503 when the database fails or is too slow.
- I ran the real server. `curl /api/health` gave the version and an `X-Request-Id` header. With a wrong database port the health check answered **503**, and the log showed the reason.
- The log helped at once. My local database had not run migration `0004` yet. The log showed `relation "users" does not exist`, with the request id.

## 5. Limits and later work

- A 500 error that Starlette builds itself has **no** `X-Request-Id` header (the middleware is inside that layer). The log line still has the id.
- Logs go to stdout only. On AWS, CloudWatch keeps them 30 days (Terraform, Step 5).
- No metrics or traces yet. The CloudWatch alarms in Step 5 cover errors and down time.
