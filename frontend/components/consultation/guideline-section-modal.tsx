"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, X, Loader2, AlertTriangle } from "lucide-react";

import { ragApi } from "@/lib/api";

interface GuidelineSectionModalProps {
  guidelineId: string;
  section: string | null;
  /** Nombre legible de la guía — se usa mientras carga el detalle. */
  guidelineName?: string;
  open: boolean;
  onClose: () => void;
}

export default function GuidelineSectionModal({
  guidelineId,
  section,
  guidelineName,
  open,
  onClose,
}: GuidelineSectionModalProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["guideline-section", guidelineId, section],
    queryFn: () => ragApi.getSection(guidelineId, section ?? undefined),
    enabled: open && !!guidelineId,
  });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guideline-modal-title"
      onClick={onClose}
    >
      <div
        className="medicop-card max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col p-0 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 p-5 border-b border-medicop-border">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-10 h-10 bg-medicop-primary-light rounded-lg flex items-center justify-center shrink-0">
              <BookOpen className="w-5 h-5 text-medicop-primary" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wide font-semibold text-medicop-text-muted">
                Guía clínica oficial
              </p>
              <h2
                id="guideline-modal-title"
                className="font-bold text-medicop-text leading-snug truncate"
              >
                {data?.guideline?.title ?? guidelineName ?? "Cargando…"}
              </h2>
              <p className="text-xs text-medicop-text-muted mt-0.5">
                {data?.guideline ? (
                  <>
                    {data.guideline.institution} · {data.guideline.year}
                    {data.guideline.is_demo && (
                      <span className="ml-2 inline-flex items-center text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 rounded">
                        ejemplo demostrativo
                      </span>
                    )}
                  </>
                ) : (
                  "Cargando metadata…"
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-medicop-text-muted hover:text-medicop-text hover:bg-medicop-bg rounded-md transition-colors shrink-0"
            aria-label="Cerrar"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex items-center gap-2 text-medicop-text-muted text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Cargando sección…
            </div>
          )}

          {error && (
            <div
              className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2 flex items-start gap-2"
              role="alert"
            >
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>No se pudo cargar la sección de la guía.</span>
            </div>
          )}

          {data?.section ? (
            <article className="prose prose-sm max-w-none">
              <h3 className="font-bold text-medicop-text mb-3">
                {data.section.section_title}
              </h3>
              <pre className="whitespace-pre-wrap break-words text-sm text-medicop-text leading-relaxed font-sans bg-transparent p-0 clinical-data">
                {data.section.text}
              </pre>
            </article>
          ) : (
            !isLoading &&
            !error && (
              <p className="text-sm text-medicop-text-muted italic">
                Sin contenido para esta sección.
              </p>
            )
          )}
        </div>

        <footer className="px-5 py-3 border-t border-medicop-border bg-medicop-bg/50 text-[11px] text-medicop-text-muted">
          Esta es la fuente que MediCop utilizó para sugerir el diagnóstico.
          Verifícala antes de firmar.
        </footer>
      </div>
    </div>
  );
}
