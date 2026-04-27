"""Autenticación — dependencia FastAPI que decodifica el JWT y carga al médico.

Soporta dos transportes de credenciales:
1. **httpOnly cookie** `medicop_session` (preferida — inmune a XSS).
2. **Authorization: Bearer <token>** (fallback para tooling y tests).

Antes de validar, consulta la blacklist de Redis: si el token fue revocado por
logout, se rechaza aunque siga vigente por fecha.
"""
from typing import Annotated

from fastapi import Cookie, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import http_unauthorized
from app.core.security import decode_access_token
from app.db.models import User
from app.services import rate_limit

SESSION_COOKIE_NAME = "medicop_session"

# `auto_error=False` para permitir que el cookie sea la fuente principal.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    cookie_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    token = cookie_token or bearer_token
    if not token:
        raise http_unauthorized("Sin sesión activa")

    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise http_unauthorized("Token inválido o expirado") from exc

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        raise http_unauthorized("Token mal formado")

    # Revocación (logout) — el jti está en la blacklist hasta que expire
    if await rate_limit.is_token_revoked(str(jti)):
        raise http_unauthorized("Sesión cerrada — vuelve a iniciar sesión")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise http_unauthorized("Usuario inactivo o inexistente")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
