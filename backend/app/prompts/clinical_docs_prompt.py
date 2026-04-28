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
3. CITAS — regla crítica: cada item en `citations` debe ser una sección \
QUE APARECE LITERALMENTE en el bloque GUIAS_CLINICAS de tu input. \
   - `guideline_id` = el UUID exacto que aparece tras "guideline_id:" en el bloque. \
   - `section` = el texto que aparece tras "Sección:" en el bloque (ej. \
"6. Banderas rojas — referir a obstetricia de alto riesgo"). \
   - NUNCA pongas la palabra "Sección" sola, ni "<copiar>", ni placeholders del \
template. Si no encuentras una sección que respalde lo que dijiste, devuelve \
`citations: []`. Es PREFERIBLE no citar a citar mal.
4. Eres ASISTENTE INFORMATIVO. El médico decide. No uses lenguaje imperativo.
5. `red_flags` = signos/síntomas/condiciones que el paciente PRESENTA o \
REFIERE en ESTA atención y que requieren atención inmediata o cambian el \
manejo. NO copies la lista teórica de la guía — solo lo que APLICA a este \
paciente. Reglas concretas: \
   - SatO2 < 90% → red flag. \
   - Fiebre ≥ 38.5°C + dolor lumbar unilateral → "sospecha pielonefritis". \
   - Alergia documentada a familia farmacológica relevante para el manejo \
(ej. paciente con alergia a sulfas y cuadro de ITU) → red flag explícito \
nombrando al fármaco a evitar. \
   - Dolor torácico de esfuerzo en post-IAM/post-stent (< 30 días) → \
red flag de trombosis intra-stent. \
   - Sangrado, fiebre alta sin foco, alteración del sensorio, signos de \
shock → red flag. \
   Si el paciente NO tiene ninguno, devuelve []. Es preferible [] a copiar \
banderas teóricas que no aplican.
6. `prescription.drugs` = SOLO medicamentos NUEVOS que vas a indicar hoy. NO \
repitas la medicación crónica que ya está en CONTEXTO_PACIENTE.medicación_actual. \
7. SOAP: `subjective` = lo que dice el paciente (síntomas, antecedentes \
referidos). `objective` = signos vitales, examen físico, datos medibles. \
NUNCA copies el mismo texto en ambos.
8. Responde en español médico claro, conciso, formato JSON estricto.
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
    {"guideline_id": "<UUID exacto del bloque GUIAS_CLINICAS>", "guideline_name": "<nombre exacto>", "section": "<título exacto de la sección — ejemplo: '6. Banderas rojas — referir a obstetricia de alto riesgo'>"}
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
  "citations": [{"guideline_id": "<UUID exacto del bloque>", "guideline_name": "<nombre exacto>", "section": "<título exacto de la sección que cita>"}],
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
  "citations": [{"guideline_id": "<UUID exacto del bloque>", "guideline_name": "<nombre exacto>", "section": "<título exacto de la sección que cita>"}],
  "red_flags": []
}"""


CIRUGIA_OUTPUT = """\
{
  "pre_op_note": {
    "narrative": "...",
    "anesthesia_risk": "ASA I|II|III|IV|V",
    "pre_op_indications": "..."
  },
  "citations": [{"guideline_id": "<UUID exacto del bloque>", "guideline_name": "<nombre exacto>", "section": "<título exacto de la sección que cita>"}],
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

INSTRUCCIONES PARA CITAR (obligatorio leer):
- Las secciones citables están en el bloque GUIAS_CLINICAS de arriba, tras
  la etiqueta "Sección:". Copia ese texto LITERAL.
- Si una decisión clínica que tomas (un dx, una receta, un examen) está
  respaldada por una sección de arriba, AGRÉGALA a `citations`. Los
  documentos sin citas pierden valor — busca al menos 1-2 citas reales.
- NO inventes secciones, NO escribas "Sección" sola, NO escribas el
  número sin el título completo. Copia lo que ves.

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
