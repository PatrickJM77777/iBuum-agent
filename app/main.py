"""
iBuum Agent 0.1 — FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import training, workout
from app.core.config import get_settings

# Standard logger. Only technical metadata is ever logged here (exception
# type/message, request path). Full request bodies (age, weight, cycle
# context, user_id, etc.) are never logged — see app/services/cycle_context.py,
# app/services/training_rules.py, and app/api/routes/training.py, none of
# which log the payload.
logger = logging.getLogger("ibuum_agent")

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
app.include_router(workout.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Safety net for unexpected internal errors.

    Ensures a stack trace or exception message is never leaked to the
    client (no internal details, no secrets, no request payload echoed
    back). Only the exception type and request path are logged
    server-side for debugging; the request body itself is never logged.
    """
    logger.exception(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Simple liveness/health check endpoint. No authentication required."""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.agent_version,
    }
