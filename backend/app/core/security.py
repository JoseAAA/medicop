"""Autenticación JWT + bcrypt para MediCop.

Notas de seguridad:
- JWT firmado con HS256 + SECRET_KEY (>= 64 bytes, generada con openssl).
- Cada token incluye `jti` único → permite revocación (ver rate_limit.py).
- `iat` permite calcular el TTL restante para insertar en blacklist al logout.
- Por defecto access token dura 8 horas (configurable).
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> dict[str, str | int]:
    """Genera JWT de acceso con `jti` para soportar revocación.

    Retorna dict con `token` (string) + `jti` + `expires_at` (epoch seconds) +
    `expires_in` (segundos hasta expirar) — útil para set-cookie y blacklist.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    jti = str(uuid4())

    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": jti,
        "type": "access",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return {
        "token": token,
        "jti": jti,
        "expires_at": int(expire.timestamp()),
        "expires_in": int((expire - now).total_seconds()),
    }


def decode_access_token(token: str) -> dict[str, object]:
    """Decodifica y valida el JWT. Lanza JWTError si expiró o es inválido."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
