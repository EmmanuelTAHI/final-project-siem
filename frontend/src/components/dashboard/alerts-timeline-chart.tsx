"use client";

import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { motion } from "framer-motion";
import { format, parseISO } from "date-fns";
import { fr } from "date-fns/locale";
import { useTimeline } from "@/hooks/use-dashboard";
import type { TimelineDataPoint } from "@/types";

type Period = "24h" | "7d" | "30d";

const periodFormats: Record<Period, string> = {
  "24h": "HH:mm",
  "7d": "EEE dd",
  "30d": "dd MMM",
};

// Custom tooltip
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;

  return (
    <div
      className="rounded-xl border border-border px-4 py-3 text-sm shadow-xl"
      style={{
        background: "hsl(var(--card))",
        backdropFilter: "blur(20px)",
      }}
    >
      <p className="text-muted-foreground text-xs mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
          <span className="text-muted-foreground capitalize">{entry.name}:</span>
          <span className="font-semibold text-foreground">{entry.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export function AlertsTimelineChart() {
  const [period, setPeriod] = useState<Period>("24h");
  const { data: timelineData } = useTimeline(period);

  const data = (Array.isArray(timelineData) ? timelineData : []).map((d: TimelineDataPoint) => {
    try {
      return { ...d, time: format(parseISO(d.timestamp), periodFormats[period], { locale: fr }) };
    } catch {
      return { ...d, time: d.timestamp };
    }
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      className="card"
      style={{ padding: 20 }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>Timeline d&apos;activité</div>
          <div style={{ fontSize: 12, color: "var(--text-2)" }}>Logs, alertes et anomalies ML</div>
        </div>
        {/* Period toggle */}
        <div style={{ display: "flex", gap: 2, padding: 3, background: "color-mix(in srgb, var(--text) 5%, transparent)", borderRadius: 10 }}>
          {(["24h", "7d", "30d"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className="font-mono"
              style={{
                padding: "5px 10px",
                borderRadius: 7,
                border: "none",
                cursor: "pointer",
                background: period === p ? "var(--surface)" : "transparent",
                color: period === p ? "var(--text)" : "var(--text-2)",
                fontWeight: period === p ? 600 : 500,
                fontSize: 12,
                boxShadow: period === p ? "0 2px 6px -2px color-mix(in srgb, var(--text) 18%, transparent)" : "none",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="logsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="alertsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="anomaliesGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border))"
            vertical={false}
            opacity={0.5}
          />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} />

          <Area
            type="monotone"
            dataKey="logs"
            name="Logs"
            stroke="var(--primary)"
            strokeWidth={2}
            fill="url(#logsGrad)"
            dot={false}
            activeDot={{ r: 4, fill: "#3b82f6", strokeWidth: 0 }}
          />
          <Area
            type="monotone"
            dataKey="alerts"
            name="Alertes"
            stroke="#ef4444"
            strokeWidth={2}
            fill="url(#alertsGrad)"
            dot={false}
            activeDot={{ r: 4, fill: "#ef4444", strokeWidth: 0 }}
          />
          <Area
            type="monotone"
            dataKey="anomalies"
            name="Anomalies"
            stroke="#8b5cf6"
            strokeWidth={2}
            fill="url(#anomaliesGrad)"
            dot={false}
            activeDot={{ r: 4, fill: "#8b5cf6", strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center justify-center gap-5 mt-3">
        {[
          { label: "Logs", color: "#3b82f6" },
          { label: "Alertes", color: "#ef4444" },
          { label: "Anomalies ML", color: "#8b5cf6" },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: item.color }} />
            <span className="text-xs text-muted-foreground">{item.label}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
