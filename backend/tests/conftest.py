from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import Depends, Header
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.auth import current_user, get_or_create_user
from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import User

# Send this header to act as user B. Without a header the request is made by user A.
AS_B = {"X-Test-User": "b"}


@pytest.fixture
async def db_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # Fresh schema per test against the dedicated test database
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def raw_client(
    db_sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """A client with the real login check. Use it to test login itself."""

    async def override() -> AsyncIterator[AsyncSession]:
        async with db_sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def client(raw_client: AsyncClient) -> AsyncClient:
    """A client that is already logged in as user A. Add AS_B to a request to be user B."""

    async def fake_current_user(
        session: Annotated[AsyncSession, Depends(get_session)],
        x_test_user: Annotated[str, Header()] = "a",
    ) -> User:
        return await get_or_create_user(session, f"test-{x_test_user}", f"{x_test_user}@example.com")

    app.dependency_overrides[current_user] = fake_current_user
    return raw_client
