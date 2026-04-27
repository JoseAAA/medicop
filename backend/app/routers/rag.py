"""Router RAG — búsqueda en guías clínicas indexadas y consulta de fuentes."""
import re
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import http_not_found
from app.db.models import Guideline
from app.models.guideline import GuidelineDetail, GuidelineRead
from app.services import rag_service
from app.services.auth_service import CurrentUser

router = APIRouter()


class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    area: str | None = Field(None, description="Filtrar por área hospitalaria aplicable")
    top_k: int = Field(5, ge=1, le=20)


class RAGSearchHit(BaseModel):
    score: float
    guideline_id: str | None = None
    guideline_name: str
    institution: str
    section: str
    text: str
    applicable_areas: list[str] = Field(default_factory=list)


class RAGSearchResponse(BaseModel):
    query: str
    hits: list[RAGSearchHit]


class GuidelineSection(BaseModel):
    """Una sección extraída de una guía clínica."""

    section_title: str
    text: str


class GuidelineSectionResponse(BaseModel):
    """Respuesta cuando el médico hace clic en una cita.

    Incluye metadata de la guía + la sección específica resaltada.
    """

    guideline: GuidelineRead
    section: GuidelineSection | None = None
    """Sección que coincide con `?section=`. Si None, se devuelve la primera."""


# Mismo patrón que el chunker — secciones empiezan con "## N."
_SECTION_PATTERN = re.compile(r"(?=^##\s+\d+\.)", re.MULTILINE)
_HEADER_PATTERN = re.compile(r"^##\s+(.+?)$", re.MULTILINE)


def _split_sections(content: str) -> list[GuidelineSection]:
    sections: list[GuidelineSection] = []
    for raw in _SECTION_PATTERN.split(content):
        block = raw.strip()
        if len(block) < 50:
            continue
        first_line = block.split("\n", 1)[0]
        m = _HEADER_PATTERN.match(first_line)
        title = m.group(1).strip() if m else "Sección"
        sections.append(GuidelineSection(section_title=title, text=block))
    return sections


@router.post("/search", response_model=RAGSearchResponse, summary="Buscar en guías clínicas")
async def search_guidelines(
    body: RAGSearchRequest,
    current_user: CurrentUser,  # noqa: ARG001
) -> RAGSearchResponse:
    hits_raw = await rag_service.search(body.query, area=body.area, top_k=body.top_k)
    hits = [RAGSearchHit(**h) for h in hits_raw]
    return RAGSearchResponse(query=body.query, hits=hits)


@router.get("/sources", response_model=list[GuidelineRead], summary="Listar guías indexadas")
async def list_sources(
    current_user: CurrentUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[GuidelineRead]:
    result = await db.execute(select(Guideline).order_by(Guideline.title))
    return [GuidelineRead.model_validate(g) for g in result.scalars().all()]


@router.get(
    "/sources/{guideline_id}",
    response_model=GuidelineDetail,
    summary="Contenido completo de una guía clínica",
)
async def get_guideline(
    guideline_id: str,
    current_user: CurrentUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GuidelineDetail:
    g = await db.get(Guideline, guideline_id)
    if g is None:
        raise http_not_found(f"Guía {guideline_id} no encontrada")
    return GuidelineDetail.model_validate(g)


@router.get(
    "/sources/{guideline_id}/section",
    response_model=GuidelineSectionResponse,
    summary="Devuelve una sección específica de la guía (para cuando el médico hace clic en una cita)",
)
async def get_guideline_section(
    guideline_id: str,
    current_user: CurrentUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],
    section: str | None = None,
) -> GuidelineSectionResponse:
    g = await db.get(Guideline, guideline_id)
    if g is None:
        raise http_not_found(f"Guía {guideline_id} no encontrada")

    sections = _split_sections(g.content)

    chosen: GuidelineSection | None = None
    if section:
        needle = section.lower().strip()
        # Match flexible: el LLM a veces escribe "1. Definición" o sólo "Definición"
        for s in sections:
            t = s.section_title.lower()
            if t == needle or needle in t or t in needle:
                chosen = s
                break
    if chosen is None and sections:
        chosen = sections[0]

    return GuidelineSectionResponse(
        guideline=GuidelineRead.model_validate(g),
        section=chosen,
    )
