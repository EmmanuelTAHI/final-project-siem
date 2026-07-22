"use client";

import { AreaChart, Area, ResponsiveContainer } from "recharts";

interface IPSparklineProps {
  values: number[];
  color?: string;
}

/** Mini graphique d'activité par IP (colonne de tableau, façon Grafana). */
export function IPSparkline({ values, color = "var(--primary)" }: IPSparklineProps) {
  if (!values || values.length === 0 || values.every((v) => v === 0)) {
    return <div className="w-20 h-8 flex items-center justify-center text-[10px] text-muted-foreground">—</div>;
  }
  const data = values.map((v, i) => ({ i, v }));
  const gradientId = `spark-${Math.random().toString(36).slice(2, 9)}`;

  return (
    <div className="w-20 h-8">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} fill={`url(#${gradientId})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
