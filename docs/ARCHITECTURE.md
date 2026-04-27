# MediCop — Arquitectura del sistema

## Topología

```
┌──────────────────────────────────────────────────────────────────────┐
│                  Infraestructura del hospital                         │
│                                                                       │
│  ┌────────────┐    ┌────────────────────────────────┐               │
│  │  Frontend  │──▶│        Backend API               │               │
│  │ Next.js 15 │    │  FastAPI · Pydantic v2          │               │
│  │   :3000    │    │  Auth httpOnly cookie · :8000   │               │
│  └────────────┘    └──┬──────┬──────┬──────┬─────────┘               │
│                       │      │      │      │                         │
│            ┌──────────┘      │      │      └────────┐               │
│            ▼                 ▼      ▼               ▼               │
│   ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│   │   Ollama     │  │  Qdrant  │  │  Redis   │  │ PostgreSQL   │  │
│   │ MedGemma 4B  │  │ guías ES │  │ sesiones │  │ pacientes,   │  │
│   │   (GPU)      │  │  + RAG   │  │ + RL +   │  │ encounters,  │  │
│   │   :11434     │  │  :6333   │  │ blacklist│  │ audit log    │  │
│   └──────────────┘  └──────────┘  └──────────┘  └──────────────┘  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
              ↑ Ningún dato sale de este perímetro (Ley 29733)
```

## Modelo de datos

- **Patient** (entidad central) — `nhc` (PK clínica), `dni` opcional, alergias / condiciones / medicación actual como JSONB.
- **Encounter** — atención del paciente en un área (`emergencia | hospitalizacion | consulta_externa | cirugia`). Estados: `open → documents_ready → signed`.
- **ClinicalDocument** — generado por el LLM dentro de un encounter. Tipos: `soap`, `prescription`, `lab_order`, `imaging_order`, `referral`, `evolution_note`, `discharge_summary`, `pre_op_note`, `surgical_report`, `post_op_note`, `triage_note`, `admission_note`, `differential_diagnoses`. Contenido en JSONB con citas y red flags.
- **Guideline** — guía clínica indexada en Qdrant. Contenido completo (Markdown) en Postgres + chunks embebidos en Qdrant.
- **AuditLog** — append-only, registra todas las acciones AI con IP.
- **User** — médico colegiado con CMP.

## Flujo de una atención

```
1. Doctor busca paciente por NHC      → GET /api/patients/?q=NHC
2. Abre ficha → ve timeline 4 áreas    → GET /api/encounters/by-patient/{id}
3. Click en área → crea encounter      → POST /api/encounters/
4. Graba audio → Whisper transcribe    → POST /api/transcription/
5. Guarda transcript                   → PATCH /api/encounters/{id}/transcript
6. "Generar documentos" →
     a. extract_highlights del paciente (cross-area)
     b. RAG search en guías filtrado por área
     c. LLM con prompt JSON (diferenciales + SOAP + Rx + lab + citations + red_flags)
     d. check_drug_allergy_conflicts (sulfas/penicilinas/AINEs/macrólidos/quinolonas)
     e. Materializa cada bloque como ClinicalDocument
                                       → POST /api/encounters/{id}/generate-docs
7. Médico revisa, edita inline, "Aceptar" un diferencial → patch SOAP
                                       → PATCH /api/encounters/{id}/documents/{doc_id}
8. Click cita → abre modal con párrafo MINSA
                                       → GET /api/rag/sources/{guideline_id}/section?section=...
9. Firma → status SIGNED + audit log inmutable
                                       → POST /api/encounters/{id}/sign
```

## Decisiones de diseño

- **Multi-área desde día uno**: el paciente acumula contexto cruzado entre las 4 áreas. Esto es el diferenciador frente a HIS tradicionales y frente a competidores cloud (Nuance DAX, Suki, Abridge) que no tienen esta vista cruzada local.
- **Offline-first**: Ollama + Qdrant + PostgreSQL corren sin internet. El frontend Next.js se sirve estático tras `next build`.
- **Embeddings ligeros**: MiniLM multilingüe (384 dims, 120 MB) en lugar de BGE-M3 (1024 dims, 2.3 GB). Suficiente para Spanish RAG con 10-30 guías; CPU-friendly.
- **Sin Alembic**: dev usa `Base.metadata.create_all()` en lifespan. Producción real necesitará migraciones cuando el schema deje de ser greenfield.
- **Sin diarización**: pyannote requiere token HuggingFace + es lento. Para el MVP transcribimos sin separar voces.
- **Audio efímero**: el archivo del audio se descarta inmediatamente tras transcribir. La transcripción en texto plano sí se guarda en `encounters.transcript` (en producción debe ir cifrada con AES-256-GCM).
- **Append-only audit**: tabla `audit_logs` sin DELETE permissions a nivel aplicación; ediciones del médico se guardan como nueva fila con `edited_response`.
- **Anti-alucinación**: prompt sistémico exige al LLM copiar `guideline_id` y `section` exactos del bloque RAG. El front muestra cita clickeable; el médico puede verificar cada afirmación contra el párrafo original.
