"use client";

import { usePathname } from "next/navigation";
import { Bell, User, LogOut, ChevronRight } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/contexts/auth-context";

const ROUTE_LABELS: Record<string, string> = {
  "/dashboard": "Inicio",
  "/patients": "Pacientes",
};

function labelFor(pathname: string): string {
  if (ROUTE_LABELS[pathname]) return ROUTE_LABELS[pathname];
  if (pathname.startsWith("/patients/")) return "Detalle de paciente";
  if (pathname.startsWith("/consultation/")) return "Consulta en curso";
  return "MediCop";
}

function shortName(fullName: string | undefined): string {
  if (!fullName) return "—";
  const parts = fullName.trim().split(/\s+/);
  // Si dice "Dr. Demo Test" → "Dr. Test"; si dice "Demo Test" → "Test"
  if (parts[0]?.toLowerCase().startsWith("dr")) {
    return `${parts[0]} ${parts[parts.length - 1]}`;
  }
  return `Dr. ${parts[parts.length - 1]}`;
}

export default function Topbar() {
  const pathname = usePathname();
  const label = labelFor(pathname);
  const { user, logout } = useAuth();

  return (
    <header className="h-14 bg-white border-b border-medicop-border px-5 flex items-center justify-between shrink-0 z-10">
      <nav className="flex items-center gap-1.5 text-sm" aria-label="Breadcrumb">
        <Link
          href="/dashboard"
          className="text-medicop-text-muted hover:text-medicop-primary transition-colors"
        >
          Inicio
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-medicop-border" />
        <span className="font-medium text-medicop-text">{label}</span>
      </nav>

      <div className="flex items-center gap-1">
        <button
          className="relative p-2 text-medicop-text-muted hover:text-medicop-text hover:bg-medicop-bg rounded-lg transition-colors"
          aria-label="Notificaciones"
        >
          <Bell className="w-4 h-4" />
        </button>

        <div className="w-px h-5 bg-medicop-border mx-1" />

        <div className="flex items-center gap-2.5 pl-1">
          <div className="w-8 h-8 bg-medicop-primary-light border border-medicop-primary/20 rounded-full flex items-center justify-center">
            <User className="w-4 h-4 text-medicop-primary" />
          </div>
          <div className="hidden sm:block">
            <p className="text-xs font-semibold text-medicop-text leading-none">
              {shortName(user?.full_name)}
            </p>
            {user?.cmp_number && (
              <p className="text-[10px] text-medicop-text-muted leading-none mt-0.5">
                CMP {user.cmp_number}
              </p>
            )}
          </div>
          <button
            onClick={() => logout()}
            className="p-1.5 text-medicop-text-muted hover:text-medicop-danger hover:bg-red-50 rounded-md transition-colors"
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
