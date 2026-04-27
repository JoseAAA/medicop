"""Excepciones de dominio MediCop."""
from fastapi import HTTPException, status


class MediCopError(Exception):
    pass


class PatientNotFoundError(MediCopError):
    pass


class EncounterNotFoundError(MediCopError):
    pass


class UnauthorizedError(MediCopError):
    pass


class LLMUnavailableError(MediCopError):
    """Ollama no disponible — el sistema debe seguir operativo sin LLM."""
    pass


# HTTP shortcuts
def http_not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def http_unauthorized(detail: str = "No autorizado") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def http_forbidden(detail: str = "Acceso denegado") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
