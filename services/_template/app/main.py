"""Application entry point.

Run locally with:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
"""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Replace with service name",
    version="0.0.1",
)

# One router per feature area. Register new routers here, never inline# route definitions in this file.
app.include_router(health_router)