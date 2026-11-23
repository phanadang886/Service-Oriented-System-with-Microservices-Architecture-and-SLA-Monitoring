"""Booking API routes.

Gateway forwards the path unchanged, so every route lives under /api/booking.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/booking", tags=["Booking"])


@router.get("/health")
def api_health() -> dict:
    """Smoke test through the gateway. Real endpoints arrive in week 2."""
    return {"status": "ok", "service": "booking"}
