"""
iBuum Agent 0.1 — FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.routes import training
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="iBuum Agent",
    description=(
        "Independent external backend worker for the iBuum ecosystem. "
        "Exposes a deterministic training recommendation API consumed by "
        "Base44."
    ),
    version=settings.agent_version,
)

app.include_router(training.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Simple liveness/health check endpoint. No authentication required."""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.agent_version,
    }
