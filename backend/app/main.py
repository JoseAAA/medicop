import time
import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.database import Base, engine
from app.core.logger import configure_logging
from app.routers import auth, encounters, health, patients, rag, transcription

settings = get_settings()
configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("medicop_startup", environment=settings.environment)

    # Crear tablas si no existen (modo demo — para producción usar Alembic).
    # SQLAlchemy import necesario para que Base.metadata conozca todas las tablas:
    from app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("medicop_db_ready")

    # Seed automático en desarrollo (idempotente — no duplica si ya hay datos)
    if settings.is_development and settings.seed_on_startup:
        from app.db.seed import seed_demo_data

        try:
            seeded = await seed_demo_data()
            if seeded:
                logger.info("medicop_seed_loaded", patients=seeded["patients"], guidelines=seeded["guidelines"])
            else:
                logger.info("medicop_seed_skipped", reason="data_already_present")
        except Exception as exc:
            logger.warning("medicop_seed_failed", error=str(exc), exc_info=True)

        # Indexa las guías en Qdrant (idempotente — point IDs son determinísticos).
        # Carga el modelo de embeddings la primera vez (descarga ~120 MB de HF).
        try:
            from app.core.database import AsyncSessionLocal
            from app.services import rag_service

            async with AsyncSessionLocal() as session:
                rag_result = await rag_service.index_all_guidelines(session)
            logger.info(
                "medicop_rag_indexed",
                guidelines=rag_result["guidelines"],
                chunks=rag_result["chunks"],
            )
        except Exception as exc:
            logger.warning("medicop_rag_index_failed", error=str(exc), exc_info=True)

        # Pre-carga Whisper en background — primera transcripción del usuario será
        # rápida (sin esperar download/load del modelo de ~244 MB).
        try:
            import asyncio

            from app.services import whisper_service

            async def _warm_whisper() -> None:
                try:
                    await asyncio.to_thread(whisper_service._get_model)
                    logger.info("medicop_whisper_warmed", model=settings.whisper_model)
                except Exception as exc:
                    logger.warning("medicop_whisper_warm_failed", error=str(exc))

            asyncio.create_task(_warm_whisper())
        except Exception as exc:
            logger.warning("medicop_whisper_warm_setup_failed", error=str(exc))

    yield
    logger.info("medicop_shutdown")


app = FastAPI(
    title="MediCop API",
    description=(
        "Asistente clínico local con IA para hospitales en LATAM. "
        "Todos los datos permanecen en la infraestructura del hospital (Ley 29733 Perú)."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,                    # necesario para httpOnly cookie
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    max_age=3600,
)


# Security headers — aplicados a TODA respuesta. Defensa en profundidad
# contra XSS, clickjacking, MIME sniffing y filtración de referer.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",                        # bloquea sniffing MIME
    "X-Frame-Options": "DENY",                                  # previene clickjacking
    "Referrer-Policy": "strict-origin-when-cross-origin",       # no filtra paths a 3os
    "Permissions-Policy": "camera=(), microphone=(self), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",                # aísla del browsing context
    # CSP simple — el frontend Next.js maneja la suya con más detalle.
    # Strict-Transport-Security se añade SOLO en producción (requiere HTTPS).
}


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Coroutine[Any, Any, Response]],
) -> Response:
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    request.state.request_id = request_id

    bound = logger.bind(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        bound.error("http_unhandled_error", error=str(exc), duration_ms=duration_ms, exc_info=True)
        response = JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

    # Security headers en cada respuesta
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if not settings.is_development:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
        )

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    bound.info("http_request", status=response.status_code, duration_ms=duration_ms)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(patients.router, prefix="/api/patients", tags=["patients"])
app.include_router(encounters.router, prefix="/api/encounters", tags=["encounters"])
app.include_router(transcription.router, prefix="/api/transcription", tags=["transcription"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
