"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, Square, Loader2, AlertCircle, FileAudio } from "lucide-react";

import { ApiError } from "@/lib/types";
import { transcriptionApi } from "@/lib/api";

interface AudioRecorderProps {
  encounterId: string;
  onTranscript: (transcript: string) => void;
  disabled?: boolean;
  /** NHC del paciente — si coincide con un audio en demo-audio/manifest.json, aparece el botón "Cargar audio de ejemplo". */
  patientNhc?: string;
}

interface DemoAudioEntry {
  filename: string;
  label: string;
  transcript_preview: string;
}

type State =
  | { kind: "idle" }
  | { kind: "requesting" }
  | { kind: "recording"; startedAt: number }
  | { kind: "transcribing"; source: "mic" | "demo" }
  | { kind: "error"; message: string };

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioRecorder({
  onTranscript,
  disabled,
  patientNhc,
}: AudioRecorderProps) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [elapsed, setElapsed] = useState(0);
  const [demoAudio, setDemoAudio] = useState<DemoAudioEntry | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Carga manifest de demo audios y resuelve el del paciente por NHC
  useEffect(() => {
    if (!patientNhc) return;
    fetch("/demo-audio/manifest.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        const entry = data?.audios?.[patientNhc] as DemoAudioEntry | undefined;
        if (entry) setDemoAudio(entry);
      })
      .catch(() => {
        // Sin manifest, sin botón demo. Silencioso.
      });
  }, [patientNhc]);

  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  const sendBlob = async (blob: Blob, ext: string, source: "mic" | "demo") => {
    setState({ kind: "transcribing", source });
    try {
      const result = await transcriptionApi.transcribe(blob, `consulta.${ext}`);
      onTranscript(result.transcript);
      setState({ kind: "idle" });
      setElapsed(0);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo transcribir el audio";
      setState({ kind: "error", message: msg });
    }
  };

  const startRecording = async () => {
    setState({ kind: "requesting" });
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }
        if (tickRef.current) {
          clearInterval(tickRef.current);
          tickRef.current = null;
        }

        if (blob.size === 0) {
          setState({ kind: "error", message: "No se grabó audio" });
          return;
        }

        const ext = recorder.mimeType.includes("webm") ? "webm" : "ogg";
        await sendBlob(blob, ext, "mic");
      };

      recorder.start(1000);
      const startedAt = Date.now();
      setState({ kind: "recording", startedAt });
      tickRef.current = setInterval(() => {
        setElapsed(Date.now() - startedAt);
      }, 250);
    } catch (err) {
      const msg =
        (err as Error)?.name === "NotAllowedError"
          ? "Permiso de micrófono denegado"
          : "No se pudo acceder al micrófono";
      setState({ kind: "error", message: msg });
    }
  };

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  };

  const loadDemoAudio = async () => {
    if (!demoAudio) return;
    setState({ kind: "transcribing", source: "demo" });
    try {
      const res = await fetch(`/demo-audio/${demoAudio.filename}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      await sendBlob(blob, "mp3", "demo");
    } catch (err) {
      setState({
        kind: "error",
        message: `No se pudo cargar el audio de demo: ${(err as Error).message}`,
      });
    }
  };

  const isRecording = state.kind === "recording";
  const isBusy = state.kind === "requesting" || state.kind === "transcribing";

  return (
    <div className="medicop-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-medicop-text">
          Grabación de la consulta
        </h3>
        {isRecording && (
          <span className="inline-flex items-center gap-1.5 text-xs text-red-600 font-medium">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            REC · {formatDuration(elapsed)}
          </span>
        )}
        {state.kind === "transcribing" && (
          <span className="inline-flex items-center gap-1.5 text-xs text-medicop-primary">
            <Loader2 className="w-3 h-3 animate-spin" />
            Transcribiendo {state.source === "demo" ? "audio demo" : "audio"}…
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {!isRecording ? (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled || isBusy}
            className="medicop-btn-primary text-sm inline-flex items-center gap-2 disabled:opacity-50"
          >
            {state.kind === "requesting" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Mic className="w-4 h-4" />
            )}
            {state.kind === "transcribing"
              ? "Transcribiendo audio…"
              : "Iniciar grabación"}
          </button>
        ) : (
          <button
            type="button"
            onClick={stopRecording}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2 transition-colors"
          >
            <Square className="w-4 h-4 fill-white" />
            Detener
          </button>
        )}

        {demoAudio && !isRecording && (
          <button
            type="button"
            onClick={loadDemoAudio}
            disabled={disabled || isBusy}
            title={demoAudio.transcript_preview}
            className="medicop-btn-outline text-sm inline-flex items-center gap-2 disabled:opacity-50"
          >
            <FileAudio className="w-4 h-4" />
            Audio demo: {demoAudio.label}
          </button>
        )}
      </div>

      <p className="text-xs text-medicop-text-muted mt-3 leading-relaxed">
        Transcripción automática en español. El audio se procesa y se descarta
        — no se guarda. Si el micrófono falla, usa el audio de ejemplo.
      </p>

      {state.kind === "error" && (
        <div
          className="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2 flex items-start gap-2"
          role="alert"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{state.message}</span>
        </div>
      )}
    </div>
  );
}
