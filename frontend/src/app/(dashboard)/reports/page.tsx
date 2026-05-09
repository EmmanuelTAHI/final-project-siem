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
} from "lucide-react";
import { reportsApi } from "@/lib/api";
import toast from "react-hot-toast";

type Tone = "primary" | "secondary" | "danger" | "info" | "warning";

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
  },
  {
    id: "iso27001",
    title: "Conformité ISO 27001",
    desc: "Contrôles A.5 à A.18 — preuves et écarts",
    icon: FileText,
    tone: "secondary" as Tone,
    framework: "iso27001",
  },
  {
    id: "gdpr",
    title: "Conformité RGPD",
    desc: "Traçabilité accès aux données personnelles",
    icon: FileText,
    tone: "info" as Tone,
    framework: "gdpr",
  },
  {
    id: "pci_dss",
    title: "Conformité PCI DSS",
    desc: "Surveillance des données de paiement",
    icon: FileText,
    tone: "warning" as Tone,
    framework: "pci_dss",
  },
  {
    id: "top_threats",
    title: "Top menaces détectées",
    desc: "Classement MITRE ATT&CK des TTPs observés",
    icon: AlertTriangle,
    tone: "danger" as Tone,
    framework: undefined,
  },
  {
    id: "user_activity",
    title: "Activité utilisateurs",
    desc: "Connexions, escalades, anomalies ML",
    icon: UserIcon,
    tone: "primary" as Tone,
    framework: undefined,
  },
];

const statusMap: Record<"ready" | "running" | "error", { cls: string; label: string }> = {
  ready:   { cls: "badge-ok",   label: "Prêt" },
  running: { cls: "badge-high", label: "En cours" },
  error:   { cls: "badge-crit", label: "Erreur" },
};

export default function ReportsPage() {
  const [period, setPeriod] = useState<"24h" | "7j" | "30j" | "90j" | "Custom">("7j");
  const [format, setFormat] = useState<"pdf" | "csv" | "json">("pdf");
  const [generating, setGenerating] = useState<string | null>(null);

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
        toast.success(`Rapport « ${label} » mis en file d'attente`);
      }
    } catch {
      toast.error("Erreur lors de la génération");
    } finally {
      setGenerating(null);
    }
  };

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
          Rapports &amp; analyses
        </div>
        <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2 }}>
          Génération de rapports préconfigurés ou personnalisés
        </div>
      </div>

      {/* Preset grid */}
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
          Rapports prédéfinis
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 14,
          }}
        >
          {presets.map((p, i) => {
            const Icon = p.icon;
            const tone = toneVar[p.tone];
            return (
              <div
                key={p.id}
                className="card card-hover fade-up"
                style={{ padding: 18, cursor: "pointer", animationDelay: `${i * 40}ms` }}
                onClick={() => handleGenerate(p.id, p.framework, p.title)}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  <div
                    style={{
                      width: 42,
                      height: 42,
                      borderRadius: 10,
                      background: `color-mix(in srgb, ${tone} 14%, transparent)`,
                      color: tone,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={18} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
                      {p.title}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3, lineHeight: 1.45 }}>
                      {p.desc}
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 14, height: 42, display: "flex", alignItems: "flex-end", gap: 3 }}>
                  {Array.from({ length: 16 }, (_, j) => (
                    <div
                      key={j}
                      style={{
                        flex: 1,
                        height: 8 + Math.abs(Math.sin(j * 1.3 + i)) * 32,
                        background: `color-mix(in srgb, ${tone} ${35 + Math.abs(Math.sin(j * 0.7)) * 40}%, transparent)`,
                        borderRadius: 2,
                      }}
                    />
                  ))}
                </div>
                <div
                  style={{
                    marginTop: 12,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: 11.5,
                    color: "var(--text-2)",
                  }}
                >
                  <span>Période : {period}</span>
                  <span style={{ color: "var(--primary)", fontWeight: 600 }}>
                    {generating === p.id ? "Génération…" : "Générer →"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
          gap: 16,
        }}
      >
        {/* Custom builder */}
        <div className="card" style={{ padding: 20 }}>
          <div className="font-display" style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>
            Générateur personnalisé
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Field label="Période">
              <div
                style={{
                  display: "flex",
                  gap: 4,
                  padding: 3,
                  background: "color-mix(in srgb, var(--text) 5%, transparent)",
                  borderRadius: 9,
                }}
              >
                {(["24h", "7j", "30j", "90j", "Custom"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setPeriod(r)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: 6,
                      border: "none",
                      cursor: "pointer",
                      fontSize: 12,
                      flex: 1,
                      background: period === r ? "var(--surface)" : "transparent",
                      color: period === r ? "var(--text)" : "var(--text-2)",
                      fontWeight: period === r ? 600 : 500,
                    }}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Sources">
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {["Microsoft 365", "Google WS", "Wazuh", "Syslog", "Firewall", "EDR"].map((s) => (
                  <label
                    key={s}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 12,
                      padding: "5px 10px",
                      border: "1px solid var(--border)",
                      borderRadius: 999,
                      cursor: "pointer",
                    }}
                  >
                    <input type="checkbox" defaultChecked={s !== "Google WS"} />
                    {s}
                  </label>
                ))}
              </div>
            </Field>

            <Field label="Types d'événements">
              <select className="input">
                <option>Alertes + Logs corrélés</option>
                <option>Alertes uniquement</option>
                <option>Logs bruts</option>
                <option>Anomalies ML</option>
              </select>
            </Field>

            <Field label="Format de sortie">
              <div style={{ display: "flex", gap: 8 }}>
                {(["pdf", "csv", "json"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFormat(f)}
                    className={`pill ${format === f ? "active" : ""}`}
                    style={{ textTransform: "uppercase", minWidth: 60 }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </Field>

            <button
              className="btn btn-primary"
              style={{ alignSelf: "flex-start", marginTop: 6 }}
              onClick={() => handleGenerate("custom", undefined, "Custom")}
            >
              <Play size={13} />
              Générer le rapport
            </button>
          </div>
        </div>

        {/* Recent reports */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: 20, paddingBottom: 12 }}>
            <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>
              Rapports récents
            </div>
            <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 2 }}>
              Derniers rapports générés
            </div>
          </div>
          <div
            style={{
              padding: "32px 24px",
              textAlign: "center",
              color: "var(--text-2)",
              fontSize: 13,
              borderTop: "1px dashed var(--border)",
            }}
          >
            <Download size={22} style={{ margin: "0 auto 10px", opacity: 0.3 }} />
            Aucun rapport généré pour l&apos;instant.
            <br />
            <span style={{ fontSize: 12, opacity: 0.7 }}>
              Cliquez sur un rapport prédéfini ou utilisez le générateur personnalisé.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--text-2)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}
