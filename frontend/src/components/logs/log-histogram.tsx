"use client";

import { useMemo, useRef, useState, useCallback } from "react";
import type { LogHistogramResponse } from "@/types";
import { formatNumber } from "@/lib/utils";

interface LogHistogramProps {
  data: LogHistogramResponse | undefined;
  loading?: boolean;
  onZoom: (from: Date, to: Date) => void;
  zoomed: boolean;
  onResetZoom: () => void;
}

interface Bucket {
  t: Date;
  count: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

const SEVERITY_STACK: { key: keyof Omit<Bucket, "t" | "count">; color: string; label: string }[] = [
  { key: "info", color: "var(--text-2)", label: "Info" },
  { key: "low", color: "var(--info)", label: "Faible" },
  { key: "medium", color: "var(--warning)", label: "Moyen" },
  { key: "high", color: "#f97316", label: "Élevé" },
  { key: "critical", color: "var(--danger)", label: "Critique" },
];

/** Reconstruit une série continue (buckets vides inclus) à partir des
 * buckets non-vides renvoyés par le backend — sans ça, les périodes sans
 * événement seraient simplement absentes plutôt que d'apparaître à 0. */
function buildSeries(data: LogHistogramResponse): Bucket[] {
  const stepMs = data.interval_seconds * 1000;
  if (stepMs <= 0) return [];
  const start = Math.floor(new Date(data.range_from).getTime() / stepMs) * stepMs;
  const end = new Date(data.range_to).getTime();
  const byTime = new Map(data.buckets.map((b) => [new Date(b.t).getTime(), b]));
  const series: Bucket[] = [];
  const maxBars = 400; // garde-fou si range_from/to incohérents
  for (let t = start, i = 0; t <= end && i < maxBars; t += stepMs, i++) {
    const b = byTime.get(t);
    series.push({
      t: new Date(t),
      count: b?.count ?? 0,
      critical: b?.critical ?? 0,
      high: b?.high ?? 0,
      medium: b?.medium ?? 0,
      low: b?.low ?? 0,
      info: b?.info ?? 0,
    });
  }
  return series;
}

function formatBucketLabel(t: Date, stepSeconds: number): string {
  const opts: Intl.DateTimeFormatOptions =
    stepSeconds >= 86400
      ? { day: "2-digit", month: "2-digit" }
      : stepSeconds >= 3600
      ? { day: "2-digit", month: "2-digit", hour: "2-digit" }
      : { hour: "2-digit", minute: "2-digit" };
  return t.toLocaleString("fr-FR", opts);
}

export function LogHistogram({ data, loading, onZoom, zoomed, onResetZoom }: LogHistogramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const series = useMemo(() => (data ? buildSeries(data) : []), [data]);
  const maxCount = useMemo(() => Math.max(1, ...series.map((b) => b.count)), [series]);

  const indexFromClientX = useCallback(
    (clientX: number): number | null => {
      const el = containerRef.current;
      if (!el || series.length === 0) return null;
      const rect = el.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      return Math.min(series.length - 1, Math.floor(ratio * series.length));
    },
    [series.length]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    const idx = indexFromClientX(e.clientX);
    if (idx === null) return;
    setDragStart(idx);
    setDragEnd(idx);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const idx = indexFromClientX(e.clientX);
    if (idx === null) return;
    setHoverIndex(idx);
    if (dragStart !== null) setDragEnd(idx);
  };

  const handleMouseUp = () => {
    if (dragStart !== null && dragEnd !== null && data) {
      const lo = Math.min(dragStart, dragEnd);
      const hi = Math.max(dragStart, dragEnd);
      const stepMs = data.interval_seconds * 1000;
      const from = series[lo]?.t;
      const to = new Date((series[hi]?.t.getTime() ?? 0) + stepMs);
      // Un simple clic (pas de vrai drag) ne déclenche pas de zoom — sinon
      // impossible de juste survoler pour lire le tooltip sans zoomer.
      if (hi > lo && from) onZoom(from, to);
    }
    setDragStart(null);
    setDragEnd(null);
  };

  const handleMouseLeave = () => {
    setDragStart(null);
    setDragEnd(null);
    setHoverIndex(null);
  };

  const selRange =
    dragStart !== null && dragEnd !== null
      ? [Math.min(dragStart, dragEnd), Math.max(dragStart, dragEnd)]
      : null;

  const total = data?.total ?? 0;
  const hovered = hoverIndex !== null ? series[hoverIndex] : null;

  return (
    <div className="card" style={{ padding: "14px 18px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", gap: 16, fontSize: 11.5, color: "var(--text-2)", alignItems: "center", flexWrap: "wrap" }}>
          <span className="font-display" style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
            Distribution temporelle
          </span>
          <span className="font-mono" style={{ color: "var(--text)", fontWeight: 600 }}>
            {formatNumber(total)}
          </span>
          <span>événements sur la plage sélectionnée</span>
          {SEVERITY_STACK.filter((s) => series.some((b) => b[s.key] > 0)).map((s) => (
            <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 8, height: 8, background: s.color, borderRadius: 2, display: "inline-block" }} />
              {s.label}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {zoomed && (
            <button className="btn" onClick={onResetZoom} style={{ fontSize: 11, padding: "4px 10px" }}>
              Réinitialiser le zoom
            </button>
          )}
          <span style={{ fontSize: 11, color: "var(--text-2)", fontFamily: "var(--font-mono)" }}>
            {data ? `pas ${humanInterval(data.interval_seconds)}` : "—"}
          </span>
        </div>
      </div>

      <div style={{ position: "relative" }}>
        {hovered && (
          <div
            className="card"
            style={{
              position: "absolute",
              bottom: "calc(100% + 8px)",
              left: `${((hoverIndex ?? 0) / Math.max(1, series.length)) * 100}%`,
              transform: "translateX(-50%)",
              padding: "8px 10px",
              fontSize: 11,
              zIndex: 10,
              pointerEvents: "none",
              whiteSpace: "nowrap",
              boxShadow: "0 8px 24px -8px rgba(0,0,0,0.4)",
            }}
          >
            <div className="font-mono" style={{ fontWeight: 700, marginBottom: 4 }}>
              {formatBucketLabel(hovered.t, data?.interval_seconds ?? 60)}
            </div>
            <div className="font-mono" style={{ color: "var(--text-2)" }}>
              {formatNumber(hovered.count)} événement{hovered.count > 1 ? "s" : ""}
            </div>
            {SEVERITY_STACK.filter((s) => hovered[s.key] > 0).map((s) => (
              <div key={s.key} style={{ display: "flex", justifyContent: "space-between", gap: 12, color: s.color }}>
                <span>{s.label}</span>
                <span>{formatNumber(hovered[s.key])}</span>
              </div>
            ))}
          </div>
        )}

        <div
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: series.length > 120 ? 0 : 2,
            height: 70,
            cursor: "crosshair",
            userSelect: "none",
            opacity: loading ? 0.5 : 1,
            transition: "opacity 140ms ease",
          }}
        >
          {series.length === 0 && !loading && (
            <div style={{ flex: 1, textAlign: "center", color: "var(--text-2)", fontSize: 12, alignSelf: "center" }}>
              Aucun événement sur cette plage.
            </div>
          )}
          {series.map((b, i) => {
            const inSelection = selRange && i >= selRange[0] && i <= selRange[1];
            const heightPct = Math.max(b.count > 0 ? 4 : 0, (b.count / maxCount) * 100);
            return (
              <div
                key={i}
                title={`${formatBucketLabel(b.t, data?.interval_seconds ?? 60)} — ${b.count} événement(s)`}
                style={{
                  flex: 1,
                  minWidth: 1,
                  height: `${heightPct}%`,
                  display: "flex",
                  flexDirection: "column-reverse",
                  borderRadius: 1.5,
                  overflow: "hidden",
                  outline: inSelection ? "1px solid var(--primary)" : "none",
                  background: inSelection ? "color-mix(in srgb, var(--primary) 20%, transparent)" : "transparent",
                }}
              >
                {b.count > 0 &&
                  SEVERITY_STACK.map((s) => {
                    const segCount = b[s.key];
                    if (segCount <= 0) return null;
                    return (
                      <div
                        key={s.key}
                        style={{
                          width: "100%",
                          height: `${(segCount / b.count) * 100}%`,
                          background: s.color,
                          opacity: hoverIndex === i ? 1 : 0.75,
                        }}
                      />
                    );
                  })}
              </div>
            );
          })}
        </div>
      </div>
      <p style={{ fontSize: 10.5, color: "var(--text-2)", marginTop: 8, marginBottom: 0 }}>
        Cliquez-glissez sur le graphique pour zoomer sur une plage précise.
      </p>
    </div>
  );
}

function humanInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}j`;
}
