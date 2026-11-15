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
