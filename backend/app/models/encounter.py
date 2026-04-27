from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.clinical_document import ClinicalDocumentRead


class HospitalArea(str, Enum):
    EMERGENCIA = "emergencia"
    HOSPITALIZACION = "hospitalizacion"
    CONSULTA_EXTERNA = "consulta_externa"
    CIRUGIA = "cirugia"


class EncounterStatus(str, Enum):
    OPEN = "open"
    DOCUMENTS_READY = "documents_ready"
    SIGNED = "signed"
    CANCELLED = "cancelled"


class EncounterCreate(BaseModel):
    patient_id: str
    area: HospitalArea
    chief_complaint: str | None = None


class EncounterRead(BaseModel):
    id: str
    patient_id: str
    physician_id: str
    area: HospitalArea
    status: EncounterStatus
    chief_complaint: str | None = None
    transcript: str | None = None
    started_at: datetime
    signed_at: datetime | None = None

    model_config = {"from_attributes": True}


class EncounterDetail(EncounterRead):
    """Encounter con sus documentos clínicos cargados."""

    documents: list[ClinicalDocumentRead] = Field(default_factory=list)


class EncounterHighlights(BaseModel):
    """Campos clínicos clave extraídos de los documentos de una atención.

    Estos son los datos que el médico necesita ver de un vistazo y que
    el LLM debe recibir como contexto al pre-llenar una nueva atención.
    """

    diagnosis: str | None = None
    cie10_codes: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    lab_tests: list[str] = Field(default_factory=list)
    plan: str | None = None


class EncounterTimelineItem(BaseModel):
    """Resumen rico de una atención para el timeline del paciente."""

    id: str
    area: HospitalArea
    status: EncounterStatus
    chief_complaint: str | None = None
    started_at: datetime
    signed_at: datetime | None = None
    document_count: int = 0
    highlights: EncounterHighlights = Field(default_factory=EncounterHighlights)


class EncounterMineItem(BaseModel):
    """Encounter del médico actual con datos del paciente embebidos
    — para los widgets del dashboard (atenciones sin firmar / pacientes recientes)."""

    id: str
    patient_id: str
    patient_nhc: str
    patient_full_name: str
    area: HospitalArea
    status: EncounterStatus
    chief_complaint: str | None = None
    started_at: datetime
    signed_at: datetime | None = None


class TranscriptUpdate(BaseModel):
    transcript: str = Field(..., min_length=1)
