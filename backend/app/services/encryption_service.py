"""Cifrado AES-256-GCM para datos en reposo.

Usado para: audio de consultas, transcripciones, notas SOAP.
La clave se valida una sola vez al importar el módulo.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


def _load_key() -> bytes:
    key = get_settings().encryption_key.encode()
    if len(key) != 32:
        raise ValueError(
            f"ENCRYPTION_KEY debe tener exactamente 32 bytes para AES-256 (actual: {len(key)})"
        )
    return key


# Validada una vez al cargar el módulo — falla rápido si .env está mal configurado
_KEY: bytes = _load_key()


def encrypt(plaintext: bytes) -> bytes:
    """Cifra bytes con AES-256-GCM. Devuelve base64(nonce[12] + ciphertext)."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(_KEY).encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext)


def decrypt(token: bytes) -> bytes:
    """Descifra bytes producidos por encrypt(). Lanza InvalidTag si el token fue alterado."""
    raw = base64.b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(_KEY).decrypt(nonce, ciphertext, None)
