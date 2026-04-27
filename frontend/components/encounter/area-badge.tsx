import { clsx } from "clsx";
import {
  AmbulanceIcon,
  Bed,
  Stethoscope,
  Scissors,
  type LucideIcon,
} from "lucide-react";

import {
  HOSPITAL_AREA_COLORS,
  HOSPITAL_AREA_LABELS,
  type HospitalArea,
} from "@/lib/types";

const AREA_ICONS: Record<HospitalArea, LucideIcon> = {
  emergencia: AmbulanceIcon,
  hospitalizacion: Bed,
  consulta_externa: Stethoscope,
  cirugia: Scissors,
};

interface AreaBadgeProps {
  area: HospitalArea;
  size?: "sm" | "md";
  className?: string;
}

export default function AreaBadge({ area, size = "sm", className }: AreaBadgeProps) {
  const colors = HOSPITAL_AREA_COLORS[area];
  const Icon = AREA_ICONS[area];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        colors.bg,
        colors.text,
        colors.border,
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-xs",
        className,
      )}
    >
      <Icon className={size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5"} />
      {HOSPITAL_AREA_LABELS[area]}
    </span>
  );
}
