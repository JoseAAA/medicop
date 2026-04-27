"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Lock, Shield, Brain, WifiOff, Loader2 } from "lucide-react";

import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, user, isLoading: authLoading } = useAuth();

  const [email, setEmail] = useState("demo@medicop.pe");
  const [password, setPassword] = useState("Demo1234!");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Si ya hay sesión activa, saltar al dashboard
  useEffect(() => {
    if (!authLoading && user) {
      const from = searchParams.get("from");
      router.replace(
        (from && from.startsWith("/") ? from : "/dashboard") as Route,
      );
    }
  }, [authLoading, user, searchParams, router]);

  // Mensaje si el redirect vino de un 401 / sesión expirada
  useEffect(() => {
    if (searchParams.get("expired")) {
      setError("Tu sesión expiró. Vuelve a iniciar sesión.");
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      const from = searchParams.get("from");
      router.replace(
        (from && from.startsWith("/") ? from : "/dashboard") as Route,
      );
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No se pudo iniciar sesión. Intenta nuevamente.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 flex">
        {/* ── Panel izquierdo — branding ──────────────────────── */}
        <div className="hidden lg:flex lg:w-[480px] xl:w-[540px] bg-gradient-to-br from-[#002244] via-[#003366] to-[#0066B3] flex-col justify-between p-12 shrink-0 relative overflow-hidden">
          <div
            className="absolute inset-0 opacity-[0.05]"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
              backgroundSize: "28px 28px",
            }}
          />

          <div className="relative">
            <div className="flex items-center gap-3 mb-16">
              <div className="w-10 h-10 bg-white/15 rounded-xl flex items-center justify-center border border-white/20">
                <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white" aria-hidden>
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" />
                </svg>
              </div>
              <span className="text-white font-bold text-xl tracking-tight">MediCop</span>
            </div>

            <h1 className="text-4xl font-bold text-white leading-tight mb-4">
              Inteligencia clínica <span className="text-[#7DD3FC]">local</span>.
            </h1>
            <p className="text-white/70 text-lg leading-relaxed mb-12">
              Asistente de apoyo diagnóstico para médicos peruanos. Tus datos
              nunca salen del hospital.
            </p>

            <div className="space-y-3">
              {[
                { icon: Brain, text: "Consulta guías oficiales del MINSA, EsSalud y OMS" },
                { icon: WifiOff, text: "Funciona sin internet" },
                { icon: Shield, text: "Datos protegidos · Ley 29733 del Perú" },
              ].map(({ icon: Icon, text }) => (
                <div key={text} className="flex items-center gap-3 text-white/80">
                  <div className="w-8 h-8 bg-white/10 rounded-lg flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="text-sm">{text}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="relative text-white/40 text-xs">
            Inteligencia clínica local — Perú
          </p>
        </div>

        {/* ── Panel derecho — formulario ───────────────────────── */}
        <div className="flex-1 flex flex-col items-center justify-center bg-medicop-bg px-6 py-12">
          <div className="w-full max-w-[400px]">
            <div className="lg:hidden text-center mb-10">
              <div className="inline-flex items-center gap-2.5">
                <div className="w-9 h-9 bg-medicop-primary rounded-xl flex items-center justify-center">
                  <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white" aria-hidden>
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" />
                  </svg>
                </div>
                <span className="text-xl font-bold text-medicop-primary">MediCop</span>
              </div>
            </div>

            <div className="mb-8">
              <h2 className="text-2xl font-bold text-medicop-text">Bienvenido</h2>
              <p className="text-medicop-text-muted mt-1 text-sm">
                Ingresa con tus credenciales institucionales
              </p>
            </div>

            <div className="medicop-card p-8">
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="email" className="medicop-label">
                    Correo electrónico
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="medico@hospital.pe"
                    className="medicop-input"
                    disabled={submitting}
                  />
                </div>

                <div>
                  <label htmlFor="password" className="medicop-label">
                    Contraseña
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="medicop-input pr-10"
                      disabled={submitting}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-medicop-text-muted hover:text-medicop-text transition-colors p-0.5"
                      aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div
                    className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2.5"
                    role="alert"
                  >
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="medicop-btn-primary w-full py-3 text-sm font-semibold mt-2 inline-flex items-center justify-center gap-2"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {submitting ? "Ingresando…" : "Ingresar al sistema"}
                </button>
              </form>

              <div className="mt-6 pt-5 border-t border-medicop-border flex items-start gap-2.5">
                <Lock className="w-3.5 h-3.5 mt-0.5 shrink-0 text-medicop-accent" />
                <p className="text-xs text-medicop-text-muted leading-relaxed">
                  Sesión protegida. Los datos del paciente no salen del
                  hospital.
                </p>
              </div>
            </div>

            <p className="text-center mt-6 text-xs text-medicop-text-muted">
              <Link href="/" className="hover:text-medicop-primary transition-colors">
                ← Volver al inicio
              </Link>
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}
