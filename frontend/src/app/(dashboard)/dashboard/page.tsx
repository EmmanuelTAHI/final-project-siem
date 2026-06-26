"use client";

import { useRouter } from "next/navigation";
import { ShieldAlert, Activity, Server, Gauge, RefreshCw, Download } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { AlertsTimelineChart } from "@/components/dashboard/alerts-timeline-chart";
import { SeverityDonut } from "@/components/dashboard/severity-donut";
import { TopThreatsChart } from "@/components/dashboard/top-threats-chart";
import { CardGridSkeleton, ChartSkeleton } from "@/components/common/loading-skeleton";
import { useDashboardSummary, useTopThreats } from "@/hooks/use-dashboard";
import { formatDate } from "@/lib/utils";

export default function DashboardPage() {
  const router = useRouter();
  const { data: summary, isLoading: summaryLoading, refetch } = useDashboardSummary();
  const { data: threats, isLoading: threatsLoading } = useTopThreats();

  const s = summary ?? {
    open_alerts: 0,
    open_alerts_change: 0,
    logs_24h: 0,
    logs_24h_change: 0,
    active_connectors: 0,
    total_connectors: 0,
    ml_anomalies_24h: 0,
    ml_anomalies_change: 0,
    critical_alerts: 0,
    high_alerts: 0,
    medium_alerts: 0,
    low_alerts: 0,
  };
  const topThreats = threats ?? [];

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header compact */}
      <div
        className="fade-up"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div
            className="font-display"
            style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}
          >
            Tableau de bord SOC
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--text-2)",
              marginTop: 3,
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span className="dot live" style={{ width: 6, height: 6 }} />
            Temps réel · {formatDate(new Date(), "HH:mm:ss")}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => refetch()}>
            <RefreshCw size={14} />
            Actualiser
          </button>
          <button className="btn btn-primary">
            <Download size={14} />
            Exporter
          </button>
        </div>
      </div>

      {/* 4 KPI cards */}
      {summaryLoading ? (
        <CardGridSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <KpiCard
            title="Alertes ouvertes"
            value={s.open_alerts}
            change={s.open_alerts_change}
            icon={ShieldAlert}
            tone="danger"
            format="number"
            delay={0}
            subtitle={`${s.critical_alerts} crit · ${s.high_alerts} high`}
            onClick={() => router.push("/alerts")}
          />
          <KpiCard
            title="Logs collectés / 24h"
            value={s.logs_24h}
            change={s.logs_24h_change}
            icon={Activity}
            tone="primary"
            format="compact"
            delay={0.06}
          />
          <KpiCard
            title="Connecteurs actifs"
            value={s.active_connectors}
            icon={Server}
            tone="secondary"
            subtitle={`sur ${s.total_connectors} configurés`}
            format="number"
            delay={0.12}
            onClick={() => router.push("/collectors")}
          />
          <KpiCard
            title="Anomalies ML / 24h"
            value={s.ml_anomalies_24h}
            change={s.ml_anomalies_change}
            icon={Gauge}
            tone="info"
            format="number"
            delay={0.18}
            onClick={() => router.push("/ml")}
          />
        </div>
      )}

      {/* Activity timeline — full width */}
      <AlertsTimelineChart />

      {/* 2-col : Severity donut + Top threats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        {summaryLoading ? <ChartSkeleton /> : <SeverityDonut data={s} />}
        {threatsLoading ? <ChartSkeleton /> : <TopThreatsChart data={topThreats} />}
      </div>
    </div>
  );
}
