"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search, User, Loader2, AlertTriangle } from "lucide-react";

import { patientsApi } from "@/lib/api";

export default function PatientsPage() {
  const [query, setQuery] = useState("");
  const { data: patients, isLoading, error } = useQuery({
    queryKey: ["patients", query],
    queryFn: () => patientsApi.list({ q: query || undefined, limit: 100 }),
  });

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-medicop-text">Pacientes</h1>
          <p className="text-medicop-text-muted mt-1 text-sm">
            Selecciona un paciente para ver su historia y empezar una consulta
          </p>
        </div>
      </div>

      <div className="medicop-card p-3 mb-6 flex items-center gap-3">
        <Search className="w-4 h-4 text-medicop-text-muted ml-1 flex-shrink-0" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por NHC, apellido o nombre…"
          className="flex-1 text-sm bg-transparent outline-none text-medicop-text"
        />
        {isLoading && <Loader2 className="w-4 h-4 animate-spin text-medicop-text-muted" />}
      </div>

      {error && (
        <div className="medicop-card p-6 bg-red-50 border-red-200 mb-4">
          <div className="flex items-center gap-2 text-red-700">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm font-medium">No se pudo cargar la lista de pacientes.</span>
          </div>
        </div>
      )}

      {patients && patients.length === 0 && !isLoading && (
        <div className="medicop-card p-12 text-center">
          <User className="w-10 h-10 text-medicop-text-muted mx-auto mb-3" />
          <p className="text-sm text-medicop-text-muted">
            {query
              ? `Sin coincidencias para "${query}".`
              : "Aún no hay pacientes registrados."}
          </p>
        </div>
      )}

      {isLoading && !patients && (
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3" aria-busy="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <li key={i} className="medicop-card p-4 flex items-center gap-4">
              <div className="w-10 h-10 medicop-shimmer rounded-full" />
              <div className="flex-1 space-y-2">
                <div className="medicop-shimmer h-4 w-2/3 rounded" />
                <div className="medicop-shimmer h-3 w-1/2 rounded" />
              </div>
            </li>
          ))}
        </ul>
      )}

      {patients && patients.length > 0 && (
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {patients.map((p) => (
            <li key={p.id}>
              <Link
                href={`/patients/${p.id}`}
                className="medicop-card p-4 flex items-center gap-4 hover:shadow-md transition-shadow group"
              >
                <div className="w-10 h-10 bg-medicop-primary-light rounded-full flex items-center justify-center shrink-0">
                  <User className="w-5 h-5 text-medicop-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-medicop-text truncate">
                    {p.full_name}
                  </p>
                  <p className="text-xs text-medicop-text-muted">
                    NHC{" "}
                    <span className="clinical-data font-semibold text-medicop-text">
                      {p.nhc}
                    </span>{" "}
                    · {p.age} años · {p.sex === "M" ? "M" : "F"}
                  </p>
                  {p.allergies.length > 0 && (
                    <p className="text-[11px] text-red-700 font-medium mt-1 flex items-center gap-1 truncate">
                      <AlertTriangle className="w-3 h-3 shrink-0" />
                      Alergias: {p.allergies.join(", ")}
                    </p>
                  )}
                </div>
                <span className="text-medicop-primary group-hover:translate-x-0.5 transition-transform">
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
