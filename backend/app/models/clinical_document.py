from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    SOAP = "soap"
    PRESCRIPTION = "prescription"
    LAB_ORDER = "lab_order"
    IMAGING_ORDER = "imaging_order"
    REFERRAL = "referral"
    EVOLUTION_NOTE = "evolution_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    PRE_OP_NOTE = "pre_op_note"
    SURGICAL_REPORT = "surgical_report"
    POST_OP_NOTE = "post_op_note"
    TRIAGE_NOTE = "triage_note"
    ADMISSION_NOTE = "admission_note"
    DIFFERENTIAL_DIAGNOSES = "differential_diagnoses"


class Citation(BaseModel):
    """Cita obligatoria — toda afirmación clínica del LLM viene con una de estas."""

    guideline_id: str | None = None
    guideline_name: str
    section: str
    page: int | None = None
    text_excerpt: str = ""


class ClinicalDocumentRead(BaseModel):
    id: str
    encounter_id: str
    doc_type: DocumentType
    content: dict = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    is_signed: bool = False
    signed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClinicalDocumentUpdate(BaseModel):
    """Actualización inline desde el editor del médico antes de firmar."""

    content: dict | None = None


# ─── Estructuras tipadas por tipo de documento (referencia para el frontend) ──


class SOAPContent(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    cie10_codes: list[str] = Field(default_factory=list)
    plan: str = ""


class PrescriptionDrug(BaseModel):
    name: str
    dose: str
    route: str = "oral"
    frequency: str
    duration: str
    notes: str | None = None


class PrescriptionContent(BaseModel):
    drugs: list[PrescriptionDrug] = Field(default_factory=list)
    indications: str | None = None


class LabOrderItem(BaseModel):
    name: str
    urgency: str = "rutina"  # rutina | urgente | stat
    indication: str | None = None


class LabOrderContent(BaseModel):
    tests: list[LabOrderItem] = Field(default_factory=list)
