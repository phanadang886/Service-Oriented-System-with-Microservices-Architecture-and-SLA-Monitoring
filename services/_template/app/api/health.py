"""Health check endpoint.

Every service returns the same response shape so the four containers can be
compared without special-casing. Docker Compose polls this URL to decide
when a service is ready to accept traffic.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Fixed shape returned by /health."""

    status: str
    service: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Liveness probe.

    Returns as soon as the HTTP server accepts requests. It deliberately
    does not check the database: a database outage should not make Docker
    restart the container, and dependency ordering is already handled by
    `depends_on` in docker-compose.yml.
    """
    return HealthResponse(status="ok", service="replace-with-service-name")