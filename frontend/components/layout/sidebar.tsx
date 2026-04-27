"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, LogOut, User } from "lucide-react";
import { clsx } from "clsx";

import { useAuth } from "@/contexts/auth-context";

const navItems: { href: Route; label: string; icon: typeof LayoutDashboard }[] = [
  { href: "/dashboard", label: "Inicio", icon: LayoutDashboard },
  { href: "/patients", label: "Pacientes", icon: Users },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-[#002244] flex flex-col shrink-0 select-none">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-white/10">
        <div className="w-8 h-8 bg-medicop-primary rounded-lg flex items-center justify-center shrink-0">
          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-white" aria-hidden>
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" />
          </svg>
        </div>
        <span className="text-white font-bold text-base tracking-tight">
          MediCop
        </span>
      </div>

      <div className="px-4 py-3 border-b border-white/10">
        <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
          <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse-slow shrink-0" />
          <span className="text-white/60 text-xs">Sistema activo</span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                active
                  ? "bg-white/12 text-white"
                  : "text-white/55 hover:bg-white/8 hover:text-white/90"
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-[#7DD3FC] rounded-r-full" />
              )}
              <Icon className={clsx("w-4 h-4 shrink-0", active && "text-[#7DD3FC]")} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-4 border-t border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-medicop-primary/40 border border-medicop-primary/60 rounded-full flex items-center justify-center shrink-0">
            <User className="w-4 h-4 text-white/80" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white/90 text-xs font-medium truncate">
              {user?.full_name ?? "—"}
            </p>
            {user?.cmp_number && (
              <p className="text-white/40 text-[10px] truncate">CMP {user.cmp_number}</p>
            )}
          </div>
          <button
            onClick={() => logout()}
            className="text-white/40 hover:text-red-400 transition-colors p-1"
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
