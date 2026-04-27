"""
Extracción de campos clínicos clave de una atención.

Mismos datos sirven a dos consumidores:
1. Frontend: tarjetas ricas en el timeline del paciente
2. LLM: contexto del paciente al pre-llenar una nueva atención

Se mantiene como función pura sobre el modelo Encounter para que ambos
caminos vean exactamente la misma información clínica relevante.
"""
from __future__ import annotations

from typing import Any

from app.db.models import Encounter


def _truncate(text: str | None, limit: int = 220) -> str | None:
    if not text:
        return None
    s = str(text).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def extract_highlights(encounter: Encounter) -> dict[str, Any]:
    """Devuelve diagnóstico, CIE-10, medicamentos, exámenes y plan."""
    diagnosis: str | None = None
    plan: str | None = None
    cie10_codes: list[str] = []
    medications: list[str] = []
    lab_tests: list[str] = []

    for doc in encounter.documents:
        doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
        content = doc.content or {}

        # SOAP / ingreso / evolución / epicrisis aportan diagnóstico y plan
        if doc_type in (
            "soap",
            "admission_note",
            "evolution_note",
            "discharge_summary",
        ):
            for key in ("assessment", "diagnosis", "diagnosis_at_discharge"):
                if not diagnosis and content.get(key):
                    diagnosis = _truncate(content.get(key))
            if not plan and content.get("plan"):
                plan = _truncate(content.get("plan"))
            for code in content.get("cie10_codes") or []:
                if isinstance(code, str) and code.strip():
                    cie10_codes.append(code.strip())

        # Recetas: nombre y dosis
        if doc_type == "prescription":
            for drug in content.get("drugs") or []:
                if not isinstance(drug, dict):
                    continue
                name = (drug.get("name") or "").strip()
                if not name:
                    continue
                dose = (drug.get("dose") or "").strip()
                medications.append(f"{name} {dose}".strip())

        # Epicrisis: medicamentos al alta
        if doc_type == "discharge_summary":
            for med in content.get("discharge_medications") or []:
                if isinstance(med, str) and med.strip():
                    medications.append(med.strip())
                elif isinstance(med, dict) and (med.get("name") or "").strip():
                    name = med["name"].strip()
                    dose = (med.get("dose") or "").strip()
                    medications.append(f"{name} {dose}".strip())

        # Órdenes de laboratorio / imagen
        if doc_type in ("lab_order", "imaging_order"):
            for test in content.get("tests") or []:
                if isinstance(test, dict) and (test.get("name") or "").strip():
                    lab_tests.append(test["name"].strip())
                elif isinstance(test, str) and test.strip():
                    lab_tests.append(test.strip())

    # Dedupe preservando orden, máximo 4 ítems por lista
    def _dedupe(items: list[str], n: int = 4) -> list[str]:
        return list(dict.fromkeys(items))[:n]

    return {
        "diagnosis": diagnosis,
        "plan": plan,
        "cie10_codes": _dedupe(cie10_codes, 4),
        "medications": _dedupe(medications, 4),
        "lab_tests": _dedupe(lab_tests, 4),
    }
