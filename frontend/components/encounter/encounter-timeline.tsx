"use client";

import Link from "next/link";
import {
  CheckCircle2,
  Clock,
  FileText,
  Stethoscope,
  Pill,
  FlaskConical,
  ClipboardList,
} from "lucide-react";

import AreaBadge from "@/components/encounter/area-badge";
import type { EncounterTimelineItem } from "@/lib/types";

interface EncounterTimelineProps {
  items: EncounterTimelineItem[];
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const fmt = new Intl.DateTimeFormat("es-PE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  if (diffDays === 0) return "Hoy";
  if (diffDays === 1) return "Ayer";
  if (diffDays < 7) return `Hace ${diffDays} días`;
  if (diffDays < 30) return `Hace ${Math.floor(diffDays / 7)} sem`;
  return fmt.format(date);
}

export default function EncounterTimeline({ items }: EncounterTimelineProps) {
  if (items.length === 0) {
    return (
      <div className="medicop-card p-8 text-center text-sm text-medicop-text-muted">
        Sin atenciones en esta área.
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="absolute left-3 top-3 bottom-3 w-px bg-medicop-border" />

      <ol className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="relative flex gap-4">
            <div className="relative z-10 mt-1">
              <span
                className={`block w-6 h-6 rounded-full border-2 ${
                  item.status === "signed"
                    ? "bg-emerald-100 border-emerald-300"
                    : "bg-medicop-bg border-medicop-border"
                } flex items-center justify-center`}
              >
                {item.status === "signed" ? (
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                ) : (
                  <Clock className="w-3 h-3 text-medicop-text-muted" />
                )}
              </span>
            </div>

            <Link
              href={`/consultation/${item.id}`}
              className="flex-1 medicop-card p-4 hover:shadow-sm transition-shadow group"
            >
              <header className="flex items-start justify-between gap-3 mb-2 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <AreaBadge area={item.area} />
                  <span className="text-xs text-medicop-text-muted">
                    {formatRelativeDate(item.started_at)}
                  </span>
                </div>
                {item.document_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-medicop-text-muted">
                    <FileText className="w-3 h-3" />
                    {item.document_count} documento
                    {item.document_count === 1 ? "" : "s"}
                  </span>
                )}
              </header>

              {item.chief_complaint && (
                <p className="text-sm text-medicop-text font-semibold leading-snug mb-2">
                  {item.chief_complaint}
                </p>
              )}

              <Highlights item={item} />
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Highlights({ item }: { item: EncounterTimelineItem }) {
  const h = item.highlights;
  const hasContent =
    h.diagnosis ||
    h.cie10_codes.length > 0 ||
    h.medications.length > 0 ||
    h.lab_tests.length > 0 ||
    h.plan;

  if (!hasContent) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2 text-xs">
      {h.diagnosis && (
        <Field icon={<Stethoscope className="w-3.5 h-3.5" />} label="Diagnóstico">
          <span className="clinical-data">{h.diagnosis}</span>
          {h.cie10_codes.length > 0 && (
            <span className="ml-1 text-medicop-text-muted">
              ({h.cie10_codes.join(", ")})
            </span>
          )}
        </Field>
      )}
      {h.medications.length > 0 && (
        <Field icon={<Pill className="w-3.5 h-3.5" />} label="Medicación">
          <span className="clinical-data">
            {h.medications.slice(0, 3).join(" · ")}
            {h.medications.length > 3 && ` · +${h.medications.length - 3}`}
          </span>
        </Field>
      )}
      {h.lab_tests.length > 0 && (
        <Field icon={<FlaskConical className="w-3.5 h-3.5" />} label="Exámenes">
          <span className="clinical-data">
            {h.lab_tests.slice(0, 3).join(" · ")}
            {h.lab_tests.length > 3 && ` · +${h.lab_tests.length - 3}`}
          </span>
        </Field>
      )}
      {h.plan && (
        <Field
          icon={<ClipboardList className="w-3.5 h-3.5" />}
          label="Plan"
          className="md:col-span-2"
        >
          <span className="text-medicop-text-muted">{h.plan}</span>
        </Field>
      )}
    </div>
  );
}

function Field({
  icon,
  label,
  children,
  className,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={"flex items-start gap-1.5 " + (className ?? "")}>
      <span className="text-medicop-text-muted shrink-0 mt-0.5">{icon}</span>
      <div className="min-w-0">
        <span className="text-[10px] uppercase tracking-wide font-semibold text-medicop-text-muted block leading-none mb-0.5">
          {label}
        </span>
        <div className="text-medicop-text leading-snug break-words">
          {children}
        </div>
      </div>
    </div>
  );
}
