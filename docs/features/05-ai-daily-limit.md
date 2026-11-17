# Feature 5: Daily AI limit

**Status:** Built and tested. Branch `feat/ai-daily-limit`.
**Files:** `backend/app/ai_quota.py`, `backend/app/models.py` (`AIUsage`), `backend/alembic/versions/0005_add_ai_usage.py`, `backend/app/routers/ai.py`, `backend/app/config.py`, `backend/tests/test_ai_limit.py`.

## 1. What it does

1. Each user can start a fixed number of AI requests each day. The default is **20** (`AI_DAILY_LIMIT`).
2. A resume review and a cover letter use the **same** count.
3. When a user is at the limit, the API answers **429** and does **not** call the model. So it costs nothing.
4. The answer says what happened: `Daily AI limit reached (20 requests per day). It resets at 00:00 UTC.` The header `Retry-After` gives the seconds until then. The browser already shows the `detail` text of an error, so the user sees this message.
5. The count starts again at 00:00 UTC.
6. `AI_DAILY_LIMIT=0` turns the AI off for everyone.

## 2. Why this solution

### The problem

Each review or letter sends a PDF and a job description to a paid model (OpenRouter). The login (Feature 1) stops strangers. But a logged-in user, or a stolen login, or a bug in a loop, could still spend all your credit in a few minutes. A limit per user keeps the worst cost known: `users x limit x cost of one request`.

### Choice 1: Count in Postgres

| Option | Reason |
|---|---|
| **A table in Postgres (chosen)** | We already have Postgres. It works when there are 2 API tasks, because both read the same table. It survives a restart. No new service. |
| Count in memory | Each task has its own count, and a restart sets it to 0. A user could go over the limit. |
| Redis | Fast, but a new service to pay for and to operate. The plan says "no Redis at this load". |
| API Gateway or WAF rate limit | They limit requests per second per IP. They do not know the user and they do not know which request costs money. |

The table is `ai_usage`. The primary key is `(user_id, day)`. One row holds the count of one user for one day. When the user is deleted, the rows are deleted too (`ON DELETE CASCADE`).

### Choice 2: One SQL statement does the check and the add

The simple way is: read the count, check it, then add 1. This is **not safe**. Two requests at the same time can both read `2` (limit `3`), and both continue. The user gets 4.

So the code uses one statement:

```sql
INSERT INTO ai_usage (user_id, day, count) VALUES (:user, :today, 1)
ON CONFLICT (user_id, day) DO UPDATE SET count = ai_usage.count + 1
WHERE ai_usage.count < :limit
RETURNING count
```

If the row exists and the count is already at the limit, the `WHERE` is false and nothing is returned. The code reads this as "limit reached". Postgres locks the row during the statement, so the check and the add happen together. The test sends 10 requests at the same time with a limit of 3: exactly 3 pass and 7 get 429.

### Choice 3: When the count goes up

The count goes up **before** the model call, and **after** the cheap checks. So:

| Case | Counts? |
|---|---|
| No resume, or no job description (400) | No |
| An id that is not yours (404) | No |
| Over the limit (429) | No |
| The model call fails (502, 503) | **Yes** |

**Trade-off:** a failed call still counts. This is simple and cannot be abused: no way to start many expensive calls that "fail". The cost is that a user can lose a request when OpenRouter has a problem. With a limit of 20 this is small. I did not build a refund, because some failures (a cut-off answer, a refusal) did cost money, and it is hard to tell them apart. A test documents this behavior.

### Choice 4: Day = the UTC day

The day changes at 00:00 UTC for all users. It is easy to explain and to test. A user in another time zone sees the reset at a different local time. The message says "UTC".

### Choice 5: 429 and `Retry-After`

429 "Too Many Requests" is the standard answer for a limit. `Retry-After` is the standard header that tells the client when to try again.

## 3. Settings

| Variable | Default | Meaning |
|---|---|---|
| `AI_DAILY_LIMIT` | `20` | AI requests for each user each day. `0` turns the AI off. |

## 4. How it was checked

- 9 new tests (98 in total) pass. They check: request `limit + 1` gives 429 and the model is not called; review and letter share the count; users have separate counts; the count starts again the next day; 10 requests at the same time pass only 3; limit 0; failed checks do not count; a failed model call counts; `DELETE /api/me` removes the usage rows.
- I removed the `WHERE count < limit` on purpose. 6 tests failed. Then I put it back.
- The migration `0005` was tested: upgrade, downgrade, upgrade, and `alembic check` shows no difference with the models.

## 5. Not done here (you must do this)

- **A separate OpenRouter key for production, with a credit limit.** This is the second safety net. If our limit has a bug, OpenRouter stops at the credit limit. Do this in the OpenRouter website when you deploy. Put the key in Secrets Manager (Step 5).

## 6. Limits and later work

- The limit is the same for all users. A per-user limit would need a column on `users`.
- The browser does not show "you have N requests left" yet. The count could be added to `GET /api/me`.
- A real cost limit needs the token price. The count of requests is a simple stand-in.
