from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator

from services.auth.app.config import settings
from services.auth.app.database import init_db
from services.auth.app.routers.auth import router as auth_router
from services.common.errors import AppException, app_exception_handler, validation_exception_handler
from services.common.middleware import RequestIDMiddleware

# Buckets tuỳ chỉnh theo cam kết SLO và ghi chú quyết định (architecture.md mục 8.2)
CUSTOM_PROMETHEUS_BUCKETS = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng cơ sở dữ liệu nếu chưa tồn tại
    try:
        await init_db()
    except Exception as e:
        print(f"[auth-service] DB init warning (sẽ dùng migration khi lên Docker): {e}")
    yield


app = FastAPI(
    title="Auth Service",
    description="Dịch vụ quản lý tài khoản và xác thực người dùng",
    version="1.0.0",
    lifespan=lifespan
)

# Đăng ký Middleware
app.add_middleware(RequestIDMiddleware)

# Đăng ký Exception Handlers chuẩn hoá lỗi
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Cấu hình Prometheus Instrumentator với custom buckets
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/health"],
    inprogress_name="auth_requests_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app, metric_namespace="auth_service")
instrumentator.expose(app, endpoint="/metrics")

# Router chính
app.include_router(auth_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME
    }
