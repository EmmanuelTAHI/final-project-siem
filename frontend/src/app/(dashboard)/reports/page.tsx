"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Shield,
  FileText,
  AlertTriangle,
  User as UserIcon,
  Play,
  Download,
  CheckCircle2,
  Clock,
  ChevronRight,
} from "lucide-react";
import { reportsApi } from "@/lib/api";
import toast from "react-hot-toast";

type Tone = "primary" | "secondary" | "danger" | "info" | "warning";
type Period = "24h" | "7j" | "30j" | "90j";
type Format = "pdf" | "csv" | "json";

const toneVar: Record<Tone, string> = {
  primary: "var(--primary)",
  secondary: "var(--secondary)",
  danger: "var(--danger)",
  info: "var(--info)",
  warning: "var(--warning)",
};

const presets = [
  {
    id: "soc_weekly",
    title: "Rapport hebdomadaire SOC",
    desc: "Synthèse des alertes, tendances et top menaces",
    icon: Shield,
    tone: "primary" as Tone,
    framework: undefined,
    tag: "SOC",
  },
  {
    id: "iso27001",
    title: "Conformité ISO 27001",
    desc: "Contrôles A.5 à A.18 — preuves et écarts",
    icon: FileText,
    tone: "secondary" as Tone,
    framework: "iso27001",
    tag: "ISO",
  },
  {
    id: "gdpr",
    title: "Conformité RGPD",
    desc: "Traçabilité des accès aux données personnelles",
    icon: FileText,
    tone: "info" as Tone,
    framework: "gdpr",
    tag: "RGPD",
  },
  {
    id: "pci_dss",
    title: "Conformité PCI DSS",
    desc: "Surveillance des environnements de données de paiement",
    icon: FileText,
    tone: "warning" as Tone,
    framework: "pci_dss",
    tag: "PCI",
  },
  {
    id: "top_threats",
    title: "Top menaces détectées",
    desc: "Classement MITRE ATT&CK des TTPs observés",
    icon: AlertTriangle,
    tone: "danger" as Tone,
    framework: undefined,
    tag: "MITRE",
  },
  {
    id: "user_activity",
    title: "Activité utilisateurs",
    desc: "Connexions, escalades de privilèges et anomalies ML",
    icon: UserIcon,
    tone: "primary" as Tone,
    framework: undefined,
    tag: "IAM",
  },
];

const sources = ["Microsoft 365", "Google WS", "Wazuh", "Syslog", "Firewall", "EDR"];

export default function ReportsPage() {
  const [period, setPeriod] = useState<Period>("7j");
  const [format, setFormat] = useState<Format>("pdf");
  const [generating, setGenerating] = useState<string | null>(null);
  const [checkedSources, setCheckedSources] = useState<string[]>(
    sources.filter((s) => s !== "Google WS")
  );

  const { data: _frameworks } = useQuery({
    queryKey: ["compliance-frameworks"],
    queryFn: reportsApi.getFrameworks,
    staleTime: Infinity,
  });
  void _frameworks;

  const handleGenerate = async (id: string, framework?: string, label = id) => {
    setGenerating(id);
    try {
      if (framework) {
        const days = period === "24h" ? 1 : period === "7j" ? 7 : period === "30j" ? 30 : 90;
        const blob = await reportsApi.downloadReport(framework, days);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `LogPlus_${framework.toUpperCase()}_${new Date().toISOString().slice(0, 10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast.success(`Rapport ${label} téléchargé`);
      } else {
        await new Promise((r) => setTimeout(r, 800));
        toast.success(`Rapport « ${label} » mis en file d'attente`);
      }
    } catch {
      toast.error("Erreur lors de la génération");
    } finally {
      setGenerating(null);
    }
  };

  const toggleSource = (s: string) => {
    setCheckedSources((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  return (
    <div className="page" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div>
        <div className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}>
          Rapports &amp; analyses
        </div>
        <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 3 }}>
          Génération de rapports de conformité et d&apos;activité
        </div>
      </div>

      {/* Main layout: preset list + generator */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 320px",
          gap: 20,
          alignItems: "flex-start",
        }}
        className="reports-grid"
      >
        {/* Preset list */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div
            style={{
              padding: "14px 18px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
                Rapports prédéfinis
              </div>
              <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 2 }}>
                Cliquez sur un rapport pour le générer immédiatement
              </div>
            </div>
            <span className="chip font-mono" style={{ fontSize: 11 }}>
              {presets.length} modèles
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            {presets.map((p, i) => {
              const Icon = p.icon;
              const tone = toneVar[p.tone];
              const isGen = generating === p.id;
              return (
                <div
                  key={p.id}
                  className="fade-up"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 14,
                    padding: "14px 18px",
                    borderBottom: i < presets.length - 1 ? "1px solid var(--border)" : "none",
                    transition: "background 140ms ease",
                    animationDelay: `${i * 35}ms`,
                    cursor: "default",
                  }}
                >
                  {/* Icon */}
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 10,
                      background: `color-mix(in srgb, ${tone} 13%, transparent)`,
                      color: tone,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={17} />
                  </div>

                  {/* Info */}
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 600 }}>{p.title}</span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: `color-mix(in srgb, ${tone} 14%, transparent)`,
                          color: tone,
                          letterSpacing: "0.04em",
                          fontFamily: "var(--font-mono)",
                        }}
                      >
                        {p.tag}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3, lineHeight: 1.4 }}>
                      {p.desc}
                    </div>
                  </div>

                  {/* Period badge */}
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 11,
                      color: "var(--text-2)",
                      padding: "3px 8px",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      flexShrink: 0,
                    }}
                  >
                    {period}
                  </span>

                  {/* Action */}
                  <button
                    className="btn btn-primary"
                    onClick={() => handleGenerate(p.id, p.framework, p.title)}
                    disabled={!!generating}
                    style={{ flexShrink: 0, minWidth: 110 }}
                  >
                    {isGen ? (
                      <>
                        <Clock size={13} />
                        Génération…
                      </>
                    ) : (
                      <>
                        <Download size={13} />
                        Générer
                        <ChevronRight size={13} style={{ opacity: 0.6 }} />
                      </>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right column: generator + recent */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Custom generator */}
          <div className="card" style={{ padding: 20 }}>
            <div className="font-display" style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>
              Rapport personnalisé
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Period */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 7 }}>
                  Période
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 3,
                    padding: 3,
                    background: "color-mix(in srgb, var(--text) 5%, transparent)",
                    borderRadius: 9,
                  }}
                >
                  {(["24h", "7j", "30j", "90j"] as Period[]).map((r) => (
                    <button
                      key={r}
                      onClick={() => setPeriod(r)}
                      className="font-mono"
                      style={{
                        flex: 1,
                        padding: "6px 0",
                        borderRadius: 6,
                        border: "none",
                        cursor: "pointer",
                        fontSize: 12,
                        background: period === r ? "var(--surface)" : "transparent",
                        color: period === r ? "var(--text)" : "var(--text-2)",
                        fontWeight: period === r ? 600 : 500,
                        boxShadow: period === r ? "0 2px 5px -2px rgba(0,0,0,0.18)" : "none",
                        transition: "all 140ms ease",
                      }}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              {/* Format */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 7 }}>
                  Format de sortie
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {(["pdf", "csv", "json"] as Format[]).map((f) => (
                    <button
                      key={f}
                      onClick={() => setFormat(f)}
                      style={{
                        flex: 1,
                        padding: "7px 0",
                        borderRadius: 8,
                        border: `1.5px solid ${format === f ? "var(--primary)" : "var(--border)"}`,
                        background: format === f ? "color-mix(in srgb, var(--primary) 9%, transparent)" : "transparent",
                        color: format === f ? "var(--primary)" : "var(--text-2)",
                        fontWeight: format === f ? 700 : 500,
                        fontSize: 12,
                        textTransform: "uppercase",
                        cursor: "pointer",
                        fontFamily: "var(--font-mono)",
                        transition: "all 140ms ease",
                      }}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sources */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 7 }}>
                  Sources de données
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  {sources.map((s) => {
                    const checked = checkedSources.includes(s);
                    return (
                      <label
                        key={s}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 9,
                          padding: "6px 10px",
                          borderRadius: 7,
                          border: `1px solid ${checked ? "color-mix(in srgb, var(--primary) 30%, transparent)" : "var(--border)"}`,
                          background: checked ? "color-mix(in srgb, var(--primary) 6%, transparent)" : "transparent",
                          cursor: "pointer",
                          transition: "all 140ms ease",
                        }}
                      >
                        <div
                          style={{
                            width: 16,
                            height: 16,
                            borderRadius: 5,
                            border: `2px solid ${checked ? "var(--primary)" : "var(--border)"}`,
                            background: checked ? "var(--primary)" : "transparent",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 140ms ease",
                            flexShrink: 0,
                          }}
                        >
                          {checked && <CheckCircle2 size={10} color="white" strokeWidth={3} />}
                        </div>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSource(s)}
                          style={{ display: "none" }}
                        />
                        <span style={{ fontSize: 12.5, fontWeight: checked ? 500 : 400, color: checked ? "var(--text)" : "var(--text-2)" }}>
                          {s}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <button
                className="btn btn-primary"
                style={{ marginTop: 4 }}
                onClick={() => handleGenerate("custom", undefined, "Rapport personnalisé")}
                disabled={!!generating || checkedSources.length === 0}
              >
                <Play size={13} />
                {generating === "custom" ? "Génération…" : "Générer le rapport"}
              </button>
            </div>
          </div>

          {/* Recent reports placeholder */}
          <div className="card" style={{ padding: 18 }}>
            <div className="font-display" style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>
              Historique
            </div>
            <div style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 16 }}>
              Rapports récemment générés
            </div>
            <div
              style={{
                padding: "24px 0",
                textAlign: "center",
                color: "var(--text-2)",
                fontSize: 12,
              }}
            >
              <Download size={22} style={{ margin: "0 auto 10px", opacity: 0.25 }} />
              Aucun rapport généré.
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
