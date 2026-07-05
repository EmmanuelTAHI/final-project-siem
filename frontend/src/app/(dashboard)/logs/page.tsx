"use client";

import { useState, useMemo, useEffect, useCallback, Fragment } from "react";
import {
  Search,
  Download,
  RefreshCw,
  SlidersHorizontal,
  X,
  ChevronDown,
  ChevronUp,
  Zap,
} from "lucide-react";
import { useLogs } from "@/hooks/use-logs";
import { formatNumber, formatDate } from "@/lib/utils";
import { FlagBadge } from "@/components/common/country-flag";
import { IpLink } from "@/components/common/ip-link";
import type { NormalizedLog } from "@/types";

type View = "table" | "json" | "raw";

const levelLabel: Record<NormalizedLog["severity"], string> = {
  critical: "CRIT",
  high: "HIGH",
  medium: "MED",
  low: "LOW",
  info: "INFO",
};

const levelColor: Record<NormalizedLog["severity"], string> = {
  critical: "var(--danger)",
  high: "var(--danger)",
  medium: "var(--warning)",
  low: "var(--info)",
  info: "var(--info)",
};

const severityBg: Record<NormalizedLog["severity"], string> = {
  critical: "color-mix(in srgb, var(--danger) 14%, transparent)",
  high: "color-mix(in srgb, var(--danger) 10%, transparent)",
  medium: "color-mix(in srgb, var(--warning) 12%, transparent)",
  low: "color-mix(in srgb, var(--info) 10%, transparent)",
  info: "color-mix(in srgb, var(--info) 10%, transparent)",
};

function JSONPretty({ data }: { data: unknown }) {
  const render = (v: unknown, indent = 0): React.ReactNode => {
    const pad = "  ".repeat(indent);
    if (v === null) return <span style={{ color: "#6b7280" }}>null</span>;
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
    if (typeof v === "object") {
      const keys = Object.keys(v as object);
      return (
        <>
          {"{"}
          <br />
          {keys.map((k, i) => (
            <span key={k}>
              {pad}  <span style={{ color: "var(--primary)" }}>&quot;{k}&quot;</span>:{" "}
              {render((v as Record<string, unknown>)[k], indent + 1)}
              {i < keys.length - 1 ? "," : ""}
              <br />
            </span>
          ))}
          {pad}
          {"}"}
        </>
      );
    }
    return <span>{String(v)}</span>;
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
      }}
    >
      {render(data)}
    </pre>
  );
}

interface ActiveFilter {
  key: string;
  label: string;
  value: string;
}

export default function LogsPage() {
  /* ── View state ─────────────────────────────────────────────── */
  const [view, setView] = useState<View>("table");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [liveMode, setLiveMode] = useState(false);

  /* ── Filter state ───────────────────────────────────────────── */
  const [rawSearch, setRawSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [severities, setSeverities] = useState<NormalizedLog["severity"][]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [filterUser, setFilterUser] = useState("");
  const [filterIP, setFilterIP] = useState("");

  /* ── Debounce search 300ms ──────────────────────────────────── */
  useEffect(() => {
    const t = setTimeout(() => setAppliedSearch(rawSearch), 300);
    return () => clearTimeout(t);
  }, [rawSearch]);

  /* ── API fetch ──────────────────────────────────────────────── */
  const { data: logsData, refetch, isFetching } = useLogs({
    severity: severities.length === 1 ? severities[0] : undefined,
  });

  /* ── Live mode auto-refresh ─────────────────────────────────── */
  useEffect(() => {
    if (!liveMode) return;
    const interval = setInterval(() => refetch(), 30_000);
    return () => clearInterval(interval);
  }, [liveMode, refetch]);

  /* ── Client-side filtering ──────────────────────────────────── */
  const filtered = useMemo(() => {
    let logs = logsData?.results ?? [];

    if (appliedSearch) {
      const q = appliedSearch.toLowerCase();
      logs = logs.filter(
        (l) =>
          l.action?.toLowerCase().includes(q) ||
          l.user_email?.toLowerCase().includes(q) ||
          l.source_ip?.includes(q) ||
          l.source_type?.toLowerCase().includes(q)
      );
    }

    if (severities.length > 0) {
      logs = logs.filter((l) => severities.includes(l.severity));
    }

    if (filterSource) {
      const s = filterSource.toLowerCase();
      logs = logs.filter((l) => l.source_type?.toLowerCase().includes(s));
    }

    if (filterAction) {
      const a = filterAction.toLowerCase();
      logs = logs.filter((l) => l.action?.toLowerCase().includes(a));
    }

    if (filterUser) {
      const u = filterUser.toLowerCase();
      logs = logs.filter((l) => l.user_email?.toLowerCase().includes(u));
    }

    if (filterIP) {
      logs = logs.filter((l) => l.source_ip?.includes(filterIP));
    }

    if (dateFrom) {
      const from = new Date(dateFrom).getTime();
      logs = logs.filter((l) => new Date(l.timestamp).getTime() >= from);
    }

    if (dateTo) {
      const to = new Date(dateTo).getTime();
      logs = logs.filter((l) => new Date(l.timestamp).getTime() <= to);
    }

    return logs;
  }, [logsData, appliedSearch, severities, filterSource, filterAction, filterUser, filterIP, dateFrom, dateTo]);

  /* ── Active filter chips ────────────────────────────────────── */
  const activeFilters = useMemo<ActiveFilter[]>(() => {
    const f: ActiveFilter[] = [];
    if (appliedSearch) f.push({ key: "search", label: "Recherche", value: appliedSearch });
    severities.forEach((s) => f.push({ key: `sev:${s}`, label: "Sévérité", value: s.toUpperCase() }));
    if (filterSource) f.push({ key: "source", label: "Source", value: filterSource });
    if (filterAction) f.push({ key: "action", label: "Action", value: filterAction });
    if (filterUser) f.push({ key: "user", label: "Utilisateur", value: filterUser });
    if (filterIP) f.push({ key: "ip", label: "IP", value: filterIP });
    if (dateFrom) f.push({ key: "from", label: "Depuis", value: dateFrom.replace("T", " ") });
    if (dateTo) f.push({ key: "to", label: "Jusqu'à", value: dateTo.replace("T", " ") });
    return f;
  }, [appliedSearch, severities, filterSource, filterAction, filterUser, filterIP, dateFrom, dateTo]);

  const clearFilter = useCallback((key: string) => {
    if (key === "search") { setRawSearch(""); setAppliedSearch(""); }
    else if (key.startsWith("sev:")) {
      const sv = key.replace("sev:", "") as NormalizedLog["severity"];
      setSeverities((prev) => prev.filter((x) => x !== sv));
    }
    else if (key === "source") setFilterSource("");
    else if (key === "action") setFilterAction("");
    else if (key === "user") setFilterUser("");
    else if (key === "ip") setFilterIP("");
    else if (key === "from") setDateFrom("");
    else if (key === "to") setDateTo("");
  }, []);

  const clearAll = useCallback(() => {
    setRawSearch("");
    setAppliedSearch("");
    setSeverities([]);
    setFilterSource("");
    setFilterAction("");
    setFilterUser("");
    setFilterIP("");
    setDateFrom("");
    setDateTo("");
  }, []);

  const toggleSeverity = (s: NormalizedLog["severity"]) => {
    setSeverities((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  /* ── Field stats (right sidebar) ────────────────────────────── */
  const allLogs = logsData?.results ?? [];
  const fieldStats = useMemo(() => {
    const collect = (key: keyof NormalizedLog): [string, number][] => {
      const counts = new Map<string, number>();
      allLogs.forEach((l) => {
        const v = l[key];
        if (typeof v === "string") counts.set(v, (counts.get(v) ?? 0) + 1);
      });
      return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
    };
    return [
      { field: "source_type", label: "Source", values: collect("source_type") },
      { field: "severity", label: "Sévérité", values: collect("severity") },
      { field: "action", label: "Action", values: collect("action") },
    ];
  }, [allLogs]);

  const advancedFilterCount = [filterSource, filterAction, filterUser, filterIP, dateFrom, dateTo].filter(Boolean).length;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Événements &amp; logs
          </div>
          <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3, display: "flex", alignItems: "center", gap: 6 }}>
            <span className="font-mono" style={{ color: "var(--text)", fontWeight: 600 }}>
              {formatNumber(filtered.length)}
            </span>
            {" "}résultats
            {isFetching && (
              <span style={{ color: "var(--primary)", fontSize: 11 }}>· actualisation…</span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            className={liveMode ? "btn btn-primary" : "btn"}
            onClick={() => setLiveMode(!liveMode)}
            style={{ gap: 6 }}
          >
            <span
              className={`dot ${liveMode ? "live" : "off"}`}
              style={{ width: 6, height: 6, flexShrink: 0 }}
            />
            <Zap size={13} />
            Live
          </button>
          <button className="btn" onClick={() => refetch()}>
            <RefreshCw size={14} />
          </button>
          <button className="btn">
            <Download size={14} />
            Exporter
          </button>
        </div>
      </div>

      {/* ── Filter panel ────────────────────────────────────────── */}
      <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 11 }}>

        {/* Row 1 : Search input */}
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ flex: 1, position: "relative" }}>
            <Search
              size={15}
              style={{
                position: "absolute",
                top: "50%",
                left: 12,
                transform: "translateY(-50%)",
                color: "var(--primary)",
                pointerEvents: "none",
              }}
            />
            <input
              className="input font-mono"
              value={rawSearch}
              onChange={(e) => setRawSearch(e.target.value)}
              placeholder="Recherche en temps réel : action, utilisateur, IP, source…"
              style={{ paddingLeft: 36, fontSize: 13 }}
            />
            {rawSearch !== appliedSearch && (
              <div
                style={{
                  position: "absolute",
                  top: "50%",
                  right: 12,
                  transform: "translateY(-50%)",
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  border: "2px solid var(--primary)",
                  borderTopColor: "transparent",
                  animation: "spin 0.7s linear infinite",
                }}
              />
            )}
          </div>
          <button
            className="btn"
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              gap: 6,
              color: showAdvanced || advancedFilterCount > 0 ? "var(--primary)" : undefined,
              borderColor: advancedFilterCount > 0 ? "var(--primary)" : undefined,
              whiteSpace: "nowrap",
            }}
          >
            <SlidersHorizontal size={14} />
            Avancé
            {advancedFilterCount > 0 && (
              <span
                style={{
                  background: "var(--primary)",
                  color: "white",
                  fontSize: 10,
                  fontWeight: 700,
                  padding: "1px 5px",
                  borderRadius: 999,
                  lineHeight: "14px",
                }}
              >
                {advancedFilterCount}
              </span>
            )}
            {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>

        {/* Row 2 : Severity quick-pills */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", flexShrink: 0 }}>
            Sévérité
          </span>
          <button
            className={`pill ${severities.length === 0 ? "active" : ""}`}
            onClick={() => setSeverities([])}
            style={{ fontSize: 11 }}
          >
            Tous
          </button>
          {(["high", "medium", "low"] as NormalizedLog["severity"][]).map((s) => (
            <button
              key={s}
              onClick={() => toggleSeverity(s)}
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                border: `1px solid ${severities.includes(s) ? levelColor[s] : "var(--border)"}`,
                background: severities.includes(s) ? severityBg[s] : "transparent",
                color: severities.includes(s) ? levelColor[s] : "var(--text-2)",
                fontSize: 11,
                fontWeight: severities.includes(s) ? 700 : 500,
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                letterSpacing: "0.04em",
                transition: "all 140ms ease",
              }}
            >
              {levelLabel[s]}
            </button>
          ))}
        </div>

        {/* Row 3 : Advanced filters (expandable) */}
        {showAdvanced && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
              gap: 12,
              paddingTop: 12,
              borderTop: "1px solid var(--border)",
            }}
          >
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Date début
              </label>
              <input
                type="datetime-local"
                className="input font-mono"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                style={{ fontSize: 12 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Date fin
              </label>
              <input
                type="datetime-local"
                className="input font-mono"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                style={{ fontSize: 12 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Source
              </label>
              <input
                className="input font-mono"
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value)}
                placeholder="ex: wazuh, syslog…"
                style={{ fontSize: 12 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Action / Événement
              </label>
              <input
                className="input font-mono"
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
                placeholder="ex: login, deny…"
                style={{ fontSize: 12 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Utilisateur
              </label>
              <input
                className="input font-mono"
                value={filterUser}
                onChange={(e) => setFilterUser(e.target.value)}
                placeholder="email ou identifiant…"
                style={{ fontSize: 12 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Adresse IP
              </label>
              <input
                className="input font-mono"
                value={filterIP}
                onChange={(e) => setFilterIP(e.target.value)}
                placeholder="ex: 192.168.1…"
                style={{ fontSize: 12 }}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Active filter chips ──────────────────────────────────── */}
      {activeFilters.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", flexShrink: 0 }}>
            Actifs :
          </span>
          {activeFilters.map((f) => (
            <span
              key={f.key}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 9px",
                background: "color-mix(in srgb, var(--primary) 11%, transparent)",
                border: "1px solid color-mix(in srgb, var(--primary) 28%, transparent)",
                borderRadius: 999,
                fontSize: 11,
                color: "var(--primary)",
                fontFamily: "var(--font-mono)",
              }}
            >
              <span style={{ opacity: 0.65, fontSize: 10, fontFamily: "var(--font-ui)" }}>{f.label}:</span>
              {f.value}
              <button
                onClick={() => clearFilter(f.key)}
                style={{
                  border: "none",
                  background: "none",
                  cursor: "pointer",
                  padding: 0,
                  color: "currentColor",
                  display: "flex",
                  alignItems: "center",
                  opacity: 0.55,
                  lineHeight: 1,
                }}
              >
                <X size={11} />
              </button>
            </span>
          ))}
          <button
            onClick={clearAll}
            style={{
              fontSize: 11,
              color: "var(--text-2)",
              background: "none",
              border: "1px solid var(--border)",
              borderRadius: 999,
              padding: "3px 9px",
              cursor: "pointer",
              transition: "color 140ms ease, border-color 140ms ease",
            }}
          >
            Tout effacer
          </button>
        </div>
      )}

      {/* ── Histogram ───────────────────────────────────────────── */}
      <div className="card" style={{ padding: "14px 18px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", gap: 16, fontSize: 11.5, color: "var(--text-2)", alignItems: "center" }}>
            <span className="font-display" style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
              Distribution temporelle
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 8, height: 8, background: "var(--primary)", borderRadius: 2, opacity: 0.5, display: "inline-block" }} />
              Événements
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 8, height: 8, background: "var(--danger)", borderRadius: 2, display: "inline-block" }} />
              Pics
            </div>
          </div>
          <span style={{ fontSize: 11, color: "var(--text-2)", fontFamily: "var(--font-mono)" }}>
            fenêtres 20 min
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 60 }}>
          {Array.from({ length: 72 }).map((_, i) => {
            const v = 0.3 + Math.abs(Math.sin(i * 0.4)) * 0.5 + Math.abs(Math.sin(i * 1.7)) * 0.15;
            const peak = i % 14 === 0;
            return (
              <div
                key={i}
                title={`Bin ${i}`}
                style={{
                  flex: 1,
                  height: `${v * 100}%`,
                  background: peak ? "var(--danger)" : "var(--primary)",
                  opacity: peak ? 0.85 : 0.45,
                  borderRadius: 2,
                  cursor: "pointer",
                  transition: "opacity 140ms ease",
                }}
              />
            );
          })}
        </div>
      </div>

      {/* ── Log viewer + Field stats ─────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) 240px",
          gap: 14,
        }}
      >
        {/* Main log card */}
        <div className="card" style={{ overflow: "hidden", minWidth: 0 }}>
          {/* Toolbar */}
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 3,
                padding: 3,
                background: "color-mix(in srgb, var(--text) 5%, transparent)",
                borderRadius: 9,
              }}
            >
              {(["table", "json", "raw"] as View[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  style={{
                    padding: "5px 12px",
                    borderRadius: 6,
                    border: "none",
                    cursor: "pointer",
                    fontSize: 12,
                    fontWeight: 500,
                    background: view === v ? "var(--surface)" : "transparent",
                    color: view === v ? "var(--text)" : "var(--text-2)",
                    boxShadow:
                      view === v
                        ? "0 2px 6px -2px color-mix(in srgb, var(--text) 16%, transparent)"
                        : "none",
                    textTransform: "capitalize",
                    transition: "all 140ms ease",
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <div className="font-mono" style={{ fontSize: 11, color: "var(--text-2)" }}>
              {formatNumber(filtered.length)} lignes
            </div>
          </div>

          {/* Table view */}
          {view === "table" && (
            <div style={{ maxHeight: 540, overflow: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: 160 }}>Timestamp</th>
                    <th style={{ width: 72 }}>Level</th>
                    <th style={{ width: 120 }}>Source</th>
                    <th style={{ width: 160 }}>Action</th>
                    <th style={{ width: 190 }}>Utilisateur</th>
                    <th>IP / Pays</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 100).map((e) => (
                    <Fragment key={e.id}>
                      <tr
                        onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                        style={{ cursor: "pointer" }}
                      >
                        <td className="font-mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>
                          {formatDate(e.timestamp, "dd/MM HH:mm:ss")}
                        </td>
                        <td>
                          <span
                            className="font-mono"
                            style={{
                              fontSize: 10.5,
                              fontWeight: 700,
                              color: levelColor[e.severity],
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: severityBg[e.severity],
                            }}
                          >
                            {levelLabel[e.severity]}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.source_type}</td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.action}</td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.user_email || "—"}</td>
                        <td style={{ fontSize: 11.5 }}>
                          <div className="flex items-center gap-2">
                            <IpLink ip={e.source_ip} className="text-[11.5px]" />
                            {e.geo_country_code && (
                              <FlagBadge code={e.geo_country_code} label={e.geo_country_code} />
                            )}
                          </div>
                        </td>
                      </tr>
                      {expanded === e.id && (
                        <tr>
                          <td
                            colSpan={6}
                            style={{
                              padding: 14,
                              background: "color-mix(in srgb, var(--bg) 40%, var(--surface))",
                            }}
                          >
                            <JSONPretty data={e} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        style={{ textAlign: "center", padding: "32px 0", color: "var(--text-2)" }}
                      >
                        Aucun événement ne correspond aux filtres actifs.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {view === "json" && (
            <div style={{ padding: 14, maxHeight: 540, overflow: "auto" }}>
              <JSONPretty data={filtered.slice(0, 6)} />
            </div>
          )}

          {view === "raw" && (
            <pre
              className="font-mono"
              style={{
                margin: 0,
                padding: 14,
                fontSize: 11.5,
                lineHeight: 1.6,
                maxHeight: 540,
                overflow: "auto",
              }}
            >
              {filtered.slice(0, 100).map((e) => (
                <div key={e.id}>
                  <span style={{ color: "var(--text-2)" }}>[{formatDate(e.timestamp, "dd/MM HH:mm:ss")}]</span>{" "}
                  <span style={{ color: levelColor[e.severity], fontWeight: 700 }}>
                    {levelLabel[e.severity].padEnd(5)}
                  </span>{" "}
                  <span style={{ color: "var(--primary)" }}>{e.source_type}</span>{" "}
                  <span>{e.action}</span>{" "}
                  <span style={{ color: "var(--text-2)" }}>user={e.user_email || "-"}</span>{" "}
                  ip={e.source_ip}
                </div>
              ))}
            </pre>
          )}
        </div>

        {/* Field stats sidebar */}
        <div className="card" style={{ padding: 14, alignSelf: "flex-start" }}>
          <div
            className="font-display"
            style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 14, color: "var(--text)" }}
          >
            Champs disponibles
          </div>
          {fieldStats.map((fs) => (
            <div key={fs.field} style={{ marginBottom: 18 }}>
              <div
                style={{
                  fontSize: 10.5,
                  color: "var(--primary)",
                  fontWeight: 700,
                  marginBottom: 7,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {fs.label}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                {fs.values.map(([v, c]) => {
                  const pct = allLogs.length > 0 ? (c / allLogs.length) * 100 : 0;
                  return (
                    <div
                      key={v}
                      style={{
                        position: "relative",
                        padding: "4px 7px",
                        borderRadius: 5,
                        cursor: "pointer",
                        overflow: "hidden",
                      }}
                      onClick={() => {
                        if (fs.field === "source_type") setFilterSource(v);
                        else if (fs.field === "action") setFilterAction(v);
                        else if (fs.field === "severity") toggleSeverity(v as NormalizedLog["severity"]);
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          inset: 0,
                          background: "color-mix(in srgb, var(--primary) 8%, transparent)",
                          width: `${pct}%`,
                          borderRadius: 5,
                        }}
                      />
                      <div style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                        <span
                          className="font-mono"
                          style={{
                            fontSize: 11,
                            color: "var(--text)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {v}
                        </span>
                        <span className="font-mono" style={{ fontSize: 10.5, color: "var(--text-2)", flexShrink: 0 }}>
                          {formatNumber(c)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <style jsx>{`
        @keyframes spin {
          to { transform: translateY(-50%) rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
