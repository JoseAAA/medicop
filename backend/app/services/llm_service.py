"""
Servicio LLM — cliente Ollama para MedGemma 4B.

`generate_json` fuerza salida JSON (Ollama soporta `format="json"` con MedGemma).
Si Ollama no responde tras un reintento, lanza LLMUnavailableError — el caller
decide si caer en modo degradado.

Notas operativas:
- `timeout` explícito de 5 min: el primer call frío de MedGemma puede tomar
  20-60 s mientras se carga; sin timeout explícito httpx aborta antes.
- `keep_alive="30m"`: indica a Ollama mantener el modelo en VRAM tras la
  request — evita la recarga lenta entre requests cercanos.
- Reintento único en errores de conexión transitorios: con
  `OLLAMA_NUM_PARALLEL=1` un segundo request mientras hay uno en vuelo a
  veces se desconecta. Un retry resuelve la colisión transitoria.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import ollama
import structlog

from app.config import get_settings
from app.core.exceptions import LLMUnavailableError

logger = structlog.get_logger()
settings = get_settings()

_client: ollama.AsyncClient | None = None

LLM_TIMEOUT_SECONDS = 300.0  # 5 min — cubre primer call frío + generación larga


def _get_client() -> ollama.AsyncClient:
    global _client
    if _client is None:
        _client = ollama.AsyncClient(
            host=settings.ollama_base_url,
            timeout=LLM_TIMEOUT_SECONDS,
        )
    return _client


_RETRYABLE_EXC = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.NetworkError,
)


async def generate(
    prompt: str,
    *,
    system: str | None = None,
    format: str | None = None,
    temperature: float = 0.1,
    num_predict: int = 5500,
) -> str:
    """Llamada cruda al LLM. Reintenta una vez ante errores de conexión
    transitorios (típicos cuando Ollama está procesando otro request)."""
    client = _get_client()
    options = {
        "temperature": temperature,
        "num_predict": num_predict,
        # MedGemma 4B soporta hasta 128k, pero VRAM limita; 8192 cubre prompt
        # (sistema + paciente + RAG + transcripción) + JSON de respuesta largo.
        "num_ctx": 8192,
    }

    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            response = await client.generate(
                model=settings.ollama_model,
                prompt=prompt,
                system=system or "",
                format=format or "",
                options=options,
                stream=False,
                keep_alive="30m",
            )
            return response.get("response", "")
        except _RETRYABLE_EXC as exc:
            last_exc = exc
            logger.warning(
                "llm_transient_error",
                attempt=attempt,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if attempt == 1:
                await asyncio.sleep(2.0)
                continue
        except httpx.HTTPError as exc:
            logger.error("llm_http_error", error=str(exc))
            raise LLMUnavailableError(f"El asistente devolvió error: {exc}") from exc

    logger.error("llm_unreachable_after_retry", error=str(last_exc))
    raise LLMUnavailableError(
        "El asistente clínico no respondió a tiempo. Intenta generar de nuevo."
    ) from last_exc


async def generate_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.1,
    num_predict: int = 5500,
) -> dict[str, Any]:
    """Pide salida JSON al LLM y la parsea.

    Si el JSON viene truncado (típico cuando el modelo se queda sin tokens en
    mitad de una cadena), intenta repararlo cerrando la string + balanceando
    `{` y `[`. Esto salva el ~95% de los truncamientos sin reintentar.
    Si la reparación falla, lanza LLMUnavailableError.
    """
    text = await generate(
        prompt,
        system=system,
        format="json",
        temperature=temperature,
        num_predict=num_predict,
    )
    text = text.strip()
    if not text:
        raise LLMUnavailableError("El asistente devolvió respuesta vacía. Reintenta.")

    # Limpia ```json ... ``` si lo hubo
    if text.startswith("```"):
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                text = p
                break

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Reparación de JSON truncado: balanceando llaves/corchetes y cerrando
    # cualquier string abierto que haya quedado por num_predict insuficiente.
    repaired = _repair_truncated_json(text)
    if repaired is not None:
        try:
            data = json.loads(repaired)
            logger.warning(
                "llm_json_repaired",
                original_len=len(text),
                repaired_len=len(repaired),
            )
            return data
        except json.JSONDecodeError:
            pass

    logger.error("llm_json_parse_failed", text_preview=text[-500:])
    raise LLMUnavailableError(
        "El asistente clínico devolvió un documento incompleto. Intenta generar de nuevo."
    )


def _repair_truncated_json(text: str) -> str | None:
    """Cierra strings abiertas y balancea `{`/`[` para JSON truncado por num_predict.

    Heurística simple: recorre caracteres tracking si estamos dentro de string
    o no, y al final agrega los cierres faltantes. Funciona para los casos más
    comunes (truncamiento durante el texto de un valor string).
    """
    if not text:
        return None

    in_string = False
    escape = False
    stack: list[str] = []  # contiene '{' o '['

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{" or ch == "[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    repaired = text
    # 1) Si quedó string abierta, ciérrala. Quita el último carácter si es `\`
    #    para evitar dejar un escape colgante.
    if in_string:
        if repaired.endswith("\\"):
            repaired = repaired[:-1]
        repaired += '"'
    # 2) Quita coma colgante (común tras truncar): `..., ` o `...,\n`
    stripped = repaired.rstrip()
    if stripped.endswith(","):
        repaired = stripped[:-1]
    # 3) Balancea llaves y corchetes pendientes
    while stack:
        opener = stack.pop()
        repaired += "}" if opener == "{" else "]"
    return repaired


async def health_check() -> bool:
    """Verifica que Ollama está operativo."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
