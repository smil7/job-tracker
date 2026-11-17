# Feature 6: Container image and local production test

**Status:** Built and tested on a laptop. Branch `feat/container-image`.
**Files:** `backend/Dockerfile`, `backend/.dockerignore`, `docker-compose.prod.yml`, `docker/nginx.conf`.

## 1. What it does

1. `backend/Dockerfile` builds an image of the API. AWS (ECS) will run this image.
2. `docker-compose.prod.yml` runs the production build on your laptop: Postgres, the API image, and nginx that serves the built React app. nginx sends `/api` to the API.
3. You can test the same image that will run on AWS before you send it there.

## 2. Why this solution

### The problem

On AWS, ECS does not run `uv run uvicorn --reload` from your folder. It runs a **container image**. If the image is wrong, you find out only after a slow deploy. A local test finds the problem in minutes.

### Choice 1: A multi-stage Dockerfile

| Stage | Job |
|---|---|
| `builder` | Has `uv`. Installs the packages from `uv.lock` (`uv sync --locked --no-dev`). |
| `runtime` | A small Python image. Gets only the finished `.venv` and the code. No `uv`, no compilers, no test packages. |

A smaller image is faster to push and to start, and has less that an attacker could use. `--locked` makes the build fail if `uv.lock` does not match `pyproject.toml`, so the image has the same package versions as your tests. `--no-dev` leaves out pytest.

The two lock files are copied **first**. Docker keeps that layer until they change, so a code change does not install all packages again.

### Choice 2: A user that is not root

The app runs as user `app` (uid 1000). If someone breaks into the app, they cannot change the system files in the container.

### Choice 3: What goes in the image

| In the image | Not in the image |
|---|---|
| `app/`, `alembic/`, `alembic.ini` (the migration task needs the last two) | `.env` (secrets), `tests/`, `.venv` from your laptop, `__pycache__`, `openapi.json` |

`.dockerignore` keeps these out. I checked the finished image: there is no `/app/.env` and no `/app/tests`.

### Choice 4: Settings come from the environment

The image has no settings and no secrets. On AWS, ECS gives `DATABASE_URL`, `COGNITO_*` and the OpenRouter key as environment variables. `GIT_SHA` is the only value set at build time (`--build-arg GIT_SHA=...`). `/api/health` shows it, so you can see which version runs.

### Choice 5: One worker

The plan said 2 workers. The task on AWS is small (0.25 vCPU), and you are the only user. One worker is enough and uses less memory. To change this later, add `--workers N` to `CMD`.

### Choice 6: `--proxy-headers`

On AWS the load balancer is in front of the API. With `--proxy-headers`, uvicorn reads the real client address from the headers that the load balancer sends.

### Choice 7: nginx for the local test only

On AWS, S3 and CloudFront serve the React files and send `/api` to the load balancer. On your laptop, nginx does the same two jobs (`docker/nginx.conf`). It also copies the real cache rules: files in `/assets` (they have a hash in the name) are kept for a year, and `index.html` is never kept. Any other path returns `index.html`, so a page reload on a deep link works. The browser calls `/api` on the **same address** as the page, so no CORS setting is needed (same as on AWS).

### Choice 8: `ENVIRONMENT=staging` in the test

The API refuses to start with `ENVIRONMENT=production` and `AUTH_DISABLED=true` (Feature 1). So the local test uses `staging` with login off. The frontend is built with `VITE_AUTH_DISABLED=true` for the same reason. I also checked that the image **does refuse** to start with `production` and login off, and with `production` and no Cognito settings.

## 3. How to run it

```
cd frontend && VITE_AUTH_DISABLED=true npm run build && cd ..
GIT_SHA=$(git rev-parse --short HEAD) docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

Open `http://localhost:8080`. To stop and delete the test database: `docker compose -f docker-compose.prod.yml down -v`.

The test database has its own volume. It does not touch your normal dev database (`docker-compose.yml`).

## 4. How it was checked

- The image builds. It runs as `uid=1000(app)`, has no `.env` and no `tests`, and shows `GIT_SHA`. Size: 388 MB.
- With compose: migrations `0001` to `0005` run in the container. `/api/health` returns `{"status":"ok","version":"<sha>"}` through nginx. The page, a deep link, creating an application and listing it all work. The cache headers are correct.
- The JSON logs appear in `docker compose logs api`.
- The image refuses to start in two unsafe settings (see Choice 8).

## 5. Not done here

- The image is not pushed to ECR yet (Step 6 or 7).
- The Dockerfile has no `HEALTHCHECK`. On AWS, ECS and the load balancer do the check (Step 5). Compose has its own check for the test.
- CI does not build the image yet. This can be added in Step 6.
