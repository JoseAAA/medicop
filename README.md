# ✚ MediCop

**Inteligencia clínica local. Tus datos nunca salen del hospital.**

HIS con IA para hospitales peruanos. El médico graba la conversación con el paciente, MediCop transcribe, sugiere 3-5 diagnósticos diferenciales con razonamiento, pre-llena la nota SOAP + receta + orden de exámenes con citas a guías oficiales del MINSA, y el médico valida y firma. Cubre las 4 áreas hospitalarias: emergencia, hospitalización, consulta externa y cirugía.

100% local, funciona sin internet. Conforme a Ley 29733 de Protección de Datos Personales del Perú.

---

## Quick Start

Un solo comando — el script verifica Docker, genera claves seguras automáticamente, construye las imágenes, levanta los 6 servicios y descarga el modelo MedGemma 4B (~3.3 GB).

```bash
git clone <repo> medicop && cd medicop
make install
```

Tras 10-15 minutos (la primera vez) está todo listo. Si prefieres dividir pasos:

```bash
make setup         # solo verifica Docker + .env + build + up
make pull-models   # descarga MedGemma 4B aparte
```

| URL | Descripción |
|---|---|
| http://localhost:3000 | App MediCop (te redirige a `/login`) |
| http://localhost:8000/docs | API docs (FastAPI) |
| http://localhost:6333/dashboard | Qdrant dashboard |

**Credenciales demo**: `demo@medicop.pe` / `Demo1234!`

---

## Cómo se ve el flujo

1. **Login** del médico → cookie httpOnly + redirect al dashboard.
2. **Dashboard** con buscador por NHC (Número de Historia Clínica), apellido o nombre.
3. **Ficha del paciente** muestra alergias en rojo, condiciones activas, medicación actual + un timeline de **atenciones previas separadas por área** (último año por defecto, opción de ver historial completo).
4. **Hero "Atender al paciente"** con 4 botones grandes — un clic crea la atención en el área elegida y abre la pantalla de grabación.
5. **Pantalla de consulta** con stepper claro (1 Grabar → 2 Revisar → 3 Validar → 4 Firmar):
   - Lateral con contexto del paciente siempre visible
   - Card "MediCop te recuerda" con highlights de la última atención (diagnóstico, meds, plan)
   - Grabador con MediaRecorder + botón **"Audio demo"** como respaldo si el micrófono falla
   - Transcripción en español (Faster-Whisper `small`, ~5 s con modelo caliente)
   - **Sugerencias diagnósticas**: 3-5 opciones del LLM con likelihood (Más probable / Posible / A descartar), rationale específico, y cita clickeable que abre el párrafo exacto del MINSA
   - Documentos pre-llenados (SOAP, receta, orden de exámenes) editables inline
   - Top 10 diagnósticos comunes en Perú como referencia rápida
   - **Chequeo de alergias** automático (sulfonamidas, penicilinas, cefalosporinas, AINEs, macrólidos, quinolonas)
   - Firma final con animación + audit log inmutable

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| LLM | MedGemma 4B (Q4_K_M) vía Ollama, GPU |
| Embeddings RAG | MiniLM multilingüe (CPU, ~120 MB) |
| Vector DB | Qdrant 1.13 |
| Transcripción | Faster-Whisper `small` español, INT8, CPU |
| Backend | FastAPI · Python 3.11 · Pydantic v2 · SQLAlchemy 2.0 async |
| Frontend | Next.js 15 · TypeScript strict · Tailwind · React Query |
| Base de datos | PostgreSQL 16 |
| Cache / sesiones / rate limit | Redis 7 |
| Auth | JWT en cookie httpOnly + SameSite=Lax · token revocation list |
| Cifrado | AES-256-GCM (servicio listo) · TLS 1.3 (en reverse proxy) |

---

## Estructura del proyecto

```
medicop/
├── backend/                       FastAPI — routers, services, models, prompts, seed
├── frontend/                      Next.js 15 — App Router
│   └── public/demo-audio/         4 audios pre-grabados (gTTS) como fallback de demo
├── data-pipeline/seed-corpus/     10 guías MINSA generadas (Markdown) + manifest
├── docs/                          ARCHITECTURE.md, SECURITY.md
├── scripts/                       setup.sh, healthcheck.sh, pull_models.sh, seed_database.sh
├── docker-compose.yml             6 servicios: postgres · redis · qdrant · ollama · backend · frontend
├── Makefile
├── CLAUDE.md                      Contexto para Claude Code (cómo trabajar en este repo)
└── README.md
```

---

## Comandos útiles

```bash
make install       # instalación end-to-end (recomendado)
make up / down     # levantar / detener servicios
make logs          # logs en tiempo real (logs-backend / logs-frontend / logs-qdrant)
make health        # /health del backend
make seed          # re-siembra demo (idempotente)
make pull-models   # descargar MedGemma 4B (~3.3 GB)
make test          # pytest
make lint          # ruff (backend) + next lint (frontend)
make format        # ruff format + ruff --fix
make type-check    # tsc --noEmit
make shell-backend / shell-frontend / shell-postgres
make down-volumes  # ⚠️ borra volúmenes (datos perdidos)
```

---

## Datos demostrativos

6 pacientes peruanos con 21 atenciones cruzadas + 10 guías clínicas oficiales generadas (HTA, DM2, ITU, NAC, EPOC, SCA, control prenatal, anemia infantil, EDA, cetoacidosis). El caso estrella es **María Rodríguez Quispe (NHC 0024381)** — DM2 + HTA + alergia a sulfonamidas, con un TMP-SMX prescrito en emergencia hace 1 mes. Cuando un nuevo médico abre la ficha y empieza una atención, MediCop detecta la incompatibilidad histórica y la marca como red flag.

---

## Restricciones inviolables

1. **100% local** — ningún dato del paciente sale de la infraestructura del hospital.
2. **Funciona offline** — sin internet, el sistema sigue operativo.
3. **Anti-alucinación** — todo lo que el LLM afirma debe venir con cita a guía clínica; si no encuentra evidencia, responde "No documentado". Las citas son clickeables y abren el párrafo exacto del MINSA.

---

## Producción real (post-piloto)

Pendientes para hospital piloto en producción:
- TLS 1.3 con certificado real (en reverse proxy nginx/caddy del hospital)
- Validación del número CMP contra el Colegio Médico del Perú al crear cuentas
- 2FA / TOTP para médicos
- Encriptación del audio en reposo (el servicio AES-256-GCM ya existe; hoy el audio se descarta tras transcribir)
- Migraciones Alembic (hoy usamos `Base.metadata.create_all()` para simplicidad demo)
- Hash-chain del audit log para tamper-detection
- Reemplazo de las guías generadas como ejemplo por las guías oficiales reales del MINSA, EsSalud-IETSI y OMS

> **MediCop es una herramienta de apoyo informativo. No reemplaza el juicio clínico del médico colegiado.**
