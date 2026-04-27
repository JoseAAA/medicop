"""Router de transcripción — sube audio, devuelve texto en español."""
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.services import whisper_service
from app.services.auth_service import CurrentUser

router = APIRouter()

# Comparamos sólo el media type — el browser anexa el codec
# (e.g. "audio/webm;codecs=opus") y antes lo rechazábamos por strict match.
ALLOWED_MEDIA_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "application/octet-stream",  # los navegadores a veces envían esto
}


def _normalize_media_type(content_type: str | None) -> str:
    """Devuelve sólo el tipo y subtipo: `audio/webm;codecs=opus` → `audio/webm`."""
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()

MAX_AUDIO_BYTES = 50 * 1024 * 1024  # 50 MB


class TranscriptionResponse(BaseModel):
    transcript: str
    language: str
    language_probability: float
    duration_seconds: float
    segments: list[dict[str, Any]]


@router.post(
    "/",
    response_model=TranscriptionResponse,
    summary="Transcribir un audio (Whisper, español)",
)
async def transcribe_audio(
    current_user: CurrentUser,  # noqa: ARG001
    file: UploadFile = File(..., description="Archivo de audio (wav, mp3, m4a, ogg, webm)"),
) -> TranscriptionResponse:
    media_type = _normalize_media_type(file.content_type)
    if media_type and media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de audio no soportado: {file.content_type}",
        )

    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archivo vacío",
        )
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio supera el límite de {MAX_AUDIO_BYTES // (1024 * 1024)} MB",
        )

    result = await whisper_service.transcribe(audio_bytes, filename_hint=file.filename or "audio.wav")
    return TranscriptionResponse(
        transcript=result["text"],
        language=result["language"],
        language_probability=result["language_probability"],
        duration_seconds=result["duration_seconds"],
        segments=result["segments"],
    )
