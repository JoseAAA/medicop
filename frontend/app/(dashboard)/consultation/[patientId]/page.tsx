"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  History,
  Mic,
  FileText,
  PenLine,
} from "lucide-react";

import AreaBadge from "@/components/encounter/area-badge";
import AudioRecorder from "@/components/consultation/audio-recorder";
import DocumentCard from "@/components/consultation/document-card";
import DifferentialDiagnosesCard from "@/components/consultation/differential-diagnoses-card";
import CommonDiagnosesPicker from "@/components/consultation/common-diagnoses-picker";
import PatientContextPanel from "@/components/patient/patient-context-panel";
import { encountersApi, patientsApi } from "@/lib/api";
import {
  ApiError,
  HOSPITAL_AREA_LABELS,
  type EncounterTimelineItem,
} from "@/lib/types";

// La ruta del archivo es `consultation/[patientId]` por compatibilidad con
// el scaffolding original, pero el parámetro recibido es el `encounterId`.
export default function ConsultationPage({
  params,
}: {
  params: Promise<{ patientId: string }>;
}) {
  const { patientId: encounterId } = use(params);
  const queryClient = useQueryClient();

  const {
    data: encounter,
    isLoading: encounterLoading,
    error: encounterError,
  } = useQuery({
    queryKey: ["encounter", encounterId],
    queryFn: () => encountersApi.get(encounterId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "open" || status === "documents_ready" ? 5000 : false;
    },
  });

  const { data: patient } = useQuery({
    queryKey: ["patient", encounter?.patient_id],
    queryFn: () => patientsApi.get(encounter!.patient_id),
    enabled: !!encounter?.patient_id,
  });

  // Atenciones previas del paciente — para el "resumen del paciente"
  const { data: timeline } = useQuery({
    queryKey: ["encounters", "by-patient", encounter?.patient_id],
    queryFn: () => encountersApi.byPatient(encounter!.patient_id),
    enabled: !!encounter?.patient_id,
  });

  const [transcript, setTranscript] = useState("");
  const [transcriptError, setTranscriptError] = useState<string | null>(null);

  // Sincroniza la transcripción local con la del encounter al cargar
  useEffect(() => {
    if (encounter?.transcript) setTranscript(encounter.transcript);
  }, [encounter?.transcript]);

  const saveTranscriptMutation = useMutation({
    mutationFn: (text: string) => encountersApi.updateTranscript(encounterId, text),
    onError: (err) => {
      setTranscriptError(
        err instanceof ApiError ? err.message : "No se pudo guardar la transcripción",
      );
    },
    onSuccess: () => {
      setTranscriptError(null);
      queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => encountersApi.generateDocs(encounterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
    },
  });

  const signMutation = useMutation({
    mutationFn: () => encountersApi.sign(encounterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
      queryClient.invalidateQueries({
        queryKey: ["encounters", "by-patient", encounter?.patient_id],
      });
    },
  });

  // ── Estados de carga / error ─────────────────────────────────────────────

  if (encounterLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-medicop-text-muted">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Cargando consulta…
      </div>
    );
  }

  if (encounterError || !encounter) {
    return (
      <div className="max-w-md mx-auto medicop-card p-8 text-center">
        <AlertTriangle className="w-8 h-8 text-medicop-danger mx-auto mb-3" />
        <p className="text-sm text-medicop-text-muted">
          No se pudo cargar la atención.
        </p>
        <Link href="/patients" className="text-medicop-primary text-sm mt-4 inline-block">
          ← Volver a pacientes
        </Link>
      </div>
    );
  }

  const isSigned = encounter.status === "signed";
  const hasDocuments = encounter.documents.length > 0;
  const allRedFlags = encounter.documents.flatMap((d) => d.red_flags);

  // Última atención previa firmada (excluyendo la actual)
  const lastSignedPrior = (timeline ?? []).find(
    (t: EncounterTimelineItem) =>
      t.id !== encounter.id && t.status === "signed",
  );

  // Pasos del flujo: hace claro al médico dónde está
  const step =
    isSigned ? 4
    : hasDocuments ? 3
    : transcript.trim() ? 2
    : 1;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="max-w-7xl mx-auto">
      {patient && (
        <Link
          href={`/patients/${patient.id}`}
          className="inline-flex items-center gap-1.5 text-sm text-medicop-text-muted hover:text-medicop-primary mb-4 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Ficha del paciente
        </Link>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Columna izquierda — contexto del paciente */}
        {patient ? (
          <PatientContextPanel patient={patient} />
        ) : (
          <div className="medicop-card p-4 text-medicop-text-muted text-sm">
            Cargando paciente…
          </div>
        )}

        {/* Columna derecha — workspace */}
        <div className="space-y-4">
          {/* Header de la atención + indicador de paso */}
          <div className="medicop-card p-5">
            <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <AreaBadge area={encounter.area} size="md" />
                  {isSigned && (
                    <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Firmada
                    </span>
                  )}
                </div>
                {encounter.chief_complaint ? (
                  <h1 className="text-lg font-semibold text-medicop-text leading-snug mt-1">
                    {encounter.chief_complaint}
                  </h1>
                ) : (
                  <h1 className="text-lg font-semibold text-medicop-text-muted italic leading-snug mt-1">
                    Sin motivo de consulta indicado todavía
                  </h1>
                )}
              </div>
            </div>

            {!isSigned && <StepBar current={step} />}
          </div>

          {/* Resumen del paciente — lo que MediCop le recuerda al médico */}
          {lastSignedPrior && !isSigned && (
            <PatientRecap last={lastSignedPrior} />
          )}

          {/* Señales de alarma consolidadas */}
          {allRedFlags.length > 0 && (
            <div
              className="medicop-card border-2 border-red-300 bg-red-50 p-4"
              role="alert"
            >
              <div className="flex items-center gap-2 text-red-800 font-bold mb-2">
                <AlertTriangle className="w-5 h-5" />
                Señales de alarma detectadas por MediCop
              </div>
              <ul className="space-y-1 ml-7 list-disc">
                {[...new Set(allRedFlags)].map((f, i) => (
                  <li key={i} className="text-sm text-red-800 leading-snug">
                    {f}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-red-700 mt-3 ml-7">
                Verifica cada punto antes de firmar.
              </p>
            </div>
          )}

          {/* Grabación + transcripción */}
          {!isSigned && (
            <AudioRecorder
              encounterId={encounterId}
              patientNhc={patient?.nhc}
              disabled={generateMutation.isPending}
              onTranscript={(text) => {
                const merged = transcript
                  ? `${transcript}\n${text}`
                  : text;
                setTranscript(merged);
                saveTranscriptMutation.mutate(merged);
              }}
            />
          )}

          <div className="medicop-card p-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-medicop-text">
                Transcripción de la consulta
              </h3>
              {saveTranscriptMutation.isPending && (
                <span className="text-[11px] text-medicop-text-muted inline-flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  guardando…
                </span>
              )}
            </div>
            <textarea
              rows={6}
              value={transcript}
              disabled={isSigned}
              onChange={(e) => setTranscript(e.target.value)}
              onBlur={() => {
                if (transcript && transcript !== encounter.transcript) {
                  saveTranscriptMutation.mutate(transcript);
                }
              }}
              placeholder="La transcripción aparecerá aquí tras detener la grabación. También puedes editar a mano."
              className="medicop-input font-mono text-sm leading-relaxed"
            />
            {transcriptError && (
              <p className="text-xs text-red-600 mt-2">{transcriptError}</p>
            )}

            {!isSigned && (
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => generateMutation.mutate()}
                  disabled={!transcript.trim() || generateMutation.isPending}
                  className="medicop-btn-primary text-sm inline-flex items-center gap-2 disabled:opacity-50"
                >
                  {generateMutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generando documentos (puede tardar 10-30 s)…
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      {hasDocuments
                        ? "Regenerar documentos"
                        : "Generar documentos clínicos"}
                    </>
                  )}
                </button>
                {generateMutation.isError && (
                  <span className="text-xs text-red-600">
                    {(generateMutation.error as ApiError)?.message ??
                      "Error al generar"}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Sugerencias diagnósticas — el asistente propone, el médico decide */}
          {(() => {
            const differentialDoc = encounter.documents.find(
              (d) => d.doc_type === "differential_diagnoses",
            );
            const soapDoc = encounter.documents.find(
              (d) => d.doc_type === "soap",
            );
            return (
              <>
                {differentialDoc && (
                  <DifferentialDiagnosesCard
                    document={differentialDoc}
                    soapDocument={soapDoc}
                    encounterId={encounterId}
                    readOnly={isSigned}
                  />
                )}
                {soapDoc && !isSigned && (
                  <CommonDiagnosesPicker
                    soapDocument={soapDoc}
                    encounterId={encounterId}
                    disabled={isSigned}
                  />
                )}
              </>
            );
          })()}

          {/* Documentos generados (excluyendo el de diferenciales) */}
          {hasDocuments && (
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-medicop-text-muted uppercase tracking-wide pl-1">
                Documentos clínicos
              </h2>
              {encounter.documents
                .filter((doc) => doc.doc_type !== "differential_diagnoses")
                .map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    document={doc}
                    encounterId={encounterId}
                  />
                ))}
            </div>
          )}

          {/* Firma final */}
          {hasDocuments && !isSigned && (
            <div className="medicop-card p-5 bg-medicop-primary-light/40 border-medicop-primary/30">
              <div className="flex items-start gap-3">
                <ShieldCheck className="w-5 h-5 text-medicop-primary mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold text-medicop-text">
                    Firmar y archivar la atención
                  </p>
                  <p className="text-sm text-medicop-text-muted mt-0.5">
                    Una vez firmados, los documentos no se pueden modificar y
                    queda un registro permanente conforme a la Ley 29733.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => signMutation.mutate()}
                  disabled={signMutation.isPending}
                  className="medicop-btn-primary text-sm inline-flex items-center gap-2"
                >
                  {signMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Firmar todo
                </button>
              </div>
              {signMutation.isError && (
                <p className="text-xs text-red-600 mt-3 ml-8">
                  {(signMutation.error as ApiError)?.message ?? "Error al firmar"}
                </p>
              )}
            </div>
          )}

          {isSigned && (
            <div
              className="medicop-card p-5 bg-emerald-50 border-2 border-emerald-300 text-emerald-800 flex items-center gap-3 animate-sign-in"
              role="status"
            >
              <div className="relative">
                <span className="absolute inset-0 bg-emerald-400/40 rounded-full animate-ping" />
                <CheckCircle2 className="w-6 h-6 relative" />
              </div>
              <div>
                <p className="font-semibold">Atención firmada y archivada</p>
                <p className="text-xs text-emerald-700/80 mt-0.5">
                  Registro permanente creado el{" "}
                  {encounter.signed_at
                    ? new Date(encounter.signed_at).toLocaleString("es-PE")
                    : "—"}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-componentes que ayudan al médico durante la atención
// ─────────────────────────────────────────────────────────────────────────────

const STEPS: { num: number; label: string; icon: typeof Mic }[] = [
  { num: 1, label: "Grabar", icon: Mic },
  { num: 2, label: "Revisar transcripción", icon: PenLine },
  { num: 3, label: "Validar documentos", icon: FileText },
  { num: 4, label: "Firmar", icon: ShieldCheck },
];

function StepBar({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-2 flex-wrap">
      {STEPS.map(({ num, label, icon: Icon }) => {
        const done = num < current;
        const active = num === current;
        return (
          <li
            key={num}
            className={
              "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border " +
              (done
                ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                : active
                  ? "border-medicop-primary bg-medicop-primary text-white"
                  : "border-medicop-border bg-white text-medicop-text-muted")
            }
            aria-current={active ? "step" : undefined}
          >
            <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-white/30 text-[10px] font-bold">
              {done ? <CheckCircle2 className="w-3 h-3" /> : num}
            </span>
            <Icon className="w-3 h-3" />
            <span className="hidden sm:inline">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function PatientRecap({ last }: { last: EncounterTimelineItem }) {
  const date = new Date(last.started_at);
  const now = new Date();
  const days = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  const ago =
    days === 0 ? "hoy" : days === 1 ? "ayer" : days < 7 ? `hace ${days} días` : `hace ${Math.floor(days / 7)} semanas`;
  const h = last.highlights;

  return (
    <aside
      className="medicop-card p-5 bg-medicop-primary-light/40 border-medicop-primary/20"
      aria-label="Resumen del paciente"
    >
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-medicop-primary" />
        <h2 className="text-sm font-semibold text-medicop-text">
          MediCop te recuerda
        </h2>
      </div>
      <p className="text-sm text-medicop-text leading-relaxed">
        Última atención <strong>{ago}</strong> en {HOSPITAL_AREA_LABELS[last.area]}
        {last.chief_complaint && (
          <>
            {" — "}
            <span className="italic text-medicop-text-muted">{last.chief_complaint}</span>
          </>
        )}
        {"."}
      </p>

      <ul className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        {h.diagnosis && (
          <li>
            <span className="text-medicop-text-muted font-semibold uppercase tracking-wide text-[10px]">
              Diagnóstico
            </span>{" "}
            <span className="clinical-data">{h.diagnosis}</span>
          </li>
        )}
        {h.medications.length > 0 && (
          <li>
            <span className="text-medicop-text-muted font-semibold uppercase tracking-wide text-[10px]">
              Medicación
            </span>{" "}
            <span className="clinical-data">
              {h.medications.slice(0, 2).join(" · ")}
              {h.medications.length > 2 && ` · +${h.medications.length - 2}`}
            </span>
          </li>
        )}
        {h.lab_tests.length > 0 && (
          <li>
            <span className="text-medicop-text-muted font-semibold uppercase tracking-wide text-[10px]">
              Exámenes
            </span>{" "}
            <span className="clinical-data">
              {h.lab_tests.slice(0, 2).join(" · ")}
              {h.lab_tests.length > 2 && ` · +${h.lab_tests.length - 2}`}
            </span>
          </li>
        )}
        {h.plan && (
          <li className="md:col-span-2">
            <span className="text-medicop-text-muted font-semibold uppercase tracking-wide text-[10px]">
              Plan acordado
            </span>{" "}
            <span className="text-medicop-text">{h.plan}</span>
          </li>
        )}
      </ul>

      {h.diagnosis === null &&
        h.medications.length === 0 &&
        h.lab_tests.length === 0 && (
          <p className="text-xs text-medicop-text-muted italic mt-2">
            La atención previa no dejó datos clínicos estructurados.
          </p>
        )}
    </aside>
  );
}

