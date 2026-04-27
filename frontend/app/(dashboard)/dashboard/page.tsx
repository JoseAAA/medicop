"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Users,
  Calendar,
  Search,
  ArrowRight,
  Loader2,
  AlertCircle,
  Clock,
  ChevronRight,
} from "lucide-react";

import AreaBadge from "@/components/encounter/area-badge";
import { useAuth } from "@/contexts/auth-context";
import { encountersApi, patientsApi, type EncounterMineItem } from "@/lib/api";

function shortAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60_000);
  if (m < 1) return "hace un momento";
  if (m < 60) return `hace ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `hace ${d} d`;
  return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" }).format(
    new Date(iso),
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  const { data: pendingEncounters, isLoading: pendingLoading } = useQuery({
    queryKey: ["encounters", "mine", "open"],
    queryFn: () => encountersApi.mine({ status: "open", limit: 10 }),
    refetchInterval: 30_000, // refresca cada 30 s — algo nuevo puede aparecer
  });

  const { data: recentEncounters } = useQuery({
    queryKey: ["encounters", "mine", "recent"],
    queryFn: () => encountersApi.mine({ limit: 10 }),
  });

  // Pacientes únicos recientes (de los últimos encounters firmados)
  const recentPatients = (() => {
    if (!recentEncounters) return [];
    const seen = new Set<string>();
    const list: EncounterMineItem[] = [];
    for (const e of recentEncounters) {
      if (e.status === "open") continue;
      if (seen.has(e.patient_id)) continue;
      seen.add(e.patient_id);
      list.push(e);
      if (list.length >= 4) break;
    }
    return list;
  })();

  const today = new Intl.DateTimeFormat("es-PE", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date());

  const greeting = user?.full_name
    ? `Hola, Dr. ${user.full_name.split(" ").slice(-2).join(" ")}`
    : "Bienvenido";

  const handleSearch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSearchError(null);
    const q = query.trim();
    if (!q) {
      router.push("/patients");
      return;
    }
    setSearching(true);
    try {
      const matches = await patientsApi.list({ q, limit: 2 });
      // Si parece un NHC (solo dígitos) y hay un match exacto, abre directo.
      // Para búsquedas por nombre/apellido siempre mostramos la lista, así
      // el médico ve si hay homónimos antes de elegir.
      const looksLikeNhc = /^\d+$/.test(q);
      const exactNhcMatch =
        matches.length === 1 &&
        looksLikeNhc &&
        matches[0].nhc.replace(/^0+/, "") === q.replace(/^0+/, "");

      if (matches.length === 0) {
        setSearchError(`Sin coincidencias para "${q}".`);
      } else if (exactNhcMatch) {
        router.push(`/patients/${matches[0].id}`);
      } else {
        router.push(`/patients?q=${encodeURIComponent(q)}`);
      }
    } catch {
      setSearchError("Error al buscar. Intenta de nuevo.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-medicop-text">{greeting}</h1>
        <p className="text-medicop-text-muted text-sm mt-1 capitalize flex items-center gap-2">
          <Calendar className="w-4 h-4" />
          {today}
        </p>
      </div>

      {/* ── Buscador prominente — atajo principal ───────────────── */}
      <form onSubmit={handleSearch} className="medicop-card p-5">
        <label
          htmlFor="patient-search"
          className="block text-sm font-semibold text-medicop-text mb-2"
        >
          Buscar paciente
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-medicop-text-muted" />
            <input
              id="patient-search"
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSearchError(null);
              }}
              placeholder="Número de Historia Clínica (NHC), nombre o apellido…"
              className="medicop-input pl-9 text-base"
              autoFocus
              disabled={searching}
            />
          </div>
          <button
            type="submit"
            disabled={searching}
            className="medicop-btn-primary text-sm inline-flex items-center gap-2"
          >
            {searching && <Loader2 className="w-4 h-4 animate-spin" />}
            Buscar
          </button>
        </div>
        {searchError && (
          <p className="text-xs text-red-600 mt-2 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" />
            {searchError}
          </p>
        )}
        <p className="text-xs text-medicop-text-muted mt-2">
          Si encontramos un paciente exacto te llevamos directo a su ficha.
        </p>
      </form>

      {/* ── Atenciones sin terminar — acción urgente ───────────── */}
      {pendingEncounters && pendingEncounters.length > 0 && (
        <section
          aria-label="Atenciones sin firmar"
          className="medicop-card p-5 border-2 border-amber-300 bg-amber-50/40"
        >
          <header className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-amber-900 uppercase tracking-wide flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              Atenciones sin terminar ({pendingEncounters.length})
            </h2>
          </header>
          <ul className="space-y-2">
            {pendingEncounters.map((e) => (
              <li key={e.id}>
                <Link
                  href={`/consultation/${e.id}`}
                  className="flex items-center gap-3 p-3 bg-white border border-amber-200 rounded-lg hover:border-amber-400 hover:shadow-sm transition-all group"
                >
                  <Clock className="w-4 h-4 text-amber-700 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-medicop-text">
                      {e.patient_full_name}{" "}
                      <span className="text-xs font-mono font-normal text-medicop-text-muted">
                        NHC {e.patient_nhc}
                      </span>
                    </p>
                    <div className="flex items-center gap-2 flex-wrap mt-0.5">
                      <AreaBadge area={e.area} />
                      <span className="text-xs text-medicop-text-muted">
                        iniciada {shortAgo(e.started_at)}
                      </span>
                    </div>
                    {e.chief_complaint && (
                      <p className="text-xs text-medicop-text-muted mt-1 truncate">
                        {e.chief_complaint}
                      </p>
                    )}
                  </div>
                  <span className="text-amber-700 text-sm font-medium group-hover:translate-x-0.5 transition-transform">
                    Continuar
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Pacientes recientes ─────────────────────────────────── */}
      {pendingLoading ? (
        <div className="medicop-card p-5">
          <div className="medicop-shimmer h-4 w-40 mb-3 rounded" />
          <div className="medicop-shimmer h-12 w-full rounded" />
        </div>
      ) : recentPatients.length > 0 ? (
        <section aria-label="Pacientes recientes" className="medicop-card p-5">
          <h2 className="text-sm font-semibold text-medicop-text-muted uppercase tracking-wide mb-3">
            Pacientes que atendiste recientemente
          </h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {recentPatients.map((e) => (
              <li key={e.id}>
                <Link
                  href={`/patients/${e.patient_id}`}
                  className="flex items-center gap-3 p-3 bg-white border border-medicop-border rounded-lg hover:border-medicop-primary/40 hover:shadow-sm transition-all group"
                >
                  <div className="w-9 h-9 bg-medicop-primary-light rounded-full flex items-center justify-center shrink-0">
                    <Users className="w-4 h-4 text-medicop-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-medicop-text truncate">
                      {e.patient_full_name}
                    </p>
                    <p className="text-[11px] text-medicop-text-muted">
                      NHC {e.patient_nhc} · última atención {shortAgo(e.started_at)}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-medicop-text-muted group-hover:text-medicop-primary transition-colors" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* ── Link a la lista completa ────────────────────────────── */}
      <Link
        href="/patients"
        className="medicop-card p-4 flex items-center justify-between hover:shadow-sm hover:border-medicop-primary/40 transition-all group"
      >
        <div className="flex items-center gap-3">
          <Users className="w-4 h-4 text-medicop-text-muted" />
          <span className="text-sm text-medicop-text">
            Ver todos los pacientes del hospital
          </span>
        </div>
        <ArrowRight className="w-4 h-4 text-medicop-text-muted group-hover:text-medicop-primary group-hover:translate-x-0.5 transition-all" />
      </Link>
    </div>
  );
}
