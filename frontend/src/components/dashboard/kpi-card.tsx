"use client";

import CountUp from "react-countup";
import { TrendingUp, TrendingDown, type LucideIcon } from "lucide-react";
import { formatNumber } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: number;
  change?: number;
  changeLabel?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  format?: "number" | "compact";
  pulse?: boolean;
  subtitle?: string;
  delay?: number;
  onClick?: () => void;
  spark?: number[];
  tone?: "danger" | "primary" | "secondary" | "info" | "warning";
}

const toneColors: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  danger: "var(--danger)",
  primary: "var(--primary)",
  secondary: "var(--secondary)",
  info: "var(--info)",
  warning: "var(--warning)",
};

function SparkLine({ data, color, w = 90, h = 32 }: { data: number[]; color: string; w?: number; h?: number }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = Math.max(1, max - min);
  const step = w / (data.length - 1);
  const pts = data.map((v, i) => [i * step, h - ((v - min) / range) * h * 0.8 - h * 0.1]);
  const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const fill = path + ` L${w},${h} L0,${h} Z`;
  return (
    <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <path d={fill} className="fill" fill={color} />
      <path d={path} stroke={color} />
    </svg>
  );
}

export function KpiCard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  format = "compact",
  subtitle,
  delay = 0,
  onClick,
  spark,
  tone = "primary",
}: KpiCardProps) {
  const color = toneColors[tone];
  const iconBg = `linear-gradient(135deg, color-mix(in srgb, ${color} 20%, transparent), color-mix(in srgb, ${color} 6%, transparent))`;

  const isUp = (change ?? 0) >= 0;
  const deltaBad = tone === "danger" && isUp;
  const deltaColor = deltaBad || (tone === "danger" && (change ?? 0) > 0) ? "var(--danger)" : "var(--secondary)";

  return (
    <div
      className="card card-hover fade-up"
      style={{ padding: 20, animationDelay: `${delay * 1000}ms`, cursor: onClick ? "pointer" : "default" }}
      onClick={onClick}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: iconBg,
            color,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon size={18} />
        </div>
        {change !== undefined && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11.5,
              fontWeight: 600,
              color: deltaColor,
              padding: "3px 8px",
              borderRadius: 999,
              background: `color-mix(in srgb, ${deltaColor} 12%, transparent)`,
            }}
          >
            {isUp ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            <span className="font-mono">
              {isUp ? "+" : ""}
              {change}%
            </span>
          </div>
        )}
      </div>
      <div
        style={{
          fontSize: 12.5,
          color: "var(--text-2)",
          fontWeight: 500,
          letterSpacing: "0.02em",
        }}
      >
        {title}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 10,
          marginTop: 4,
        }}
      >
        <div
          className="font-display font-mono"
          style={{
            fontSize: 32,
            fontWeight: 700,
            letterSpacing: "-0.02em",
            lineHeight: 1.1,
          }}
        >
          <CountUp
            end={value}
            duration={1.2}
            delay={delay}
            separator=" "
            formattingFn={format === "compact" ? formatNumber : undefined}
          />
        </div>
        {spark && <SparkLine data={spark} color={color} />}
      </div>
      {subtitle && (
        <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--text-2)" }}>{subtitle}</div>
      )}
      {changeLabel && change !== undefined && (
        <div style={{ marginTop: 4, fontSize: 11, color: "var(--text-2)" }}>{changeLabel}</div>
      )}
    </div>
  );
}
