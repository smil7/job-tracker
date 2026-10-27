from datetime import date

from httpx import AsyncClient


async def create(client: AsyncClient, **fields) -> dict:
    payload = {"company": "Acme", "role": "Graduate Software Engineer", **fields}
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_defaults(client: AsyncClient):
    app = await create(client)
    assert app["status"] == "applied"
    assert app["applied_at"] == date.today().isoformat()
    assert len(app["events"]) == 1
    assert app["events"][0]["to_status"] == "applied"


async def test_wishlist_has_no_applied_date(client: AsyncClient):
    app = await create(client, status="wishlist")
    assert app["applied_at"] is None


async def test_create_requires_company_and_role(client: AsyncClient):
    response = await client.post("/api/applications", json={"company": "Acme"})
    assert response.status_code == 422


async def test_status_change_logs_event(client: AsyncClient):
    app = await create(client)
    response = await client.patch(f"/api/applications/{app['id']}", json={"status": "interview"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "interview"
    latest = body["events"][0]
    assert (latest["from_status"], latest["to_status"]) == ("applied", "interview")

    # Same status again is not a change
    response = await client.patch(f"/api/applications/{app['id']}", json={"status": "interview"})
    assert len(response.json()["events"]) == 2


async def test_wishlist_to_applied_sets_date(client: AsyncClient):
    app = await create(client, status="wishlist")
    response = await client.patch(f"/api/applications/{app['id']}", json={"status": "applied"})
    assert response.json()["applied_at"] == date.today().isoformat()


async def test_edit_fields_without_status(client: AsyncClient):
    app = await create(client)
    response = await client.patch(
        f"/api/applications/{app['id']}", json={"notes": "Referral from Sara", "location": "Dubai"}
    )
    body = response.json()
    assert body["notes"] == "Referral from Sara"
    assert body["location"] == "Dubai"
    assert len(body["events"]) == 1


async def test_list_filter_and_search(client: AsyncClient):
    await create(client, company="Emirates Group", role="Graduate Programme")
    await create(client, company="Careem", role="Junior Backend Engineer", status="interview")
    await create(client, company="Noon", role="Data Analyst", location="Dubai")

    all_apps = (await client.get("/api/applications")).json()
    assert len(all_apps) == 3

    interviews = (await client.get("/api/applications", params={"status": "interview"})).json()
    assert [a["company"] for a in interviews] == ["Careem"]

    search = (await client.get("/api/applications", params={"q": "dubai"})).json()
    assert [a["company"] for a in search] == ["Noon"]

    by_company = (await client.get("/api/applications", params={"sort": "company"})).json()
    assert [a["company"] for a in by_company] == ["Careem", "Emirates Group", "Noon"]


async def test_note_event_and_delete(client: AsyncClient):
    app = await create(client)
    response = await client.post(
        f"/api/applications/{app['id']}/events", json={"note": "Recruiter called"}
    )
    assert response.status_code == 201
    assert response.json()["to_status"] is None

    detail = (await client.get(f"/api/applications/{app['id']}")).json()
    assert len(detail["events"]) == 2

    assert (await client.delete(f"/api/applications/{app['id']}")).status_code == 204
    assert (await client.get(f"/api/applications/{app['id']}")).status_code == 404


async def test_stats(client: AsyncClient):
    a = await create(client)
    b = await create(client)
    await create(client)
    await create(client, status="wishlist")
    await client.patch(f"/api/applications/{a['id']}", json={"status": "interview"})
    await client.patch(f"/api/applications/{a['id']}", json={"status": "rejected"})
    await client.patch(f"/api/applications/{b['id']}", json={"status": "offer"})

    stats = (await client.get("/api/stats")).json()
    assert stats["total_applied"] == 3
    assert stats["active"] == 1
    assert stats["interviews"] == 2  # a interviewed before rejection, b reached offer
    assert stats["offers"] == 1
    assert stats["applied_this_week"] == 3
    assert stats["response_rate"] == round(2 / 3, 3)
    assert stats["by_status"]["wishlist"] == 1


async def test_stats_ignore_undone_moves(client: AsyncClient):
    a = await create(client)
    for status in ("assessment", "applied"):
        await client.patch(f"/api/applications/{a['id']}", json={"status": status})

    stats = (await client.get("/api/stats")).json()
    assert stats["response_rate"] == 0
    assert stats["interviews"] == 0

    # Undoing a rejection drops the response but keeps the interview reached before it
    for status in ("interview", "rejected", "interview"):
        await client.patch(f"/api/applications/{a['id']}", json={"status": status})
    stats = (await client.get("/api/stats")).json()
    assert stats["interviews"] == 1
    assert stats["response_rate"] == 1

    await client.patch(f"/api/applications/{a['id']}", json={"status": "applied"})
    stats = (await client.get("/api/stats")).json()
    assert (stats["interviews"], stats["response_rate"]) == (0, 0)
