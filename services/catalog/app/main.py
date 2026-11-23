from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator

from services.catalog.app.config import settings
from services.catalog.app.database import init_db
from services.catalog.app.routers.catalog import router as catalog_router
from services.common.errors import AppException, app_exception_handler, validation_exception_handler
from services.common.middleware import RequestIDMiddleware

CUSTOM_PROMETHEUS_BUCKETS = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as e:
        print(f"[catalog-service] DB init warning (sẽ dùng migration khi lên Docker): {e}")
    yield


app = FastAPI(
    title="Catalog Service",
    description="Dịch vụ danh mục khoa, bác sĩ và khung giờ khám",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(RequestIDMiddleware)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/health"],
    inprogress_name="catalog_requests_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app, metric_namespace="catalog_service", latency_lowr_buckets=CUSTOM_PROMETHEUS_BUCKETS)
instrumentator.expose(app, endpoint="/metrics")

app.include_router(catalog_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME
    }
