import asyncio

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from sqlalchemy import text

from app.config import get_settings
from app.core.database import engine

router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, str]


async def _check_postgres() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_redis() -> str:
    try:
        client = aioredis.from_url(settings.redis_url, socket_timeout=2)
        await client.ping()
        await client.aclose()
        return "ok"
    except Exception:
        return "error"


async def _check_qdrant() -> str:
    try:
        client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=3)
        await client.get_collections()
        await client.close()
        return "ok"
    except Exception:
        return "error"


async def _check_ollama() -> str:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            return "ok" if r.status_code == 200 else "error"
    except Exception:
        return "error"


@router.get("/health", response_model=HealthResponse, summary="Healthcheck del sistema")
async def health_check() -> HealthResponse:
    """Verifica conectividad real con todos los servicios dependientes."""
    postgres, redis, qdrant, ollama = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        _check_qdrant(),
        _check_ollama(),
        return_exceptions=False,
    )

    services: dict[str, str] = {
        "api": "ok",
        "database": postgres,
        "redis": redis,
        "qdrant": qdrant,
        "ollama": ollama,
    }
    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"

    return HealthResponse(status=overall, version="0.1.0", services=services)
