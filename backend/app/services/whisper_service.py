"""
Servicio Whisper — transcripción con faster-whisper.

Carga lazy del modelo (configurable via env). Para el demo MVP corre con
WHISPER_MODEL=small en CPU + INT8 (~244M params, ~700 MB RAM, ~3-5x real-time
en CPU moderna). Para mayor calidad y velocidad: large-v3-turbo en GPU.

Notas de seguridad: el audio crudo NO se guarda en disco fuera de un archivo
temporal que se elimina inmediatamente tras transcribir. La transcripción
final se persiste en `encounters.transcript` (texto plano por ahora; cifrado
AES-256 en reposo es trabajo futuro).
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_model: Any = None


def _get_model() -> Any:
    """Carga faster-whisper en el primer uso. Reutiliza la instancia."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        logger.info(
            "whisper_loading",
            model=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


async def transcribe(audio_bytes: bytes, *, filename_hint: str = "audio.wav") -> dict[str, Any]:
    """Transcribe audio bytes a texto en español. Retorna texto + metadata."""
    suffix = os.path.splitext(filename_hint)[1] or ".wav"

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(audio_bytes)

        model = _get_model()

        def _run() -> dict[str, Any]:
            segments, info = model.transcribe(
                tmp_path,
                language=settings.whisper_language,
                beam_size=1,             # demo: priorizar velocidad sobre exactitud
                vad_filter=True,         # filtra silencios (mejor calidad)
                without_timestamps=False,
            )
            seg_list = list(segments)
            text = " ".join(s.text.strip() for s in seg_list).strip()
            return {
                "text": text,
                "language": info.language,
                "language_probability": float(info.language_probability),
                "duration_seconds": float(info.duration),
                "segments": [
                    {"start": s.start, "end": s.end, "text": s.text.strip()}
                    for s in seg_list
                ],
            }

        return await asyncio.to_thread(_run)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
