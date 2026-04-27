from datetime import date

from pydantic import BaseModel, Field


class PatientBase(BaseModel):
    nhc: str = Field(..., min_length=4, max_length=20, description="Número de Historia Clínica")
    dni: str | None = Field(None, min_length=8, max_length=12, description="DNI peruano (opcional)")
    first_name: str
    last_name: str
    birth_date: date
    sex: str = Field(..., pattern="^(M|F)$")


class PatientCreate(PatientBase):
    allergies: list[str] = Field(default_factory=list)
    active_conditions: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)


class PatientRead(PatientBase):
    id: str
    age: int
    full_name: str
    allergies: list[str] = Field(default_factory=list)
    active_conditions: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PatientContext(BaseModel):
    """Contexto inyectado en prompts del LLM. Nunca incluye datos fuera del modelo."""

    patient_id: str
    age: int
    sex: str
    chief_complaint: str | None = None
    active_conditions: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    # Resumen cruzado de encounters previos en cualquier área (insumo del LLM)
    recent_encounters_summary: str | None = None
