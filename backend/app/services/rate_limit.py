"""
Rate limiting basado en Redis (sliding fixed window).

Uso típico:
    allowed, count = await check_rate_limit(f"login:{ip}", 5, 900)
    if not allowed:
        raise HTTPException(429, "Demasiados intentos")

También expone helpers para mantener una lista de revocación de JWT (logout).
"""
from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


# ─── Rate limiting ───────────────────────────────────────────────────────────


async def check_rate_limit(
    key: str,
    *,
    max_attempts: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Ventana fija con TTL. Retorna (allowed, current_count)."""
    r = await _get_redis()
    full_key = f"medicop:rl:{key}"
    count = await r.incr(full_key)
    if count == 1:
        await r.expire(full_key, window_seconds)
    return count <= max_attempts, count


async def reset_rate_limit(key: str) -> None:
    """Útil tras un login exitoso — el contador se borra para esa IP."""
    r = await _get_redis()
    await r.delete(f"medicop:rl:{key}")


# ─── Token revocation list (logout) ──────────────────────────────────────────


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """Inserta el `jti` (JWT ID) en Redis con TTL ≈ tiempo restante del token."""
    if ttl_seconds <= 0:
        return
    r = await _get_redis()
    await r.setex(f"medicop:revoked:{jti}", ttl_seconds, "1")


async def is_token_revoked(jti: str) -> bool:
    r = await _get_redis()
    return bool(await r.exists(f"medicop:revoked:{jti}"))
