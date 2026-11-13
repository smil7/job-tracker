"""One user must never see or change the data of another user.

User A is the default in tests. User B is made by adding AS_B to the request.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.llm.client import get_llm
from app.main import app
from app.models import Application, CoverLetter, Profile, ResumeReview, StatusEvent, User
from tests.conftest import AS_B
from tests.test_ai import PDF, FakeLLM


@pytest.fixture
def llm(client: AsyncClient) -> FakeLLM:
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    return fake


async def add_application(client: AsyncClient, headers: dict | None = None, **fields) -> dict:
    payload = {"company": "Acme", "role": "Engineer", "job_description": "Python, SQL", **fields}
    response = await client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def add_resume(client: AsyncClient, headers: dict | None = None) -> None:
    response = await client.put(
        "/api/profile/resume", files={"file": ("cv.pdf", PDF, "application/pdf")}, headers=headers
    )
    assert response.status_code == 200, response.text


# ---------- applications ----------


async def test_lists_show_only_own_applications(client: AsyncClient):
    await add_application(client, company="A-only")
    await add_application(client, AS_B, company="B-only")

    a = (await client.get("/api/applications")).json()
    b = (await client.get("/api/applications", headers=AS_B)).json()
    assert [x["company"] for x in a] == ["A-only"]
    assert [x["company"] for x in b] == ["B-only"]


async def test_search_does_not_leak_across_users(client: AsyncClient):
    await add_application(client, company="Secret Corp")
    response = await client.get("/api/applications", params={"q": "Secret"}, headers=AS_B)
    assert response.json() == []


async def test_other_users_application_is_404_on_every_route(client: AsyncClient):
    app_a = await add_application(client)
    url = f"/api/applications/{app_a['id']}"

    assert (await client.get(url, headers=AS_B)).status_code == 404
    assert (await client.patch(url, json={"notes": "hacked"}, headers=AS_B)).status_code == 404
    assert (await client.delete(url, headers=AS_B)).status_code == 404
    assert (await client.post(f"{url}/events", json={"note": "x"}, headers=AS_B)).status_code == 404

    # ... and nothing changed for the owner
    mine = (await client.get(url)).json()
    assert mine["notes"] is None
    assert len(mine["events"]) == 1


async def test_unknown_id_and_other_users_id_look_the_same(client: AsyncClient):
    app_a = await add_application(client)
    other = await client.get(f"/api/applications/{app_a['id']}", headers=AS_B)
    unknown = await client.get(f"/api/applications/{uuid.uuid4()}", headers=AS_B)
    assert other.status_code == unknown.status_code == 404
    assert other.json() == unknown.json()  # B cannot tell that the id exists


async def test_stats_count_only_own_applications(client: AsyncClient):
    await add_application(client, status="applied")
    await add_application(client, status="interview")
    await add_application(client, AS_B, status="offer")

    a = (await client.get("/api/stats")).json()
    b = (await client.get("/api/stats", headers=AS_B)).json()
    assert a["total_applied"] == 2
    assert a["interviews"] == 1
    assert a["offers"] == 0
    assert b["total_applied"] == 1
    assert b["offers"] == 1
    assert b["interviews"] == 1  # B has an offer, so B did interview. The interview of A is not counted.


# ---------- profile ----------


async def test_profiles_are_separate(client: AsyncClient):
    await client.put("/api/profile", json={"about_me": "I am A"})
    await add_resume(client)

    b = (await client.get("/api/profile", headers=AS_B)).json()
    assert b["about_me"] is None
    assert b["has_resume"] is False
    assert (await client.get("/api/profile/resume", headers=AS_B)).status_code == 404

    await client.put("/api/profile", json={"about_me": "I am B"}, headers=AS_B)
    assert (await client.get("/api/profile")).json()["about_me"] == "I am A"
    assert (await client.get("/api/profile")).json()["has_resume"] is True


# ---------- AI results ----------


async def test_other_users_ai_results_are_404(client: AsyncClient, llm: FakeLLM):
    await add_resume(client)
    app_a = await add_application(client)
    base = f"/api/applications/{app_a['id']}"
    assert (await client.post(f"{base}/review")).status_code == 201
    assert (await client.post(f"{base}/cover-letter", json={})).status_code == 200
    calls_before = len(llm.calls)

    for method, path, kwargs in [
        ("GET", "/review", {}),
        ("POST", "/review", {}),
        ("GET", "/cover-letter", {}),
        ("POST", "/cover-letter", {"json": {}}),
        ("PUT", "/cover-letter", {"json": {"content": "mine now"}}),
        ("GET", "/cover-letter.docx", {}),
    ]:
        response = await client.request(method, base + path, headers=AS_B, **kwargs)
        assert response.status_code == 404, f"{method} {path} gave {response.status_code}"

    assert len(llm.calls) == calls_before  # the attempts of B never reached the AI (no cost)


async def test_ai_uses_the_resume_of_the_caller_only(client: AsyncClient, llm: FakeLLM):
    await add_resume(client)  # A has a resume. B does not.
    app_b = await add_application(client, AS_B)
    response = await client.post(f"/api/applications/{app_b['id']}/review", headers=AS_B)
    assert response.status_code == 400
    assert "resume" in response.json()["detail"].lower()
    assert llm.calls == []


# ---------- delete my account ----------


async def test_delete_me_removes_everything_of_the_user_only(
    client: AsyncClient, llm: FakeLLM, db_sessions: async_sessionmaker[AsyncSession]
):
    await add_resume(client)
    app_a = await add_application(client)
    await client.post(f"/api/applications/{app_a['id']}/review")
    await client.post(f"/api/applications/{app_a['id']}/cover-letter", json={})
    await client.patch(f"/api/applications/{app_a['id']}", json={"status": "interview"})
    app_b = await add_application(client, AS_B)
    await add_resume(client, AS_B)

    response = await client.delete("/api/me")
    assert response.status_code == 204

    async with db_sessions() as session:

        async def count(model) -> int:
            return await session.scalar(select(func.count()).select_from(model))

        # Only the rows of B are left, in every table
        assert await count(User) == 1
        assert await count(Application) == 1
        assert await count(Profile) == 1
        assert await count(StatusEvent) == 1  # the "Added" event of B
        assert await count(ResumeReview) == 0
        assert await count(CoverLetter) == 0

    still_there = await client.get(f"/api/applications/{app_b['id']}", headers=AS_B)
    assert still_there.status_code == 200


async def test_me_returns_the_caller(client: AsyncClient):
    a = (await client.get("/api/me")).json()
    b = (await client.get("/api/me", headers=AS_B)).json()
    assert a["email"] == "a@example.com"
    assert b["email"] == "b@example.com"
    assert a["id"] != b["id"]


# ---------- every private route needs a login ----------


def _private_routes() -> list[tuple[str, str]]:
    # The OpenAPI schema lists every route, also those of included routers
    routes = []
    for path, operations in app.openapi()["paths"].items():
        if path == "/api/health":
            continue
        for method in operations:
            routes.append((method.upper(), path))
    return routes


def test_there_are_private_routes_to_check():
    # Guards the guard: if this list is empty, the test below proves nothing
    assert len(_private_routes()) >= 15


@pytest.mark.parametrize("method,path", _private_routes())
async def test_every_private_route_needs_login(
    raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, method: str, path: str
):
    monkeypatch.setattr(settings, "auth_disabled", False)
    url = path.replace("{application_id}", str(uuid.uuid4()))
    response = await raw_client.request(method, url)
    assert response.status_code == 401, f"{method} {path} is open to everyone"


async def test_health_stays_public(raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    assert (await raw_client.get("/api/health")).status_code == 200
