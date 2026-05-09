"use client";

import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { severityHex } from "@/lib/utils";
import type { TopThreat } from "@/types";

interface TopThreatsChartProps {
  data: TopThreat[];
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ value: number; payload: TopThreat }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div
      className="rounded-xl border border-border px-3 py-2 text-sm shadow-xl"
      style={{ background: "hsl(var(--card))" }}
    >
      <p className="font-medium text-foreground mb-1">{d.name}</p>
      <p className="text-muted-foreground">Occurrences: <span className="font-semibold text-foreground">{d.count.toLocaleString()}</span></p>
      <p className="text-muted-foreground capitalize">Sévérité: <span className="font-semibold" style={{ color: severityHex[d.severity] }}>{d.severity}</span></p>
    </div>
  );
}

export function TopThreatsChart({ data }: TopThreatsChartProps) {
  const safe = Array.isArray(data) ? data : [];
  const chartData = safe.slice(0, 8).map((t) => ({
    ...t,
    name: t.name.length > 20 ? t.name.slice(0, 18) + "…" : t.name,
    fullName: t.name,
  }));

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="card"
      style={{ padding: 20 }}
    >
      <div style={{ marginBottom: 16 }}>
        <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>Top règles déclenchées</div>
        <div style={{ fontSize: 12, color: "var(--text-2)" }}>7 derniers jours</div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 0, right: 10, left: 0, bottom: 0 }}
          barSize={16}
        >
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            width={110}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--secondary))", opacity: 0.5 }} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={severityHex[entry.severity]}
                opacity={0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Trend indicators */}
      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-border">
        <div className="flex items-center gap-1.5 text-xs text-red-400">
          <TrendingUp className="w-3.5 h-3.5" />
          <span>{safe.filter((d) => d.trend === "up").length} en hausse</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-emerald-400">
          <TrendingDown className="w-3.5 h-3.5" />
          <span>{safe.filter((d) => d.trend === "down").length} en baisse</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Minus className="w-3.5 h-3.5" />
          <span>{safe.filter((d) => d.trend === "stable").length} stables</span>
        </div>
      </div>
    </motion.div>
  );
}
