import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.logging_config import RequestLogMiddleware, setup_logging
from app.routers import ai, applications, me, profile, stats

setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Refuse to start with an unsafe login setup, instead of running with an open API
    settings.check_auth_config()
    yield


app = FastAPI(title="Job Tracker API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last, so it is the outer layer: it sees every request and every answer
app.add_middleware(RequestLogMiddleware)

app.include_router(applications.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(me.router, prefix="/api")


logger = logging.getLogger(__name__)

HEALTH_DB_TIMEOUT_SECONDS = 3


class Health(BaseModel):
    status: str
    version: str


@app.get(
    "/api/health",
    tags=["meta"],
    response_model=Health,
    responses={503: {"model": Health, "description": "The database does not answer"}},
)
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> Health | JSONResponse:
    """Is the API up AND can it reach the database? The load balancer calls this. No login."""
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), HEALTH_DB_TIMEOUT_SECONDS)
    except Exception:
        # Do not send the error text to the caller: it can show the database address
        logger.exception("Health check failed: the database does not answer")
        body = Health(status="unavailable", version=settings.git_sha)
        return JSONResponse(body.model_dump(), status_code=503)
    return Health(status="ok", version=settings.git_sha)
