"""
Servicio de audit log inmutable.

Cada acción relevante (login, generación de documento por IA, firma de
encounter, edición de documento) debe registrar una fila aquí. La tabla es
append-only — nunca se modifica ni elimina.

Conforme Ley 29733 Perú — trazabilidad de acceso a datos de salud.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def log_interaction(
    db: AsyncSession,
    user_id: str,
    action: str,
    patient_id: str | None = None,
    encounter_id: str | None = None,
    query: str | None = None,
    ai_response: str | None = None,
    edited_response: str | None = None,
    action_taken: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Inserta un registro en `audit_logs`. No hace commit — el caller decide."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        patient_id=patient_id,
        encounter_id=encounter_id,
        query=query,
        ai_response=ai_response,
        edited_response=edited_response,
        action_taken=action_taken,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
