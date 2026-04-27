// Capa tipada sobre apiClient. Cada función representa un endpoint del backend.
import { apiClient } from "./api-client";
import type {
  ClinicalDocument,
  Encounter,
  EncounterDetail,
  EncounterTimelineItem,
  HospitalArea,
  LoginRequest,
  Patient,
  TokenResponse,
  TranscriptionResponse,
  User,
} from "./types";

// ── Auth ────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (body: LoginRequest) =>
    apiClient.post<TokenResponse>("/api/auth/login", body),
  logout: () => apiClient.post<{ detail: string }>("/api/auth/logout"),
  me: () => apiClient.get<User>("/api/auth/me"),
};

// ── Patients ────────────────────────────────────────────────────────────────

export const patientsApi = {
  list: (params?: { q?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return apiClient.get<Patient[]>(`/api/patients/${qs ? "?" + qs : ""}`);
  },
  get: (id: string) => apiClient.get<Patient>(`/api/patients/${id}`),
};

// ── Encounters ──────────────────────────────────────────────────────────────

export interface CreateEncounterBody {
  patient_id: string;
  area: HospitalArea;
  chief_complaint?: string;
}

export interface EncounterMineItem {
  id: string;
  patient_id: string;
  patient_nhc: string;
  patient_full_name: string;
  area: import("./types").HospitalArea;
  status: import("./types").EncounterStatus;
  chief_complaint: string | null;
  started_at: string;
  signed_at: string | null;
}

export const encountersApi = {
  create: (body: CreateEncounterBody) =>
    apiClient.post<Encounter>("/api/encounters/", body),
  get: (id: string) => apiClient.get<EncounterDetail>(`/api/encounters/${id}`),
  byPatient: (patientId: string) =>
    apiClient.get<EncounterTimelineItem[]>(
      `/api/encounters/by-patient/${patientId}`,
    ),
  /** Atenciones del médico actual, para widgets del dashboard. */
  mine: (params?: { status?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return apiClient.get<EncounterMineItem[]>(
      `/api/encounters/mine${qs ? "?" + qs : ""}`,
    );
  },
  updateTranscript: (id: string, transcript: string) =>
    apiClient.patch<Encounter>(`/api/encounters/${id}/transcript`, {
      transcript,
    }),
  generateDocs: (id: string) =>
    apiClient.post<EncounterDetail>(
      `/api/encounters/${id}/generate-docs`,
      undefined,
      // LLM con reintentos auto-reductivos en backend puede llegar a ~3 min;
      // 4 min de timeout en cliente cubre escenario peor caso (transcripción
      // de 10 min + cold start de Ollama).
      { timeout: 240_000 },
    ),
  updateDocument: (
    encounterId: string,
    documentId: string,
    content: Record<string, unknown>,
  ) =>
    apiClient.patch<ClinicalDocument>(
      `/api/encounters/${encounterId}/documents/${documentId}`,
      { content },
    ),
  sign: (id: string) =>
    apiClient.post<EncounterDetail>(`/api/encounters/${id}/sign`),
};

// ── Transcription ───────────────────────────────────────────────────────────

export const transcriptionApi = {
  transcribe: (audioBlob: Blob, filename = "consulta.webm") => {
    const fd = new FormData();
    fd.append("file", audioBlob, filename);
    return apiClient.upload<TranscriptionResponse>("/api/transcription/", fd);
  },
};

// ── RAG ─────────────────────────────────────────────────────────────────────

export interface RAGSearchHit {
  score: number;
  guideline_id: string | null;
  guideline_name: string;
  institution: string;
  section: string;
  text: string;
  applicable_areas: string[];
}

export const ragApi = {
  search: (query: string, area?: string, top_k = 5) =>
    apiClient.post<{ query: string; hits: RAGSearchHit[] }>(
      "/api/rag/search",
      { query, area, top_k },
    ),
  /** Trae la sección específica de una guía (para mostrar la cita expandida). */
  getSection: (guidelineId: string, section?: string) => {
    const qs = section ? `?section=${encodeURIComponent(section)}` : "";
    return apiClient.get<{
      guideline: {
        id: string;
        title: string;
        institution: string;
        year: number;
        category: string;
        is_demo: boolean;
      };
      section: { section_title: string; text: string } | null;
    }>(`/api/rag/sources/${guidelineId}/section${qs}`);
  },
};
