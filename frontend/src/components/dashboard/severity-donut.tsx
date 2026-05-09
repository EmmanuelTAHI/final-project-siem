"use client";

import { motion } from "framer-motion";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { severityHex } from "@/lib/utils";
import type { DashboardSummary } from "@/types";

interface SeverityDonutProps {
  data: DashboardSummary;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number; payload: { color: string } }> }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl border border-border px-3 py-2 text-sm shadow-xl"
      style={{ background: "hsl(var(--card))" }}
    >
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ background: payload[0].payload.color }} />
        <span className="text-muted-foreground capitalize">{payload[0].name}:</span>
        <span className="font-semibold">{payload[0].value}</span>
      </div>
    </div>
  );
}

function safeNum(v: unknown): number {
  return typeof v === "number" && isFinite(v) ? v : 0;
}

export function SeverityDonut({ data }: SeverityDonutProps) {
  const critical = safeNum(data.critical_alerts);
  const high = safeNum(data.high_alerts);
  const medium = safeNum(data.medium_alerts);
  const low = safeNum(data.low_alerts);
  const total = critical + high + medium + low;

  const chartData = [
    { name: "Critique", value: critical, color: severityHex.critical },
    { name: "Élevé", value: high, color: severityHex.high },
    { name: "Moyen", value: medium, color: severityHex.medium },
    { name: "Faible", value: low, color: severityHex.low },
  ].filter((d) => d.value > 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="card"
      style={{ padding: 20 }}
    >
      <div className="font-display" style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
        Répartition par sévérité
      </div>

      <div className="relative">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
              startAngle={90}
              endAngle={-270}
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color}
                  stroke="transparent"
                  style={{ filter: `drop-shadow(0 0 6px ${entry.color}50)` }}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-2xl font-bold text-foreground">{total}</span>
          <span className="text-xs text-muted-foreground">alertes</span>
        </div>
      </div>

      {/* Legend */}
      <div className="space-y-2 mt-3">
        {chartData.map((item) => (
          <div key={item.name} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: item.color }} />
            <span className="text-xs text-muted-foreground flex-1">{item.name}</span>
            <span className="text-xs font-semibold text-foreground">{item.value}</span>
            <span className="text-xs text-muted-foreground w-8 text-right">
              {total > 0 ? Math.round((item.value / total) * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
