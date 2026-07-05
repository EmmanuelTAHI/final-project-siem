"use client";

import { useState } from "react";
import {
  Search,
  Download,
  Plus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Server,
  User,
  Globe,
  Eye,
  Check,
  XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useAlerts, useAlertStats, useUpdateAlert, useAddAlertComment } from "@/hooks/use-alerts";
import { useDebounce } from "@/hooks/use-debounce";
import { useRealtimeStore } from "@/stores/realtime-store";
import { formatDate, formatNumber, severityHex } from "@/lib/utils";
import type { Alert } from "@/types";
import toast from "react-hot-toast";

const PAGE_SIZE = 25;

function LiveChip() {
  const connected = useRealtimeStore((s) => s.connected);
  return (
    <span
      className="chip"
      title={connected ? "Flux WebSocket actif — les alertes apparaissent en direct" : "Flux temps réel interrompu — repli sur rafraîchissement périodique"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11,
        color: connected ? "var(--success, #06D6A0)" : "var(--warning, #F59E0B)",
        borderColor: "color-mix(in srgb, currentColor 35%, transparent)",
      }}
    >
      <span className={`dot ${connected ? "live" : ""}`} style={{ width: 7, height: 7, background: "currentColor" }} />
      {connected ? "Temps réel" : "Reconnexion…"}
    </span>
  );
}

const sevPills: { id: "all" | Alert["severity"]; label: string }[] = [
  { id: "all", label: "Toutes" },
  { id: "critical", label: "Critique" },
  { id: "high", label: "Élevée" },
  { id: "medium", label: "Moyenne" },
  { id: "low", label: "Faible" },
];

const statusPills: { id: "all" | Alert["status"]; label: string }[] = [
  { id: "all", label: "Tous" },
  { id: "open", label: "Nouveau" },
  { id: "in_progress", label: "En cours" },
  { id: "resolved", label: "Résolu" },
  { id: "false_positive", label: "Faux positif" },
];

function SeverityBadge({ sev }: { sev: Alert["severity"] }) {
  const label = sev === "critical" ? "Critique" : sev === "high" ? "Élevé" : sev === "medium" ? "Moyen" : "Faible";
  const cls = sev === "critical" ? "badge-crit" : sev === "high" ? "badge-high" : sev === "medium" ? "badge-med" : "badge-low";
  return <span className={`badge ${cls}`} style={{ color: severityHex[sev] }}>{label}</span>;
}

function StatusBadge({ status }: { status: Alert["status"] }) {
  const map: Record<Alert["status"], { cls: string; label: string }> = {
    open: { cls: "badge-crit", label: "Nouveau" },
    in_progress: { cls: "badge-high", label: "En cours" },
    resolved: { cls: "badge-ok", label: "Résolu" },
    false_positive: { cls: "badge-info", label: "Faux positif" },
  };
  const m = map[status];
  return <span className={`badge ${m.cls}`}>{m.label}</span>;
}

function Row({ k, v, mono, wrap }: { k: string; v: React.ReactNode; mono?: boolean; wrap?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: wrap ? "flex-start" : "center" }}>
      <div style={{ width: 130, color: "var(--text-2)", flexShrink: 0 }}>{k}</div>
      <div className={mono ? "font-mono" : ""} style={{ flex: 1, fontSize: mono ? 12 : 12.5, wordBreak: wrap ? "break-all" : "normal" }}>
        {v}
      </div>
    </div>
  );
}

function JSONPretty({ data }: { data: unknown }) {
  const render = (v: unknown, indent = 0): React.ReactNode => {
    const pad = "  ".repeat(indent);
    if (v === null || v === undefined) return <span style={{ color: "#6b7280" }}>null</span>;
    if (typeof v === "string") return <span style={{ color: "var(--secondary)" }}>&quot;{v}&quot;</span>;
    if (typeof v === "number") return <span style={{ color: "var(--warning)" }}>{v}</span>;
    if (typeof v === "boolean") return <span style={{ color: "var(--primary)" }}>{String(v)}</span>;
    if (Array.isArray(v)) {
      return (
        <>
          [<br />
          {v.map((x, i) => (
            <span key={i}>
              {pad}  {render(x, indent + 1)}
              {i < v.length - 1 ? "," : ""}
              <br />
            </span>
          ))}
          {pad}]
        </>
      );
    }
    const keys = Object.keys(v as object);
    return (
      <>
        {"{"}
        <br />
        {keys.map((k, i) => (
          <span key={k}>
            {pad}  <span style={{ color: "var(--primary)" }}>&quot;{k}&quot;</span>: {render((v as Record<string, unknown>)[k], indent + 1)}
            {i < keys.length - 1 ? "," : ""}
            <br />
          </span>
        ))}
        {pad}
        {"}"}
      </>
    );
  };
  return (
    <pre
      className="font-mono"
      style={{
        margin: 0,
        fontSize: 12,
        lineHeight: 1.55,
        padding: 14,
        background: "color-mix(in srgb, var(--text) 4%, transparent)",
        borderRadius: 10,
        overflow: "auto",
        border: "1px solid var(--border)",
        maxHeight: 400,
      }}
    >
      {render(data)}
    </pre>
  );
}

function AlertCard({
  alert,
  expanded,
  isNew,
  onToggle,
  onSetStatus,
  onComment,
}: {
  alert: Alert;
  expanded: boolean;
  isNew: boolean;
  onToggle: () => void;
  onSetStatus: (status: Alert["status"]) => void;
  onComment: (content: string) => void;
}) {
  const isCrit = alert.severity === "critical";
  const [comment, setComment] = useState("");
  return (
    <div
      className={`card ${isCrit ? "crit-glow" : ""} ${isNew ? "alert-live-in" : ""}`}
      style={{
        padding: 0,
        overflow: "hidden",
        borderLeft: isCrit ? undefined : `3px solid ${severityHex[alert.severity]}`,
      }}
    >
      <div
        role="button"
        tabIndex={0}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter") onToggle();
        }}
        style={{ padding: 14, display: "flex", alignItems: "center", gap: 14, cursor: "pointer", flexWrap: "wrap" }}
      >
        <SeverityBadge sev={alert.severity} />
        <span className="font-mono" style={{ fontSize: 12, color: "var(--text-2)", minWidth: 140 }}>
          {formatDate(alert.created_at, "dd/MM HH:mm:ss")}
        </span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
            {alert.rule_name}
            <span className="badge badge-info font-mono" style={{ fontSize: 10 }}>
              R-{alert.rule_id}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3, display: "flex", gap: 14, flexWrap: "wrap" }}>
            {alert.source_ip && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                <Globe size={11} />
                <span className="font-mono">{alert.source_ip}</span>
              </span>
            )}
            {alert.user_email && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                <User size={11} />
                {alert.user_email}
              </span>
            )}
            {alert.destination_ip && (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                <Server size={11} />
                <span className="font-mono">{alert.destination_ip}</span>
              </span>
            )}
            <span className="font-mono" style={{ color: "var(--primary)" }}>
              ×{alert.event_count}
            </span>
          </div>
        </div>
        {alert.mitre_tactic && (
          <span
            style={{
              fontSize: 11,
              color: "var(--text-2)",
              background: "color-mix(in srgb, var(--text) 6%, transparent)",
              padding: "3px 8px",
              borderRadius: 999,
            }}
          >
            {alert.mitre_tactic}
          </span>
        )}
        <StatusBadge status={alert.status} />
        <div onClick={(e) => e.stopPropagation()} style={{ display: "flex", gap: 4 }}>
          <button
            className="btn btn-ghost"
            style={{ padding: 6 }}
            title="Prendre en charge"
            disabled={alert.status !== "open"}
            onClick={() => onSetStatus("in_progress")}
          >
            <Check size={15} />
          </button>
          <button className="btn btn-ghost" style={{ padding: 6 }} title="Détails" onClick={onToggle}>
            <Eye size={15} />
          </button>
        </div>
        <ChevronDown
          size={16}
          style={{
            color: "var(--text-2)",
            transform: expanded ? "rotate(180deg)" : "rotate(0)",
            transition: "transform 220ms",
          }}
        />
      </div>
      {expanded && (
        <div
          className="fade-up"
          style={{
            borderTop: "1px solid var(--border)",
            padding: 18,
            background: "color-mix(in srgb, var(--bg) 40%, var(--surface))",
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20 }}>
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--text-2)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: 10,
                }}
              >
                Détails techniques
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12.5 }}>
                {alert.mitre_tactic && <Row k="MITRE tactic" v={alert.mitre_tactic} />}
                {alert.mitre_technique && <Row k="Technique" v={alert.mitre_technique} mono />}
                <Row k="Alert ID" v={`#${alert.id}`} mono />
                <Row k="Events" v={alert.event_count} mono />
                <Row k="Source IP" v={alert.source_ip || "—"} mono />
                {alert.destination_ip && <Row k="Destination" v={alert.destination_ip} mono />}
                {alert.user_email && <Row k="Utilisateur" v={alert.user_email} mono />}
                {alert.assigned_to_name && <Row k="Assigné à" v={alert.assigned_to_name} />}
                <Row k="Description" v={alert.description} wrap />
              </div>
              <div style={{ marginTop: 16 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-2)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: 8,
                  }}
                >
                  Commentaire
                </div>
                <textarea
                  className="input"
                  rows={2}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Ajouter une note d'investigation…"
                  style={{ resize: "vertical", width: "100%" }}
                />
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                  {comment.trim() && (
                    <button
                      className="btn"
                      onClick={() => {
                        onComment(comment.trim());
                        setComment("");
                      }}
                    >
                      Commenter
                    </button>
                  )}
                  <button
                    className="btn"
                    disabled={alert.status === "false_positive"}
                    onClick={() => onSetStatus("false_positive")}
                  >
                    Marquer faux positif
                  </button>
                  <button
                    className="btn btn-primary"
                    disabled={alert.status === "resolved"}
                    onClick={() => onSetStatus("resolved")}
                  >
                    Acquitter &amp; résoudre
                  </button>
                </div>
              </div>
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--text-2)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: 10,
                }}
              >
                Événement brut
              </div>
              <JSONPretty
                data={
                  alert.log_sources?.[0]?.raw_data ?? {
                    id: alert.id,
                    rule: alert.rule_name,
                    severity: alert.severity,
                    source_ip: alert.source_ip,
                    user: alert.user_email,
                    event_count: alert.event_count,
                    created_at: alert.created_at,
                  }
                }
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AlertsPage() {
  const router = useRouter();
  const [sevFilter, setSevFilter] = useState<"all" | Alert["severity"]>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | Alert["status"]>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("date");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  // Recherche instantanée : la requête part 250 ms après la dernière frappe,
  // et keepPreviousData évite tout flash de liste vide pendant le refetch.
  const debouncedSearch = useDebounce(search, 250);

  const { data: alertsData, isFetching } = useAlerts({
    severity: sevFilter !== "all" ? sevFilter : undefined,
    status: statusFilter !== "all" ? statusFilter : undefined,
    search: debouncedSearch || undefined,
    page,
    page_size: PAGE_SIZE,
  });
  const localAlerts = alertsData?.results ?? [];
  const totalCount = alertsData?.count ?? localAlerts.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const { data: statsData } = useAlertStats();
  const updateAlert = useUpdateAlert();
  const addComment = useAddAlertComment();
  const recentAlertIds = useRealtimeStore((s) => s.recentAlertIds);

  const toggle = (id: number) => {
    const s = new Set(expanded);
    if (s.has(id)) s.delete(id);
    else s.add(id);
    setExpanded(s);
  };

  const setStatus = (alert: Alert, status: Alert["status"]) => {
    const labels: Record<Alert["status"], string> = {
      open: "Nouveau",
      in_progress: "En cours",
      resolved: "Résolu",
      false_positive: "Faux positif",
    };
    updateAlert.mutate(
      { id: alert.id, updates: { status } },
      { onSuccess: () => toast.success(`Statut mis à jour : ${labels[status]}`) }
    );
  };

  const filtered = [...localAlerts].sort((a, b) => {
    if (sort === "sev") {
      const order: Record<Alert["severity"], number> = { critical: 0, high: 1, medium: 2, low: 3 };
      return order[a.severity] - order[b.severity];
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const clearFilters = () => {
    setSearch("");
    setSevFilter("all");
    setStatusFilter("all");
    setPage(1);
  };

  const changeFilter = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(1);
  };

  const bulkExport = () => {
    if (!filtered.length) {
      toast.error("Aucune alerte à exporter");
      return;
    }
    const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const header = ["id", "date", "severite", "statut", "regle", "titre", "source_ip", "utilisateur", "evenements"];
    const rows = filtered.map((a) =>
      [a.id, a.created_at, a.severity, a.status, a.rule_name, a.title, a.source_ip, a.user_email, a.event_count]
        .map(esc)
        .join(",")
    );
    const csv = [header.join(","), ...rows].join("\n");
    const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `alertes_logplus_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success(`${filtered.length} alertes exportées`);
  };

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: 12 }}>
            Gestion des alertes
            <LiveChip />
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2 }}>
            <span className="font-mono" style={{ color: "var(--text)", fontWeight: 600 }}>
              {formatNumber(filtered.length)}
            </span>{" "}
            alertes affichées sur <span className="font-mono">{formatNumber(totalCount)}</span>
            {(statsData as { total_open?: number } | undefined)?.total_open !== undefined && (
              <> · <span className="font-mono" style={{ color: "var(--danger, #EF4444)" }}>{formatNumber((statsData as unknown as { total_open: number }).total_open)}</span> ouvertes</>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={bulkExport}>
            <Download size={14} />
            Exporter CSV
          </button>
          <button
            className="btn btn-primary"
            onClick={() => router.push("/correlation?new=1")}
          >
            <Plus size={14} />
            Créer règle
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div
        className="card"
        style={{ padding: 14, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}
      >
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--text-2)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginRight: 4,
            }}
          >
            Sévérité
          </span>
          {sevPills.map((s) => (
            <button
              key={s.id}
              className={`pill ${sevFilter === s.id ? "active" : ""}`}
              onClick={() => changeFilter(setSevFilter)(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div style={{ width: 1, height: 22, background: "var(--border)" }} />
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--text-2)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginRight: 4,
            }}
          >
            Statut
          </span>
          {statusPills.map((s) => (
            <button
              key={s.id}
              className={`pill ${statusFilter === s.id ? "active" : ""}`}
              onClick={() => changeFilter(setStatusFilter)(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, minWidth: 180 }} />
        <div style={{ position: "relative", minWidth: 240, flex: "0 1 auto" }}>
          <Search
            size={14}
            style={{
              position: "absolute",
              top: "50%",
              left: 10,
              transform: "translateY(-50%)",
              color: "var(--text-2)",
              pointerEvents: "none",
            }}
          />
          <input
            className="input"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Recherche instantanée : titre, description…"
            style={{ paddingLeft: 32 }}
          />
          {isFetching && (
            <span
              className="dot live"
              style={{ position: "absolute", top: "50%", right: 10, transform: "translateY(-50%)", width: 6, height: 6 }}
            />
          )}
        </div>
        <select
          className="input"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ width: 180 }}
        >
          <option value="date">Tri : Date ↓</option>
          <option value="sev">Tri : Sévérité</option>
        </select>
        {(search || sevFilter !== "all" || statusFilter !== "all") && (
          <button className="btn btn-ghost" onClick={clearFilters} style={{ padding: "6px 10px" }}>
            <XCircle size={13} />
            Effacer
          </button>
        )}
      </div>

      {/* List */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {filtered.map((a) => (
          <AlertCard
            key={a.id}
            alert={a}
            expanded={expanded.has(a.id)}
            isNew={recentAlertIds.has(String(a.id))}
            onToggle={() => toggle(a.id)}
            onSetStatus={(status) => setStatus(a, status)}
            onComment={(content) => addComment.mutate({ id: a.id, content })}
          />
        ))}
        {filtered.length === 0 && (
          <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-2)" }}>
            Aucune alerte ne correspond aux filtres.
          </div>
        )}
      </div>

      {/* Pagination */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: 4,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>
          Affichage {totalCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{(page - 1) * PAGE_SIZE + filtered.length} de{" "}
          <span className="font-mono">{formatNumber(totalCount)}</span> alertes
        </div>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <button
            className="pill"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            style={{ opacity: page <= 1 ? 0.4 : 1, display: "inline-flex", alignItems: "center", gap: 3 }}
          >
            <ChevronLeft size={13} /> Préc.
          </button>
          <span className="font-mono" style={{ fontSize: 12.5, color: "var(--text-2)", padding: "0 8px" }}>
            {page} / {totalPages}
          </span>
          <button
            className="pill"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            style={{ opacity: page >= totalPages ? 0.4 : 1, display: "inline-flex", alignItems: "center", gap: 3 }}
          >
            Suiv. <ChevronRight size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
