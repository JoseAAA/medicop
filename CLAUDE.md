# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Producto

MediCop es un **HIS con IA** para hospitales peruanos (piloto Perú). Cubre las **4 áreas hospitalarias** — emergencia, hospitalización, consulta externa y cirugía — con el paciente como entidad central que acumula contexto cruzado entre áreas.

El flujo principal: el médico inicia una atención en un área, graba la conversación con el paciente, y MediCop pre-llena los documentos clínicos (SOAP, receta, orden de exámenes) con citas a guías oficiales del MINSA / EsSalud-IETSI / OMS. El médico revisa, edita y firma. El asistente sugiere 3-5 **diagnósticos diferenciales** con razonamiento y likelihood (alta/media/baja); el médico decide cuál tomar.

**Posicionamiento**: "asistente informativo, no decisor autónomo".

**Restricciones inviolables**:
1. **100% local**: ningún dato del paciente sale de la infraestructura del hospital (Ley 29733 Perú).
2. **Funciona offline**: sin internet, el sistema sigue operativo.
3. **Anti-alucinación**: el LLM solo afirma cosas con cita a guía; si no encuentra evidencia responde "No documentado".

## Stack

| Componente | Tecnología | Notas |
|---|---|---|
| LLM | `medgemma:4b` (Q4_K_M) vía Ollama | RTX 3060 6 GB — ~3.2 GB VRAM, ~90 tok/s · `OLLAMA_KEEP_ALIVE=30m` · `num_ctx=8192` |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (384 dims) | Reemplazó a BGE-M3 — más liviano (~120 MB), CPU-friendly, suficiente para Spanish RAG |
| Vector DB | Qdrant 1.13.6 | colección `clinical_guidelines`, cosine, IDs determinísticos por SHA1 |
| Transcripción | Faster-Whisper `small` ES, INT8, CPU | Pre-warmed en lifespan · sin pyannote (diarización omitida en MVP) |
| Backend | FastAPI · Python 3.11 · Pydantic v2 · SQLAlchemy 2.0 async · structlog | |
| Frontend | Next.js 15 (App Router) · TypeScript strict · Tailwind · `@tanstack/react-query` · `react-hook-form` · `zod` | |
| Base de datos | PostgreSQL 16 | Sin Alembic — `Base.metadata.create_all()` en lifespan. Producción real necesitará migraciones |
| Cache / sesión / rate limit / token revocation | Redis 7 | |
| Cifrado | AES-256-GCM (servicio listo, audio se descarta tras transcribir hoy) · TLS 1.3 (depende del reverse proxy del hospital) | |

## Comandos

Todo se opera vía `Makefile`. Los comandos corren dentro de Docker — no hace falta tener Python/Node local.

```bash
make install       # instalación end-to-end: setup + pull-models (~10-15 min primera vez)
make setup         # solo verifica + .env + build + up
make pull-models   # descarga medgemma:4b en Ollama (~3.3 GB)
make up            # levanta los 6 servicios
make up-dev        # con docker-compose.dev.yml (hot reload)
make down          # detiene
make down-volumes  # ⚠️ borra volúmenes (datos perdidos)
make health        # /health del backend
make logs          # logs en vivo (logs-backend / logs-frontend / logs-qdrant)
make seed          # re-siembra (idempotente — útil tras down-volumes)
make test          # pytest
make lint          # ruff (backend) + next lint (frontend)
make format        # ruff format + ruff --fix
make type-check    # tsc --noEmit en frontend
make shell-backend / shell-frontend / shell-postgres
```

URLs locales tras `make up`: frontend `:3000`, API docs `:8000/docs`, Qdrant dashboard `:6333/dashboard`.

`scripts/setup.sh` genera `POSTGRES_PASSWORD`, `SECRET_KEY` (64 bytes) y `ENCRYPTION_KEY` (32 bytes) automáticamente con `openssl rand -hex` — el operador no necesita Python en el host.

## Arquitectura

### Topología Docker (6 servicios, red `medicop-net`)

`postgres` → `redis` → `qdrant` → `ollama` → `backend` (FastAPI uvicorn) → `frontend` (Next.js). Cada servicio depende del healthcheck del anterior. Los healthchecks de qdrant y ollama usan `bash /dev/tcp` porque esas imágenes no traen curl/wget.

**Presupuesto VRAM** (RTX 3060 6 GB): MedGemma Q4_K_M ≈ 3.2 GB siempre cargado. Whisper corre en CPU por default. No agregues un segundo modelo a Ollama (`OLLAMA_MAX_LOADED_MODELS=1`).

**Volúmenes persistentes**: `postgres_data`, `redis_data`, `qdrant_storage`, `ollama_models`, `hf_cache` (modelos HuggingFace), `whisper_cache`. Sobreviven a `make down` pero no a `make down-volumes`.

### Backend (`backend/app/`)

Layering:
- `routers/` — endpoints HTTP (`auth`, `patients`, `encounters`, `transcription`, `rag`, `health`). Solo orquestación.
- `services/` — lógica de dominio:
  - `auth_service` — dependencia `CurrentUser` + token blacklist
  - `audit_service` — registros append-only en `audit_logs`
  - `clinical_doc_generator` — orquesta RAG + LLM + chequeo de alergias por familia. Reintento auto-reductivo en 3 niveles (transcript 4000→2500→1500 chars, num_predict 5500→5500→4500) si el JSON sale truncado. Recorta el transcript inteligentemente (mantiene inicio + final, descarta el medio) para reuniones de 10 min. Al **regenerar**, borra primero los documentos no firmados del encounter.
  - `encounter_highlights` — extrae diagnóstico/meds/labs/plan; insumo compartido frontend ↔ LLM
  - `encryption_service` — AES-256-GCM (validación de key al import)
  - `llm_service` — cliente Ollama (`generate`, `generate_json`, `num_ctx=8192`, `num_predict=5500`). Reparador de JSON truncado (cierra strings + balancea llaves) y retry único en errores transitorios. `keep_alive=30m`, `timeout=300s`.
  - `rag_service` — chunker + embedder + Qdrant (`query_points`)
  - `rate_limit` — login throttling + JWT revocation list
  - `whisper_service` — faster-whisper con pre-warm
- `db/models.py` — SQLAlchemy 2.0 typed mappers: `User`, `Patient`, `Encounter`, `ClinicalDocument`, `Guideline`, `AuditLog`. **No hay tabla `Consultation`** — fue renombrada a `Encounter` con `area: emergencia | hospitalizacion | consulta_externa | cirugia`.
- `db/seed.py` — datos demostrativos: 1 médico + 6 pacientes peruanos con 21 atenciones cruzadas + 10 guías clínicas. Idempotente.
- `models/` — schemas Pydantic v2 (DTOs de API, no confundir con `db/models.py`).
- `prompts/clinical_docs_prompt.py` — única plantilla de prompt; varía la estructura JSON por área.
- `core/` — infra transversal: `database` (engine async), `logger` (structlog JSON), `security` (JWT con `jti`, bcrypt), `exceptions`.
- `config.py` — `Settings` Pydantic singleton (`@cache`-decorado). **Toda configuración pasa por aquí**, nunca leer `os.environ` directo.

Patrones a respetar:
- **DB sesiones**: `Depends(get_db)` de `core/database.py`. Engine con `pool_pre_ping=True, pool_size=10, max_overflow=20`.
- **Logging**: structlog con `request_id` UUID inyectado por middleware. Cada response devuelve header `X-Request-ID`.
- **Auth**: el JWT vive en cookie `medicop_session` (httpOnly, SameSite=Lax, Secure en producción). Hay fallback Authorization Bearer para tooling. Cada request pasa por `CurrentUser` + chequeo de revocación en Redis.
- **Cifrado**: `encryption_service.encrypt()` valida la key (32 bytes) al **importar** el módulo — falla rápido si `.env` está mal.
- **AuditLog inmutable**: nunca hagas `UPDATE`/`DELETE` sobre `audit_logs`. Ediciones se guardan como nueva fila con `edited_response`.
- **Rate limit**: `rate_limit.check_rate_limit("login:{ip}", 5, 900)` — 5 intentos / 15 min por IP.

### Frontend (`frontend/`)

Next.js 15 App Router con dos route groups:
- `app/(dashboard)/` — rutas autenticadas: `dashboard`, `patients`, `patients/[id]`, `consultation/[patientId]` (el param es realmente el `encounterId`).
- `app/login/` — fuera del grupo.

`app/layout.tsx` envuelve en `<Providers>` (QueryClient + AuthProvider). `middleware.ts` redirige a `/login` si falta el cookie.

Componentes activos en `frontend/components/`:
- `consultation/audio-recorder.tsx` — MediaRecorder + botón "Audio demo" (fallback canned)
- `consultation/document-card.tsx` — render por tipo de documento (SOAP / receta / lab / generic) con citas clickeables que abren modal
- `consultation/differential-diagnoses-card.tsx` — diferenciales con likelihood, rationale, "Aceptar" → SOAP assessment
- `consultation/common-diagnoses-picker.tsx` — top 10 diagnósticos comunes Perú como referencia rápida
- `consultation/guideline-section-modal.tsx` — visor de la sección MINSA citada
- `encounter/area-badge.tsx`, `encounter/encounter-timeline.tsx`
- `layout/sidebar.tsx`, `layout/topbar.tsx`
- `patient/patient-context-panel.tsx`
- `providers.tsx`

`lib/api-client.ts` (fetch con `credentials: include` + timeout) y `lib/api.ts` (endpoints tipados). NO usar `fetch` directo desde componentes.

Tokens de diseño en `tailwind.config.ts` + `app/globals.css`. Clases utilitarias compuestas: `.medicop-card`, `.medicop-btn-primary`, `.medicop-btn-outline`, `.medicop-input`, `.medicop-skeleton`, `.medicop-shimmer`, `.clinical-data` (JetBrains Mono para CIE-10 y datos clínicos), `.animate-sign-in` (firma).

### Identificadores del paciente

- **`nhc`** (Número de Historia Clínica) — identificador clínico interno del hospital. Es el campo PRIMARIO para buscar al paciente. Único, indexado.
- **`dni`** — opcional. Sirve para SIS / EsSalud / facturación. Puede no existir (extranjeros, recién nacidos sin trámite).

La búsqueda en `/api/patients/?q=...` matchea NHC ∪ DNI ∪ apellido ∪ nombre.

### Datos demostrativos del seed

| NHC | Paciente | Caso clínico clave |
|---|---|---|
| 0024381 | María Rodríguez Quispe (62, F) | DM2 + HTA + alergia sulfas — recibió TMP-SMX en emergencia hace 1 mes (caso "wow" para el demo) |
| 0019472 | Juan García López (58, M) | HTA + alergia penicilina + IAM hace 7 días con stent |
| 0031925 | Carmen Mendoza Flores (35, F) | Gestante 32 sem · sangrado escaso hace 2 días en emergencia · cistitis hace 1 mes |
| 0034001 | Diego Vargas Huamán (4, M) | NAC pediátrica resuelta hace 9 días |
| 0008153 | Roberto Silva Paredes (71, M) | EPOC + HTA + alergia AINEs · RTU prostática hace 6 meses |
| 0028719 | Lucía Castillo Núñez (28, F) | Cistitis hace 7 días, paciente sano |

Las 10 guías clínicas viven en `data-pipeline/seed-corpus/*.md` (HTA, DM2, ITU, NAC, EPOC, SCA, control prenatal, anemia infantil, EDA, cetoacidosis). Están marcadas `is_demo=true` en la tabla — cuando lleguen guías oficiales reales se filtran con un solo query.

### Endpoint de salud

`GET /health` (en `routers/health.py`) ejecuta `asyncio.gather` de 4 checks (Postgres, Redis, Qdrant, Ollama) en paralelo. Si añades nuevas dependencias externas: agrega un `_check_xxx()` y suma al gather.

## Capas de seguridad

| Capa | Implementación |
|---|---|
| Auth | JWT HS256 con `jti` único · cookie httpOnly + SameSite=Lax · `secure=True` en producción · TTL 8h |
| Rate limit | 5 intentos / 15 min por IP en `/login` (Redis sliding window) |
| Token revocation | Logout añade `jti` a Redis blacklist con TTL=remaining; `CurrentUser` valida en cada request |
| CORS | Origins explícitos · `allow_credentials=True` |
| Security headers backend | X-Content-Type-Options, X-Frame-Options:DENY, Referrer-Policy, Permissions-Policy, COOP, HSTS-en-prod |
| CSP frontend | `default-src 'self'`, `frame-ancestors 'none'`, `connect-src` restringido (en `next.config.js`) |
| Audit log inmutable | login, encounter_created, transcript_updated, documents_generated, document_edited, encounter_signed con IP |
| Mensaje genérico de login | "Email o contraseña incorrectos" — no revela si el usuario existe |

## Flujo de trabajo Git (Git Flow)

| Branch | Propósito |
|---|---|
| `main` | Código en producción / demos. Solo recibe merges desde `release/*` o `hotfix/*`. |
| `develop` | Branch de integración. Todo el trabajo nuevo se mergea aquí primero. |
| `feature/<nombre>` | Nuevas features. Salen de `develop`, vuelven a `develop` vía PR. |
| `release/<vX.Y>` | Estabilización antes de un release. Sale de `develop`, mergea en `main` + `develop`. |
| `hotfix/<descripcion>` | Bug crítico en prod. Sale de `main`, mergea en `main` + `develop`. |

Convenciones:
- **Branch activo de trabajo**: `develop`. Nunca commits directos a `main`.
- Naming: `feature/audio-encryption`, `hotfix/login-rate-limit`, `release/v0.2`.
- PRs siempre con descripción del cambio, screenshots si toca UI, y test plan.
- Commits en imperativo presente: "add X", "fix Y", no "added"/"fixed".

## Reglas de código

1. **Nunca alucinar**: el prompt del LLM exige citar `guideline_id` y `section` exactos del bloque RAG; si no, responde "No documentado".
2. **Citas obligatorias**: cada `Citation` lleva `guideline_id`, `guideline_name`, `section`. El frontend hace clickeable la cita y abre el modal con el párrafo.
3. **Audit log inmutable**: append-only.
4. **TypeScript strict** + **type hints** en Python.
5. **Validación**: Pydantic v2 backend, Zod frontend (cuando hay forms). Nunca `any` ni `dict` sin schema.
6. **No localStorage** para tokens — JWT vive en httpOnly cookie.
7. **Identificación del paciente**: SIEMPRE por NHC en la UI; DNI solo informativo.

## Estado del proyecto

| Fase | Alcance | Estado |
|---|---|---|
| F0 — Limpieza | Bugs configuración, eliminación landing pública, instalación con `make install` | ✅ |
| F1 — Datos + seeds | Modelo de datos 4 áreas, 6 pacientes con 21 encounters cruzados, 10 guías generadas | ✅ |
| F2 — Backend del flujo | Auth real, encounters CRUD, Whisper, RAG, LLM con prompts por área, allergy check, audit log | ✅ |
| F3 — Frontend + seguridad | Login, dashboard búsqueda, /patients con tabs por área + filtro 12 meses, /consultation con stepper + diferenciales + visor MINSA, todas las capas de seguridad | ✅ |
| F4 — Polish demo | Whisper pre-warm, audio canned por NHC, animación de firma, top 10 Dx comunes Perú, citas clickeables al texto del MINSA | ✅ |
| F5 — Resiliencia LLM | `num_predict=5500`, reparador de JSON truncado, retry auto-reductivo del orquestador (3 niveles), cap inteligente de transcript para reuniones largas, dedup al regenerar, router siempre devuelve 503 con mensaje útil | ✅ |

Demo presentable end-to-end y robusta para reuniones de hasta ~10 min. Pendientes para producción real (post-inversión): TLS con cert real, validación CMP contra Colegio Médico, 2FA, encriptación del audio en reposo (servicio listo, no conectado), Alembic, hash-chain del audit log, refinar prompt para que `red_flags` sean **del paciente** y no copia genérica de la guía.
