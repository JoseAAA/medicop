"""Router de encounters — atenciones del paciente en cualquiera de las 4 áreas."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import LLMUnavailableError, http_not_found
from app.db.models import (
    ClinicalDocument,
    Encounter,
    EncounterStatus,
    HospitalArea,
    Patient,
)
from app.models.clinical_document import (
    ClinicalDocumentRead,
    ClinicalDocumentUpdate,
)
from app.models.encounter import (
    EncounterCreate,
    EncounterDetail,
    EncounterMineItem,
    EncounterRead,
    EncounterStatus as EncounterStatusEnum,
    EncounterTimelineItem,
    TranscriptUpdate,
)
from app.services import audit_service
from app.services.auth_service import CurrentUser
from app.services.clinical_doc_generator import generate_documents_for_encounter
from app.services.encounter_highlights import extract_highlights

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _enum_value(v: object) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _to_timeline_item(encounter: Encounter) -> EncounterTimelineItem:
    return EncounterTimelineItem(
        id=encounter.id,
        area=HospitalArea(_enum_value(encounter.area)),
        status=EncounterStatus(_enum_value(encounter.status)),
        chief_complaint=encounter.chief_complaint,
        started_at=encounter.started_at,
        signed_at=encounter.signed_at,
        document_count=len(encounter.documents),
        highlights=extract_highlights(encounter),  # type: ignore[arg-type]
    )


def _to_detail(encounter: Encounter) -> EncounterDetail:
    return EncounterDetail(
        id=encounter.id,
        patient_id=encounter.patient_id,
        physician_id=encounter.physician_id,
        area=HospitalArea(_enum_value(encounter.area)),
        status=EncounterStatus(_enum_value(encounter.status)),
        chief_complaint=encounter.chief_complaint,
        transcript=encounter.transcript,
        started_at=encounter.started_at,
        signed_at=encounter.signed_at,
        documents=[ClinicalDocumentRead.model_validate(d) for d in encounter.documents],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/", response_model=EncounterRead, summary="Iniciar nuevo encounter")
async def create_encounter(
    body: EncounterCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterRead:
    patient = await db.get(Patient, body.patient_id)
    if patient is None:
        raise http_not_found(f"Paciente {body.patient_id} no encontrado")

    encounter = Encounter(
        patient_id=patient.id,
        physician_id=current_user.id,
        area=body.area.value,
        chief_complaint=body.chief_complaint,
        status=EncounterStatus.OPEN,
    )
    db.add(encounter)
    await db.flush()

    await audit_service.log_interaction(
        db,
        user_id=current_user.id,
        action="encounter_created",
        patient_id=patient.id,
        encounter_id=encounter.id,
        action_taken=f"Iniciado encounter en área {body.area.value}",
    )

    await db.commit()
    await db.refresh(encounter)
    return EncounterRead.model_validate(encounter)


@router.get(
    "/by-patient/{patient_id}",
    response_model=list[EncounterTimelineItem],
    summary="Timeline cruzado del paciente entre las 4 áreas",
)
async def get_patient_timeline(
    patient_id: str,
    current_user: CurrentUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EncounterTimelineItem]:
    patient = await db.get(Patient, patient_id)
    if patient is None:
        raise http_not_found(f"Paciente {patient_id} no encontrado")

    stmt = (
        select(Encounter)
        .where(Encounter.patient_id == patient_id)
        .order_by(Encounter.started_at.desc())
    )
    result = await db.execute(stmt)
    encounters = result.scalars().all()
    return [_to_timeline_item(e) for e in encounters]


@router.get(
    "/mine",
    response_model=list[EncounterMineItem],
    summary="Atenciones del médico actual — para widgets del dashboard",
)
async def list_my_encounters(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: EncounterStatusEnum | None = None,
    limit: int = 10,
) -> list[EncounterMineItem]:
    """Últimas atenciones del médico autenticado, opcionalmente filtradas por
    status. Incluye nombre y NHC del paciente embebidos para evitar requests
    adicionales en el frontend.
    """
    stmt = (
        select(Encounter, Patient)
        .join(Patient, Encounter.patient_id == Patient.id)
        .where(Encounter.physician_id == current_user.id)
        .order_by(Encounter.started_at.desc())
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(Encounter.status == status.value)

    result = await db.execute(stmt)
    items: list[EncounterMineItem] = []
    for encounter, patient in result.all():
        items.append(
            EncounterMineItem(
                id=encounter.id,
                patient_id=patient.id,
                patient_nhc=patient.nhc,
                patient_full_name=patient.full_name,
                area=HospitalArea(_enum_value(encounter.area)),
                status=EncounterStatus(_enum_value(encounter.status)),
                chief_complaint=encounter.chief_complaint,
                started_at=encounter.started_at,
                signed_at=encounter.signed_at,
            )
        )
    return items


@router.get("/{encounter_id}", response_model=EncounterDetail, summary="Detalle del encounter")
async def get_encounter(
    encounter_id: str,
    current_user: CurrentUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterDetail:
    encounter = await db.get(Encounter, encounter_id)
    if encounter is None:
        raise http_not_found(f"Encounter {encounter_id} no encontrado")
    return _to_detail(encounter)


@router.patch(
    "/{encounter_id}/transcript",
    response_model=EncounterRead,
    summary="Guardar/actualizar la transcripción de la conversación",
)
async def update_transcript(
    encounter_id: str,
    body: TranscriptUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterRead:
    encounter = await db.get(Encounter, encounter_id)
    if encounter is None:
        raise http_not_found(f"Encounter {encounter_id} no encontrado")

    encounter.transcript = body.transcript
    await audit_service.log_interaction(
        db,
        user_id=current_user.id,
        action="transcript_updated",
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
    )
    await db.commit()
    await db.refresh(encounter)
    return EncounterRead.model_validate(encounter)


@router.post(
    "/{encounter_id}/generate-docs",
    response_model=EncounterDetail,
    summary="Pedir al LLM que pre-llene los documentos clínicos del encounter",
)
async def generate_docs(
    encounter_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> EncounterDetail:
    encounter = await db.get(Encounter, encounter_id)
    if encounter is None:
        raise http_not_found(f"Encounter {encounter_id} no encontrado")

    # Orquestador: RAG + LLM + chequeo de alergias. Persiste documentos en la BD.
    try:
        result = await generate_documents_for_encounter(db, encounter)
    except LLMUnavailableError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Cualquier otra falla (JSON corrupto irrecuperable, BD, etc.) —
        # devolvemos 503 con mensaje accionable en vez de 500 genérico.
        # Evita que el frontend muestre "Error 500" sin contexto.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No se pudieron generar los documentos en este momento. "
                "Intenta de nuevo en unos segundos."
            ),
        ) from exc

    encounter.status = EncounterStatus.DOCUMENTS_READY

    await audit_service.log_interaction(
        db,
        user_id=current_user.id,
        action="documents_generated",
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        query=encounter.transcript or encounter.chief_complaint,
        ai_response=str(result.get("summary", "")),
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(encounter)
    return _to_detail(encounter)


@router.patch(
    "/{encounter_id}/documents/{document_id}",
    response_model=ClinicalDocumentRead,
    summary="Edición inline del documento por el médico antes de firmar",
)
async def update_document(
    encounter_id: str,
    document_id: str,
    body: ClinicalDocumentUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClinicalDocumentRead:
    doc = await db.get(ClinicalDocument, document_id)
    if doc is None or doc.encounter_id != encounter_id:
        raise http_not_found(f"Documento {document_id} no encontrado en encounter {encounter_id}")
    if doc.is_signed:
        raise http_not_found("El documento ya está firmado y no puede editarse")

    if body.content is not None:
        doc.content = body.content

    await audit_service.log_interaction(
        db,
        user_id=current_user.id,
        action="document_edited",
        encounter_id=encounter_id,
        edited_response=str(body.content) if body.content else None,
    )
    await db.commit()
    await db.refresh(doc)
    return ClinicalDocumentRead.model_validate(doc)


@router.post(
    "/{encounter_id}/sign",
    response_model=EncounterDetail,
    summary="Firmar y archivar el encounter (audit log inmutable)",
)
async def sign_encounter(
    encounter_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> EncounterDetail:
    encounter = await db.get(Encounter, encounter_id)
    if encounter is None:
        raise http_not_found(f"Encounter {encounter_id} no encontrado")
    if encounter.status == EncounterStatus.SIGNED:
        return _to_detail(encounter)

    now = datetime.now(timezone.utc)
    encounter.status = EncounterStatus.SIGNED
    encounter.signed_at = now

    for doc in encounter.documents:
        if not doc.is_signed:
            doc.is_signed = True
            doc.signed_at = now

    await audit_service.log_interaction(
        db,
        user_id=current_user.id,
        action="encounter_signed",
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        ip_address=request.client.host if request.client else None,
        action_taken=f"Firmado con {len(encounter.documents)} documento(s)",
    )

    await db.commit()
    await db.refresh(encounter)
    return _to_detail(encounter)
