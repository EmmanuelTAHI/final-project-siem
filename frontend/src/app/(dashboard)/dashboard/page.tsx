"use client";

import { useRouter } from "next/navigation";
import { ShieldAlert, Activity, Server, Gauge, RefreshCw, Download, ChevronRight } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { AlertsTimelineChart } from "@/components/dashboard/alerts-timeline-chart";
import { SeverityDonut } from "@/components/dashboard/severity-donut";
import { TopThreatsChart } from "@/components/dashboard/top-threats-chart";
import { CardGridSkeleton, ChartSkeleton } from "@/components/common/loading-skeleton";
import { useDashboardSummary, useTopThreats } from "@/hooks/use-dashboard";
import { useAlerts } from "@/hooks/use-alerts";
import { useConnectors } from "@/hooks/use-collectors";
import { formatDate, formatNumber, severityHex } from "@/lib/utils";
import type { Alert, Connector } from "@/types";

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

function statusBadge(a: Alert) {
  const map: Record<Alert["status"], { cls: string; label: string }> = {
    open: { cls: "badge badge-crit", label: "Nouveau" },
    in_progress: { cls: "badge badge-high", label: "En cours" },
    resolved: { cls: "badge badge-ok", label: "Résolu" },
    false_positive: { cls: "badge badge-info", label: "Faux positif" },
  };
  const m = map[a.status] || map.open;
  return <span className={m.cls}>{m.label}</span>;
}

function severityBadge(sev: Alert["severity"]) {
  const map: Record<Alert["severity"], string> = {
    critical: "badge badge-crit",
    high: "badge badge-high",
    medium: "badge badge-med",
    low: "badge badge-low",
  };
  return (
    <span className={map[sev]} style={{ color: severityHex[sev] }}>
      {sev === "critical" ? "Critique" : sev === "high" ? "Élevé" : sev === "medium" ? "Moyen" : "Faible"}
    </span>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useDashboardSummary();
  const { data: threats, isLoading: threatsLoading } = useTopThreats();
  const { data: alertsData } = useAlerts({ status: "open" });
  const { data: connectors = [] } = useConnectors();

  const s = summary ?? { open_alerts: 0, open_alerts_change: 0, logs_24h: 0, logs_24h_change: 0, active_connectors: 0, total_connectors: 0, ml_anomalies_24h: 0, ml_anomalies_change: 0, critical_alerts: 0, high_alerts: 0, medium_alerts: 0, low_alerts: 0 };
  const topThreats = threats ?? [];
  const recentAlerts = alertsData?.results ?? [];
  const connectorList = Array.isArray(connectors) ? connectors : [];

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Page header */}
      <div className="fade-up" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Tableau de bord SOC
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2 }}>
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

      {/* KPIs */}
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
          />
          <KpiCard
            title="Anomalies ML / 24h"
            value={s.ml_anomalies_24h}
            change={s.ml_anomalies_change}
            icon={Gauge}
            tone="info"
            format="number"
            delay={0.18}
          />
        </div>
      )}

      {/* 2fr / 1fr grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Left col */}
        <div className="xl:col-span-2" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <AlertsTimelineChart />
          {threatsLoading ? <ChartSkeleton /> : <TopThreatsChart data={topThreats} />}
        </div>

        {/* Right col */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {summaryLoading ? <ChartSkeleton height="h-auto" /> : <SeverityDonut data={s} />}

          <div className="card" style={{ padding: 20 }}>
            <div className="font-display" style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>
              Sources de logs actives
            </div>
            <SourcesList connectors={connectorList} />
          </div>
        </div>
      </div>

      {/* Last critical alerts */}
      <div className="card" style={{ overflow: "hidden" }}>
        <div
          style={{
            padding: 20,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid var(--border)",
            flexWrap: "wrap",
            gap: 8,
          }}
        >
          <div>
            <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>
              Dernières alertes critiques
            </div>
            <div style={{ fontSize: 12, color: "var(--text-2)" }}>
              Les 6 alertes les plus prioritaires non résolues
            </div>
          </div>
          <button
            className="btn btn-ghost"
            onClick={() => router.push("/alerts")}
            style={{ color: "var(--primary)" }}
          >
            Voir toutes les alertes <ChevronRight size={13} />
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 110 }}>Sévérité</th>
                <th style={{ width: 180 }}>Timestamp</th>
                <th>Règle</th>
                <th style={{ width: 140 }}>Source IP</th>
                <th style={{ width: 200 }}>Utilisateur</th>
                <th style={{ width: 110 }}>Statut</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {recentAlerts.slice(0, 6).map((a) => (
                <tr
                  key={a.id}
                  onClick={() => router.push(`/alerts/${a.id}`)}
                  style={{
                    cursor: "pointer",
                    boxShadow: a.severity === "critical" ? "inset 3px 0 0 var(--danger)" : undefined,
                  }}
                >
                  <td>{severityBadge(a.severity)}</td>
                  <td className="font-mono" style={{ fontSize: 12, color: "var(--text-2)" }}>
                    {formatDate(a.created_at, "dd/MM HH:mm:ss")}
                  </td>
                  <td style={{ fontWeight: 500 }}>{a.rule_name}</td>
                  <td className="font-mono" style={{ fontSize: 12, color: "var(--text-2)" }}>
                    {a.source_ip || "—"}
                  </td>
                  <td className="font-mono" style={{ fontSize: 12 }}>
                    {a.user_email || "—"}
                  </td>
                  <td>{statusBadge(a)}</td>
                  <td>
                    <ChevronRight size={14} style={{ color: "var(--text-2)" }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
