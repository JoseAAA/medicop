"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  CheckCircle2,
  ChevronDown,
  Loader2,
  BookOpen,
} from "lucide-react";

import GuidelineSectionModal from "@/components/consultation/guideline-section-modal";
import { encountersApi } from "@/lib/api";
import type {
  Citation,
  ClinicalDocument,
  DifferentialDiagnosis,
} from "@/lib/types";

interface DifferentialDiagnosesCardProps {
  /** Documento del LLM con doc_type === "differential_diagnoses" */
  document: ClinicalDocument;
  /** SOAP del encounter — si existe, "Aceptar" actualiza su assessment */
  soapDocument?: ClinicalDocument;
  encounterId: string;
  readOnly?: boolean;
}

const LIKELIHOOD_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  alta:  { label: "Más probable", bg: "bg-emerald-50",  text: "text-emerald-700" },
  media: { label: "Posible",      bg: "bg-amber-50",    text: "text-amber-700" },
  baja:  { label: "A descartar",  bg: "bg-medicop-bg",  text: "text-medicop-text-muted" },
};

export default function DifferentialDiagnosesCard({
  document: doc,
  soapDocument,
  encounterId,
  readOnly = false,
}: DifferentialDiagnosesCardProps) {
  const queryClient = useQueryClient();
  const [acceptedName, setAcceptedName] = useState<string | null>(
    typeof soapDocument?.content?.assessment === "string"
      ? (soapDocument.content.assessment as string)
      : null,
  );
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const options = (doc.content?.options as DifferentialDiagnosis[] | undefined) ?? [];
  // Citas a nivel del documento — usamos la primera como link de la cita por
  // diagnóstico cuando el LLM no incluyó guideline_id en la opción.
  const docCitations = (doc.citations as Citation[] | undefined) ?? [];
  const [openedCitation, setOpenedCitation] = useState<{
    id: string;
    section: string | null;
    name?: string;
  } | null>(null);

  const acceptMutation = useMutation({
    mutationFn: async (dx: DifferentialDiagnosis) => {
      if (!soapDocument) {
        return null;
      }
      const prevContent = (soapDocument.content as Record<string, unknown>) || {};
      const prevCodes = Array.isArray(prevContent.cie10_codes)
        ? (prevContent.cie10_codes as string[])
        : [];
      const newCodes = dx.cie10
        ? Array.from(new Set([dx.cie10, ...prevCodes]))
        : prevCodes;
      const newAssessment = dx.cie10
        ? `${dx.name} (${dx.cie10})`
        : dx.name;

      return encountersApi.updateDocument(encounterId, soapDocument.id, {
        ...prevContent,
        assessment: newAssessment,
        cie10_codes: newCodes,
      });
    },
    onSuccess: (_data, dx) => {
      setAcceptedName(dx.name);
      queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
    },
  });

  if (options.length === 0) return null;

  return (
    <section className="medicop-card p-5 border-medicop-primary/30 bg-gradient-to-br from-medicop-primary-light/40 to-white">
      <header className="flex items-center gap-2 mb-1">
        <Sparkles className="w-5 h-5 text-medicop-primary" />
        <h3 className="font-bold text-medicop-text">
          El asistente considera estos diagnósticos
        </h3>
      </header>
      <p className="text-xs text-medicop-text-muted mb-4">
        Sugerencias basadas en la conversación, las atenciones previas del
        paciente y las guías oficiales del MINSA. Tú decides cuál tomar.
      </p>

      <ol className="space-y-2.5">
        {options.map((dx, i) => {
          const style =
            LIKELIHOOD_STYLES[(dx.likelihood || "").toLowerCase()] ??
            LIKELIHOOD_STYLES.media;
          const isAccepted =
            acceptedName !== null &&
            acceptedName.toLowerCase().includes(dx.name.toLowerCase());
          const isPending =
            acceptMutation.isPending && acceptMutation.variables?.name === dx.name;
          const isExpanded = expanded[i] ?? i === 0;

          return (
            <li
              key={i}
              className={
                "border rounded-lg p-3 transition-all " +
                (isAccepted
                  ? "border-emerald-400 bg-emerald-50/60"
                  : "border-medicop-border bg-white hover:border-medicop-primary/40")
              }
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${style.bg} ${style.text}`}
                    >
                      {style.label}
                    </span>
                    <span className="font-semibold text-medicop-text clinical-data">
                      {dx.name}
                    </span>
                    {dx.cie10 && (
                      <span className="text-[11px] font-mono text-medicop-text-muted">
                        {dx.cie10}
                      </span>
                    )}
                    {isAccepted && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Diagnóstico principal
                      </span>
                    )}
                  </div>

                  {(isExpanded || isAccepted) && (
                    <>
                      {dx.rationale && (
                        <p className="text-sm text-medicop-text mt-2 leading-relaxed">
                          {dx.rationale}
                        </p>
                      )}
                      {dx.guideline_section &&
                        (() => {
                          // El LLM no siempre incluye guideline_id en cada Dx;
                          // hacemos lookup en `docCitations` por nombre de sección.
                          const matchedCitation = docCitations.find(
                            (c) =>
                              c.guideline_id &&
                              ((dx.guideline_section || "")
                                .toLowerCase()
                                .includes((c.section || "").toLowerCase()) ||
                                (c.section || "")
                                  .toLowerCase()
                                  .includes((dx.guideline_section || "").toLowerCase())),
                          ) ?? docCitations.find((c) => c.guideline_id);
                          if (!matchedCitation?.guideline_id) {
                            return (
                              <p className="text-[11px] text-medicop-text-muted mt-1.5 inline-flex items-center gap-1">
                                <BookOpen className="w-3 h-3" />
                                {dx.guideline_section}
                              </p>
                            );
                          }
                          return (
                            <button
                              type="button"
                              onClick={() =>
                                setOpenedCitation({
                                  id: matchedCitation.guideline_id as string,
                                  section: dx.guideline_section || null,
                                  name: matchedCitation.guideline_name,
                                })
                              }
                              className="text-[11px] text-medicop-primary hover:underline mt-1.5 inline-flex items-center gap-1"
                            >
                              <BookOpen className="w-3 h-3" />
                              Ver guía: {dx.guideline_section}
                            </button>
                          );
                        })()}
                    </>
                  )}
                </div>

                <div className="flex flex-col gap-1.5 items-end shrink-0">
                  {!isAccepted && !readOnly && soapDocument && (
                    <button
                      type="button"
                      onClick={() => acceptMutation.mutate(dx)}
                      disabled={acceptMutation.isPending}
                      className="medicop-btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
                    >
                      {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                      Aceptar
                    </button>
                  )}
                  {!isAccepted && (
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded((s) => ({ ...s, [i]: !isExpanded }))
                      }
                      className="text-[11px] text-medicop-text-muted hover:text-medicop-text inline-flex items-center gap-0.5"
                      aria-expanded={isExpanded}
                    >
                      {isExpanded ? "Menos" : "Más detalle"}
                      <ChevronDown
                        className={
                          "w-3 h-3 transition-transform " +
                          (isExpanded ? "rotate-180" : "")
                        }
                      />
                    </button>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {acceptMutation.isError && (
        <p className="text-xs text-red-600 mt-3" role="alert">
          No se pudo aplicar el diagnóstico. Inténtalo de nuevo.
        </p>
      )}

      {openedCitation && (
        <GuidelineSectionModal
          guidelineId={openedCitation.id}
          section={openedCitation.section}
          guidelineName={openedCitation.name}
          open
          onClose={() => setOpenedCitation(null)}
        />
      )}
    </section>
  );
}
