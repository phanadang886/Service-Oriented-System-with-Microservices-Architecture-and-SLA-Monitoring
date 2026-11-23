"""Notification API routes.

Gateway forwards the path unchanged, so every route lives under
/api/notification.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/notification", tags=["Notification"])


@router.get("/health")
def api_health() -> dict:
    """Smoke test through the gateway. Real endpoints arrive in week 2."""
    return {"status": "ok", "service": "notification"}
