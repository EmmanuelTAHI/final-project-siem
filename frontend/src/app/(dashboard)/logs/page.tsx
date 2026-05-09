"use client";

import { useState, useMemo, Fragment } from "react";
import { Search, Download, RefreshCw, Play } from "lucide-react";
import { useLogs } from "@/hooks/use-logs";
import { formatNumber, formatDate } from "@/lib/utils";
import { FlagBadge } from "@/components/common/country-flag";
import type { NormalizedLog } from "@/types";

type View = "table" | "json" | "raw";
type LevelFilter = "all" | NormalizedLog["severity"];

const levelLabel: Record<NormalizedLog["severity"], string> = {
  info: "INFO",
  warning: "WARN",
  error: "ERROR",
  critical: "CRIT",
};

const levelColor: Record<NormalizedLog["severity"], string> = {
  critical: "var(--danger)",
  error: "var(--danger)",
  warning: "var(--warning)",
  info: "var(--info)",
};

const suggestions = [
  "source:wazuh AND level:>7",
  "source:firewall AND action:deny",
  "level:ERROR AND host:SRV-*",
  "user:admin AND event_id:4625",
  'message:"powershell" AND NOT user:SYSTEM',
];

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

export default function LogsPage() {
  const [query, setQuery] = useState("source:wazuh AND level:>7");
  const [view, setView] = useState<View>("table");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");

  const { data: logsData, refetch } = useLogs({
    severity: levelFilter !== "all" ? levelFilter : undefined,
  });
  const allLogs = logsData?.results ?? [];
  const filtered = useMemo(
    () => (levelFilter === "all" ? allLogs : allLogs.filter((e) => e.severity === levelFilter)),
    [allLogs, levelFilter]
  );

  const fieldStats = useMemo(() => {
    const collect = (key: keyof NormalizedLog): [string, number][] => {
      const counts = new Map<string, number>();
      allLogs.forEach((l) => {
        const v = l[key];
        if (typeof v === "string") counts.set(v, (counts.get(v) ?? 0) + 1);
      });
      return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
    };
    return [
      { field: "source_type", values: collect("source_type") },
      { field: "severity", values: collect("severity") },
      { field: "action", values: collect("action") },
    ];
  }, [allLogs]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
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
          <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Événements &amp; logs bruts
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2 }}>
            <span className="font-mono" style={{ color: "var(--text)", fontWeight: 600 }}>
              {formatNumber(logsData?.count ?? allLogs.length)}
            </span>{" "}
            événements chargés
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn">
            <Download size={14} />
            Exporter
          </button>
          <button className="btn" onClick={() => refetch()}>
            <RefreshCw size={14} />
            Rafraîchir
          </button>
        </div>
      </div>

      {/* KQL search */}
      <div className="card" style={{ padding: 14 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <div style={{ flex: 1, position: "relative", minWidth: 260 }}>
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
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{
                paddingLeft: 36,
                fontSize: 13,
                borderColor: "var(--primary)",
                boxShadow: "0 0 0 3px var(--glow)",
              }}
              placeholder="ex: source:wazuh AND level:>7"
            />
          </div>
          <button className="btn btn-primary">
            <Play size={13} />
            Exécuter
          </button>
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            marginTop: 10,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: "var(--text-2)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Exemples
          </span>
          {suggestions.map((s) => (
            <button
              key={s}
              className="pill font-mono"
              onClick={() => setQuery(s)}
              style={{ fontSize: 11.5 }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Histogram (simple bars) */}
      <div className="card" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <div>
            <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
              Distribution temporelle
            </div>
            <div style={{ fontSize: 11.5, color: "var(--text-2)" }}>
              Cliquer sur un bin pour zoomer · fenêtres de 20 min
            </div>
          </div>
          <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--text-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 10, height: 10, background: "var(--primary)", borderRadius: 2, opacity: 0.5 }} />
              Événements
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 10, height: 10, background: "var(--danger)", borderRadius: 2 }} />
              Pics d&apos;erreurs
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 80 }}>
          {Array.from({ length: 72 }).map((_, i) => {
            const v = 0.3 + Math.abs(Math.sin(i * 0.4)) * 0.5 + Math.abs(Math.sin(i * 1.7)) * 0.15;
            const peak = i % 14 === 0;
            return (
              <div
                key={i}
                style={{
                  flex: 1,
                  height: `${v * 100}%`,
                  background: peak ? "var(--danger)" : "var(--primary)",
                  opacity: peak ? 0.85 : 0.5,
                  borderRadius: 2,
                }}
              />
            );
          })}
        </div>
      </div>

      {/* View toggle + log grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) 260px",
          gap: 16,
        }}
      >
        <div className="card" style={{ overflow: "hidden", minWidth: 0 }}>
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 4,
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
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
            <div style={{ width: 1, height: 22, background: "var(--border)" }} />
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {(["all", "critical", "error", "warning", "info"] as LevelFilter[]).map((l) => (
                <button
                  key={l}
                  className={`pill ${levelFilter === l ? "active" : ""}`}
                  onClick={() => setLevelFilter(l)}
                  style={{ fontSize: 11 }}
                >
                  {l === "all" ? "Tous" : levelLabel[l]}
                </button>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <div className="font-mono" style={{ fontSize: 11, color: "var(--text-2)" }}>
              {formatNumber(filtered.length)} lignes
            </div>
          </div>

          {view === "table" && (
            <div style={{ maxHeight: 540, overflow: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: 170 }}>Timestamp</th>
                    <th style={{ width: 80 }}>Level</th>
                    <th style={{ width: 130 }}>Source</th>
                    <th style={{ width: 150 }}>Action</th>
                    <th style={{ width: 200 }}>Utilisateur</th>
                    <th>IP / Pays</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 80).map((e) => (
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
                            style={{ fontSize: 11, fontWeight: 700, color: levelColor[e.severity] }}
                          >
                            {levelLabel[e.severity]}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.source_type}</td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.action}</td>
                        <td className="font-mono" style={{ fontSize: 11.5 }}>{e.user_email || "—"}</td>
                        <td style={{ fontSize: 11.5 }}>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-muted-foreground">{e.source_ip || "—"}</span>
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
              {filtered.slice(0, 80).map((e) => (
                <div key={e.id}>
                  <span style={{ color: "var(--text-2)" }}>[{formatDate(e.timestamp, "dd/MM HH:mm:ss")}]</span>{" "}
                  <span style={{ color: levelColor[e.severity], fontWeight: 700 }}>
                    {levelLabel[e.severity].padEnd(5)}
                  </span>{" "}
                  <span style={{ color: "var(--primary)" }}>{e.source_type}</span>{" "}
                  <span>{e.action}</span>{" "}
                  <span style={{ color: "var(--text-2)" }}>user={e.user_email || "-"}</span>{" "}
                  — ip={e.source_ip}
                </div>
              ))}
            </pre>
          )}
        </div>

        {/* Fields sidebar */}
        <div className="card" style={{ padding: 14, alignSelf: "flex-start" }}>
          <div className="font-display" style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>
            Champs disponibles
          </div>
          {fieldStats.map((fs) => (
            <div key={fs.field} style={{ marginBottom: 16 }}>
              <div
                className="font-mono"
                style={{ fontSize: 11, color: "var(--primary)", fontWeight: 600, marginBottom: 6 }}
              >
                {fs.field}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {fs.values.map(([v, c]) => (
                  <div
                    key={v}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      fontSize: 11.5,
                      cursor: "pointer",
                      padding: "3px 6px",
                      borderRadius: 4,
                    }}
                  >
                    <span className="font-mono" style={{ color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {v}
                    </span>
                    <span className="font-mono" style={{ color: "var(--text-2)" }}>
                      {formatNumber(c)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
