# syntax=docker/dockerfile:1

# ---- Stage 1: install the packages ----
# This stage has `uv`. The final image does not need it.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
# Pre-compile the .pyc files so the app starts faster. Copy files (no links) to the venv.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Copy only the two lock files first. Docker keeps this layer while they do not change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

# ---- Stage 2: the image that runs ----
FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app

# A user that is not root. If someone breaks into the app, they get fewer rights.
RUN useradd --system --uid 1000 --no-create-home app

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
# The migration task needs these two
COPY alembic ./alembic
COPY alembic.ini ./

# The health check shows this value. The deploy sets it to the git commit.
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000
# --proxy-headers: the load balancer sends the real client address in a header.
# One worker is enough for one user and a small task (0.25 vCPU).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
