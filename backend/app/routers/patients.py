"""Router de pacientes — listado, búsqueda por DNI, detalle."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import http_not_found
from app.db.models import Patient
from app.models.patient import PatientRead
from app.services.auth_service import CurrentUser

router = APIRouter()


def _age_from_birth_date(birth_date: datetime) -> int:
    today = datetime.now(timezone.utc)
    bd = birth_date if birth_date.tzinfo else birth_date.replace(tzinfo=timezone.utc)
    years = today.year - bd.year
    if (today.month, today.day) < (bd.month, bd.day):
        years -= 1
    return max(years, 0)


def _to_read(p: Patient) -> PatientRead:
    return PatientRead(
        id=p.id,
        nhc=p.nhc,
        dni=p.dni,
        first_name=p.first_name,
        last_name=p.last_name,
        birth_date=p.birth_date.date(),
        sex=p.sex,
        age=_age_from_birth_date(p.birth_date),
        full_name=p.full_name,
        allergies=list(p.allergies or []),
        active_conditions=list(p.active_conditions or []),
        current_medications=list(p.current_medications or []),
    )


@router.get("/", response_model=list[PatientRead], summary="Listar pacientes")
async def list_patients(
    current_user: CurrentUser,  # noqa: ARG001 — fuerza autenticación
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(description="Búsqueda por NHC, DNI, apellido o nombre")] = None,
    limit: int = 50,
) -> list[PatientRead]:
    stmt = select(Patient).order_by(Patient.last_name, Patient.first_name).limit(limit)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Patient.nhc.ilike(like),
                Patient.dni.ilike(like),
                Patient.last_name.ilike(like),
                Patient.first_name.ilike(like),
            )
        )

    result = await db.execute(stmt)
    return [_to_read(p) for p in result.scalars().all()]


@router.get("/{patient_id}", response_model=PatientRead, summary="Detalle de paciente")
async def get_patient(
    patient_id: str,
    current_user: CurrentUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PatientRead:
    patient = await db.get(Patient, patient_id)
    if patient is None:
        raise http_not_found(f"Paciente {patient_id} no encontrado")
    return _to_read(patient)
