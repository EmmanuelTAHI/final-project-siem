"use client";

import { useState, useMemo, useEffect, useCallback, Fragment, useRef } from "react";
import {
  Search,
  Download,
  RefreshCw,
  SlidersHorizontal,
  X,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Zap,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { useLogs, useLogHistogram } from "@/hooks/use-logs";
import { formatNumber, formatDate } from "@/lib/utils";
import { parseLogSearch } from "@/lib/log-search";
import { FlagBadge } from "@/components/common/country-flag";
import { IpLink } from "@/components/common/ip-link";
import { LogHistogram } from "@/components/logs/log-histogram";
import { logsApi } from "@/lib/api";
import type { NormalizedLog, LogFacetField } from "@/types";
import toast from "react-hot-toast";

type View = "table" | "json" | "raw";
type RangePreset = "15m" | "1h" | "6h" | "24h" | "7d" | "30d" | "custom";

const RANGE_PRESETS: { key: RangePreset; label: string; seconds: number }[] = [
  { key: "15m", label: "15 min", seconds: 15 * 60 },
  { key: "1h", label: "1 h", seconds: 3600 },
  { key: "6h", label: "6 h", seconds: 6 * 3600 },
  { key: "24h", label: "24 h", seconds: 86400 },
  { key: "7d", label: "7 j", seconds: 7 * 86400 },
  { key: "30d", label: "30 j", seconds: 30 * 86400 },
];

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

const FACET_LABELS: Record<LogFacetField, string> = {
  source_type: "Source",
  severity: "Sévérité",
  action: "Action",
  user_email: "Utilisateur",
  source_ip: "IP source",
  geo_country: "Pays",
  outcome: "Résultat",
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

function rangeToISO(preset: RangePreset, customFrom: string, customTo: string, tick: number): { from: string; to: string } {
  void tick; // force la recomputation de "now" à chaque tick (refresh manuel / live)
  const now = new Date();
  if (preset === "custom") {
    return {
      from: customFrom ? new Date(customFrom).toISOString() : "",
      to: customTo ? new Date(customTo).toISOString() : "",
    };
  }
  const p = RANGE_PRESETS.find((r) => r.key === preset) ?? RANGE_PRESETS[3];
  return { from: new Date(now.getTime() - p.seconds * 1000).toISOString(), to: now.toISOString() };
}

function toDatetimeLocal(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function LogsPage() {
  /* ── View state ─────────────────────────────────────────────── */
  const [view, setView] = useState<View>("table");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [liveMode, setLiveMode] = useState(false);
  const [nowTick, setNowTick] = useState(0);
  const [exporting, setExporting] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  /* ── Time range ─────────────────────────────────────────────── */
  const [rangePreset, setRangePreset] = useState<RangePreset>("24h");
  const [lastNonCustomPreset, setLastNonCustomPreset] = useState<RangePreset>("24h");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const range = useMemo(
    () => rangeToISO(rangePreset, customFrom, customTo, nowTick),
    [rangePreset, customFrom, customTo, nowTick]
  );

  /* ── Filter state ───────────────────────────────────────────── */
  const [rawSearch, setRawSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [severities, setSeverities] = useState<NormalizedLog["severity"][]>([]);
  const [outcomes, setOutcomes] = useState<string[]>([]);
  const [filterSource, setFilterSource] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [filterUser, setFilterUser] = useState("");
  const [filterIP, setFilterIP] = useState("");
  const [filterCountry, setFilterCountry] = useState("");
  const [ordering, setOrdering] = useState("-event_time");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  /* ── Debounce search 300ms, puis parse champ:valeur ──────────── */
  useEffect(() => {
    const t = setTimeout(() => setAppliedSearch(rawSearch), 300);
    return () => clearTimeout(t);
  }, [rawSearch]);

  const parsed = useMemo(() => parseLogSearch(appliedSearch), [appliedSearch]);

  // Les tokens champ:valeur tapés dans la barre de recherche s'ajoutent aux
  // filtres structurés (pills, panneau avancé) — comme dans Splunk, taper
  // `severity:critical` équivaut à cliquer la pastille correspondante.
  useEffect(() => {
    if (parsed.severity.length > 0) {
      setSeverities((prev) => Array.from(new Set([...prev, ...(parsed.severity as NormalizedLog["severity"][])])));
    }
    if (parsed.outcome.length > 0) {
      setOutcomes((prev) => Array.from(new Set([...prev, ...parsed.outcome])));
    }
    if (parsed.source_type) setFilterSource(parsed.source_type);
    if (parsed.action) setFilterAction(parsed.action);
    if (parsed.user_email) setFilterUser(parsed.user_email);
    if (parsed.source_ip) setFilterIP(parsed.source_ip);
    if (parsed.geo_country) setFilterCountry(parsed.geo_country);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedSearch]);

  /* ── Reset pagination quand les filtres/la plage changent ────── */
  useEffect(() => {
    setPage(1);
  }, [parsed.freeText, severities, outcomes, filterSource, filterAction, filterUser, filterIP, filterCountry, range.from, range.to, ordering]);

  /* ── Raccourci clavier "/" pour focus la recherche (Splunk-like) ─ */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  /* ── Paramètres effectifs envoyés au backend ─────────────────── */
  const queryParams = useMemo(
    () => ({
      search: parsed.freeText || undefined,
      severity: severities.length > 0 ? severities : undefined,
      outcome: outcomes.length > 0 ? outcomes : undefined,
      source_type: filterSource || undefined,
      action: filterAction || undefined,
      user_email: filterUser || undefined,
      source_ip: filterIP || undefined,
      geo_country: filterCountry || undefined,
      event_time_from: range.from || undefined,
      event_time_to: range.to || undefined,
      ordering,
    }),
    [parsed.freeText, severities, outcomes, filterSource, filterAction, filterUser, filterIP, filterCountry, range, ordering]
  );

  /* ── API fetch : résultats paginés + histogramme/facettes ────── */
  const { data: logsData, refetch, isFetching } = useLogs({ ...queryParams, page, page_size: pageSize });
  const { data: histogramData, isFetching: histogramFetching } = useLogHistogram(queryParams);

  /* ── Live mode : re-tick la plage + refetch toutes les 15s ────── */
  useEffect(() => {
    if (!liveMode) return;
    const interval = setInterval(() => {
      setNowTick((t) => t + 1);
      refetch();
    }, 15_000);
    return () => clearInterval(interval);
  }, [liveMode, refetch]);

  const results = logsData?.results ?? [];
  const totalResults = logsData?.count ?? histogramData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));

  /* ── Zoom histogramme (sélection par glisser) ────────────────── */
  const handleHistogramZoom = useCallback((from: Date, to: Date) => {
    setCustomFrom(toDatetimeLocal(from.toISOString()));
    setCustomTo(toDatetimeLocal(to.toISOString()));
    setRangePreset("custom");
  }, []);

  const handleRangePresetClick = (p: RangePreset) => {
    setRangePreset(p);
    setLastNonCustomPreset(p);
  };

  const resetZoom = () => setRangePreset(lastNonCustomPreset);

  /* ── Active filter chips ────────────────────────────────────── */
  const activeFilters = useMemo<ActiveFilter[]>(() => {
    const f: ActiveFilter[] = [];
    if (parsed.freeText) f.push({ key: "search", label: "Recherche", value: parsed.freeText });
    severities.forEach((s) => f.push({ key: `sev:${s}`, label: "Sévérité", value: s.toUpperCase() }));
    outcomes.forEach((o) => f.push({ key: `out:${o}`, label: "Résultat", value: o }));
    if (filterSource) f.push({ key: "source", label: "Source", value: filterSource });
    if (filterAction) f.push({ key: "action", label: "Action", value: filterAction });
    if (filterUser) f.push({ key: "user", label: "Utilisateur", value: filterUser });
    if (filterIP) f.push({ key: "ip", label: "IP", value: filterIP });
    if (filterCountry) f.push({ key: "country", label: "Pays", value: filterCountry });
    return f;
  }, [parsed.freeText, severities, outcomes, filterSource, filterAction, filterUser, filterIP, filterCountry]);

  const clearFilter = useCallback(
    (key: string) => {
      if (key === "search") {
        setRawSearch("");
        setAppliedSearch("");
      } else if (key.startsWith("sev:")) {
        const sv = key.replace("sev:", "") as NormalizedLog["severity"];
        setSeverities((prev) => prev.filter((x) => x !== sv));
      } else if (key.startsWith("out:")) {
        const ov = key.replace("out:", "");
        setOutcomes((prev) => prev.filter((x) => x !== ov));
      } else if (key === "source") setFilterSource("");
      else if (key === "action") setFilterAction("");
      else if (key === "user") setFilterUser("");
      else if (key === "ip") setFilterIP("");
      else if (key === "country") setFilterCountry("");
    },
    []
  );

  const clearAll = useCallback(() => {
    setRawSearch("");
    setAppliedSearch("");
    setSeverities([]);
    setOutcomes([]);
    setFilterSource("");
    setFilterAction("");
    setFilterUser("");
    setFilterIP("");
    setFilterCountry("");
  }, []);

  const toggleSeverity = (s: NormalizedLog["severity"]) => {
    setSeverities((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  /* ── Clic sur une facette (sidebar) ───────────────────────────── */
  const handleFacetClick = (field: LogFacetField, value: string) => {
    if (field === "severity") toggleSeverity(value as NormalizedLog["severity"]);
    else if (field === "outcome") setOutcomes((prev) => (prev.includes(value) ? prev.filter((x) => x !== value) : [...prev, value]));
    else if (field === "source_type") setFilterSource(value);
    else if (field === "action") setFilterAction(value);
    else if (field === "user_email") setFilterUser(value);
    else if (field === "source_ip") setFilterIP(value);
    else if (field === "geo_country") setFilterCountry(value);
  };

  const advancedFilterCount = [filterSource, filterAction, filterUser, filterIP, filterCountry].filter(Boolean).length + outcomes.length;

  const toggleOrdering = (field: "event_time" | "severity") => {
    setOrdering((prev) => (prev === `-${field}` ? field : `-${field}`));
  };

  /* ── Export CSV (respecte les filtres actifs) ────────────────── */
  const handleExport = async () => {
    setExporting(true);
    const t = toast.loading("Préparation de l'export…");
    try {
      const page1 = await logsApi.getLogs({ ...queryParams, page: 1, page_size: 1000 });
      if (page1.results.length === 0) {
        toast.error("Aucun résultat à exporter avec les filtres actifs.", { id: t });
        return;
      }
      const headers = ["timestamp", "severity", "source_type", "action", "outcome", "user_email", "source_ip", "geo_country", "resource"];
      const rows = page1.results.map((l) =>
        headers
          .map((h) => {
            const v = (l as unknown as Record<string, unknown>)[h] ?? "";
            const s = String(v).replace(/"/g, '""');
            return `"${s}"`;
          })
          .join(",")
      );
      const csv = [headers.join(","), ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `logs_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      const truncated = page1.count > page1.results.length;
      toast.success(
        truncated
          ? `${formatNumber(page1.results.length)} lignes exportées (sur ${formatNumber(page1.count)} au total — limite d'export à 1000 lignes, affinez les filtres pour le reste).`
          : `${formatNumber(page1.results.length)} lignes exportées.`,
        { id: t, duration: 5000 }
      );
    } catch {
      toast.error("Erreur lors de l'export.", { id: t });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="page" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Événements &amp; logs
          </div>
          <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3, display: "flex", alignItems: "center", gap: 6 }}>
            <span className="font-mono" style={{ color: "var(--text)", fontWeight: 600 }}>
              {formatNumber(totalResults)}
            </span>{" "}
            résultats
            {(isFetching || histogramFetching) && <span style={{ color: "var(--primary)", fontSize: 11 }}>· actualisation…</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className={liveMode ? "btn btn-primary" : "btn"} onClick={() => setLiveMode(!liveMode)} style={{ gap: 6 }} title="Rafraîchit automatiquement toutes les 15s">
            <span className={`dot ${liveMode ? "live" : "off"}`} style={{ width: 6, height: 6, flexShrink: 0 }} />
            <Zap size={13} />
            Live
          </button>
          <button className="btn" onClick={() => { setNowTick((t) => t + 1); refetch(); }} title="Actualiser">
            <RefreshCw size={14} />
          </button>
          <button className="btn" onClick={handleExport} disabled={exporting} title="Exporter les résultats filtrés en CSV">
            <Download size={14} />
            {exporting ? "Export…" : "Exporter"}
          </button>
        </div>
      </div>

      {/* ── Filter panel ────────────────────────────────────────── */}
      <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 11 }}>
        {/* Row 1 : Search input + time range */}
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240, position: "relative" }}>
            <Search size={15} style={{ position: "absolute", top: "50%", left: 12, transform: "translateY(-50%)", color: "var(--primary)", pointerEvents: "none" }} />
            <input
              ref={searchInputRef}
              className="input font-mono"
              value={rawSearch}
              onChange={(e) => setRawSearch(e.target.value)}
              placeholder='Recherche : severity:critical source:wazuh user:ana… ("/" pour focus)'
              style={{ paddingLeft: 36, fontSize: 13 }}
            />
            {rawSearch !== appliedSearch && (
              <div
                style={{
                  position: "absolute", top: "50%", right: 12, transform: "translateY(-50%)",
                  width: 14, height: 14, borderRadius: "50%", border: "2px solid var(--primary)",
                  borderTopColor: "transparent", animation: "spin-centered 0.7s linear infinite",
                }}
              />
            )}
          </div>

          {/* Time range presets */}
          <div style={{ display: "flex", gap: 3, padding: 3, background: "color-mix(in srgb, var(--text) 5%, transparent)", borderRadius: 9 }}>
            {RANGE_PRESETS.map((p) => (
              <button
                key={p.key}
                onClick={() => handleRangePresetClick(p.key)}
                className="font-mono"
                style={{
                  padding: "5px 10px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 11.5, fontWeight: 600,
                  background: rangePreset === p.key ? "var(--surface)" : "transparent",
                  color: rangePreset === p.key ? "var(--primary)" : "var(--text-2)",
                  boxShadow: rangePreset === p.key ? "0 2px 6px -2px color-mix(in srgb, var(--text) 16%, transparent)" : "none",
                  transition: "all 140ms ease",
                }}
              >
                {p.label}
              </button>
            ))}
            <button
              onClick={() => setRangePreset("custom")}
              className="font-mono"
              style={{
                padding: "5px 10px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 11.5, fontWeight: 600,
                background: rangePreset === "custom" ? "var(--surface)" : "transparent",
                color: rangePreset === "custom" ? "var(--primary)" : "var(--text-2)",
                boxShadow: rangePreset === "custom" ? "0 2px 6px -2px color-mix(in srgb, var(--text) 16%, transparent)" : "none",
              }}
            >
              Personnalisé
            </button>
          </div>

          <button
            className="btn"
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{ gap: 6, color: showAdvanced || advancedFilterCount > 0 ? "var(--primary)" : undefined, borderColor: advancedFilterCount > 0 ? "var(--primary)" : undefined, whiteSpace: "nowrap" }}
          >
            <SlidersHorizontal size={14} />
            Avancé
            {advancedFilterCount > 0 && (
              <span style={{ background: "var(--primary)", color: "white", fontSize: 10, fontWeight: 700, padding: "1px 5px", borderRadius: 999, lineHeight: "14px" }}>
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
          <button className={`pill ${severities.length === 0 ? "active" : ""}`} onClick={() => setSeverities([])} style={{ fontSize: 11 }}>
            Tous
          </button>
          {(["critical", "high", "medium", "low", "info"] as NormalizedLog["severity"][]).map((s) => (
            <button
              key={s}
              onClick={() => toggleSeverity(s)}
              style={{
                padding: "4px 10px", borderRadius: 999, border: `1px solid ${severities.includes(s) ? levelColor[s] : "var(--border)"}`,
                background: severities.includes(s) ? severityBg[s] : "transparent",
                color: severities.includes(s) ? levelColor[s] : "var(--text-2)",
                fontSize: 11, fontWeight: severities.includes(s) ? 700 : 500, cursor: "pointer",
                fontFamily: "var(--font-mono)", letterSpacing: "0.04em", transition: "all 140ms ease",
              }}
            >
              {levelLabel[s]}
            </button>
          ))}
        </div>

        {/* Row 3 : Advanced filters (expandable) */}
        {showAdvanced && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 12, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
            {rangePreset === "custom" && (
              <>
                <div>
                  <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                    Date début
                  </label>
                  <input type="datetime-local" className="input font-mono" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} style={{ fontSize: 12 }} />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                    Date fin
                  </label>
                  <input type="datetime-local" className="input font-mono" value={customTo} onChange={(e) => setCustomTo(e.target.value)} style={{ fontSize: 12 }} />
                </div>
              </>
            )}
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Source
              </label>
              <input className="input font-mono" value={filterSource} onChange={(e) => setFilterSource(e.target.value)} placeholder="ex: wazuh, syslog…" style={{ fontSize: 12 }} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Action / Événement
              </label>
              <input className="input font-mono" value={filterAction} onChange={(e) => setFilterAction(e.target.value)} placeholder="ex: login, deny…" style={{ fontSize: 12 }} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Utilisateur
              </label>
              <input className="input font-mono" value={filterUser} onChange={(e) => setFilterUser(e.target.value)} placeholder="email ou identifiant…" style={{ fontSize: 12 }} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Adresse IP
              </label>
              <input className="input font-mono" value={filterIP} onChange={(e) => setFilterIP(e.target.value)} placeholder="ex: 192.168.1…" style={{ fontSize: 12 }} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-2)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5, display: "block" }}>
                Pays
              </label>
              <input className="input font-mono" value={filterCountry} onChange={(e) => setFilterCountry(e.target.value)} placeholder="ex: FR, CI…" style={{ fontSize: 12 }} />
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
                display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 9px",
                background: "color-mix(in srgb, var(--primary) 11%, transparent)",
                border: "1px solid color-mix(in srgb, var(--primary) 28%, transparent)",
                borderRadius: 999, fontSize: 11, color: "var(--primary)", fontFamily: "var(--font-mono)",
              }}
            >
              <span style={{ opacity: 0.65, fontSize: 10, fontFamily: "var(--font-ui)" }}>{f.label}:</span>
              {f.value}
              <button onClick={() => clearFilter(f.key)} style={{ border: "none", background: "none", cursor: "pointer", padding: 0, color: "currentColor", display: "flex", alignItems: "center", opacity: 0.55, lineHeight: 1 }}>
                <X size={11} />
              </button>
            </span>
          ))}
          <button
            onClick={clearAll}
            style={{ fontSize: 11, color: "var(--text-2)", background: "none", border: "1px solid var(--border)", borderRadius: 999, padding: "3px 9px", cursor: "pointer", transition: "color 140ms ease, border-color 140ms ease" }}
          >
            Tout effacer
          </button>
        </div>
      )}

      {/* ── Histogram ───────────────────────────────────────────── */}
      <LogHistogram
        data={histogramData}
        loading={histogramFetching}
        onZoom={handleHistogramZoom}
        zoomed={rangePreset === "custom"}
        onResetZoom={resetZoom}
      />

      {/* ── Log viewer + Field stats ─────────────────────────────── */}
      <div className="split-aside" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 240px", gap: 14 }}>
        {/* Main log card */}
        <div className="card" style={{ overflow: "hidden", minWidth: 0 }}>
          {/* Toolbar */}
          <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 3, padding: 3, background: "color-mix(in srgb, var(--text) 5%, transparent)", borderRadius: 9 }}>
              {(["table", "json", "raw"] as View[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  style={{
                    padding: "5px 12px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 500,
                    background: view === v ? "var(--surface)" : "transparent", color: view === v ? "var(--text)" : "var(--text-2)",
                    boxShadow: view === v ? "0 2px 6px -2px color-mix(in srgb, var(--text) 16%, transparent)" : "none",
                    textTransform: "capitalize", transition: "all 140ms ease",
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <div className="font-mono" style={{ fontSize: 11, color: "var(--text-2)" }}>
              {totalResults > 0 ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, totalResults)} sur ${formatNumber(totalResults)}` : "0 ligne"}
            </div>
          </div>

          {/* Table view */}
          {view === "table" && (
            <div className="tbl-scroll" style={{ maxHeight: 540, overflow: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: 160, cursor: "pointer" }} onClick={() => toggleOrdering("event_time")}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        Timestamp
                        {ordering === "-event_time" ? <ArrowDown size={11} /> : ordering === "event_time" ? <ArrowUp size={11} /> : null}
                      </span>
                    </th>
                    <th style={{ width: 72, cursor: "pointer" }} onClick={() => toggleOrdering("severity")}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        Level
                        {ordering === "-severity" ? <ArrowDown size={11} /> : ordering === "severity" ? <ArrowUp size={11} /> : null}
                      </span>
                    </th>
                    <th style={{ width: 120 }}>Source</th>
                    <th style={{ width: 160 }}>Action</th>
                    <th style={{ width: 190 }}>Utilisateur</th>
                    <th>IP / Pays</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((e) => (
                    <Fragment key={e.id}>
                      <tr onClick={() => setExpanded(expanded === e.id ? null : e.id)} style={{ cursor: "pointer" }}>
                        <td className="font-mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>
                          {formatDate(e.timestamp, "dd/MM HH:mm:ss")}
                        </td>
                        <td>
                          <span className="font-mono" style={{ fontSize: 10.5, fontWeight: 700, color: levelColor[e.severity], padding: "2px 6px", borderRadius: 4, background: severityBg[e.severity] }}>
                            {levelLabel[e.severity]}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.source_type}</td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.action}</td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.user_email || "—"}</td>
                        <td style={{ fontSize: 11.5 }}>
                          <div className="flex items-center gap-2">
                            <IpLink ip={e.source_ip} className="text-[11.5px]" />
                            {e.geo_country_code && <FlagBadge code={e.geo_country_code} label={e.geo_country_code} />}
                          </div>
                        </td>
                      </tr>
                      {expanded === e.id && (
                        <tr>
                          <td colSpan={6} style={{ padding: 14, background: "color-mix(in srgb, var(--bg) 40%, var(--surface))" }}>
                            <JSONPretty data={e} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                  {results.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", padding: "32px 0", color: "var(--text-2)" }}>
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
              <JSONPretty data={results.slice(0, 6)} />
            </div>
          )}

          {view === "raw" && (
            <pre className="font-mono" style={{ margin: 0, padding: 14, fontSize: 11.5, lineHeight: 1.6, maxHeight: 540, overflow: "auto" }}>
              {results.map((e) => (
                <div key={e.id}>
                  <span style={{ color: "var(--text-2)" }}>[{formatDate(e.timestamp, "dd/MM HH:mm:ss")}]</span>{" "}
                  <span style={{ color: levelColor[e.severity], fontWeight: 700 }}>{levelLabel[e.severity].padEnd(5)}</span>{" "}
                  <span style={{ color: "var(--primary)" }}>{e.source_type}</span> <span>{e.action}</span>{" "}
                  <span style={{ color: "var(--text-2)" }}>user={e.user_email || "-"}</span> ip={e.source_ip}
                </div>
              ))}
            </pre>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "10px 14px", borderTop: "1px solid var(--border)" }}>
              <button className="btn" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} style={{ padding: "5px 8px" }}>
                <ChevronLeft size={14} />
              </button>
              <span className="font-mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>
                Page {page} / {formatNumber(totalPages)}
              </span>
              <button className="btn" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} style={{ padding: "5px 8px" }}>
                <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>

        {/* Field stats sidebar — facettes réelles agrégées côté serveur */}
        <div className="card" style={{ padding: 14, alignSelf: "flex-start" }}>
          <div className="font-display" style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 14, color: "var(--text)" }}>
            Champs disponibles
          </div>
          {(["source_type", "severity", "action", "user_email", "source_ip", "geo_country", "outcome"] as LogFacetField[]).map((field) => {
            const values = histogramData?.facets?.[field] ?? [];
            if (values.length === 0) return null;
            const maxCount = Math.max(1, ...values.map((v) => v.count));
            return (
              <div key={field} style={{ marginBottom: 18 }}>
                <div style={{ fontSize: 10.5, color: "var(--primary)", fontWeight: 700, marginBottom: 7, textTransform: "uppercase", letterSpacing: "0.06em", fontFamily: "var(--font-mono)" }}>
                  {FACET_LABELS[field]}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  {values.map((fv) => {
                    const pct = (fv.count / maxCount) * 100;
                    return (
                      <div
                        key={fv.value}
                        style={{ position: "relative", padding: "4px 7px", borderRadius: 5, cursor: "pointer", overflow: "hidden" }}
                        onClick={() => handleFacetClick(field, fv.value)}
                      >
                        <div style={{ position: "absolute", inset: 0, background: "color-mix(in srgb, var(--primary) 8%, transparent)", width: `${pct}%`, borderRadius: 5 }} />
                        <div style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                          <span className="font-mono" style={{ fontSize: 11, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {fv.value}
                          </span>
                          <span className="font-mono" style={{ fontSize: 10.5, color: "var(--text-2)", flexShrink: 0 }}>
                            {formatNumber(fv.count)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
          {!histogramData && (
            <div style={{ fontSize: 11.5, color: "var(--text-2)" }}>Chargement…</div>
          )}
        </div>
      </div>
    </div>
  );
}
