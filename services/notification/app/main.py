from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Notification Service", description="Phụ trách: Đông (Tuần 2)")

instrumentator = Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/health"]
)
instrumentator.instrument(app, metric_namespace="notification_service")
instrumentator.expose(app, endpoint="/metrics")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": "notification-service"}
