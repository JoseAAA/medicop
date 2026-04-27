"""Modelos SQLAlchemy de MediCop.

Las tablas se crean automáticamente al arrancar el backend (lifespan en main.py)
mediante `Base.metadata.create_all()`. Para producción real, sustituir por
migraciones Alembic.

Modelo de dominio:
    User (médico) ──< Encounter >── Patient
                          │
                          └──< ClinicalDocument
    Guideline (independiente — corpus indexado en Qdrant + metadata aquí)
    AuditLog (append-only, referencia transversal)
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────


class HospitalArea(str, enum.Enum):
    """Las 4 áreas hospitalarias por las que puede pasar un paciente."""

    EMERGENCIA = "emergencia"
    HOSPITALIZACION = "hospitalizacion"
    CONSULTA_EXTERNA = "consulta_externa"
    CIRUGIA = "cirugia"


class EncounterStatus(str, enum.Enum):
    """Ciclo de vida de un encounter."""

    OPEN = "open"                          # iniciado, grabación / pre-llenado en curso
    DOCUMENTS_READY = "documents_ready"    # LLM ya generó documentos, médico revisa
    SIGNED = "signed"                      # médico firmó y archivó (audit log inmutable)
    CANCELLED = "cancelled"


class DocumentType(str, enum.Enum):
    """Tipos de documentos clínicos pre-llenados por el LLM, según el área."""

    # Consulta externa
    SOAP = "soap"
    PRESCRIPTION = "prescription"
    LAB_ORDER = "lab_order"
    IMAGING_ORDER = "imaging_order"
    REFERRAL = "referral"
    # Hospitalización
    EVOLUTION_NOTE = "evolution_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    # Cirugía
    PRE_OP_NOTE = "pre_op_note"
    SURGICAL_REPORT = "surgical_report"
    POST_OP_NOTE = "post_op_note"
    # Emergencia
    TRIAGE_NOTE = "triage_note"
    ADMISSION_NOTE = "admission_note"
    # Asistencia clínica — diagnósticos sugeridos
    DIFFERENTIAL_DIAGNOSES = "differential_diagnoses"


# ──────────────────────────────────────────────────────────────────────────────
# Tablas
# ──────────────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    cmp_number: Mapped[str | None] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Patient(Base):
    """Paciente — entidad central que atraviesa las 4 áreas hospitalarias.

    Identificadores:
    - **nhc** (Número de Historia Clínica): identificador clínico interno del
      hospital. Es el que el médico usa para buscar al paciente. Único por
      hospital. Independiente de si el paciente tiene DNI.
    - **dni**: documento nacional, útil para SIS / EsSalud / facturación.
      Puede no existir (extranjeros, recién nacidos sin DNI tramitado).
    """

    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    nhc: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    dni: Mapped[str | None] = mapped_column(String(12), unique=True, nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[datetime] = mapped_column(DateTime)
    sex: Mapped[str] = mapped_column(String(1))

    # Contexto clínico longitudinal — visible en cualquier encounter futuro
    allergies: Mapped[list[str]] = mapped_column(JSONB, default=list)
    active_conditions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    current_medications: Mapped[list[str]] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    encounters: Mapped[list["Encounter"]] = relationship(
        back_populates="patient",
        order_by="Encounter.started_at.desc()",
        lazy="selectin",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Encounter(Base):
    """Una instancia de atención del paciente en alguna de las 4 áreas.

    Reemplaza al modelo Consultation original — es más amplio porque cubre
    consulta externa, emergencia, hospitalización y cirugía.
    """

    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    physician_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    area: Mapped[HospitalArea] = mapped_column(
        Enum(HospitalArea, name="hospital_area"),
        nullable=False,
        index=True,
    )
    status: Mapped[EncounterStatus] = mapped_column(
        Enum(EncounterStatus, name="encounter_status"),
        default=EncounterStatus.OPEN,
        nullable=False,
    )

    chief_complaint: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)         # texto plano (cifrado en F2)
    audio_path: Mapped[str | None] = mapped_column(String(500))  # ruta cifrada en disco

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["Patient"] = relationship(back_populates="encounters", lazy="selectin")
    documents: Mapped[list["ClinicalDocument"]] = relationship(
        back_populates="encounter",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ClinicalDocument(Base):
    """Documento clínico pre-llenado por el LLM dentro de un encounter.

    Ejemplos: nota SOAP, receta, orden de laboratorio, reporte operatorio.
    El médico puede editar `content` antes de firmar (`is_signed=True`).
    """

    __tablename__ = "clinical_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    encounter_id: Mapped[str] = mapped_column(
        ForeignKey("encounters.id"), nullable=False, index=True
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False
    )

    # Estructura libre por tipo de documento (JSONB):
    #   SOAP: {subjective, objective, assessment, cie10_codes, plan}
    #   PRESCRIPTION: {drugs: [{name, dose, route, frequency, duration, ...}]}
    #   LAB_ORDER: {tests: [{name, urgency, indication}]}
    #   ...
    content: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Citas a guías clínicas que respaldan el contenido (siempre obligatorio)
    citations: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    # Red flags detectadas por el LLM (síntomas de alarma, conflictos con alergias, etc.)
    red_flags: Mapped[list[str]] = mapped_column(JSONB, default=list)

    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    encounter: Mapped["Encounter"] = relationship(back_populates="documents")


class Guideline(Base):
    """Guía clínica oficial (MINSA, IETSI, OMS, PNUME).

    Para el MVP demo, el contenido se genera manualmente en `data-pipeline/
    seed-corpus/` y se carga desde ahí. Cuando lleguen guías oficiales reales,
    los registros con `is_demo=True` pueden filtrarse o reemplazarse.

    Los chunks embebidos viven en Qdrant (collection `clinical_guidelines`).
    Esta tabla guarda los metadatos para listar/buscar por área.
    """

    __tablename__ = "guidelines"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    institution: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(100))  # cardiologia, infectologia, ...

    # Áreas hospitalarias donde aplica esta guía (lista de HospitalArea.value)
    applicable_areas: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Markdown completo de la guía (insumo para chunkear + embeber en F2)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Marca explícita: ¿es contenido de ejemplo demostrativo o guía oficial real?
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):
    """Registro inmutable — NO se eliminan ni modifican filas de esta tabla.

    Conforme Ley 29733 Perú: trazabilidad de acceso a datos de salud.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"))
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id"))
    action: Mapped[str] = mapped_column(String(100))
    query: Mapped[str | None] = mapped_column(Text)
    ai_response: Mapped[str | None] = mapped_column(Text)
    edited_response: Mapped[str | None] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(50))
