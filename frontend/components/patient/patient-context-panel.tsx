"use client";

import { AlertTriangle, Heart, Pill } from "lucide-react";

import type { Patient } from "@/lib/types";

interface PatientContextPanelProps {
  patient: Patient;
  compact?: boolean;
}

export default function PatientContextPanel({
  patient,
  compact = false,
}: PatientContextPanelProps) {
  return (
    <aside
      className={
        compact
          ? "medicop-card p-4 space-y-4"
          : "medicop-card p-5 space-y-5 sticky top-4"
      }
    >
      <div>
        <h2 className="text-xs font-semibold text-medicop-text-muted uppercase tracking-wide mb-1">
          Paciente
        </h2>
        <p className="font-semibold text-medicop-text leading-tight">
          {patient.full_name}
        </p>
        <p className="text-xs text-medicop-text-muted mt-1">
          NHC{" "}
          <span className="font-mono text-medicop-text font-semibold">
            {patient.nhc}
          </span>
        </p>
        <p className="text-xs text-medicop-text-muted mt-0.5">
          {patient.age} años · {patient.sex === "M" ? "Masculino" : "Femenino"}
          {patient.dni && (
            <>
              {" "}
              · DNI <span className="font-mono">{patient.dni}</span>
            </>
          )}
        </p>
      </div>

      {patient.allergies.length > 0 ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-red-800 text-xs font-bold uppercase mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Alergias documentadas
          </div>
          <ul className="space-y-1">
            {patient.allergies.map((a, i) => (
              <li
                key={i}
                className="text-sm text-red-800 leading-snug font-medium"
              >
                · {a}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="text-xs text-medicop-text-muted italic border border-medicop-border rounded-lg p-3">
          Sin alergias documentadas.
        </div>
      )}

      {patient.active_conditions.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-medicop-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Heart className="w-3.5 h-3.5" />
            Condiciones activas
          </h3>
          <ul className="space-y-1">
            {patient.active_conditions.map((c, i) => (
              <li
                key={i}
                className="text-sm text-medicop-text leading-snug clinical-data"
              >
                · {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {patient.current_medications.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-medicop-text-muted uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Pill className="w-3.5 h-3.5" />
            Medicación actual
          </h3>
          <ul className="space-y-1">
            {patient.current_medications.map((m, i) => (
              <li
                key={i}
                className="text-sm text-medicop-text leading-snug clinical-data"
              >
                · {m}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
