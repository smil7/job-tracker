from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import applications, stats

app = FastAPI(title="Job Tracker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
