"use client";

import { use, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AmbulanceIcon,
  ArrowLeft,
  Bed,
  ChevronRight,
  Loader2,
  Mic,
  Scissors,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";

import EncounterTimeline from "@/components/encounter/encounter-timeline";
import PatientContextPanel from "@/components/patient/patient-context-panel";
import { encountersApi, patientsApi } from "@/lib/api";
import { ApiError, type EncounterTimelineItem, type HospitalArea } from "@/lib/types";

const AREAS: { id: HospitalArea; label: string; icon: LucideIcon; description: string }[] = [
  {
    id: "consulta_externa",
    label: "Consulta externa",
    icon: Stethoscope,
    description: "Control, seguimiento y atención ambulatoria",
  },
  {
    id: "emergencia",
    label: "Emergencia",
    icon: AmbulanceIcon,
    description: "Atención inmediata por dolor, fiebre o trauma",
  },
  {
    id: "hospitalizacion",
    label: "Hospitalización",
    icon: Bed,
    description: "Evolución diaria, kárdex e indicaciones",
  },
  {
    id: "cirugia",
    label: "Cirugía",
    icon: Scissors,
    description: "Pre, intra y postoperatorio",
  },
];

export default function PatientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: patient, isLoading: patientLoading } = useQuery({
    queryKey: ["patient", id],
    queryFn: () => patientsApi.get(id),
  });

  const { data: timeline, isLoading: timelineLoading } = useQuery({
    queryKey: ["encounters", "by-patient", id],
    queryFn: () => encountersApi.byPatient(id),
    enabled: !!patient,
  });

  // Filtro temporal — por defecto último año (relevante clínicamente).
  // Mantiene la pantalla útil aun para pacientes con historial de muchos años.
  const [showAllHistory, setShowAllHistory] = useState(false);
  const ONE_YEAR_MS = 365 * 24 * 60 * 60 * 1000;
  const recentTimeline = useMemo<EncounterTimelineItem[]>(() => {
    if (!timeline) return [];
    if (showAllHistory) return timeline;
    const cutoff = Date.now() - ONE_YEAR_MS;
    return timeline.filter(
      (t: EncounterTimelineItem) => new Date(t.started_at).getTime() >= cutoff,
    );
  }, [timeline, showAllHistory]);

  const olderCount = (timeline?.length ?? 0) - recentTimeline.length;

  const counts = useMemo(() => {
    const map: Record<HospitalArea, number> = {
      consulta_externa: 0,
      emergencia: 0,
      hospitalizacion: 0,
      cirugia: 0,
    };
    for (const t of recentTimeline) map[t.area]++;
    return map;
  }, [recentTimeline]);

  const defaultArea: HospitalArea = useMemo(() => {
    if (recentTimeline.length > 0) return recentTimeline[0].area;
    return "consulta_externa";
  }, [recentTimeline]);

  const [activeTab, setActiveTab] = useState<HospitalArea | null>(null);
  const tab = activeTab ?? defaultArea;

  const filteredItems = useMemo<EncounterTimelineItem[]>(
    () =>
      recentTimeline.filter((t: EncounterTimelineItem) => t.area === tab),
    [recentTimeline, tab],
  );

  // Acción principal: iniciar atención en un área (sin modal — clic directo)
  const startMutation = useMutation({
    mutationFn: (area: HospitalArea) =>
      encountersApi.create({ patient_id: id, area }),
    onSuccess: (encounter) => {
      queryClient.invalidateQueries({ queryKey: ["encounters", "by-patient", id] });
      router.push(`/consultation/${encounter.id}`);
    },
  });

  if (patientLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-medicop-text-muted">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Cargando paciente…
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="max-w-md mx-auto medicop-card p-8 text-center">
        <p className="text-medicop-text-muted text-sm">Paciente no encontrado.</p>
        <Link
          href="/patients"
          className="text-medicop-primary text-sm mt-4 inline-block"
        >
          ← Volver a pacientes
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <Link
        href="/patients"
        className="inline-flex items-center gap-1.5 text-sm text-medicop-text-muted hover:text-medicop-primary mb-4 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Pacientes
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        <PatientContextPanel patient={patient} />

        <div className="space-y-6">
          {/* ── Hero: empezar una nueva atención ───────────────── */}
          <section className="medicop-card p-6 bg-gradient-to-br from-medicop-primary-light/60 to-white border-medicop-primary/20">
            <div className="flex items-center gap-2 mb-1">
              <Mic className="w-5 h-5 text-medicop-primary" />
              <h2 className="text-lg font-bold text-medicop-text">
                Atender al paciente
              </h2>
            </div>
            <p className="text-sm text-medicop-text-muted mb-4">
              Elige el área. Se abrirá la pantalla de grabación para que
              MediCop pre-llene los documentos por ti.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {AREAS.map(({ id: areaId, label, icon: Icon, description }) => {
                const isPending =
                  startMutation.isPending && startMutation.variables === areaId;
                return (
                  <button
                    key={areaId}
                    type="button"
                    onClick={() => startMutation.mutate(areaId)}
                    disabled={startMutation.isPending}
                    className="group flex items-start gap-3 text-left p-4 bg-white border-2 border-medicop-border rounded-xl hover:border-medicop-primary hover:shadow-md transition-all disabled:opacity-50 disabled:cursor-wait"
                  >
                    <div className="w-10 h-10 bg-medicop-primary-light rounded-lg flex items-center justify-center shrink-0 group-hover:bg-medicop-primary group-hover:text-white text-medicop-primary transition-colors">
                      {isPending ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <Icon className="w-5 h-5" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-medicop-text">{label}</p>
                      <p className="text-xs text-medicop-text-muted leading-snug mt-0.5">
                        {description}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-medicop-text-muted self-center group-hover:text-medicop-primary group-hover:translate-x-0.5 transition-all" />
                  </button>
                );
              })}
            </div>

            {startMutation.isError && (
              <p className="text-xs text-red-600 mt-3" role="alert">
                {(startMutation.error as ApiError)?.message ??
                  "No se pudo iniciar la atención"}
              </p>
            )}
          </section>

          {/* ── Atenciones previas — separadas por área ─────────── */}
          <section>
            <div className="flex items-baseline justify-between mb-3 px-1 gap-3 flex-wrap">
              <h2 className="text-sm font-semibold text-medicop-text-muted uppercase tracking-wide">
                Atenciones previas
                {!showAllHistory && (
                  <span className="ml-2 text-[11px] font-normal normal-case">
                    · último año
                  </span>
                )}
              </h2>
              {olderCount > 0 && (
                <button
                  type="button"
                  onClick={() => setShowAllHistory((v) => !v)}
                  className="text-xs text-medicop-primary hover:underline"
                >
                  {showAllHistory
                    ? "Ver solo el último año"
                    : `Ver historial completo (+${olderCount})`}
                </button>
              )}
            </div>

            {timelineLoading ? (
              <ol className="space-y-3" aria-busy="true">
                {Array.from({ length: 3 }).map((_, i) => (
                  <li key={i} className="medicop-card p-4 flex gap-4">
                    <div className="w-6 h-6 medicop-shimmer rounded-full mt-1" />
                    <div className="flex-1 space-y-2">
                      <div className="medicop-shimmer h-3 w-32 rounded" />
                      <div className="medicop-shimmer h-4 w-2/3 rounded" />
                    </div>
                  </li>
                ))}
              </ol>
            ) : (timeline ?? []).length === 0 ? (
              <div className="medicop-card p-8 text-center text-sm text-medicop-text-muted">
                Este paciente aún no tiene atenciones registradas.
              </div>
            ) : (
              <>
                {/* Pestañas por área (sólo se muestran las áreas con atenciones) */}
                <div
                  role="tablist"
                  className="flex flex-wrap gap-1 mb-3 border-b border-medicop-border"
                >
                  {AREAS.filter((a) => counts[a.id] > 0).map(
                    ({ id: areaId, label, icon: Icon }) => {
                      const active = tab === areaId;
                      return (
                        <button
                          key={areaId}
                          role="tab"
                          aria-selected={active}
                          onClick={() => setActiveTab(areaId)}
                          className={
                            "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors " +
                            (active
                              ? "border-medicop-primary text-medicop-primary"
                              : "border-transparent text-medicop-text-muted hover:text-medicop-text")
                          }
                        >
                          <Icon className="w-3.5 h-3.5" />
                          {label}
                          <span
                            className={
                              "ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-semibold " +
                              (active
                                ? "bg-medicop-primary text-white"
                                : "bg-medicop-border text-medicop-text-muted")
                            }
                          >
                            {counts[areaId]}
                          </span>
                        </button>
                      );
                    },
                  )}
                </div>

                <EncounterTimeline items={filteredItems} />
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
