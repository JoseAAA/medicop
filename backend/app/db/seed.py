"""Seed de datos demostrativos para MediCop.

Carga al arrancar el backend si SEED_ON_STARTUP=true (default en desarrollo) o
manualmente con `make seed`. Es **idempotente**: si detecta que el médico de
demostración ya existe, no inserta nada.

Contenido:
- 1 médico demo (Dr. Demo Test, demo@medicop.pe / Demo1234!)
- 6 pacientes peruanos con historiales cruzados entre las 4 áreas hospitalarias
- 10 guías clínicas oficiales generadas en `data-pipeline/seed-corpus/`
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.db.models import (
    ClinicalDocument,
    DocumentType,
    Encounter,
    EncounterStatus,
    Guideline,
    HospitalArea,
    Patient,
    User,
)

logger = structlog.get_logger()


# Ruta del corpus dentro del contenedor (montado desde data-pipeline/seed-corpus/)
CORPUS_DIR = Path("/app/seed-corpus")


# ─────────────────────────────────────────────────────────────────────────────
# Datos del médico demo
# ─────────────────────────────────────────────────────────────────────────────

DEMO_PHYSICIAN = {
    "email": "demo@medicop.pe",
    "password": "Demo1234!",
    "full_name": "Dr. Demo Test",
    "cmp_number": "99999",
}


# ─────────────────────────────────────────────────────────────────────────────
# Pacientes peruanos con historial cruzado entre áreas
# ─────────────────────────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc)


def _ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


PATIENTS_SEED: list[dict[str, Any]] = [
    # ── Caso estrella de la demo: cross-area + alergia a sulfas ─────────────
    {
        "nhc": "0024381",
        "dni": "41234567",
        "first_name": "María",
        "last_name": "Rodríguez Quispe",
        "birth_date": datetime(1962, 3, 14),
        "sex": "F",
        "allergies": ["Sulfonamidas (sulfas)"],
        "active_conditions": [
            "Diabetes mellitus tipo 2 (E11.9)",
            "Hipertensión arterial esencial (I10)",
        ],
        "current_medications": [
            "Metformina 850 mg c/12 h",
            "Enalapril 10 mg c/24 h",
        ],
        "encounters": [
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 180,
                "chief_complaint": "Control trimestral de diabetes e hipertensión",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Paciente refiere adherencia parcial a dieta. Niega síntomas hiperglucémicos. Toma medicación regular.",
                            "objective": "PA 138/86 mmHg. FC 76. Peso 72 kg. HbA1c 7.8%. Glucemia ayunas 142 mg/dL. Examen físico sin novedades.",
                            "assessment": "DM2 con control subóptimo. HTA controlada al límite.",
                            "cie10_codes": ["E11.9", "I10"],
                            "plan": "Continuar metformina 850 mg c/12 h. Reforzar dieta. Control en 3 meses con HbA1c.",
                        },
                    },
                    {
                        "doc_type": DocumentType.LAB_ORDER,
                        "content": {
                            "tests": [
                                {"name": "HbA1c", "urgency": "rutina"},
                                {"name": "Perfil lipídico", "urgency": "rutina"},
                                {"name": "Creatinina sérica", "urgency": "rutina"},
                                {"name": "Microalbuminuria", "urgency": "rutina"},
                            ]
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 90,
                "chief_complaint": "Control de diabetes",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Refiere mayor sed y nicturia las últimas semanas.",
                            "objective": "PA 142/88 mmHg. HbA1c 8.9%. Glucemia ayunas 178 mg/dL.",
                            "assessment": "DM2 descontrolada. HTA al límite superior.",
                            "cie10_codes": ["E11.9", "I10"],
                            "plan": "Mantener metformina y agregar empagliflozina 10 mg c/24 h. Educación nutricional. Control en 6 semanas.",
                        },
                    },
                    {
                        "doc_type": DocumentType.PRESCRIPTION,
                        "content": {
                            "drugs": [
                                {"name": "Metformina", "dose": "850 mg", "route": "oral", "frequency": "c/12 h", "duration": "indefinido"},
                                {"name": "Empagliflozina", "dose": "10 mg", "route": "oral", "frequency": "c/24 h", "duration": "indefinido"},
                                {"name": "Enalapril", "dose": "10 mg", "route": "oral", "frequency": "c/24 h", "duration": "indefinido"},
                            ]
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.EMERGENCIA,
                "started_ago_days": 30,
                "chief_complaint": "Dolor lumbar derecho + fiebre 38.5 °C de 24 h",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.TRIAGE_NOTE,
                        "content": {
                            "narrative": "Paciente DM2 con dolor lumbar derecho irradiado a flanco, fiebre 38.5 °C, disuria y polaquiuria de 24 h.",
                            "vital_signs": {"PA": "132/84", "FC": 98, "FR": 18, "T": 38.5, "SatO2": "97%"},
                            "triage_level": "II - urgente",
                        },
                    },
                    {
                        "doc_type": DocumentType.ADMISSION_NOTE,
                        "content": {
                            "narrative": "Mujer 62 años, DM2 conocida. Cuadro compatible con pielonefritis aguda derecha. Examen de orina con leucocituria masiva, nitritos positivos. Hemograma con leucocitosis 15 200 con desviación izquierda.",
                            "diagnosis": "Pielonefritis aguda derecha (N10) en paciente con DM2",
                            "indications": "Hidratación EV, antipirético, antibiótico empírico ambulatorio post-observación.",
                        },
                    },
                    {
                        # ⚠️ Documento histórico: prescribieron TMP-SMX a paciente con
                        # alergia documentada a sulfas. Esta es la falla que MediCop
                        # detectaría en una atención futura cruzando áreas.
                        "doc_type": DocumentType.PRESCRIPTION,
                        "content": {
                            "drugs": [
                                {"name": "Trimetoprima-sulfametoxazol", "dose": "160/800 mg", "route": "oral", "frequency": "c/12 h", "duration": "10 días", "notes": "Pielonefritis no complicada"},
                                {"name": "Paracetamol", "dose": "500 mg", "route": "oral", "frequency": "c/8 h SOS", "duration": "5 días"},
                            ]
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.HOSPITALIZACION,
                "started_ago_days": 1,
                "chief_complaint": "Descompensación hiperglucémica con cetonuria",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.ADMISSION_NOTE,
                        "content": {
                            "narrative": "Paciente DM2 ingresa por glucemia 412 mg/dL, cetonuria ++, deshidratación moderada. Bicarbonato sérico 16 mEq/L, pH 7.32. Cetoacidosis diabética leve.",
                            "diagnosis": "Cetoacidosis diabética leve (E11.1) en paciente con DM2 descompensada",
                            "indications": "Hidratación EV con SS 0.9% 1000 mL primera hora. Insulina regular en infusión 0.1 UI/kg/h. Reposición de potasio. Monitorización cada hora.",
                        },
                    },
                    {
                        "doc_type": DocumentType.EVOLUTION_NOTE,
                        "content": {
                            "narrative": "Paciente estable, glucemia descendió a 180 mg/dL en 6 horas. Cetonuria negativa. Tolerando vía oral. Pasamos a esquema basal-bolo subcutáneo.",
                            "vital_signs": {"PA": "128/78", "FC": 82, "T": 36.8, "Glucemia": 178},
                        },
                    },
                    {
                        "doc_type": DocumentType.DISCHARGE_SUMMARY,
                        "content": {
                            "summary": "Paciente egresa estable tras 24 h de hospitalización por cetoacidosis diabética leve resuelta con hidratación e insulinoterapia. Se ajusta tratamiento ambulatorio.",
                            "diagnosis_at_discharge": "DM2 descompensada (E11.65) - resuelta. HTA estable (I10).",
                            "discharge_medications": [
                                "Insulina glargina 18 UI subcutáneas al acostarse",
                                "Insulina lispro 6 UI antes de cada comida",
                                "Metformina 850 mg c/12 h",
                                "Enalapril 10 mg c/24 h",
                            ],
                            "follow_up": "Control en consulta externa en 7 días con glucemias capilares.",
                        },
                    },
                ],
            },
        ],
    },
    # ── Sr. García: HTA + SCA reciente ──────────────────────────────────────
    {
        "nhc": "0019472",
        "dni": "09876543",
        "first_name": "Juan",
        "last_name": "García López",
        "birth_date": datetime(1966, 7, 22),
        "sex": "M",
        "allergies": ["Penicilina (rash generalizado)"],
        "active_conditions": [
            "Hipertensión arterial esencial (I10)",
            "Dislipidemia mixta (E78.2)",
            "Cardiopatía isquémica post-IAM (I25.2)",
        ],
        "current_medications": [
            "Aspirina 100 mg c/24 h",
            "Clopidogrel 75 mg c/24 h",
            "Atorvastatina 80 mg c/24 h",
            "Bisoprolol 5 mg c/24 h",
            "Losartán 50 mg c/24 h",
        ],
        "encounters": [
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 365,
                "chief_complaint": "Hallazgo de PA elevada en chequeo laboral",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Asintomático. Antecedente paterno de IAM a los 62 años.",
                            "objective": "PA 162/96 mmHg en tres mediciones. ECG sin alteraciones agudas. Perfil lipídico: LDL 168 mg/dL.",
                            "assessment": "HTA estadio 2 de novo. Dislipidemia.",
                            "cie10_codes": ["I10", "E78.2"],
                            "plan": "Iniciar losartán 50 mg c/24 h y atorvastatina 20 mg c/24 h. Cambios de estilo de vida.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 60,
                "chief_complaint": "Control de HTA y dislipidemia",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Tolera bien la medicación. Camina 30 min/día. Niega síntomas cardiovasculares.",
                            "objective": "PA 134/82. LDL 102 mg/dL.",
                            "assessment": "HTA controlada. Dislipidemia con respuesta parcial.",
                            "cie10_codes": ["I10", "E78.2"],
                            "plan": "Subir atorvastatina a 40 mg c/24 h. Continuar losartán.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.EMERGENCIA,
                "started_ago_days": 7,
                "chief_complaint": "Dolor opresivo precordial irradiado al brazo izquierdo de 30 minutos",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.TRIAGE_NOTE,
                        "content": {
                            "narrative": "Varón 58 años con dolor opresivo precordial 8/10 irradiado a brazo izquierdo y mandíbula, de 30 minutos, asociado a sudoración y náuseas.",
                            "vital_signs": {"PA": "152/94", "FC": 102, "FR": 22, "SatO2": "94%"},
                            "triage_level": "I - emergencia",
                        },
                    },
                    {
                        "doc_type": DocumentType.ADMISSION_NOTE,
                        "content": {
                            "narrative": "ECG con depresión del ST 1 mm en cara inferolateral. Troponina T inicial 0.08 ng/mL (elevada). GRACE score 142.",
                            "diagnosis": "SCA sin elevación del ST (I21.4) — IAM tipo NSTEMI",
                            "indications": "AAS 300 mg, clopidogrel 600 mg de carga, enoxaparina 60 mg SC c/12 h, atorvastatina 80 mg, bisoprolol 2.5 mg. Coronariografía urgente.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.HOSPITALIZACION,
                "started_ago_days": 6,
                "chief_complaint": "Post-cateterismo cardiaco — colocación de stent en CD",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.DISCHARGE_SUMMARY,
                        "content": {
                            "summary": "Paciente con NSTEMI tratado mediante coronariografía con angioplastia + stent farmacoactivo en arteria coronaria derecha. Evolución favorable, sin complicaciones. Estable al alta.",
                            "diagnosis_at_discharge": "Cardiopatía isquémica post-IAM no Q (I25.2). Stent farmacoactivo en CD.",
                            "discharge_medications": [
                                "Aspirina 100 mg c/24 h indefinido",
                                "Clopidogrel 75 mg c/24 h por 12 meses",
                                "Atorvastatina 80 mg c/24 h",
                                "Bisoprolol 5 mg c/24 h",
                                "Losartán 50 mg c/24 h",
                            ],
                            "follow_up": "Cardiología en 2 semanas. Rehabilitación cardiaca al mes.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 3,
                "chief_complaint": "Control post-alta tras IAM",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Asintomático. Tolera bien la doble antiagregación. Caminata diaria 20 min sin disnea ni angina.",
                            "objective": "PA 124/78. FC 64. Examen físico sin novedades. Cicatriz de punción radial limpia.",
                            "assessment": "Cardiopatía isquémica post-IAM en buena evolución. HTA controlada.",
                            "cie10_codes": ["I25.2", "I10"],
                            "plan": "Mantener tratamiento. Iniciar rehabilitación cardiaca. Solicitar ecocardiograma de control.",
                        },
                    },
                ],
            },
        ],
    },
    # ── Sra. Mendoza: gestante 32 semanas con sangrado reciente ─────────────
    {
        "nhc": "0031925",
        "dni": "71234567",
        "first_name": "Carmen",
        "last_name": "Mendoza Flores",
        "birth_date": datetime(1990, 11, 5),
        "sex": "F",
        "allergies": [],
        "active_conditions": [
            "Embarazo de 32 semanas (Z34.83)",
        ],
        "current_medications": [
            "Sulfato ferroso 60 mg + ácido fólico 0.4 mg c/24 h",
            "Calcio 1000 mg c/24 h",
        ],
        "encounters": [
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 150,
                "chief_complaint": "Primera consulta prenatal",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "G2 P1, FUM hace 11 semanas. Embarazo deseado.",
                            "objective": "Examen ginecológico normal. Útero acorde a edad gestacional. PA 110/70.",
                            "assessment": "Gestación de 11 semanas — primera atención prenatal.",
                            "cie10_codes": ["Z34.83"],
                            "plan": "Iniciar suplementación con hierro y ácido fólico. Solicitar exámenes de primer trimestre.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 90,
                "chief_complaint": "Tercer control prenatal — semana 22",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Refiere movimientos fetales activos. Niega banderas rojas.",
                            "objective": "Altura uterina 22 cm. LCF 148 lpm. PA 116/74. Ecografía morfológica normal, sin malformaciones.",
                            "assessment": "Gestación de 22 semanas en evolución normal.",
                            "cie10_codes": ["Z34.83"],
                            "plan": "Continuar suplementación. PTOG entre semanas 24–28. Control en 4 semanas.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 30,
                "chief_complaint": "Disuria y polaquiuria",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Disuria, polaquiuria de 48 horas. Sin fiebre ni dolor lumbar.",
                            "objective": "PA 118/72. Examen abdominal normal. PPRU bilateral negativo.",
                            "assessment": "Cistitis aguda en gestante de 28 semanas.",
                            "cie10_codes": ["N30.0"],
                            "plan": "Cefalexina 500 mg c/8 h por 7 días. Solicitar urocultivo. Control en 7 días.",
                        },
                    },
                    {
                        "doc_type": DocumentType.PRESCRIPTION,
                        "content": {
                            "drugs": [
                                {"name": "Cefalexina", "dose": "500 mg", "route": "oral", "frequency": "c/8 h", "duration": "7 días"}
                            ]
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.EMERGENCIA,
                "started_ago_days": 2,
                "chief_complaint": "Sangrado vaginal escaso de 4 horas",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.TRIAGE_NOTE,
                        "content": {
                            "narrative": "Gestante 32 semanas con sangrado vaginal escaso, sin dolor abdominal ni contracciones. Movimientos fetales presentes.",
                            "vital_signs": {"PA": "110/70", "FC": 88, "FR": 16, "T": 36.8},
                            "triage_level": "II - urgente",
                        },
                    },
                    {
                        "doc_type": DocumentType.ADMISSION_NOTE,
                        "content": {
                            "narrative": "Ecografía obstétrica: feto único vivo, FCF 142 lpm, placenta de inserción normal, sin desprendimiento ni placenta previa. Cervicometría 32 mm. Especuloscopia: sangrado escaso del orificio cervical externo.",
                            "diagnosis": "Sangrado vaginal en gestación de 32 semanas — etiología incierta",
                            "indications": "Observación 6 horas. Reposo. Si reanuda sangrado o dolor, valorar.",
                        },
                    },
                ],
            },
            # ── HOY: control post-emergencia que el médico abrió pero no terminó ──
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 0,
                "chief_complaint": "Control post-emergencia (sangrado) + posible recidiva ITU",
                "signed": False,
                "documents": [],
            },
        ],
    },
    # ── Niño Diego: NAC pediátrica reciente ─────────────────────────────────
    {
        "nhc": "0034001",
        "dni": "81234567",
        "first_name": "Diego",
        "last_name": "Vargas Huamán",
        "birth_date": datetime(2021, 8, 10),
        "sex": "M",
        "allergies": [],
        "active_conditions": [],
        "current_medications": [],
        "encounters": [
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 120,
                "chief_complaint": "Control de niño sano — 4 años",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Niño activo, alimentación variada, sin enfermedades intercurrentes.",
                            "objective": "Peso 16 kg (P50). Talla 102 cm (P50). Hb 12.4 g/dL. Vacunas al día.",
                            "assessment": "Niño sano de 4 años con desarrollo adecuado.",
                            "cie10_codes": ["Z00.129"],
                            "plan": "Mantener alimentación balanceada. Próximo control en 6 meses.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.EMERGENCIA,
                "started_ago_days": 14,
                "chief_complaint": "Tos + fiebre 39 °C + dificultad respiratoria de 3 días",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.TRIAGE_NOTE,
                        "content": {
                            "narrative": "Niño 4 años con tos productiva, fiebre 39.2 °C, taquipnea (FR 48) y tiraje subcostal moderado. Saturación 92%.",
                            "vital_signs": {"FC": 138, "FR": 48, "T": 39.2, "SatO2": "92%"},
                            "triage_level": "II - urgente",
                        },
                    },
                    {
                        "doc_type": DocumentType.ADMISSION_NOTE,
                        "content": {
                            "narrative": "Radiografía de tórax con infiltrado alveolar en lóbulo medio derecho. Hemograma: leucocitos 18 500 con desviación izquierda. PCR 124 mg/L.",
                            "diagnosis": "Neumonía adquirida en la comunidad — lóbulo medio derecho (J18.9). Hipoxemia leve.",
                            "indications": "Hospitalizar. Ampicilina 200 mg/kg/día EV c/6 h. Oxígeno por cánula nasal a 1 L/min. Hidratación.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.HOSPITALIZACION,
                "started_ago_days": 9,
                "chief_complaint": "Continuación de manejo de NAC pediátrica",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.EVOLUTION_NOTE,
                        "content": {
                            "narrative": "Día 5 de hospitalización. Afebril 48 horas. Saturación 96% sin oxígeno. Tolera vía oral. Radiografía de control con mejoría.",
                            "vital_signs": {"FC": 102, "FR": 28, "T": 36.5, "SatO2": "96%"},
                        },
                    },
                    {
                        "doc_type": DocumentType.DISCHARGE_SUMMARY,
                        "content": {
                            "summary": "Niño egresa tras 5 días de hospitalización por NAC con buena respuesta a ampicilina EV. Completar 5 días adicionales de amoxicilina oral.",
                            "diagnosis_at_discharge": "Neumonía adquirida en la comunidad lóbulo medio derecho (J18.9), resuelta clínicamente.",
                            "discharge_medications": [
                                "Amoxicilina suspensión 50 mg/kg/día c/8 h por 5 días",
                            ],
                            "follow_up": "Control en consulta externa en 7 días.",
                        },
                    },
                ],
            },
        ],
    },
    # ── Sr. Silva: 71 años, EPOC + cirugía previa ───────────────────────────
    {
        "nhc": "0008153",
        "dni": "06543210",
        "first_name": "Roberto",
        "last_name": "Silva Paredes",
        "birth_date": datetime(1953, 5, 30),
        "sex": "M",
        "allergies": ["AINEs (aspirina, ibuprofeno) — broncoespasmo"],
        "active_conditions": [
            "EPOC moderada (J44.9)",
            "Hipertensión arterial (I10)",
            "Fibrilación auricular paroxística (I48.0)",
            "Hiperplasia prostática post-RTU (N40.1)",
        ],
        "current_medications": [
            "Tiotropio 18 µg inhalado c/24 h",
            "Salmeterol/fluticasona 50/250 µg inhalado c/12 h",
            "Apixabán 5 mg c/12 h",
            "Amlodipino 5 mg c/24 h",
            "Tamsulosina 0.4 mg c/24 h",
        ],
        "encounters": [
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 240,
                "chief_complaint": "Disuria y nocturia de varios meses",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Disuria, chorro débil, nocturia 3 veces. Próstata grado II al tacto rectal.",
                            "objective": "PSA 4.2 ng/mL. IPSS 22. Ecografía con próstata de 65 cc.",
                            "assessment": "Hiperplasia prostática benigna sintomática severa.",
                            "cie10_codes": ["N40"],
                            "plan": "Referir a urología para evaluación de cirugía. Continuar tamsulosina 0.4 mg c/24 h.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CIRUGIA,
                "started_ago_days": 180,
                "chief_complaint": "Resección transuretral de próstata programada",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.PRE_OP_NOTE,
                        "content": {
                            "narrative": "Paciente programado para RTU prostática. Comorbilidades: EPOC moderada controlada, FA en apixabán (suspendido 48 h pre-op). PA controlada.",
                            "anesthesia_risk": "ASA III",
                            "pre_op_indications": "NPO desde medianoche. Profilaxis antibiótica con cefazolina 2 g 30 min antes de incisión.",
                        },
                    },
                    {
                        "doc_type": DocumentType.SURGICAL_REPORT,
                        "content": {
                            "procedure": "Resección transuretral de próstata (RTU) bajo anestesia raquídea",
                            "findings": "Próstata adenomatosa de 65 cc resecada en 60 minutos. Sangrado mínimo, sin complicaciones.",
                            "specimen": "Tejido prostático enviado a anatomía patológica.",
                            "duration_minutes": 60,
                        },
                    },
                    {
                        "doc_type": DocumentType.POST_OP_NOTE,
                        "content": {
                            "narrative": "Post-operatorio inmediato sin complicaciones. Sonda Foley 22 Fr con irrigación continua. Diuresis adecuada, sin hematuria significativa.",
                            "indications": "Antibiótico profiláctico 24 h. Reanudar apixabán a las 48 h. Retiro de sonda al tercer día.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.EMERGENCIA,
                "started_ago_days": 60,
                "chief_complaint": "Disnea progresiva + tos productiva amarillenta de 3 días",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.TRIAGE_NOTE,
                        "content": {
                            "narrative": "EPOC conocido con disnea en reposo, esputo purulento, sibilancias audibles. Saturación 89%.",
                            "vital_signs": {"PA": "146/88", "FC": 108, "FR": 26, "SatO2": "89%"},
                            "triage_level": "II - urgente",
                        },
                    },
                    {
                        "doc_type": DocumentType.ADMISSION_NOTE,
                        "content": {
                            "narrative": "Exacerbación aguda EPOC tipo I de Anthonisen (3 síntomas cardinales). Sin acidosis respiratoria en gases (pH 7.38, PaCO2 48). Tratamiento ambulatorio dado buen apoyo familiar.",
                            "diagnosis": "Exacerbación aguda de EPOC (J44.1)",
                            "indications": "Salbutamol + ipratropio nebulizado c/6 h. Prednisona 40 mg c/24 h por 5 días. Amoxicilina-clavulánico 875/125 mg c/12 h por 7 días.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 7,
                "chief_complaint": "Control de rutina cardiopulmonar",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Tolera bien medicación. Disnea solo a esfuerzo. Sin angina ni palpitaciones.",
                            "objective": "PA 132/78. FC 72 regular. SatO2 95%. Auscultación con sibilancias espiratorias escasas.",
                            "assessment": "EPOC estable. HTA controlada. FA con apixabán.",
                            "cie10_codes": ["J44.9", "I10", "I48.0"],
                            "plan": "Mantener tratamiento. Vacunación antiinfluenza. Control en 3 meses.",
                        },
                    },
                ],
            },
        ],
    },
    # ── Sra. Castillo: ITU baja reciente ────────────────────────────────────
    {
        "nhc": "0028719",
        "dni": "71234999",
        "first_name": "Lucía",
        "last_name": "Castillo Núñez",
        "birth_date": datetime(1996, 2, 14),
        "sex": "F",
        "allergies": [],
        "active_conditions": [],
        "current_medications": [],
        "encounters": [
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 60,
                "chief_complaint": "Chequeo general anual",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Sin síntomas ni quejas. Activa, deportista. Niega antecedentes familiares de relevancia.",
                            "objective": "PA 110/68. IMC 22. Examen físico sin novedades.",
                            "assessment": "Mujer joven sana en chequeo de rutina.",
                            "cie10_codes": ["Z00.00"],
                            "plan": "Hemograma, perfil lipídico, glucemia. Papanicolaou trienal.",
                        },
                    },
                ],
            },
            {
                "area": HospitalArea.CONSULTA_EXTERNA,
                "started_ago_days": 7,
                "chief_complaint": "Disuria, polaquiuria y urgencia de 36 horas",
                "signed": True,
                "documents": [
                    {
                        "doc_type": DocumentType.SOAP,
                        "content": {
                            "subjective": "Disuria, polaquiuria, urgencia miccional. Sin fiebre ni dolor lumbar.",
                            "objective": "Examen abdominal normal. PPRU negativo bilateral.",
                            "assessment": "Cistitis aguda no complicada en mujer no gestante.",
                            "cie10_codes": ["N30.0"],
                            "plan": "Nitrofurantoína 100 mg c/6 h por 5 días. Hidratación abundante. Control si no mejora en 48 h.",
                        },
                    },
                    {
                        "doc_type": DocumentType.PRESCRIPTION,
                        "content": {
                            "drugs": [
                                {"name": "Nitrofurantoína", "dose": "100 mg", "route": "oral", "frequency": "c/6 h", "duration": "5 días"}
                            ]
                        },
                    },
                ],
            },
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Lógica del seed
# ─────────────────────────────────────────────────────────────────────────────


async def seed_demo_data() -> dict[str, int] | None:
    """Inserta datos demostrativos. Idempotente por entidad — si solo falta una
    parte (ej. se borraron encounters pero los pacientes están), agrega lo que
    falta en lugar de saltar todo o duplicar.

    Retorna conteos de lo recién insertado, o None si todo ya estaba.
    """

    async with AsyncSessionLocal() as session:
        # 1. Médico demo (idempotente por email)
        existing = await session.execute(
            select(User).where(User.email == DEMO_PHYSICIAN["email"])
        )
        physician = existing.scalar_one_or_none()
        physician_created = False
        if physician is None:
            physician = User(
                email=DEMO_PHYSICIAN["email"],
                hashed_password=hash_password(DEMO_PHYSICIAN["password"]),
                full_name=DEMO_PHYSICIAN["full_name"],
                cmp_number=DEMO_PHYSICIAN["cmp_number"],
                is_active=True,
            )
            session.add(physician)
            await session.flush()
            physician_created = True

        # 2. Pacientes + encounters + documentos (idempotente por NHC y por
        # presencia de encounters). Si el paciente ya existe, no se duplica.
        # Si el paciente existe PERO no tiene encounters, los agrega.
        seed_data = copy.deepcopy(PATIENTS_SEED)
        patient_count = 0
        encounter_count = 0
        doc_count = 0

        for p_data in seed_data:
            encounters_data = p_data.pop("encounters", [])

            # ¿Existe el paciente?
            result = await session.execute(
                select(Patient).where(Patient.nhc == p_data["nhc"])
            )
            patient = result.scalar_one_or_none()
            if patient is None:
                patient = Patient(**p_data)
                session.add(patient)
                await session.flush()
                patient_count += 1

            # ¿Tiene al menos un encounter? Si sí, no tocamos el historial
            existing_enc = await session.execute(
                select(Encounter.id).where(Encounter.patient_id == patient.id).limit(1)
            )
            if existing_enc.scalar_one_or_none() is not None:
                continue

            # Sin encounters → re-creamos el historial completo
            for enc_data in encounters_data:
                docs_data = enc_data.pop("documents", [])
                signed = enc_data.pop("signed", False)
                started_ago = enc_data.pop("started_ago_days")

                started_at = _ago(started_ago)
                signed_at = (started_at + timedelta(hours=1)) if signed else None
                status = EncounterStatus.SIGNED if signed else EncounterStatus.OPEN

                encounter = Encounter(
                    patient_id=patient.id,
                    physician_id=physician.id,
                    started_at=started_at,
                    signed_at=signed_at,
                    status=status,
                    **enc_data,
                )
                session.add(encounter)
                await session.flush()
                encounter_count += 1

                for doc_data in docs_data:
                    doc = ClinicalDocument(
                        encounter_id=encounter.id,
                        is_signed=signed,
                        signed_at=signed_at,
                        created_at=started_at,
                        **doc_data,
                    )
                    session.add(doc)
                    doc_count += 1

        # Si todo ya estaba (médico + cada paciente con sus encounters + 10
        # guías), retornamos None para que el log diga "skipped".
        if (
            not physician_created
            and patient_count == 0
            and encounter_count == 0
        ):
            # Aún así dejamos correr la sección de guías por si faltan.
            pass

        # 3. Guías clínicas desde corpus — idempotente: chequea por título antes de insertar
        guideline_count = 0
        if CORPUS_DIR.exists():
            metadata_path = CORPUS_DIR / "metadata.json"
            if metadata_path.exists():
                with metadata_path.open(encoding="utf-8") as fp:
                    meta = json.load(fp)

                existing_titles = {
                    row[0]
                    for row in (
                        await session.execute(select(Guideline.title))
                    ).all()
                }

                for entry in meta.get("guidelines", []):
                    if entry["title"] in existing_titles:
                        continue
                    md_path = CORPUS_DIR / entry["filename"]
                    if not md_path.exists():
                        logger.warning("seed_guideline_missing", filename=entry["filename"])
                        continue
                    g = Guideline(
                        title=entry["title"],
                        institution=entry["institution"],
                        year=entry["year"],
                        category=entry["category"],
                        applicable_areas=entry["applicable_areas"],
                        content=md_path.read_text(encoding="utf-8"),
                        is_demo=True,
                    )
                    session.add(g)
                    guideline_count += 1
        else:
            logger.warning("seed_corpus_not_found", path=str(CORPUS_DIR))

        await session.commit()

        # Si NO se insertó NADA, retornamos None (lifespan loguea "skipped")
        if (
            not physician_created
            and patient_count == 0
            and encounter_count == 0
            and doc_count == 0
            and guideline_count == 0
        ):
            return None

        return {
            "patients": patient_count,
            "encounters": encounter_count,
            "documents": doc_count,
            "guidelines": guideline_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point CLI: `python -m app.db.seed` (usado por scripts/seed_database.sh)
# ─────────────────────────────────────────────────────────────────────────────


async def _main() -> None:
    from app.core.database import Base, engine
    from app.db import models  # noqa: F401  -- registra metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    result = await seed_demo_data()
    if result is None:
        print("[seed] datos ya presentes — no se inserta nada (idempotente).")
    else:
        print(
            f"[seed] insertados: {result['patients']} pacientes, "
            f"{result['encounters']} encounters, {result['documents']} documentos, "
            f"{result['guidelines']} guías clínicas."
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
