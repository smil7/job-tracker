import io
import json
import logging
import sys
from collections.abc import Callable, Iterator

import pytest
from httpx import AsyncClient

from app.config import settings
from app.logging_config import JsonFormatter, request_context, set_user_id


@pytest.fixture
def read_log() -> Iterator[Callable[[], list[dict]]]:
    """Returns a function that gives the JSON lines the app wrote so far, as dicts."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    root.removeHandler(handler)
    root.setLevel(old_level)


def _requests(lines: list[dict]) -> list[dict]:
    return [line for line in lines if line["logger"] == "app.request"]


async def test_each_request_writes_one_log_line(
    raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, read_log
):
    # raw_client uses the real current_user. With login off it is the dev user.
    monkeypatch.setattr(settings, "auth_disabled", True)
    response = await raw_client.get("/api/applications?q=secret-search-text")
    (line,) = _requests(read_log())
    assert line["method"] == "GET"
    assert line["path"] == "/api/applications"
    assert line["status"] == 200
    assert line["duration_ms"] >= 0
    # The line has the same id as the response header
    assert line["request_id"] == response.headers["X-Request-Id"]
    # The user is in the line (the database id, not the email)
    assert "user_id" in line and "@" not in line["user_id"]
    # The query string (search text) is not in the log
    app_lines = [x for x in read_log() if x["logger"] != "httpx"]  # httpx is the test client
    assert "secret-search-text" not in json.dumps(app_lines)


async def test_a_good_request_id_from_the_client_is_kept(client: AsyncClient, read_log):
    response = await client.get("/api/me", headers={"X-Request-Id": "abc-123"})
    assert response.headers["X-Request-Id"] == "abc-123"
    assert _requests(read_log())[0]["request_id"] == "abc-123"


@pytest.mark.parametrize("bad", ["has space", "a" * 65, "<script>", ""])
async def test_a_bad_request_id_is_replaced(client: AsyncClient, bad: str):
    response = await client.get("/api/me", headers={"X-Request-Id": bad})
    assert response.headers["X-Request-Id"] != bad
    assert len(response.headers["X-Request-Id"]) == 32


async def test_failed_requests_are_logged_with_their_status(
    raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, read_log
):
    monkeypatch.setattr(settings, "auth_disabled", False)
    await raw_client.get("/api/applications")  # no token: 401
    (line,) = _requests(read_log())
    assert line["status"] == 401
    assert "user_id" not in line


def test_formatter_writes_json_with_request_data():
    token = request_context.set({"request_id": "r1"})
    try:
        set_user_id("u1")
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("you",), None)
        record.status = 200
        data = json.loads(JsonFormatter().format(record))
    finally:
        request_context.reset(token)
    assert data["message"] == "hello you"
    assert data["level"] == "INFO"
    assert data["request_id"] == "r1"
    assert data["user_id"] == "u1"
    assert data["status"] == 200
    assert "time" in data


def test_formatter_includes_the_stack_trace():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    data = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in data["exception"]


def test_set_user_id_outside_a_request_does_nothing():
    set_user_id("u1")  # must not raise
    assert request_context.get() is None


async def test_unhandled_error_is_logged_with_stack_trace(read_log):
    from starlette.applications import Starlette
    from starlette.routing import Route
    from httpx import ASGITransport

    from app.logging_config import RequestLogMiddleware

    async def boom(_):
        raise RuntimeError("kaboom")

    small = RequestLogMiddleware(Starlette(routes=[Route("/boom", boom)]))
    transport = ASGITransport(app=small, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/boom")
    (line,) = _requests(read_log())
    assert line["level"] == "ERROR"
    assert line["status"] == 500
    assert "RuntimeError: kaboom" in line["exception"]
    assert line["request_id"]


async def test_ai_calls_are_logged_without_the_resume(client: AsyncClient, read_log):
    from tests.test_ai import FakeLLM, make_application, upload_resume
    from app.llm.client import get_llm
    from app.main import app

    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    await client.put("/api/profile", json={"about_me": "my-private-story"})
    await upload_resume(client)
    application_id = await make_application(client, "a-private-job-text")
    assert (await client.post(f"/api/applications/{application_id}/review")).status_code == 201

    ai = [x for x in read_log() if x["logger"] == "app.llm.service"]
    assert [x["message"] for x in ai] == ["AI request started", "AI request finished"]
    assert ai[0]["task"] == "resume_review"
    assert ai[1]["duration_ms"] >= 0 and ai[1]["finish_reason"] == "stop"
    assert ai[0]["request_id"] == ai[1]["request_id"]
    text = json.dumps(read_log())
    assert "my-private-story" not in text and "a-private-job-text" not in text


async def test_failed_ai_call_is_logged_as_warning(client: AsyncClient, read_log):
    from openai import APIConnectionError
    import httpx
    from tests.test_ai import FakeLLM, make_application, upload_resume
    from app.llm.client import get_llm
    from app.main import app

    fake = FakeLLM()

    async def fail(**kwargs):
        raise APIConnectionError(request=httpx.Request("POST", "http://x"))

    fake.chat.completions.create = fail
    app.dependency_overrides[get_llm] = lambda: fake
    await upload_resume(client)
    application_id = await make_application(client)
    assert (await client.post(f"/api/applications/{application_id}/cover-letter", json={})).status_code == 503
    failed = [x for x in read_log() if x["message"] == "AI request failed"]
    assert len(failed) == 1 and failed[0]["level"] == "WARNING"
    assert failed[0]["reason"] == "APIConnectionError" and failed[0]["api_status"] == 503
