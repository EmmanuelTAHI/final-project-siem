"use client";

import { motion } from "framer-motion";
import CountUp from "react-countup";
import { ShieldAlert, AlertTriangle, AlertCircle, Info } from "lucide-react";
import { severityHex } from "@/lib/utils";
import type { DashboardSummary } from "@/types";

interface SeverityCardsProps {
  data: DashboardSummary;
}

function safeNum(v: unknown): number {
  return typeof v === "number" && isFinite(v) ? v : 0;
}

const CONFIG = [
  { key: "critical_alerts", label: "Critique", desc: "Action immédiate requise", icon: ShieldAlert, color: severityHex.critical },
  { key: "high_alerts", label: "Élevé", desc: "À traiter en priorité", icon: AlertTriangle, color: severityHex.high },
  { key: "medium_alerts", label: "Moyen", desc: "À surveiller", icon: AlertCircle, color: severityHex.medium },
  { key: "low_alerts", label: "Faible", desc: "Information", icon: Info, color: severityHex.low },
] as const;

export function SeverityCards({ data }: SeverityCardsProps) {
  const counts = CONFIG.map((c) => safeNum(data[c.key as keyof DashboardSummary]));
  const total = counts.reduce((a, b) => a + b, 0);

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CONFIG.map((cfg, i) => {
        const value = counts[i];
        const pct = total > 0 ? Math.round((value / total) * 100) : 0;
        return (
          <motion.div
            key={cfg.key}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.05 }}
            className="card card-hover"
            style={{
              padding: 18,
              position: "relative",
              overflow: "hidden",
              boxShadow: `inset 3px 0 0 ${cfg.color}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: `color-mix(in srgb, ${cfg.color} 16%, transparent)`,
                  color: cfg.color,
                }}
              >
                <cfg.icon size={17} />
              </div>
              <span
                className="font-mono"
                style={{ fontSize: 11.5, fontWeight: 600, color: "var(--text-2)" }}
              >
                {pct}%
              </span>
            </div>

            <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)" }}>
              Alertes {cfg.label}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 1, marginBottom: 10 }}>
              {cfg.desc}
            </div>

            <div className="font-display font-mono" style={{ fontSize: 28, fontWeight: 700, lineHeight: 1, marginBottom: 10 }}>
              <CountUp end={value} duration={1} separator=" " />
            </div>

            <div className="prog">
              <div style={{ width: `${pct}%`, background: cfg.color }} />
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
