"use client";

import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { ShieldAlert, Activity, Server, Gauge, RefreshCw, Download } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { SeverityCards } from "@/components/dashboard/severity-summary-cards";
import { AlertsTimelineChart } from "@/components/dashboard/alerts-timeline-chart";
import { SeverityDonut } from "@/components/dashboard/severity-donut";
import { TopThreatsChart } from "@/components/dashboard/top-threats-chart";
import { CardGridSkeleton, ChartSkeleton } from "@/components/common/loading-skeleton";
import { useDashboardSummary, useTopThreats, useGeoMap } from "@/hooks/use-dashboard";
import { useConnectors } from "@/hooks/use-collectors";
import { formatDate, formatNumber } from "@/lib/utils";
import type { Connector } from "@/types";

const GeoMapLeaflet = dynamic(
  () => import("@/components/dashboard/geo-map-leaflet").then((m) => m.GeoMapLeaflet),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

function StatusDot({ kind }: { kind: "live" | "warn" | "off" }) {
  return <span className={`dot ${kind}`} />;
}

function SourcesList({ connectors }: { connectors: Connector[] }) {
  if (!connectors.length) {
    return <div style={{ fontSize: 12, color: "var(--text-2)", padding: "12px 0" }}>Aucun connecteur configuré</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {connectors.map((c, i) => {
        const kind = c.status === "inactive" || c.status === "error" ? "off"
          : c.last_job_status === "failed" ? "warn" : "live";
        return (
          <div
            key={c.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "9px 4px",
              borderBottom: i < connectors.length - 1 ? "1px solid var(--border)" : "none",
            }}
          >
            <StatusDot kind={kind} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500 }}>{c.display_name || c.name}</div>
              <div className="font-mono" style={{ fontSize: 10.5, color: "var(--text-2)" }}>
                {c.status === "inactive" ? "— hors ligne —" : `${formatNumber(c.logs_collected_24h)} evt/24h`}
              </div>
            </div>
            {kind === "warn" && (
              <span className="badge badge-high" style={{ fontSize: 9.5 }}>Dégradé</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useDashboardSummary();
  const { data: threats, isLoading: threatsLoading } = useTopThreats();
  const { data: connectors = [] } = useConnectors();
  const { data: geoData, isLoading: geoLoading } = useGeoMap();

  const s = summary ?? { open_alerts: 0, open_alerts_change: 0, logs_24h: 0, logs_24h_change: 0, active_connectors: 0, total_connectors: 0, ml_anomalies_24h: 0, ml_anomalies_change: 0, critical_alerts: 0, high_alerts: 0, medium_alerts: 0, low_alerts: 0 };
  const topThreats = threats ?? [];
  const connectorList = Array.isArray(connectors) ? connectors : [];
  const geoPoints = Array.isArray(geoData) ? geoData : [];

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Page header */}
      <div className="fade-up" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Tableau de bord SOC
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2, display: "flex", alignItems: "center", gap: 8 }}>
            <span className="dot live" />
            Vue d&apos;ensemble temps réel · dernière mise à jour {formatDate(new Date(), "HH:mm:ss")}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => refetchSummary()}>
            <RefreshCw size={14} />
            Actualiser
          </button>
          <button className="btn btn-primary">
            <Download size={14} />
            Exporter
          </button>
        </div>
      </div>

      {/* Severity breakdown */}
      <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Alertes ouvertes par criticité
        </div>
        {summaryLoading ? <CardGridSkeleton count={4} /> : <SeverityCards data={s} />}
      </div>

      {/* General KPIs */}
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

      {/* Severity breakdown / Active sources / Top threats — equal-height row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        {summaryLoading ? <ChartSkeleton height="h-auto" /> : <SeverityDonut data={s} />}

        <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column" }}>
          <div className="font-display" style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>
            Sources de logs actives
          </div>
          <SourcesList connectors={connectorList} />
        </div>

        {threatsLoading ? <ChartSkeleton /> : <TopThreatsChart data={topThreats} />}
      </div>

      {/* Geo distribution — full width */}
      <div className="card" style={{ padding: 20 }}>
        <div style={{ marginBottom: 16 }}>
          <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>Origine géographique</div>
          <div style={{ fontSize: 12, color: "var(--text-2)" }}>Répartition des événements par pays</div>
        </div>
        {geoLoading ? <ChartSkeleton /> : <GeoMapLeaflet data={geoPoints} height="320px" />}
      </div>
    </div>
  );
}
