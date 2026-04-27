"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2, ListTodo } from "lucide-react";

import { encountersApi } from "@/lib/api";
import { COMMON_DIAGNOSES_PERU } from "@/lib/common-diagnoses";
import type { ClinicalDocument } from "@/lib/types";

interface CommonDiagnosesPickerProps {
  /** SOAP doc del encounter — al elegir un diagnóstico se setea como assessment principal. */
  soapDocument?: ClinicalDocument;
  encounterId: string;
  disabled?: boolean;
}

export default function CommonDiagnosesPicker({
  soapDocument,
  encounterId,
  disabled = false,
}: CommonDiagnosesPickerProps) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const applyMutation = useMutation({
    mutationFn: async (dx: { cie10: string; name: string }) => {
      if (!soapDocument) return null;
      const prevContent = (soapDocument.content as Record<string, unknown>) || {};
      const prevCodes = Array.isArray(prevContent.cie10_codes)
        ? (prevContent.cie10_codes as string[])
        : [];
      const newCodes = Array.from(new Set([dx.cie10, ...prevCodes]));
      return encountersApi.updateDocument(encounterId, soapDocument.id, {
        ...prevContent,
        assessment: `${dx.name} (${dx.cie10})`,
        cie10_codes: newCodes,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
      setOpen(false);
    },
  });

  return (
    <section className="medicop-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-medicop-bg/50 transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <ListTodo className="w-4 h-4 text-medicop-text-muted" />
          <span className="text-sm font-medium text-medicop-text">
            Diagnósticos comunes en Perú
          </span>
          <span className="text-[11px] text-medicop-text-muted">(referencia)</span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-medicop-text-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-medicop-text-muted" />
        )}
      </button>

      {open && (
        <div className="border-t border-medicop-border p-3">
          <p className="text-xs text-medicop-text-muted mb-3 leading-relaxed">
            Si el caso encaja con uno de estos, puedes aplicarlo directamente al
            diagnóstico principal. Fuente: HIS MINSA — atención primaria.
          </p>
          <ul className="space-y-1.5">
            {COMMON_DIAGNOSES_PERU.map((dx) => {
              const isPending =
                applyMutation.isPending &&
                applyMutation.variables?.cie10 === dx.cie10;
              return (
                <li
                  key={dx.cie10}
                  className="flex items-start gap-3 p-2 rounded hover:bg-medicop-bg/60"
                >
                  <span className="text-[11px] font-mono font-bold text-medicop-primary bg-medicop-primary-light px-1.5 py-0.5 rounded shrink-0 min-w-[3rem] text-center">
                    {dx.cie10}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-medicop-text leading-snug">
                      {dx.name}
                    </p>
                    <p className="text-xs text-medicop-text-muted leading-snug mt-0.5">
                      {dx.hint}
                    </p>
                  </div>
                  {soapDocument && !disabled && (
                    <button
                      type="button"
                      onClick={() => applyMutation.mutate(dx)}
                      disabled={applyMutation.isPending}
                      className="text-xs text-medicop-primary hover:underline shrink-0 inline-flex items-center gap-1 self-center"
                    >
                      {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                      Aplicar
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
