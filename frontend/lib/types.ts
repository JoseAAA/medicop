// Tipos TypeScript que reflejan los schemas Pydantic del backend.
// Mantener sincronizados manualmente — un mismatch causa errores en runtime.

export type HospitalArea =
  | "emergencia"
  | "hospitalizacion"
  | "consulta_externa"
  | "cirugia";

export const HOSPITAL_AREA_LABELS: Record<HospitalArea, string> = {
  emergencia: "Emergencia",
  hospitalizacion: "Hospitalización",
  consulta_externa: "Consulta externa",
  cirugia: "Cirugía",
};

export const HOSPITAL_AREA_COLORS: Record<HospitalArea, { bg: string; text: string; border: string }> = {
  emergencia:        { bg: "bg-red-50",     text: "text-red-700",     border: "border-red-200" },
  hospitalizacion:   { bg: "bg-amber-50",   text: "text-amber-700",   border: "border-amber-200" },
  consulta_externa:  { bg: "bg-blue-50",    text: "text-blue-700",    border: "border-blue-200" },
  cirugia:           { bg: "bg-purple-50",  text: "text-purple-700",  border: "border-purple-200" },
};

export type EncounterStatus =
  | "open"
  | "documents_ready"
  | "signed"
  | "cancelled";

export type DocumentType =
  | "soap"
  | "prescription"
  | "lab_order"
  | "imaging_order"
  | "referral"
  | "evolution_note"
  | "discharge_summary"
  | "pre_op_note"
  | "surgical_report"
  | "post_op_note"
  | "triage_note"
  | "admission_note"
  | "differential_diagnoses";

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  soap: "Nota de evolución (SOAP)",
  prescription: "Receta médica",
  lab_order: "Orden de laboratorio",
  imaging_order: "Orden de imagen",
  referral: "Referencia",
  evolution_note: "Nota de evolución",
  discharge_summary: "Epicrisis",
  pre_op_note: "Nota pre-operatoria",
  surgical_report: "Reporte operatorio",
  post_op_note: "Nota post-operatoria",
  triage_note: "Nota de triaje",
  admission_note: "Nota de ingreso",
  differential_diagnoses: "Sugerencias diagnósticas",
};

export interface DifferentialDiagnosis {
  name: string;
  cie10: string | null;
  likelihood: "alta" | "media" | "baja" | string;
  rationale: string;
  guideline_section?: string | null;
}

// ── User / auth ─────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  cmp_number: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── Patient ─────────────────────────────────────────────────────────────────

export interface Patient {
  id: string;
  /** Número de Historia Clínica — identificador interno del hospital. */
  nhc: string;
  /** DNI — opcional, sirve para SIS/EsSalud/facturación. */
  dni: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  birth_date: string;
  sex: "M" | "F";
  age: number;
  allergies: string[];
  active_conditions: string[];
  current_medications: string[];
}

// ── Encounter ───────────────────────────────────────────────────────────────

export interface Encounter {
  id: string;
  patient_id: string;
  physician_id: string;
  area: HospitalArea;
  status: EncounterStatus;
  chief_complaint: string | null;
  transcript: string | null;
  started_at: string;
  signed_at: string | null;
}

export interface EncounterHighlights {
  diagnosis: string | null;
  cie10_codes: string[];
  medications: string[];
  lab_tests: string[];
  plan: string | null;
}

export interface EncounterTimelineItem {
  id: string;
  area: HospitalArea;
  status: EncounterStatus;
  chief_complaint: string | null;
  started_at: string;
  signed_at: string | null;
  document_count: number;
  highlights: EncounterHighlights;
}

// ── Clinical document ───────────────────────────────────────────────────────

export interface Citation {
  guideline_id: string | null;
  guideline_name: string;
  section: string;
  page?: number | null;
  text_excerpt?: string;
}

export interface GuidelineSection {
  section_title: string;
  text: string;
}

export interface GuidelineSectionResponse {
  guideline: {
    id: string;
    title: string;
    institution: string;
    year: number;
    category: string;
    is_demo: boolean;
  };
  section: GuidelineSection | null;
}

export interface ClinicalDocument {
  id: string;
  encounter_id: string;
  doc_type: DocumentType;
  content: Record<string, unknown>;
  citations: Citation[];
  red_flags: string[];
  is_signed: boolean;
  signed_at: string | null;
  created_at: string;
}

export interface EncounterDetail extends Encounter {
  documents: ClinicalDocument[];
}

// ── Transcription ───────────────────────────────────────────────────────────

export interface TranscriptionResponse {
  transcript: string;
  language: string;
  language_probability: number;
  duration_seconds: number;
  segments: { start: number; end: number; text: string }[];
}

// ── Errores de API ──────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
