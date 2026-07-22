"use client";

import { motion } from "framer-motion";
import { formatNumber, calcPercent } from "@/lib/utils";
import { CountryFlag } from "@/components/common/country-flag";
import type { GeoData } from "@/types";

interface GeoTableProps {
  data: GeoData[];
  subtitle?: string;
}

export function GeoTable({ data, subtitle = "Dernières 24 heures" }: GeoTableProps) {
  const maxCount = Math.max(1, ...data.map((d) => d.count));

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 }}
      className="rounded-xl border border-border p-5"
      style={{ background: "hsl(var(--card))" }}
    >
      <div className="mb-5">
        <h3 className="text-sm font-semibold text-foreground">Connexions par pays</h3>
        <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
      </div>

      <div className="space-y-3">
        {data.map((item, i) => (
          <motion.div
            key={item.country_code}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.8 + i * 0.05 }}
            className="flex items-center gap-3"
          >
            {/* Flag + country name */}
            <CountryFlag
              code={item.country_code}
              size="md"
              showName={item.country}
              className="flex-shrink-0 w-36"
            />

            {/* Progress bar */}
            <div className="flex-1 relative">
              <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${calcPercent(item.count, maxCount)}%` }}
                  transition={{ duration: 0.8, delay: 0.9 + i * 0.05, ease: "easeOut" }}
                  className="h-full rounded-full"
                  style={{
                    // Gris neutre par défaut — la couleur n'est réservée qu'aux pays
                    // avec une activité de menace réelle (ambre/rouge = signal).
                    background: item.threat_count > 10
                      ? "linear-gradient(90deg, #ef4444, #f97316)"
                      : item.threat_count > 5
                      ? "linear-gradient(90deg, #f59e0b, #eab308)"
                      : "#94a3b8",
                  }}
                />
              </div>
            </div>

            {/* Count */}
            <div className="flex-shrink-0 text-right">
              <span className="text-xs font-semibold text-foreground tabular-nums">
                {formatNumber(item.count)}
              </span>
              <span className="text-[10px] text-muted-foreground ml-1">
                {item.percentage}%
              </span>
            </div>

            {/* Threats badge */}
            {item.threat_count > 0 && (
              <div className="flex-shrink-0">
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded border font-medium"
                  style={
                    item.threat_count > 20
                      ? { color: "#ef4444", background: "rgba(239,68,68,0.1)", borderColor: "rgba(239,68,68,0.3)" }
                      : item.threat_count > 10
                      ? { color: "#f59e0b", background: "rgba(245,158,11,0.1)", borderColor: "rgba(245,158,11,0.3)" }
                      : { color: "#6b7280", background: "rgba(107,114,128,0.1)", borderColor: "rgba(107,114,128,0.3)" }
                  }
                >
                  ⚠ {item.threat_count}
                </span>
              </div>
            )}
          </motion.div>
        ))}
        {data.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">Aucune donnée géographique sur cette période</p>
        )}
      </div>
    </motion.div>
  );
}
