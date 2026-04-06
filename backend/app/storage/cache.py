"""Optional Redis cache wrapper for frequently accessed data."""

import json
from typing import Optional, Any
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class Cache:
    """Async Redis cache wrapper with graceful fallback."""

    def __init__(self):
        self._redis = None

    async def connect(self) -> None:
        if not REDIS_AVAILABLE:
            logger.warning("redis_unavailable", msg="Redis package not installed, caching disabled")
            return
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("redis_connected", url=settings.redis_url)
        except Exception as e:
            logger.warning("redis_connect_failed", error=str(e))
            self._redis = None

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Optional[Any]:
        if not self._redis:
            return None
        try:
            val = await self._redis.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        if not self._redis:
            return
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:
            pass

    async def delete(self, key: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return self._redis is not None


cache = Cache()
