"""Application entry point."""
import os

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from services.notification.app.api.health import router as health_router
from services.notification.app.routers.notification import router as notification_router

# Buckets tuỳ chỉnh theo cam kết SLO (docs/architecture.md mục 8.2).
CUSTOM_PROMETHEUS_BUCKETS = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)

SERVICE_PREFIX = os.getenv("SERVICE_PREFIX", "")

app = FastAPI(
    title=os.getenv("SERVICE_NAME", "notification"),
    version="0.0.1",
    root_path=SERVICE_PREFIX,
)

instrumentator = Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/health"],
)
instrumentator.instrument(
    app,
    metric_namespace="notification_service",
    latency_lowr_buckets=CUSTOM_PROMETHEUS_BUCKETS,
)
instrumentator.expose(app, endpoint="/metrics")

app.include_router(health_router)
app.include_router(notification_router)
