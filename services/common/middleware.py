import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("microservice")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        # Ghi log kèm Request ID
        logger.info(f"[{request_id}] {request.method} {request.url.path}")

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
