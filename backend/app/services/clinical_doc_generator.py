"""
Orquestador de generación de documentos clínicos.

Pasos:
  1. Construye CONTEXTO_PACIENTE (edad, sexo, alergias, condiciones,
     medicamentos, resumen de encounters previos cruzando áreas).
  2. RAG search con chief_complaint + transcripción → top-K chunks.
  3. Llama al LLM con prompt por área → JSON con documentos.
  4. Verifica conflictos alergia ↔ medicamento (independiente del LLM).
  5. Persiste cada documento en ClinicalDocument.

El médico siempre decide — esto solo pre-llena.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ClinicalDocument,
    DocumentType,
    Encounter,
    EncounterStatus,
    HospitalArea,
    Patient,
)
from app.prompts.clinical_docs_prompt import SYSTEM_PROMPT, build_user_prompt
from app.services import llm_service, rag_service
from app.services.encounter_highlights import extract_highlights

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del contexto del paciente
# ─────────────────────────────────────────────────────────────────────────────


def _patient_age(birth_date: datetime) -> int:
    today = datetime.now(timezone.utc)
    bd = birth_date if birth_date.tzinfo else birth_date.replace(tzinfo=timezone.utc)
    years = today.year - bd.year
    if (today.month, today.day) < (bd.month, bd.day):
        years -= 1
    return max(years, 0)


async def _summarize_recent_encounters(
    db: AsyncSession,
    patient_id: str,
    exclude_id: str,
    limit: int = 5,
) -> str:
    """Genera un resumen textual de encounters previos (cualquier área)."""
    stmt = (
        select(Encounter)
        .where(
            Encounter.patient_id == patient_id,
            Encounter.id != exclude_id,
            Encounter.status == EncounterStatus.SIGNED,
        )
        .order_by(Encounter.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    encounters = result.scalars().all()
    if not encounters:
        return "Sin atenciones previas registradas."

    lines: list[str] = []
    for e in encounters:
        date = e.started_at.strftime("%Y-%m-%d")
        area = e.area.value if hasattr(e.area, "value") else str(e.area)
        complaint = e.chief_complaint or "—"
        h = extract_highlights(e)

        block = [f"- {date} · {area} · {complaint}"]
        if h["diagnosis"]:
            block.append(f"    diagnóstico: {h['diagnosis']}")
        if h["cie10_codes"]:
            block.append(f"    CIE-10: {', '.join(h['cie10_codes'])}")
        if h["medications"]:
            block.append(f"    medicación: {' | '.join(h['medications'])}")
        if h["lab_tests"]:
            block.append(f"    exámenes: {', '.join(h['lab_tests'])}")
        if h["plan"]:
            block.append(f"    plan: {h['plan']}")
        lines.append("\n".join(block))
    return "\n".join(lines)


async def _build_patient_context(
    db: AsyncSession, patient: Patient, encounter_id: str
) -> str:
    age = _patient_age(patient.birth_date)
    allergies = ", ".join(patient.allergies or []) or "ninguna conocida"
    conditions = ", ".join(patient.active_conditions or []) or "ninguna"
    meds = ", ".join(patient.current_medications or []) or "ninguno"
    history = await _summarize_recent_encounters(db, patient.id, encounter_id)

    return f"""Nombre: {patient.full_name}
Edad: {age} años · Sexo: {patient.sex}
Alergias documentadas: {allergies}
Condiciones activas: {conditions}
Medicación actual: {meds}

Atenciones previas (cualquier área hospitalaria):
{history}"""


# ─────────────────────────────────────────────────────────────────────────────
# RAG context
# ─────────────────────────────────────────────────────────────────────────────


def _format_rag_context(hits: list[dict[str, Any]], chunk_max_chars: int = 600) -> str:
    if not hits:
        return "(sin guías relevantes encontradas)"

    blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        text = (hit.get("text") or "").strip()
        if len(text) > chunk_max_chars:
            text = text[:chunk_max_chars] + "…"
        gid = hit.get("guideline_id") or ""
        blocks.append(
            f"[{i}] guideline_id: {gid}\n"
            f"    Guía: {hit['guideline_name']} · {hit['institution']}\n"
            f"    Sección: {hit['section']}\n"
            f"    {text}"
        )
    return "\n\n".join(blocks)


def _trim_transcript(transcript: str, max_chars: int) -> str:
    """Recorta la transcripción manteniendo el INICIO (motivo, anamnesis) y
    el FINAL (plan, indicaciones). El medio se descarta porque suele ser
    diálogo redundante. Para reuniones de 10+ min esto preserva las dos
    partes con mayor contenido clínico."""
    transcript = (transcript or "").strip()
    if len(transcript) <= max_chars:
        return transcript
    half = (max_chars - 80) // 2  # 80 chars para el separador
    head = transcript[:half].rstrip()
    tail = transcript[-half:].lstrip()
    return f"{head}\n\n[…fragmento intermedio omitido por extensión…]\n\n{tail}"


# ─────────────────────────────────────────────────────────────────────────────
# Chequeo de alergias (independiente del LLM)
# ─────────────────────────────────────────────────────────────────────────────


# Mapeo grueso de medicamento → familia. El frontend / la guía MINSA tiene
# referencias más completas; esto es una verificación de seguridad básica.
_DRUG_FAMILY_KEYWORDS = {
    "sulfonamida": [
        "sulfametoxazol", "sulfa", "tmp-smx", "tmp/smx",
        "trimetoprima-sulfametoxazol", "trimetoprima/sulfametoxazol",
        "cotrimoxazol", "sulfasalazina", "sulfadiazina",
    ],
    "penicilina": [
        "amoxicilina", "ampicilina", "penicilina", "bencilpenicilina",
        "cloxacilina", "dicloxacilina", "piperacilina", "ticarcilina",
    ],
    "cefalosporina": [
        "cefalexina", "cefazolina", "cefuroxima", "ceftriaxona", "cefepime",
        "cefotaxima", "cefadroxilo", "cefoxitina", "ceftazidima",
    ],
    "aine": [
        "aspirina", "ibuprofeno", "naproxeno", "diclofenaco", "ketorolaco",
        "ketoprofeno", "indometacina", "celecoxib", "meloxicam", "piroxicam",
    ],
    "macrolido": [
        "azitromicina", "claritromicina", "eritromicina",
    ],
    "quinolona": [
        "ciprofloxacino", "levofloxacino", "moxifloxacino", "norfloxacino",
    ],
}


def check_drug_allergy_conflicts(
    drugs: list[dict[str, Any]],
    patient_allergies: list[str],
) -> list[str]:
    """Devuelve red flags si algún drug entra en conflicto con alergias."""
    flags: list[str] = []
    if not drugs or not patient_allergies:
        return flags

    allergies_lower = [a.lower() for a in patient_allergies]

    for drug in drugs:
        drug_name_raw = drug.get("name", "")
        drug_name = drug_name_raw.lower().strip()
        if not drug_name:
            continue

        for allergy in allergies_lower:
            # 1) Coincidencia directa por nombre
            if drug_name and drug_name in allergy:
                flags.append(
                    f"⚠️ {drug_name_raw} aparece directamente en alergia documentada: "
                    f"«{allergy}»"
                )
                continue

            # 2) Coincidencia por familia
            for family, keywords in _DRUG_FAMILY_KEYWORDS.items():
                allergy_mentions_family = (
                    family in allergy
                    or any(kw in allergy for kw in keywords)
                )
                drug_in_family = any(kw in drug_name for kw in keywords)
                if allergy_mentions_family and drug_in_family:
                    flags.append(
                        f"⚠️ {drug_name_raw} es {family} — paciente con alergia "
                        f"documentada: «{allergy}»"
                    )
                    break

    # Deduplicar manteniendo orden
    seen: set[str] = set()
    unique: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# Validación anti-alucinación de citas
# ─────────────────────────────────────────────────────────────────────────────


# Strings que el LLM puede generar como placeholder mal-pegado (sin reemplazar).
_CITATION_PLACEHOLDER_VALUES = {
    "",
    "sección",
    "section",
    "<copiar>",
    "<copiar tal cual>",
    "<copiar del bloque>",
    "<del bloque>",
    "...",
    "…",
    "n/a",
}


def _match_section(llm_section_norm: str, valid_sections: set[str]) -> str | None:
    """Empareja la `section` que dijo el LLM con una sección real del RAG.

    Estrategias en orden:
      1) Match exacto (case-insensitive, trimmed).
      2) La sección del LLM **empieza con** una sección real (típico cuando
         el modelo escribe "2. Diagnóstico → Sospecha pielo" pero la real
         es "2. Diagnóstico").
      3) Una sección real **empieza con** la del LLM (caso inverso).
      4) Match por número de sección al inicio: "2." → cualquier sección
         que empiece con "2."

    Devuelve la sección REAL que matcheó (no la del LLM), o None si no matchea.
    """
    if llm_section_norm in valid_sections:
        return llm_section_norm

    # Prefijo: el LLM expandió la sección con sub-puntos
    for vs in valid_sections:
        if llm_section_norm.startswith(vs + " ") or llm_section_norm.startswith(vs + "→") \
                or llm_section_norm.startswith(vs + " →") or llm_section_norm.startswith(vs + "->"):
            return vs

    # Inverso: el LLM truncó la sección
    for vs in valid_sections:
        if vs.startswith(llm_section_norm + " ") or vs.startswith(llm_section_norm + ":"):
            return vs

    # Por número al inicio ("2." matchea "2. diagnóstico")
    import re as _re
    m = _re.match(r"^(\d+)\.\s", llm_section_norm)
    if m:
        prefix = f"{m.group(1)}."
        candidates = [v for v in valid_sections if v.startswith(prefix + " ")]
        if len(candidates) == 1:
            return candidates[0]

    return None


def _validate_citations(
    citations: list[dict[str, Any]],
    rag_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filtra citas que el LLM no pudo respaldar con los hits del RAG.

    Una cita es válida si:
      1) Su `guideline_id` aparece en los hits que le pasamos al LLM.
      2) Su `section` matchea (exacto o flexible — ver `_match_section`)
         con la sección de algún hit del MISMO `guideline_id`.
      3) `section` no es un placeholder o cadena vacía.

    Cuando el match es flexible, la cita guardada lleva la sección REAL
    del RAG (no la versión expandida del LLM). Esto garantiza que el modal
    pueda recuperar la sección correctamente.
    """
    if not citations:
        return []

    valid_sections_by_gid: dict[str, set[str]] = {}
    name_by_gid: dict[str, str] = {}
    for hit in rag_hits:
        gid = (hit.get("guideline_id") or "").strip()
        if not gid:
            continue
        section_norm = (hit.get("section") or "").strip().lower()
        valid_sections_by_gid.setdefault(gid, set()).add(section_norm)
        if hit.get("guideline_name"):
            name_by_gid.setdefault(gid, hit["guideline_name"])

    # Mapa de sección normalizada → sección "raw" original para preservar capitalización.
    raw_section_by_norm: dict[tuple[str, str], str] = {}
    for hit in rag_hits:
        gid = (hit.get("guideline_id") or "").strip()
        section_raw = (hit.get("section") or "").strip()
        if gid and section_raw:
            raw_section_by_norm[(gid, section_raw.lower())] = section_raw

    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for cit in citations:
        gid = str(cit.get("guideline_id") or "").strip()
        section_raw_llm = str(cit.get("section") or "").strip()
        section_norm_llm = section_raw_llm.lower()

        if not gid or section_norm_llm in _CITATION_PLACEHOLDER_VALUES:
            logger.warning(
                "citation_dropped_placeholder",
                guideline_id=gid,
                section=section_raw_llm,
            )
            continue

        valid_sections = valid_sections_by_gid.get(gid)
        if valid_sections is None:
            logger.warning("citation_dropped_unknown_guideline", guideline_id=gid)
            continue

        matched_norm = _match_section(section_norm_llm, valid_sections)
        if matched_norm is None:
            logger.warning(
                "citation_dropped_unknown_section",
                guideline_id=gid,
                section=section_raw_llm,
                valid_sections=sorted(valid_sections),
            )
            continue

        key = (gid, matched_norm)
        if key in seen:
            continue
        seen.add(key)

        # Usa la sección REAL del RAG (no la versión expandida del LLM)
        # para que el modal pueda buscarla correctamente en Postgres.
        real_section = raw_section_by_norm.get((gid, matched_norm), matched_norm)

        if matched_norm != section_norm_llm:
            logger.info(
                "citation_section_normalized",
                guideline_id=gid,
                llm_said=section_raw_llm,
                used=real_section,
            )

        cleaned.append({
            "guideline_id": gid,
            "guideline_name": name_by_gid.get(gid, cit.get("guideline_name", "")),
            "section": real_section,
        })

    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Persistencia de documentos
# ─────────────────────────────────────────────────────────────────────────────


def _build_documents(
    encounter: Encounter,
    llm_output: dict[str, Any],
    extra_red_flags: list[str],
) -> list[ClinicalDocument]:
    """Materializa los documentos clínicos a partir del JSON del LLM."""
    citations = llm_output.get("citations") or []
    llm_red_flags = llm_output.get("red_flags") or []
    all_red_flags = list(extra_red_flags) + [str(f) for f in llm_red_flags]

    docs: list[ClinicalDocument] = []
    encounter_id = encounter.id

    def _append(doc_type: DocumentType, content: dict[str, Any]) -> None:
        if not content:
            return
        docs.append(
            ClinicalDocument(
                encounter_id=encounter_id,
                doc_type=doc_type,
                content=content,
                citations=citations,
                red_flags=all_red_flags,
                is_signed=False,
            )
        )

    # Diagnósticos diferenciales — el asistente sugiere y el médico decide
    differentials = llm_output.get("differential_diagnoses") or []
    if differentials:
        _append(DocumentType.DIFFERENTIAL_DIAGNOSES, {"options": differentials})

    soap = llm_output.get("soap")
    if soap:
        _append(DocumentType.SOAP, soap)

    rx = llm_output.get("prescription")
    if rx and rx.get("drugs"):
        _append(DocumentType.PRESCRIPTION, rx)

    labs = llm_output.get("lab_orders")
    if labs:
        _append(DocumentType.LAB_ORDER, {"tests": labs})

    triage = llm_output.get("triage_note")
    if triage:
        _append(DocumentType.TRIAGE_NOTE, triage)

    admission = llm_output.get("admission_note")
    if admission:
        _append(DocumentType.ADMISSION_NOTE, admission)

    evolution = llm_output.get("evolution_note")
    if evolution:
        _append(DocumentType.EVOLUTION_NOTE, evolution)

    pre_op = llm_output.get("pre_op_note")
    if pre_op:
        _append(DocumentType.PRE_OP_NOTE, pre_op)

    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


async def generate_documents_for_encounter(
    db: AsyncSession,
    encounter: Encounter,
) -> dict[str, Any]:
    """Genera documentos clínicos pre-llenados. Persiste en BD. Retorna resumen."""
    patient = await db.get(Patient, encounter.patient_id)
    if patient is None:
        raise ValueError(f"Paciente {encounter.patient_id} no encontrado")

    area_value = (
        encounter.area.value if hasattr(encounter.area, "value") else str(encounter.area)
    )

    # 1) Contexto del paciente (cruzando áreas previas)
    patient_context = await _build_patient_context(db, patient, encounter.id)

    # 2) RAG: busca guías relevantes según motivo + transcripción
    rag_query = " ".join(
        x for x in [encounter.chief_complaint or "", encounter.transcript or ""] if x
    ).strip() or "control clínico general"
    hits = await rag_service.search(rag_query, area=area_value, top_k=3)
    raw_transcript = encounter.transcript or ""

    logger.info(
        "clinical_docs_generating",
        encounter_id=encounter.id,
        area=area_value,
        rag_hits=len(hits),
        transcript_chars=len(raw_transcript),
    )

    # 3) LLM con estrategia de reintento auto-reductivo.
    #    Pasada 1: contexto generoso (transcript hasta 4000 chars, RAG 600 chars)
    #    Pasada 2: contexto comprimido (transcript 2500 chars, RAG 400 chars)
    #    Pasada 3: contexto mínimo (solo motivo + últimas 1500 chars del transcript)
    #    Cada nivel es más probable que quepa en num_ctx y termine el JSON.
    attempts = [
        {"transcript_chars": 4000, "rag_chars": 600, "num_predict": 5500},
        {"transcript_chars": 2500, "rag_chars": 400, "num_predict": 5500},
        {"transcript_chars": 1500, "rag_chars": 300, "num_predict": 4500},
    ]

    llm_output: dict[str, Any] | None = None
    last_exc: Exception | None = None
    for i, params in enumerate(attempts, start=1):
        rag_context = _format_rag_context(hits, chunk_max_chars=params["rag_chars"])
        transcript_for_prompt = _trim_transcript(raw_transcript, params["transcript_chars"])

        user_prompt = build_user_prompt(
            area=area_value,
            patient_context=patient_context,
            rag_context=rag_context,
            chief_complaint=encounter.chief_complaint or "",
            transcript=transcript_for_prompt,
        )

        try:
            llm_output = await llm_service.generate_json(
                user_prompt,
                system=SYSTEM_PROMPT,
                temperature=0.1,
                num_predict=params["num_predict"],
            )
            if i > 1:
                logger.warning(
                    "clinical_docs_recovered_on_retry",
                    encounter_id=encounter.id,
                    attempt=i,
                )
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "clinical_docs_llm_attempt_failed",
                encounter_id=encounter.id,
                attempt=i,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if i == len(attempts):
                logger.error("clinical_docs_llm_all_attempts_failed", error=str(exc))
                raise

    assert llm_output is not None, "Bug: llm_output no debería ser None aquí"

    # 4a) Validación anti-alucinación de citas: descarta cualquier cita cuyo
    #     guideline_id o section no aparezcan en los hits que recibió el LLM.
    #     Esto previene placeholders mal pegados ("Sección"), guías inventadas
    #     o secciones que el modelo confundió.
    raw_citations = llm_output.get("citations") or []
    valid_citations = _validate_citations(raw_citations, hits)
    llm_output["citations"] = valid_citations
    if len(valid_citations) < len(raw_citations):
        logger.info(
            "citations_filtered",
            encounter_id=encounter.id,
            received=len(raw_citations),
            kept=len(valid_citations),
        )

    # 4b) Chequeo de alergias (independiente del LLM)
    rx = llm_output.get("prescription") or {}
    drugs = rx.get("drugs") or []
    allergy_flags = check_drug_allergy_conflicts(drugs, list(patient.allergies or []))

    # 5) Si el médico está REGENERANDO (ya hay documentos no firmados), los
    #    descartamos antes de crear los nuevos. Documentos firmados no se
    #    tocan — son legalmente inmutables.
    existing_stmt = select(ClinicalDocument).where(
        ClinicalDocument.encounter_id == encounter.id,
        ClinicalDocument.is_signed.is_(False),
    )
    existing = (await db.execute(existing_stmt)).scalars().all()
    for d in existing:
        await db.delete(d)
    await db.flush()

    # 6) Materializa documentos
    docs = _build_documents(encounter, llm_output, allergy_flags)
    for d in docs:
        db.add(d)

    summary = (
        f"{len(docs)} documento(s) generado(s); "
        f"{len(allergy_flags)} red flag(s) por alergia; "
        f"{len(hits)} chunks RAG."
    )
    logger.info(
        "clinical_docs_generated",
        encounter_id=encounter.id,
        documents=len(docs),
        allergy_flags=len(allergy_flags),
    )
    return {
        "summary": summary,
        "documents": len(docs),
        "rag_hits": len(hits),
        "allergy_flags": allergy_flags,
    }
