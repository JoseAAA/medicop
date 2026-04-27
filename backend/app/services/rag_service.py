"""
Servicio RAG — chunking + embeddings + Qdrant.

Carga lazy del modelo de embeddings (sentence-transformers MiniLM multilingüe).
Estructura del corpus:
    Guideline (Postgres) ──► chunks por sección ──► embeddings ──► Qdrant

Cada punto en Qdrant lleva en su payload metadatos suficientes para citar:
    {
        "guideline_id": ...,
        "guideline_name": ...,
        "institution": ...,
        "section": "1. Definición y diagnóstico",
        "applicable_areas": ["consulta_externa", ...],
        "text": "...",
    }
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Guideline

logger = structlog.get_logger()
settings = get_settings()

# Cache global del embedder y del cliente Qdrant (lazy, una vez por proceso).
_embedder: Any = None
_qdrant: AsyncQdrantClient | None = None


def _get_embedder() -> Any:
    """Carga sentence-transformers en el primer uso (~120 MB MiniLM, descarga 1ª vez)."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        logger.info("rag_loading_embedder", model=settings.embedding_model)
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def _get_qdrant() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _qdrant


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────


_SECTION_PATTERN = re.compile(r"(?=^##\s+\d+\.)", re.MULTILINE)
_HEADER_PATTERN = re.compile(r"^##\s+(.+?)$", re.MULTILINE)


def chunk_guideline_content(content: str) -> list[dict[str, str]]:
    """Divide el markdown de una guía por secciones `## N. Título`."""
    sections = _SECTION_PATTERN.split(content)
    chunks: list[dict[str, str]] = []
    for sec in sections:
        sec = sec.strip()
        if len(sec) < 80:  # ignora encabezado y secciones muy cortas
            continue
        first_line = sec.split("\n", 1)[0]
        m = _HEADER_PATTERN.match(first_line)
        section_title = m.group(1).strip() if m else "Sección"
        chunks.append({"section": section_title, "text": sec})
    return chunks


def _stable_point_id(guideline_id: str, section: str) -> str:
    """ID determinístico — re-indexar la misma sección sustituye en lugar de duplicar."""
    raw = f"{guideline_id}::{section}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()
    return str(uuid.UUID(digest[:32]))


# ─────────────────────────────────────────────────────────────────────────────
# Indexación
# ─────────────────────────────────────────────────────────────────────────────


async def ensure_collection() -> None:
    """Crea la colección si no existe. Idempotente."""
    qdrant = _get_qdrant()
    collections = await qdrant.get_collections()
    names = {c.name for c in collections.collections}
    if settings.qdrant_collection_guidelines in names:
        return
    await qdrant.create_collection(
        collection_name=settings.qdrant_collection_guidelines,
        vectors_config=qmodels.VectorParams(
            size=settings.embedding_dim,
            distance=qmodels.Distance.COSINE,
        ),
    )
    logger.info("rag_collection_created", name=settings.qdrant_collection_guidelines)


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embeddings en batch — bloquea CPU; lo lanzamos en thread para no congelar el loop."""
    embedder = _get_embedder()

    def _encode() -> list[list[float]]:
        vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    return await asyncio.to_thread(_encode)


async def index_guideline(guideline: Guideline) -> int:
    """Chunkea + embebe + upsert en Qdrant. Retorna número de chunks indexados."""
    chunks = chunk_guideline_content(guideline.content)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    vectors = await _embed_batch(texts)

    points = []
    for chunk, vec in zip(chunks, vectors, strict=False):
        payload = {
            "guideline_id": guideline.id,
            "guideline_name": guideline.title,
            "institution": guideline.institution,
            "section": chunk["section"],
            "applicable_areas": list(guideline.applicable_areas or []),
            "text": chunk["text"],
            "is_demo": guideline.is_demo,
        }
        points.append(
            qmodels.PointStruct(
                id=_stable_point_id(guideline.id, chunk["section"]),
                vector=vec,
                payload=payload,
            )
        )

    qdrant = _get_qdrant()
    await qdrant.upsert(
        collection_name=settings.qdrant_collection_guidelines,
        points=points,
    )
    return len(points)


async def index_all_guidelines(db: AsyncSession) -> dict[str, int]:
    """Recorre todas las guías en Postgres y las indexa en Qdrant."""
    await ensure_collection()
    result = await db.execute(select(Guideline))
    guidelines = result.scalars().all()

    total_chunks = 0
    for g in guidelines:
        n = await index_guideline(g)
        total_chunks += n
        logger.info("rag_guideline_indexed", title=g.title, chunks=n)

    return {"guidelines": len(guidelines), "chunks": total_chunks}


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda
# ─────────────────────────────────────────────────────────────────────────────


async def search(
    query: str,
    *,
    area: str | None = None,
    top_k: int = 5,
    score_threshold: float = 0.25,
) -> list[dict[str, Any]]:
    """Busca chunks relevantes. Filtra por área si se especifica."""
    if not query.strip():
        return []

    vectors = await _embed_batch([query])
    query_vector = vectors[0]

    query_filter = None
    if area:
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="applicable_areas",
                    match=qmodels.MatchAny(any=[area]),
                )
            ]
        )

    qdrant = _get_qdrant()
    # qdrant-client >= 1.10 reemplazó `search()` por `query_points()`
    response = await qdrant.query_points(
        collection_name=settings.qdrant_collection_guidelines,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True,
    )

    return [
        {
            "score": r.score,
            "guideline_id": (r.payload or {}).get("guideline_id"),
            "guideline_name": (r.payload or {}).get("guideline_name"),
            "institution": (r.payload or {}).get("institution"),
            "section": (r.payload or {}).get("section"),
            "text": (r.payload or {}).get("text"),
            "applicable_areas": (r.payload or {}).get("applicable_areas", []),
        }
        for r in response.points
    ]


async def health_check() -> bool:
    """Verifica conexión con Qdrant."""
    try:
        qdrant = _get_qdrant()
        await qdrant.get_collections()
        return True
    except Exception:
        return False
