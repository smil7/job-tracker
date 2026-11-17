import asyncio
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.ai_quota as ai_quota
from app.config import settings
from app.models import AIUsage
from tests.conftest import AS_B
from tests.test_ai import FakeLLM, make_application, upload_resume

# The `llm` fixture (the fake model) comes from tests/test_ai.py
from tests.test_ai import llm  # noqa: F401


@pytest.fixture(autouse=True)
def small_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_daily_limit", 3)


async def ready(client: AsyncClient, headers: dict | None = None) -> str:
    """A user with a resume and an application. Returns the application id."""
    await client.put(
        "/api/profile/resume",
        files={"file": ("cv.pdf", b"%PDF-1.4\n", "application/pdf")},
        headers=headers,
    )
    response = await client.post(
        "/api/applications",
        json={"company": "Acme", "role": "Engineer", "job_description": "Python"},
        headers=headers,
    )
    return response.json()["id"]


async def review(client: AsyncClient, application_id: str, headers: dict | None = None):
    return await client.post(f"/api/applications/{application_id}/review", headers=headers)


async def letter(client: AsyncClient, application_id: str, headers: dict | None = None):
    return await client.post(
        f"/api/applications/{application_id}/cover-letter", json={}, headers=headers
    )


async def test_request_number_limit_plus_one_is_429(client: AsyncClient, llm: FakeLLM):
    application_id = await ready(client)
    for _ in range(3):
        assert (await review(client, application_id)).status_code == 201
    blocked = await review(client, application_id)
    assert blocked.status_code == 429
    assert "3 requests per day" in blocked.json()["detail"]
    assert 1 <= int(blocked.headers["Retry-After"]) <= 86400
    # The model was not called for the blocked request: no cost
    assert len(llm.calls) == 3


async def test_reviews_and_letters_share_one_limit(client: AsyncClient, llm: FakeLLM):
    application_id = await ready(client)
    assert (await review(client, application_id)).status_code == 201
    assert (await letter(client, application_id)).status_code == 200
    assert (await review(client, application_id)).status_code == 201
    assert (await letter(client, application_id)).status_code == 429
    assert (await review(client, application_id)).status_code == 429


async def test_each_user_has_their_own_count(client: AsyncClient, llm: FakeLLM):
    a = await ready(client)
    b = await ready(client, AS_B)
    for _ in range(3):
        await review(client, a)
    assert (await review(client, a)).status_code == 429
    assert (await review(client, b, AS_B)).status_code == 201


async def test_the_count_starts_again_the_next_day(
    client: AsyncClient, llm: FakeLLM, monkeypatch: pytest.MonkeyPatch
):
    application_id = await ready(client)
    for _ in range(3):
        await review(client, application_id)
    assert (await review(client, application_id)).status_code == 429
    monkeypatch.setattr(ai_quota, "_today", lambda: date(2099, 1, 2))
    assert (await review(client, application_id)).status_code == 201


async def test_requests_at_the_same_time_cannot_pass_the_limit(client: AsyncClient, llm: FakeLLM):
    application_id = await ready(client)
    results = await asyncio.gather(*(review(client, application_id) for _ in range(10)))
    codes = sorted(r.status_code for r in results)
    assert codes == [201] * 3 + [429] * 7
    assert len(llm.calls) == 3


async def test_a_limit_of_zero_turns_the_ai_off(
    client: AsyncClient, llm: FakeLLM, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "ai_daily_limit", 0)
    application_id = await ready(client)
    assert (await review(client, application_id)).status_code == 429
    assert llm.calls == []


async def test_requests_that_fail_the_checks_do_not_count(client: AsyncClient, llm: FakeLLM):
    # No resume yet: 400, not counted
    application_id = await make_application(client)
    for _ in range(5):
        assert (await review(client, application_id)).status_code == 400
    await upload_resume(client)
    for _ in range(3):
        assert (await review(client, application_id)).status_code == 201


async def test_a_failed_model_call_still_counts(client: AsyncClient, llm: FakeLLM):
    llm.finish_reason = "length"  # the model call "fails" with a 502
    application_id = await ready(client)
    for _ in range(3):
        assert (await review(client, application_id)).status_code == 502
    assert (await review(client, application_id)).status_code == 429


async def test_delete_me_removes_the_usage_rows(
    client: AsyncClient, llm: FakeLLM, db_sessions: async_sessionmaker[AsyncSession]
):
    await review(client, await ready(client))
    await review(client, await ready(client, AS_B), AS_B)
    assert (await client.delete("/api/me")).status_code == 204
    async with db_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(AIUsage)) == 1
