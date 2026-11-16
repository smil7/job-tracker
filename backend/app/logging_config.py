"""Logging: one JSON object per line, written to stdout.

On AWS the ECS `awslogs` driver sends stdout to CloudWatch Logs. CloudWatch can search JSON
fields, so one request can be found by its `request_id`. No log file is needed.

Rule: never log tokens, resume text, about-me text, search text or API keys.
"""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Data of the request that is running now. The middleware makes the dict. `current_user` fills
# in `user_id` later. A dict is used so a value set deep in the request is still seen when the
# middleware writes the last log line.
request_context: ContextVar[dict[str, Any] | None] = ContextVar("request_context", default=None)

REQUEST_ID_HEADER = "X-Request-Id"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

# Attributes that every LogRecord has. Anything else came from `extra={...}` and is logged.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName", "color_message"}


def set_user_id(user_id: str) -> None:
    """Tell the logger who is making the request. Use the database id, never the email."""
    context = request_context.get()
    if context is not None:  # there is no context outside a request
        context["user_id"] = user_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        data.update(request_context.get() or {})
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                data[key] = value
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


_HANDLER_NAME = "jobtracker-json"


def setup_logging(level: str = "INFO") -> None:
    """Send all logs to stdout as JSON. Safe to call more than once."""
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() != _HANDLER_NAME]
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn has its own handlers and its own text format. Use ours for its messages.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    # The request middleware writes one line per request, so the access log would be a duplicate
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False


request_logger = logging.getLogger("app.request")


class RequestLogMiddleware:
    """Gives each request an id, times it, and writes one log line when it ends.

    This is a plain ASGI middleware (not BaseHTTPMiddleware), so the context variables work
    in every route and dependency.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        # Only accept a safe id from the client. Otherwise make one.
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_context.set({"request_id": request_id})
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            # Log the error with its stack trace, then let the server answer 500
            request_logger.exception("Unhandled error", extra=_fields(scope, 500, started))
            raise
        else:
            # Health checks run every few seconds. Log them only when they fail.
            quiet = scope["path"] == "/api/health" and status_code < 400
            level = logging.DEBUG if quiet else logging.INFO
            request_logger.log(level, "Request", extra=_fields(scope, status_code, started))
        finally:
            request_context.reset(token)


def _fields(scope: Scope, status_code: int, started: float) -> dict[str, Any]:
    # The query string is not logged: it can hold the search text of a user.
    return {
        "method": scope["method"],
        "path": scope["path"],
        "status": status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }
