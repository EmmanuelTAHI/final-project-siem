"use client";

import { motion } from "framer-motion";
import { AlertTriangle, AlertCircle, Info, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AlertSeverity } from "@/types";

interface SeverityBadgeProps {
  severity: AlertSeverity;
  showLabel?: boolean;
  size?: "sm" | "md";
  className?: string;
}

const severityConfig = {
  low: {
    label: "Faible",
    icon: Info,
    color: "text-emerald-400",
    bg: "bg-emerald-400/10",
    border: "border-emerald-400/30",
    pulse: false,
  },
  medium: {
    label: "Moyen",
    icon: AlertCircle,
    color: "text-amber-400",
    bg: "bg-amber-400/10",
    border: "border-amber-400/30",
    pulse: false,
  },
  high: {
    label: "Élevé",
    icon: AlertTriangle,
    color: "text-red-400",
    bg: "bg-red-400/10",
    border: "border-red-400/30",
    pulse: false,
  },
  critical: {
    label: "Critique",
    icon: Zap,
    color: "text-purple-400",
    bg: "bg-purple-400/10",
    border: "border-purple-500/40",
    pulse: true,
  },
};

export function SeverityBadge({ severity, showLabel = true, size = "md", className }: SeverityBadgeProps) {
  const config = severityConfig[severity];
  const Icon = config.icon;

  return (
    <div className={cn("relative inline-flex items-center", className)}>
      {config.pulse && (
        <motion.div
          className={cn("absolute inset-0 rounded-md", config.bg)}
          animate={{ opacity: [0.3, 0.8, 0.3] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <div
        className={cn(
          "relative flex items-center gap-1 rounded-md border font-medium",
          config.bg,
          config.border,
          config.color,
          size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs"
        )}
      >
        <Icon className={size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3"} />
        {showLabel && <span>{config.label}</span>}
      </div>
    </div>
  );
}
