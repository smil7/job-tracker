# Feature 2: Each user sees only their own data

**Status:** Built. Branch `feat/users-and-login`.
**Files:** `backend/app/models.py`, `backend/alembic/versions/0004_data_per_user.py`, `backend/app/routers/*.py`, `backend/tests/conftest.py`, `backend/tests/test_isolation.py`.

## 1. What it does

Feature 1 let the API know **who** is calling. This feature uses that. Now:

1. Each application belongs to one user.
2. Each profile (resume + about-me) belongs to one user.
3. Each route returns, changes or deletes **only** the rows of the caller.
4. `DELETE /api/me` deletes the user and all of their data.
5. Each private route returns **401** if there is no valid login.

## 2. Why this solution

### The problem

With login alone, any logged-in person could still read the data of any other person. The routes used to run `select(Application)` with no filter, and `Profile` was one row (`id = 1`) for the whole app. Login without separation of data does not protect anything.

### Choice 1: `user_id` on `applications` and `profile` only

The plan in `DEPLOYMENT_PLAN_AWS.md` said to add `user_id` to four tables: `applications`, `profile`, `resume_reviews` and `cover_letters`. I added it to **two**. This is a change from the plan. These are the reasons:

- A review or a cover letter is always reached **through its application**. Each route calls `_get_detail(session, application_id, user)` first. That call returns 404 if the application is not owned by the user. So the child rows cannot be reached from another user.
- A `user_id` on the child tables would copy the same fact in 3 places. Copies can become different (for example, a bug that sets the wrong `user_id`). With one owner column, there is one place to check.
- Deleting is simple. `users → applications → (events, reviews, letters)` is one chain of `ON DELETE CASCADE`.

The cost: if a future route reads `resume_reviews` without going through an application, it must join to `applications` to filter by user. The test `test_every_private_route_needs_login` and the isolation tests help to catch this.

### Choice 2: 404, not 403, for the data of another user

If user B asks for an application of user A, the API answers **404 Not found**, the same as for an id that does not exist. A 403 ("Forbidden") would tell B that the id exists. The test `test_unknown_id_and_other_users_id_look_the_same` checks that the two answers are identical, including the body.

### Choice 3: One function does the ownership check

`_get_detail(session, application_id, user)` in `routers/applications.py` is the only place that loads an application by id. All the routes (`applications.py` and `ai.py`) use it. The `user` argument is **required** (no default value). So a developer cannot forget it: the code would not run.

### Choice 4: Filter in the query, not after

The code puts `WHERE user_id = :me` in the SQL query. It does not load all rows and filter in Python. This is faster and, more important, the rows of other users never enter the memory of the request.

### Choice 5: `profile.user_id` is the primary key

A profile is "one per user". The simplest way to say this in the database is to make `user_id` the primary key. Then the database itself refuses a second profile for the same user. The old `id` column (always 1) was removed.

### Choice 6: Cascade delete in the database

`DELETE /api/me` runs one SQL statement: `DELETE FROM users WHERE id = :me`. The database then deletes the rows in all other tables because of `ON DELETE CASCADE`. This is better than deleting from each table in Python:

- One statement is **atomic**. If it fails, nothing is deleted. There is no half-deleted account.
- A new table in the future only needs a `CASCADE` foreign key. The delete code does not change.

The test `test_delete_me_removes_everything_of_the_user_only` counts the rows in every table afterwards, to prove that all rows of the user are gone and the rows of the other user are not touched.

**Note:** `DELETE /api/me` removes the **data**. It does not remove the login in Cognito. If the user logs in again, an empty account is made. To remove the login, an admin runs `aws cognito-idp admin-delete-user`. (Later, the API could do this itself.)

### Choice 7: What happens to your old local data (the migration)

You already have applications on your laptop. The migration `0004_data_per_user.py` works in four steps:

1. Add `user_id` as **nullable**. (Existing rows have no owner yet.)
2. If there are rows, create the **dev user** (`dev-user`, the same user that `AUTH_DISABLED=true` uses) and give all existing rows to it.
3. Make `user_id` **not null**, and add the foreign key and the index.
4. Change the key of `profile`.

So after the migration, `task dev` still shows all your old data. On AWS the database starts empty, so step 2 does nothing there.

I tested the migration on a scratch database that had 2 applications and a profile. All rows stayed, they all got the same owner, `alembic check` showed no difference with the models, and a downgrade and a second upgrade also worked.

## 3. Tests

### 3.1 How the tests act as two users

`tests/conftest.py` has two clients:

| Fixture | Use |
|---|---|
| `client` | Already logged in. It is user **A**. Add `headers=AS_B` to a request to act as user **B**. Almost all tests use this. |
| `raw_client` | Has the **real** login check. Used to test the login itself. |

`client` replaces the `current_user` dependency with a small fake. The fake reads the header `X-Test-User`. This is the standard FastAPI way to test a protected app (`app.dependency_overrides`). It lets one test use two users in the same database.

### 3.2 What the isolation tests prove (`tests/test_isolation.py`)

| Test | Proves |
|---|---|
| lists show only own applications | A and B each see only their own rows |
| search does not leak | The `q=` search cannot find rows of another user |
| other users' application is 404 on every route | GET, PATCH, DELETE and POST events all give 404. The owner's data does not change. |
| unknown id = other user's id | The two 404 answers are the same |
| stats count only own | The numbers on the dashboard are per user |
| profiles are separate | The resume and about-me of A are invisible to B |
| other users' AI results are 404 | Review, cover letter (read, write, generate) and the `.docx` give 404. **No AI call is made**, so there is no cost. |
| AI uses the resume of the caller | B cannot use the resume of A |
| `DELETE /api/me` | Removes all rows of the user, in every table. Keeps the rows of the other user. |
| every private route needs login | See below |

### 3.3 The "no route is forgotten" test

The most common mistake is to add a new route and forget to make it private. `test_every_private_route_needs_login` reads **all** routes from the OpenAPI schema (`app.openapi()`) and checks that each one (except `/api/health`) returns 401 without a token. If you add a route later and forget `CurrentUser`, this test fails by itself.

A second test, `test_there_are_private_routes_to_check`, makes sure the list is not empty. (It was needed: my first version read `app.routes`, found 0 routes because this FastAPI version nests the routers, and the test passed without checking anything. The second test caught this.)

### 3.4 I checked that the tests can fail

I removed the user filter from the list route on purpose. Two tests failed. I removed the user filter from the stats query. One test failed. Then I put the code back. A test that cannot fail does not prove anything.

## 4. What changed for the frontend

The routes and the data shapes are the same, so the screens do not change. The frontend now needs to send the token (Feature 3). `openapi.json` and `schema.d.ts` were regenerated with `npm run gen:api` (new: `DELETE /api/me`).

## 5. Limits and later work

- **No sharing.** A row has one owner. There is no team or share feature.
- **Resume PDFs are still in Postgres** (`profile.resume_pdf`). The plan moves them to S3 later (Phase 6).
- **No daily AI limit yet.** Each user can still call the AI without a limit. This is Step 3 of the implementation guide.
- **Row-level security** in Postgres is a stronger option (the database itself refuses the other rows). I did not use it because it needs a database setting on each request and is harder to test and to understand. The explicit `WHERE user_id` plus the tests above is simpler for an app of this size.
