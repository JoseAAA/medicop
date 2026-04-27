"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Edit2,
  AlertTriangle,
  FileText,
  Loader2,
  ExternalLink,
} from "lucide-react";

import GuidelineSectionModal from "@/components/consultation/guideline-section-modal";
import { encountersApi } from "@/lib/api";
import {
  DOCUMENT_TYPE_LABELS,
  type ClinicalDocument,
  type Citation,
} from "@/lib/types";

interface DocumentCardProps {
  document: ClinicalDocument;
  encounterId: string;
  readOnly?: boolean;
}

export default function DocumentCard({
  document: doc,
  encounterId,
  readOnly = false,
}: DocumentCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>(doc.content);
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: (content: Record<string, unknown>) =>
      encountersApi.updateDocument(encounterId, doc.id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
      setEditing(false);
    },
  });

  const onSave = () => saveMutation.mutate(draft);
  const onCancel = () => {
    setDraft(doc.content);
    setEditing(false);
  };

  const isLocked = doc.is_signed || readOnly;

  return (
    <div className="medicop-card p-5">
      <header className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-2.5">
          <FileText className="w-4 h-4 text-medicop-primary mt-0.5 shrink-0" />
          <div>
            <h3 className="font-semibold text-medicop-text">
              {DOCUMENT_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
            </h3>
            {doc.is_signed && (
              <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium mt-0.5">
                <CheckCircle2 className="w-3 h-3" />
                Firmado
              </span>
            )}
          </div>
        </div>

        {!isLocked && (
          editing ? (
            <div className="flex gap-2">
              <button
                onClick={onCancel}
                className="text-xs text-medicop-text-muted hover:text-medicop-text px-2 py-1"
                disabled={saveMutation.isPending}
              >
                Cancelar
              </button>
              <button
                onClick={onSave}
                disabled={saveMutation.isPending}
                className="medicop-btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
              >
                {saveMutation.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                Guardar
              </button>
            </div>
          ) : (
            <button
              onClick={() => setEditing(true)}
              className="text-xs text-medicop-primary hover:underline inline-flex items-center gap-1"
              aria-label="Editar"
            >
              <Edit2 className="w-3 h-3" />
              Editar
            </button>
          )
        )}
      </header>

      {/* Red flags — máxima prioridad visual */}
      {doc.red_flags.length > 0 && (
        <div
          className="mb-4 bg-red-50 border-2 border-red-300 rounded-lg p-3"
          role="alert"
        >
          <div className="flex items-center gap-1.5 text-red-800 text-xs font-bold uppercase mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Señales de alarma
          </div>
          <ul className="space-y-1">
            {doc.red_flags.map((f, i) => (
              <li key={i} className="text-sm text-red-800 leading-snug">
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      <DocumentBody
        docType={doc.doc_type}
        content={editing ? draft : doc.content}
        editing={editing && !isLocked}
        onChange={setDraft}
      />

      {doc.citations.length > 0 && (
        <CitationsBlock citations={doc.citations} />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Cuerpo del documento — switch por tipo
// ─────────────────────────────────────────────────────────────────────────────

interface BodyProps {
  content: Record<string, unknown>;
  editing: boolean;
  onChange: (next: Record<string, unknown>) => void;
}

interface DispatcherProps extends BodyProps {
  docType: string;
}

function DocumentBody({ docType, content, editing, onChange }: DispatcherProps) {
  switch (docType) {
    case "soap":
      return <SOAPBody content={content} editing={editing} onChange={onChange} />;
    case "prescription":
      return <PrescriptionBody content={content} editing={editing} onChange={onChange} />;
    case "lab_order":
      return <LabOrderBody content={content} editing={editing} onChange={onChange} />;
    default:
      return <GenericBody content={content} editing={editing} onChange={onChange} />;
  }
}

// ── SOAP ─────────────────────────────────────────────────────────────────────

function SOAPBody({ content, editing, onChange }: BodyProps) {
  const c = content as {
    subjective?: string;
    objective?: string;
    assessment?: string;
    cie10_codes?: string[];
    plan?: string;
  };

  const setField = (key: string, value: string) =>
    onChange({ ...content, [key]: value });

  const labels: Array<{ key: keyof typeof c; label: string }> = [
    { key: "subjective", label: "Subjetivo" },
    { key: "objective", label: "Objetivo" },
    { key: "assessment", label: "Análisis" },
    { key: "plan", label: "Plan" },
  ];

  return (
    <div className="space-y-3">
      {labels.map(({ key, label }) => (
        <div key={key}>
          <p className="text-xs font-semibold text-medicop-text-muted uppercase tracking-wide mb-1">
            {label}
          </p>
          {editing ? (
            <textarea
              rows={3}
              value={(c[key] as string) ?? ""}
              onChange={(e) => setField(key as string, e.target.value)}
              className="medicop-input font-mono text-sm"
            />
          ) : (
            <p className="text-sm text-medicop-text whitespace-pre-wrap leading-relaxed clinical-data">
              {(c[key] as string) || (
                <span className="italic text-medicop-text-muted">— sin datos —</span>
              )}
            </p>
          )}
        </div>
      ))}

      {c.cie10_codes && c.cie10_codes.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-medicop-text-muted uppercase tracking-wide mb-1">
            CIE-10
          </p>
          <div className="flex flex-wrap gap-1.5">
            {c.cie10_codes.map((code, i) => (
              <span
                key={i}
                className="bg-medicop-primary-light text-medicop-primary text-xs px-2 py-0.5 rounded clinical-data font-medium"
              >
                {code}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Prescription ─────────────────────────────────────────────────────────────

interface DrugLine {
  name?: string;
  dose?: string;
  route?: string;
  frequency?: string;
  duration?: string;
  indication?: string;
  notes?: string;
}

function PrescriptionBody({ content, editing, onChange }: BodyProps) {
  const c = content as { drugs?: DrugLine[]; indications?: string };
  const drugs = c.drugs ?? [];

  const setDrug = (i: number, field: keyof DrugLine, value: string) => {
    const next = [...drugs];
    next[i] = { ...next[i], [field]: value };
    onChange({ ...content, drugs: next });
  };

  const removeDrug = (i: number) => {
    const next = drugs.filter((_, idx) => idx !== i);
    onChange({ ...content, drugs: next });
  };

  return (
    <div className="space-y-2">
      {drugs.length === 0 && (
        <p className="text-sm italic text-medicop-text-muted">— sin medicamentos —</p>
      )}

      {drugs.map((drug, i) => (
        <div
          key={i}
          className="border border-medicop-border rounded-lg p-3 bg-white"
        >
          {editing ? (
            <div className="grid grid-cols-2 gap-2 text-sm">
              <input
                value={drug.name ?? ""}
                placeholder="Medicamento"
                onChange={(e) => setDrug(i, "name", e.target.value)}
                className="medicop-input col-span-2 font-medium"
              />
              <input
                value={drug.dose ?? ""}
                placeholder="Dosis (ej. 500 mg)"
                onChange={(e) => setDrug(i, "dose", e.target.value)}
                className="medicop-input"
              />
              <input
                value={drug.route ?? ""}
                placeholder="Vía (oral, EV…)"
                onChange={(e) => setDrug(i, "route", e.target.value)}
                className="medicop-input"
              />
              <input
                value={drug.frequency ?? ""}
                placeholder="Frecuencia"
                onChange={(e) => setDrug(i, "frequency", e.target.value)}
                className="medicop-input"
              />
              <input
                value={drug.duration ?? ""}
                placeholder="Duración"
                onChange={(e) => setDrug(i, "duration", e.target.value)}
                className="medicop-input"
              />
              <input
                value={drug.indication ?? ""}
                placeholder="Indicación"
                onChange={(e) => setDrug(i, "indication", e.target.value)}
                className="medicop-input col-span-2"
              />
              <button
                type="button"
                onClick={() => removeDrug(i)}
                className="col-span-2 text-xs text-red-600 hover:underline text-left"
              >
                Quitar este medicamento
              </button>
            </div>
          ) : (
            <div className="text-sm">
              <p className="font-semibold text-medicop-text clinical-data">
                {drug.name}{" "}
                <span className="text-medicop-text-muted font-normal">
                  {drug.dose}
                </span>
              </p>
              <p className="text-xs text-medicop-text-muted mt-0.5">
                {[drug.route, drug.frequency, drug.duration].filter(Boolean).join(" · ")}
              </p>
              {drug.indication && (
                <p className="text-xs text-medicop-text-muted mt-1 italic">
                  {drug.indication}
                </p>
              )}
            </div>
          )}
        </div>
      ))}

      {c.indications && (
        <p className="text-xs text-medicop-text-muted leading-relaxed pt-2">
          <span className="font-medium">Indicaciones generales:</span> {c.indications}
        </p>
      )}
    </div>
  );
}

// ── Lab order ────────────────────────────────────────────────────────────────

interface LabTest {
  name?: string;
  urgency?: string;
  indication?: string;
}

function LabOrderBody({ content, editing, onChange }: BodyProps) {
  const c = content as { tests?: LabTest[] };
  const tests = c.tests ?? [];

  const setTest = (i: number, field: keyof LabTest, value: string) => {
    const next = [...tests];
    next[i] = { ...next[i], [field]: value };
    onChange({ ...content, tests: next });
  };

  return (
    <div className="space-y-1.5">
      {tests.length === 0 && (
        <p className="text-sm italic text-medicop-text-muted">— sin exámenes —</p>
      )}
      {tests.map((t, i) => (
        <div
          key={i}
          className="flex items-center gap-3 py-2 border-b border-medicop-border/50 last:border-0"
        >
          {editing ? (
            <>
              <input
                value={t.name ?? ""}
                onChange={(e) => setTest(i, "name", e.target.value)}
                className="medicop-input flex-1 text-sm"
                placeholder="Examen"
              />
              <select
                value={t.urgency ?? "rutina"}
                onChange={(e) => setTest(i, "urgency", e.target.value)}
                className="medicop-input text-xs w-32"
              >
                <option value="rutina">rutina</option>
                <option value="urgente">urgente</option>
                <option value="stat">stat</option>
              </select>
            </>
          ) : (
            <>
              <span className="text-sm font-medium text-medicop-text clinical-data flex-1">
                {t.name}
              </span>
              {t.urgency && t.urgency !== "rutina" && (
                <span
                  className={`text-[11px] uppercase font-bold px-2 py-0.5 rounded ${
                    t.urgency === "stat"
                      ? "bg-red-100 text-red-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {t.urgency}
                </span>
              )}
              {t.indication && (
                <span className="text-xs text-medicop-text-muted italic">
                  {t.indication}
                </span>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Generic JSON fallback ────────────────────────────────────────────────────

function GenericBody({ content }: BodyProps) {
  // Render simple key/value para tipos no-cubiertos por editores específicos
  const entries = Object.entries(content).filter(
    ([k, v]) => v !== "" && v != null && !k.startsWith("_"),
  );
  if (entries.length === 0) {
    return (
      <p className="text-sm italic text-medicop-text-muted">— sin contenido —</p>
    );
  }
  return (
    <dl className="space-y-2 text-sm">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt className="text-xs font-semibold text-medicop-text-muted uppercase tracking-wide mb-0.5">
            {key.replace(/_/g, " ")}
          </dt>
          <dd className="text-medicop-text clinical-data whitespace-pre-wrap leading-relaxed">
            {typeof value === "object"
              ? JSON.stringify(value, null, 2)
              : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// ── Citations ────────────────────────────────────────────────────────────────

function CitationsBlock({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState<{ id: string; section: string | null; name?: string } | null>(
    null,
  );

  return (
    <div className="mt-4 pt-3 border-t border-medicop-border">
      <p className="text-[11px] font-semibold text-medicop-text-muted uppercase tracking-wide mb-1.5">
        Fuentes citadas — clic para ver el párrafo
      </p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => {
          const clickable = !!c.guideline_id;
          const label = `${c.guideline_name}${c.section ? " · " + c.section : ""}${c.page ? " · p." + c.page : ""}`;
          return clickable ? (
            <button
              key={i}
              type="button"
              onClick={() =>
                setOpen({
                  id: c.guideline_id as string,
                  section: c.section || null,
                  name: c.guideline_name,
                })
              }
              className="inline-flex items-center gap-1 text-[11px] text-medicop-primary bg-medicop-primary-light hover:bg-medicop-primary hover:text-white transition-colors px-2 py-0.5 rounded"
            >
              <ExternalLink className="w-2.5 h-2.5" />
              {label}
            </button>
          ) : (
            <span
              key={i}
              title={c.text_excerpt}
              className="inline-flex items-center text-[11px] text-medicop-text-muted bg-medicop-bg px-2 py-0.5 rounded"
            >
              {label}
            </span>
          );
        })}
      </div>

      {open && (
        <GuidelineSectionModal
          guidelineId={open.id}
          section={open.section}
          guidelineName={open.name}
          open
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
