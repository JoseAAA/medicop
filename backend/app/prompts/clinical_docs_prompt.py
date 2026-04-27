"""
Prompts del LLM para pre-llenar documentos clínicos según el área del encounter.

El LLM siempre debe:
1. Responder en JSON estricto con la estructura indicada.
2. NO inventar dosis, diagnósticos, exámenes ni hallazgos.
3. Citar la fuente de cada afirmación clínica con los chunks recuperados.
4. Marcar red_flags ante: alergia/medicamento conflictivo, signo de alarma,
   diagnóstico que requiere derivación urgente.
"""

SYSTEM_PROMPT = """Eres MediCop, asistente clínico informativo para médicos peruanos.

REGLAS INVIOLABLES:
1. NUNCA inventes datos clínicos (dosis, diagnósticos, exámenes, valores). Solo \
usa lo que está en el CONTEXTO_PACIENTE, las GUIAS_CLINICAS y la TRANSCRIPCION.
2. Si algo no se puede inferir, deja el campo vacío "" o lista vacía []. \
NUNCA digas "lo asumo" ni "probablemente".
3. Cada cita en `citations` debe llevar el `guideline_id` y la `section` \
EXACTOS tal como aparecen en el bloque GUIAS_CLINICAS. NO inventes ids ni \
secciones — copia los que recibiste.
4. Eres ASISTENTE INFORMATIVO. El médico decide. No uses lenguaje imperativo.
5. Detecta y marca en `red_flags`: medicamento incompatible con alergias del \
paciente, dosis fuera de rango etario, signo de alarma, diagnóstico que \
requiere derivación urgente.
6. Responde en español médico claro, conciso, formato JSON estricto.
"""


# ─── Plantillas de salida JSON por área ──────────────────────────────────────


CONSULTA_EXTERNA_OUTPUT = """\
{
  "differential_diagnoses": [
    {
      "name": "Nombre del diagnóstico (ej. Cistitis aguda no complicada)",
      "cie10": "N30.0",
      "likelihood": "alta|media|baja",
      "rationale": "1-2 frases citando los hallazgos del paciente que apoyan o descartan este diagnóstico",
      "guideline_section": "Sección específica de la guía MINSA/IETSI que respalda"
    }
  ],
  "soap": {
    "subjective": "...",
    "objective": "...",
    "assessment": "Diagnóstico principal elegido del diferencial — debe coincidir con el de likelihood alta",
    "cie10_codes": ["..."],
    "plan": "..."
  },
  "prescription": {
    "drugs": [
      {
        "name": "...",
        "dose": "...",
        "route": "oral",
        "frequency": "...",
        "duration": "...",
        "indication": "..."
      }
    ],
    "indications": "..."
  },
  "lab_orders": [
    {"name": "...", "urgency": "rutina|urgente|stat", "indication": "..."}
  ],
  "citations": [
    {"guideline_id": "<copiar del bloque>", "guideline_name": "...", "section": "<copiar tal cual>"}
  ],
  "red_flags": []
}

REGLA EXTRA — DIFERENCIALES:
- Devuelve entre 3 y 5 diagnósticos diferenciales ordenados por probabilidad clínica.
- El primero (likelihood "alta") debe ser el que el médico tomará como principal.
- Cada diferencial debe traer rationale específico al paciente, no genérico.
- Si la información no permite un diferencial sólido, devuelve menos opciones."""


EMERGENCIA_OUTPUT = """\
{
  "differential_diagnoses": [
    {"name": "...", "cie10": "...", "likelihood": "alta|media|baja", "rationale": "...", "guideline_section": "..."}
  ],
  "triage_note": {
    "narrative": "...",
    "vital_signs": {"PA": "...", "FC": ..., "FR": ..., "T": ..., "SatO2": "..."},
    "triage_level": "I-resucitación|II-emergencia|III-urgente|IV-menor|V-no urgente"
  },
  "admission_note": {
    "narrative": "...",
    "diagnosis": "Diagnóstico principal — coincide con el diferencial de likelihood alta",
    "indications": "..."
  },
  "prescription": {
    "drugs": [
      {"name": "...", "dose": "...", "route": "...", "frequency": "...", "duration": "...", "indication": "..."}
    ]
  },
  "citations": [{"guideline_id": "<del bloque>", "guideline_name": "...", "section": "<copiar>"}],
  "red_flags": []
}

REGLA EXTRA — DIFERENCIALES: 3-5 diagnósticos por probabilidad. El primero ('alta') es el que se documentará en admission_note.diagnosis."""


HOSPITALIZACION_OUTPUT = """\
{
  "evolution_note": {
    "narrative": "...",
    "vital_signs": {"PA": "...", "FC": ..., "FR": ..., "T": ..., "SatO2": "..."},
    "indications": "..."
  },
  "citations": [{"guideline_id": "<del bloque>", "guideline_name": "...", "section": "<copiar>"}],
  "red_flags": []
}"""


CIRUGIA_OUTPUT = """\
{
  "pre_op_note": {
    "narrative": "...",
    "anesthesia_risk": "ASA I|II|III|IV|V",
    "pre_op_indications": "..."
  },
  "citations": [{"guideline_id": "<del bloque>", "guideline_name": "...", "section": "<copiar>"}],
  "red_flags": []
}"""


AREA_OUTPUT_TEMPLATES = {
    "consulta_externa": CONSULTA_EXTERNA_OUTPUT,
    "emergencia": EMERGENCIA_OUTPUT,
    "hospitalizacion": HOSPITALIZACION_OUTPUT,
    "cirugia": CIRUGIA_OUTPUT,
}


def build_user_prompt(
    area: str,
    patient_context: str,
    rag_context: str,
    chief_complaint: str,
    transcript: str,
) -> str:
    """Construye el prompt completo para el LLM."""
    template = AREA_OUTPUT_TEMPLATES.get(area, CONSULTA_EXTERNA_OUTPUT)
    transcript_block = transcript.strip() or "(no se registró transcripción)"

    return f"""ÁREA HOSPITALARIA: {area}

CONTEXTO_PACIENTE:
{patient_context}

GUIAS_CLINICAS (fragmentos recuperados — único material aceptado para fundamentar):
{rag_context}

MOTIVO_DE_CONSULTA:
{chief_complaint or '(no especificado)'}

TRANSCRIPCION:
{transcript_block}

TAREA:
Pre-llena los documentos clínicos correspondientes a esta área hospitalaria. \
Devuelve un JSON con EXACTAMENTE esta estructura:

{template}

RECUERDA: solo información del contexto, citas obligatorias, red_flags si \
detectas conflicto con alergias o signos de alarma. No inventes dosis."""
