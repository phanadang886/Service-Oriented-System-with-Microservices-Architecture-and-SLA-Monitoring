import json
import logging
import redis.asyncio as redis
from services.catalog.app.config import settings

logger = logging.getLogger("catalog.redis")

redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Kiểm tra kết nối ping
            await redis_client.ping()
        except Exception as e:
            logger.warning(f"Không thể kết nối Redis ({settings.REDIS_URL}): {e}. Sẽ đọc trực tiếp Database.")
            redis_client = None
    return redis_client


async def get_cache(key: str) -> dict | list | None:
    client = await get_redis()
    if not client:
        return None
    try:
        val = await client.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.warning(f"Lỗi khi đọc cache {key}: {e}")
    return None


async def set_cache(key: str, value: dict | list, ttl_seconds: int = settings.CACHE_TTL_SECONDS):
    client = await get_redis()
    if not client:
        return
    try:
        await client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Lỗi khi ghi cache {key}: {e}")


async def invalidate_catalog_cache(pattern: str = "catalog:*"):
    client = await get_redis()
    if not client:
        return
    try:
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
            logger.info(f"Đã xoá {len(keys)} keys cache khớp pattern {pattern}")
    except Exception as e:
        logger.warning(f"Lỗi khi xoá cache pattern {pattern}: {e}")
