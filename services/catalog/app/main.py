"""Application entry point.

Run locally with:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
"""
import os

from fastapi import FastAPI

from app.api.health import router as health_router

# Path prefix that the gateway strips before forwarding, for example
# "/api/auth" for auth-service.
#
# FastAPI needs this because the Swagger page is plain HTML that loads
# first, then asks the browser for /openapi.json. Without root_path the
# browser asks the gateway for /openapi.json, which no route serves, and
# the docs page shows "Failed to load API definition".
SERVICE_PREFIX = os.getenv("SERVICE_PREFIX", "")

app = FastAPI(
    title=os.getenv("SERVICE_NAME", "service"),
    version="0.0.1",
    root_path=SERVICE_PREFIX,
)

# One router per feature area. Register new routers here, never inline
# route definitions in this file.
app.include_router(health_router)