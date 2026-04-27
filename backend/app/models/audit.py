from datetime import datetime

from pydantic import BaseModel


class AuditEntry(BaseModel):
    """Registro inmutable de cada interacción médico-IA. Conforme Ley 29733."""

    id: str
    timestamp: datetime
    user_id: str
    patient_id: str | None = None
    encounter_id: str | None = None
    action: str
    query: str | None = None
    ai_response: str | None = None
    edited_response: str | None = None
    action_taken: str | None = None
    ip_address: str | None = None

    model_config = {"from_attributes": True}
