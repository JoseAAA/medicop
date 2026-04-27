# MediCop — Seguridad

## Modelo de amenazas

Sistema local hospitalario. Vectores principales: acceso no autorizado a datos clínicos, robo de credenciales del médico, ataques desde la red interna del hospital, manipulación del audit log, fuga de datos hacia internet.

## Capas implementadas

| Capa | Mecanismo | Archivo |
|---|---|---|
| Autenticación | JWT HS256 con `jti` único · TTL 8h | `core/security.py` |
| Transporte del token | Cookie `medicop_session` · `httpOnly` · `SameSite=Lax` · `Secure=True` en producción | `routers/auth.py` |
| Rate limit en login | 5 intentos / 15 min por IP (Redis sliding window) | `services/rate_limit.py` |
| Token revocation (logout) | `jti` añadido a Redis blacklist con TTL = expiración restante; `CurrentUser` consulta en cada request | `services/rate_limit.py`, `services/auth_service.py` |
| Mensaje de login genérico | "Email o contraseña incorrectos" — no revela existencia del usuario | `routers/auth.py` |
| CORS | Origins explícitos · `allow_credentials=True` · métodos y headers acotados | `main.py` |
| Security headers backend | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy: same-origin`, `Strict-Transport-Security` (en producción) | `main.py` SECURITY_HEADERS |
| CSP frontend | `default-src 'self'`, `frame-ancestors 'none'`, `connect-src` restringido | `frontend/next.config.js` |
| Middleware de gating | Next middleware redirige rutas autenticadas a `/login` si falta el cookie | `frontend/middleware.ts` |
| Auto-redirect en 401 | Cliente HTTP detecta 401 y redirige con `?expired=1` | `frontend/lib/api-client.ts` |
| Timeout duro | 30 s por defecto, 120 s en upload audio + LLM | `frontend/lib/api-client.ts` |
| Validación de input | Pydantic v2 backend, Zod frontend | router/* + frontend forms |
| SQL injection | SQLAlchemy ORM = parameterized queries | — |
| Audit log inmutable | Append-only en PostgreSQL · IP + user_id + action en cada evento | `services/audit_service.py` |
| Cifrado AES-256-GCM | Servicio listo (validación de key al import) — pendiente conectar al audio en reposo | `services/encryption_service.py` |
| `.env` con claves auto-generadas | `setup.sh` usa `openssl rand` para `POSTGRES_PASSWORD`, `SECRET_KEY` (64 bytes), `ENCRYPTION_KEY` (32 bytes) | `scripts/setup.sh` |
| `robots: noindex,nofollow` | Previene indexación accidental de la app | `frontend/app/layout.tsx` |

## Acciones registradas en el audit log

`user_login`, `user_logout`, `encounter_created`, `transcript_updated`, `documents_generated`, `document_edited`, `encounter_signed`. Cada una guarda `user_id`, `patient_id`, `encounter_id`, `ip_address`, y para acciones AI también `query` y `ai_response`.

## Checklist OWASP Top 10 — estado

- [x] **A01 Broken Access Control** — toda ruta `/api/*` (excepto `/health` y `/api/auth/login`) exige `CurrentUser`. Auth dep verifica JWT + revocación + usuario activo.
- [x] **A02 Cryptographic Failures** — bcrypt para passwords, JWT firmado HS256 con secret de 64 bytes generado por openssl. AES-256-GCM disponible.
- [x] **A03 Injection** — Pydantic v2 + Zod en todos los boundaries. SQLAlchemy ORM previene SQL injection.
- [x] **A04 Insecure Design** — flujo append-only del audit log, identificación clínica vía NHC (independiente del DNI), anti-alucinación con citas obligatorias del MINSA.
- [x] **A05 Security Misconfiguration** — claves no hardcodeadas (auto-generadas), security headers en cada response, CSP estricto.
- [x] **A07 Authentication Failures** — rate limit + revocation list + sesión httpOnly, mensaje genérico de login.
- [x] **A09 Logging/Monitoring** — structlog JSON con `request_id`, audit log persistido, cada response devuelve `X-Request-ID`.

## Hardening pendiente para producción real

| Item | Por qué se difiere |
|---|---|
| TLS 1.3 con certificado real | Depende del reverse proxy del hospital (nginx/caddy). El backend ya lleva `Strict-Transport-Security` y `secure=True` cuando `ENVIRONMENT != development` |
| 2FA / TOTP | Impacta UX, requiere acuerdo con cliente |
| Validación CMP contra Colegio Médico del Perú | Endpoint público no expuesto; requiere convenio |
| Cifrado del audio en reposo | Hoy el archivo temporal se borra inmediatamente tras transcribir; el servicio AES-256-GCM está listo si se decide persistir el audio |
| Hash-chain del audit log | Append-only de Postgres es suficiente para Ley 29733; tamper-detection con cadena de hashes es nice-to-have post-piloto |
| Migraciones Alembic | Hoy `create_all()`; producción real necesitará migraciones versionadas |
| WAF / IPS a nivel infraestructura | Responsabilidad del datacenter del hospital |
