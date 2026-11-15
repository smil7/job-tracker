from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
