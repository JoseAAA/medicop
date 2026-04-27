"""Router de autenticación — login con rate limit + httpOnly cookie + logout."""
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.exceptions import http_unauthorized
from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.models import User
from app.models.auth import LoginRequest, TokenResponse, UserRead
from app.services import audit_service, rate_limit
from app.services.auth_service import SESSION_COOKIE_NAME, CurrentUser

router = APIRouter()
settings = get_settings()

LOGIN_RATE_MAX = 5            # 5 intentos
LOGIN_RATE_WINDOW = 60 * 15   # ventana de 15 minutos


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str, ttl_seconds: int) -> None:
    """Cookie httpOnly + SameSite=Lax (Strict cuando frontend está en mismo dominio).

    En producción agregar `secure=True` (solo HTTPS). El reverse proxy también
    debería set Strict-Transport-Security.
    """
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=ttl_seconds,
        httponly=True,                         # bloquea acceso desde JS → mitiga XSS
        secure=not settings.is_development,    # exige HTTPS en producción
        samesite="lax",                        # mitiga CSRF; Lax permite navegación normal
        path="/",
    )


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    ip = _client_ip(request)

    # 1) Rate limit por IP — protección contra fuerza bruta
    allowed, count = await rate_limit.check_rate_limit(
        f"login:{ip}",
        max_attempts=LOGIN_RATE_MAX,
        window_seconds=LOGIN_RATE_WINDOW,
    )
    if not allowed:
        # Audit log del intento bloqueado (no requiere usuario válido)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Demasiados intentos fallidos desde esta IP "
                f"({count}/{LOGIN_RATE_MAX} en {LOGIN_RATE_WINDOW // 60} min). "
                "Espera unos minutos antes de reintentar."
            ),
            headers={"Retry-After": str(LOGIN_RATE_WINDOW)},
        )

    # 2) Lookup usuario
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Mensaje genérico para no revelar si el usuario existe
    if user is None or not verify_password(body.password, user.hashed_password):
        raise http_unauthorized("Email o contraseña incorrectos")
    if not user.is_active:
        raise http_unauthorized("Cuenta desactivada")

    # 3) Login exitoso → reset del contador (no penalizamos ataques pasados)
    await rate_limit.reset_rate_limit(f"login:{ip}")

    # 4) Genera JWT, set cookie, log
    token_info = create_access_token(subject=user.id)
    _set_session_cookie(
        response,
        token=str(token_info["token"]),
        ttl_seconds=int(token_info["expires_in"]),
    )

    await audit_service.log_interaction(
        db,
        user_id=user.id,
        action="user_login",
        ip_address=ip,
    )
    await db.commit()

    return TokenResponse(
        access_token=str(token_info["token"]),  # también en body para tooling/tests
        user=UserRead.model_validate(user),
    )


@router.post("/logout", summary="Cerrar sesión y revocar el token")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, str]:
    # Revoca el token actual añadiéndolo a la blacklist Redis
    token = cookie_token
    if not token:
        # Si llegó por header en lugar de cookie
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]

    if token:
        try:
            payload = decode_access_token(token)
            jti = str(payload.get("jti", ""))
            user_id = str(payload.get("sub", ""))
            exp = int(payload.get("exp", 0))
            from datetime import datetime, timezone

            ttl = max(exp - int(datetime.now(timezone.utc).timestamp()), 0)
            if jti and ttl > 0:
                await rate_limit.revoke_token(jti, ttl)
            if user_id:
                await audit_service.log_interaction(
                    db,
                    user_id=user_id,
                    action="user_logout",
                    ip_address=_client_ip(request),
                )
                await db.commit()
        except Exception:
            # Token inválido o expirado — igual borramos la cookie
            pass

    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"detail": "Sesión cerrada"}


@router.get("/me", response_model=UserRead, summary="Perfil del médico autenticado")
async def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
