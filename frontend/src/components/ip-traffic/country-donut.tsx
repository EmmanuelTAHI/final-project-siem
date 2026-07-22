"use client";

import { useTheme } from "next-themes";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { countryName } from "@/lib/country-names";
import { CountryFlag } from "@/components/common/country-flag";
import type { IPTrafficCountry } from "@/types";

// Palette catégorielle validée (voir dataviz skill — 3 premiers slots =
// sûrs en comparaison "toutes paires", au-delà on replie sur "Autres"
// plutôt que d'ajouter une 4e couleur qui casse la distinction CVD).
const SLOTS_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a"];
const SLOTS_DARK = ["#3987e5", "#d95926", "#199e70"];
const OTHER_INK = "#898781";

interface CountryDonutProps {
  data: IPTrafficCountry[];
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number; payload: { color: string; percentage: number } }> }) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-xl border border-border px-3 py-2 text-sm shadow-xl" style={{ background: "hsl(var(--card))" }}>
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ background: item.payload.color }} />
        <span className="text-muted-foreground">{item.name}:</span>
        <span className="font-semibold">{item.value.toLocaleString()}</span>
        <span className="text-muted-foreground">({item.payload.percentage}%)</span>
      </div>
    </div>
  );
}

export function CountryDonut({ data }: CountryDonutProps) {
  const { resolvedTheme } = useTheme();
  const slots = resolvedTheme === "dark" ? SLOTS_DARK : SLOTS_LIGHT;

  const top3 = data.slice(0, 3);
  const rest = data.slice(3);
  const otherCount = rest.reduce((sum, d) => sum + d.count, 0);
  const otherPct = rest.reduce((sum, d) => sum + d.percentage, 0);

  const chartData = [
    ...top3.map((d, i) => ({
      name: countryName(d.country_code),
      code: d.country_code,
      value: d.count,
      percentage: d.percentage,
      color: slots[i],
    })),
    ...(rest.length > 0
      ? [{ name: `Autres (${rest.length} pays)`, code: "", value: otherCount, percentage: Math.round(otherPct * 10) / 10, color: OTHER_INK }]
      : []),
  ].filter((d) => d.value > 0);

  const total = chartData.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="rounded-xl border border-border p-5" style={{ background: "hsl(var(--card))" }}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-foreground">Répartition par pays</h3>
        <p className="text-xs text-muted-foreground mt-0.5">Sur la période sélectionnée</p>
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
              paddingAngle={2}
              dataKey="value"
              startAngle={90}
              endAngle={-270}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-2xl font-bold text-foreground tabular-nums">{data.length}</span>
          <span className="text-xs text-muted-foreground">pays</span>
        </div>
      </div>

      <div className="space-y-2 mt-3">
        {chartData.map((item) => (
          <div key={item.name} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: item.color }} />
            {item.code ? <CountryFlag code={item.code} size="sm" /> : <span className="w-4" />}
            <span className="text-xs text-muted-foreground flex-1 truncate">{item.name}</span>
            <span className="text-xs font-semibold text-foreground tabular-nums">{item.value.toLocaleString()}</span>
            <span className="text-xs text-muted-foreground w-10 text-right tabular-nums">{item.percentage}%</span>
          </div>
        ))}
        {total === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">Aucune donnée géographique sur cette période</p>
        )}
      </div>
    </div>
  );
}
