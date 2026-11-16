from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.main import app


async def test_health_reports_ok_and_version(raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "git_sha", "abc1234")
    response = await raw_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc1234"}


async def test_health_needs_no_login(raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    assert (await raw_client.get("/api/health")).status_code == 200


async def test_health_is_503_when_the_database_fails(raw_client: AsyncClient):
    class BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise ConnectionRefusedError("postgres://user:secret-password@db.internal:5432/x")

    async def broken() -> AsyncIterator[AsyncSession]:
        yield BrokenSession()  # type: ignore[misc]

    app.dependency_overrides[get_session] = broken
    response = await raw_client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    # The error text (it can hold the database address and password) is not sent to the caller
    assert "secret-password" not in response.text


async def test_health_is_503_when_the_database_is_too_slow(
    raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    import asyncio

    import app.main as main

    class SlowSession:
        async def execute(self, *_args, **_kwargs):
            await asyncio.sleep(5)

    async def slow() -> AsyncIterator[AsyncSession]:
        yield SlowSession()  # type: ignore[misc]

    monkeypatch.setattr(main, "HEALTH_DB_TIMEOUT_SECONDS", 0.05)
    app.dependency_overrides[get_session] = slow
    assert (await raw_client.get("/api/health")).status_code == 503
