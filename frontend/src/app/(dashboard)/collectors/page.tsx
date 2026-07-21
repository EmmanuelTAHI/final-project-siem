"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Database, Play, CheckCircle, XCircle, RefreshCw, Wifi, WifiOff,
  Clock, AlertTriangle, Plus, KeyRound, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatNumber, timeAgo } from "@/lib/utils";
import { useConnectors, useCollectorJobs } from "@/hooks/use-collectors";
import { collectorsApi } from "@/lib/api";
import type { Connector, ConnectorStatus } from "@/types";
import toast from "react-hot-toast";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

// ── Add-connector form types ──────────────────────────────────────────────────
type SourceType = "microsoft365" | "google_workspace" | "wazuh" | "syslog";

const SOURCE_OPTIONS: { value: SourceType; label: string; icon: string; fields: string[] }[] = [
  {
    value: "microsoft365",
    label: "Microsoft 365",
    icon: "🏢",
    fields: ["tenant_id", "client_id", "client_secret"],
  },
  {
    value: "google_workspace",
    label: "Google Workspace",
    icon: "🌐",
    fields: ["client_id", "client_secret"],
  },
  {
    value: "wazuh",
    label: "Wazuh SIEM",
    icon: "🛡️",
    fields: ["api_url", "username", "password"],
  },
  {
    value: "syslog",
    label: "Syslog",
    icon: "📋",
    fields: ["host", "port"],
  },
];

const FIELD_META: Record<string, { label: string; placeholder: string; secret?: boolean }> = {
  tenant_id:     { label: "Tenant ID",       placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
  client_id:     { label: "Client ID",       placeholder: "Application (client) ID" },
  client_secret: { label: "Client Secret",   placeholder: "Valeur du secret", secret: true },
  api_url:       { label: "URL de l'API",    placeholder: "https://wazuh.mon-domaine.com:55000" },
  username:      { label: "Nom d'utilisateur", placeholder: "wazuh-api" },
  password:      { label: "Mot de passe",    placeholder: "••••••••", secret: true },
  host:          { label: "Hôte / IP",       placeholder: "192.168.1.10" },
  port:          { label: "Port",            placeholder: "514" },
};

interface AddConnectorModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

function AddConnectorModal({ open, onClose, onCreated }: AddConnectorModalProps) {
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("microsoft365");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [interval, setIntervalSecs] = useState("300");
  const [saving, setSaving] = useState(false);

  const selected = SOURCE_OPTIONS.find((s) => s.value === sourceType)!;

  const handleSave = async () => {
    if (!name.trim()) { toast.error("Le nom est requis"); return; }
    setSaving(true);
    try {
      await api.post("/api/collectors/connectors/", {
        name: name.trim(),
        source_type: sourceType,
        credentials,
        polling_interval_seconds: parseInt(interval) || 300,
        is_active: true,
      });
      toast.success("Connecteur créé avec succès");
      onCreated();
      onClose();
      setName(""); setCredentials({}); setIntervalSecs("300");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? "Erreur lors de la création du connecteur");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="pb-1">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <Plus className="w-4 h-4 text-primary" />
            Ajouter un connecteur
          </DialogTitle>
          <p className="text-sm text-muted-foreground pt-1">
            Configurez une nouvelle source de logs à ingérer dans Argus.
          </p>
        </DialogHeader>

        <div className="space-y-6 px-6 py-5">
          {/* Nom */}
          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">
              Nom du connecteur <span className="text-destructive">*</span>
            </Label>
            <Input
              placeholder="Ex: Microsoft 365 — Production"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
            <p className="text-xs text-muted-foreground">Un nom explicite pour retrouver facilement cette source dans vos listes.</p>
          </div>

          {/* Type de source */}
          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">Type de source</Label>
            <p className="text-xs text-muted-foreground mb-1">D&apos;où proviennent les logs à collecter ?</p>
            <div className="grid grid-cols-2 gap-2.5">
              {SOURCE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { setSourceType(opt.value); setCredentials({}); }}
                  className={cn(
                    "flex items-center gap-2.5 px-4 py-3 rounded-xl border text-sm text-left transition-all",
                    sourceType === opt.value
                      ? "border-primary bg-primary/10 text-foreground font-semibold ring-1 ring-primary/30"
                      : "border-border bg-secondary/20 text-muted-foreground hover:bg-secondary/40 hover:text-foreground"
                  )}
                >
                  <span className="text-lg leading-none">{opt.icon}</span>
                  <span>{opt.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Credentials */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-primary flex-shrink-0" />
              <span className="text-sm font-semibold text-foreground">
                Identifiants — {selected.label}
              </span>
            </div>
            {selected.fields.map((field) => {
              const meta = FIELD_META[field] ?? { label: field, placeholder: "" };
              return (
                <div key={field} className="space-y-2">
                  <Label className="text-sm font-medium text-foreground flex items-center gap-1.5">
                    {meta.secret && <KeyRound className="w-3.5 h-3.5 text-muted-foreground" />}
                    {meta.label}
                  </Label>
                  <Input
                    type={meta.secret ? "password" : "text"}
                    placeholder={meta.placeholder}
                    value={credentials[field] ?? ""}
                    onChange={(e) =>
                      setCredentials((prev) => ({ ...prev, [field]: e.target.value }))
                    }
                  />
                </div>
              );
            })}
          </div>

          {/* Intervalle */}
          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">
              Intervalle de collecte (secondes)
            </Label>
            <Input
              type="number"
              min={60}
              max={86400}
              value={interval}
              onChange={(e) => setIntervalSecs(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Minimum 60 s · Recommandé : 300 s (5 min) · Maximum : 86 400 s (24 h)
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 pb-6 pt-4 border-t border-border">
          <Button variant="outline" onClick={onClose} className="text-sm">
            Annuler
          </Button>
          <Button onClick={handleSave} disabled={saving} className="gap-2 text-sm">
            {saving
              ? <RefreshCw className="w-4 h-4 animate-spin" />
              : <Plus className="w-4 h-4" />}
            {saving ? "Création…" : "Créer le connecteur"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const statusConfig: Record<ConnectorStatus, { label: string; color: string; icon: React.ElementType }> = {
  active: { label: "Actif", color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30", icon: Wifi },
  inactive: { label: "Inactif", color: "text-gray-400 bg-gray-400/10 border-gray-400/30", icon: WifiOff },
  error: { label: "Erreur", color: "text-red-400 bg-red-400/10 border-red-400/30", icon: AlertTriangle },
  connecting: { label: "Connexion...", color: "text-amber-400 bg-amber-400/10 border-amber-400/30", icon: RefreshCw },
};

const connectorIcons: Record<string, string> = {
  microsoft365: "🏢",
  google_workspace: "🌐",
  wazuh: "🛡️",
  syslog: "📋",
  custom: "⚙️",
};

export default function CollectorsPage() {
  const { data: connectors = [], refetch } = useConnectors();
  const { data: apiJobs } = useCollectorJobs();
  const [collectingId, setCollectingId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const handleCollect = async (connector: Connector) => {
    setCollectingId(connector.id);
    const t = toast.loading(`Collecte ${connector.display_name}…`);
    try {
      await collectorsApi.triggerCollect(connector.id);
      toast.success(`${connector.display_name} : collecte lancée`, { id: t });
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? `${connector.display_name} : erreur de collecte`, { id: t });
    } finally {
      setCollectingId(null);
    }
  };

  const handleTestConnection = async (connector: Connector) => {
    setTestingId(connector.id);
    const t = toast.loading(`Test de connexion ${connector.display_name}…`);
    try {
      const result = await collectorsApi.testConnection(connector.id);
      if (result.reachable) {
        const latency = result.latency_ms != null ? ` (${result.latency_ms} ms)` : "";
        toast.success(result.message ? `${connector.display_name} : ${result.message}` : `${connector.display_name} : connexion OK${latency}`, { id: t });
      } else {
        toast.error(`${connector.display_name} : ${result.message ?? "connexion échouée"}`, { id: t });
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? `${connector.display_name} : connexion échouée`, { id: t });
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (connector: Connector) => {
    setDeletingId(connector.id);
    try {
      await collectorsApi.deleteConnector(connector.id);
      toast.success(`${connector.display_name} : connecteur supprimé`);
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? `${connector.display_name} : erreur lors de la suppression`);
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const activeConnectors = connectors.filter((c) => c.status === "active").length;
  const totalLogs = connectors.reduce((acc, c) => acc + c.logs_collected, 0);
  const logs24h = connectors.reduce((acc, c) => acc + c.logs_collected_24h, 0);

  return (
    <div className="page p-4 lg:p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">Collecteurs de logs</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {activeConnectors}/{connectors.length} connecteurs actifs · {formatNumber(logs24h)} logs / 24h
          </p>
        </div>
        <Button className="gap-2" onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4" />
          Ajouter un connecteur
        </Button>
      </motion.div>

      {/* Stats bar */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: "Total logs collectés", value: formatNumber(totalLogs), icon: Database, color: "text-blue-400" },
          { label: "Logs / 24h", value: formatNumber(logs24h), icon: RefreshCw, color: "text-cyan-400" },
          { label: "Connecteurs actifs", value: `${activeConnectors}/${connectors.length}`, icon: Wifi, color: "text-emerald-400" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-border p-4" style={{ background: "hsl(var(--card))" }}>
            <div className="flex items-center gap-2 mb-2">
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
              <span className="text-xs text-muted-foreground">{stat.label}</span>
            </div>
            <p className="text-2xl font-bold text-foreground">{stat.value}</p>
          </div>
        ))}
      </motion.div>

      {/* Connectors cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {connectors.map((connector, i) => {
          const status = statusConfig[connector.status];
          const StatusIcon = status.icon;
          const isCollecting = collectingId === connector.id;
          const isTesting = testingId === connector.id;

          return (
            <motion.div
              key={connector.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 + i * 0.05 }}
              className="rounded-xl border border-border p-5 flex flex-col gap-4"
              style={{ background: "hsl(var(--card))" }}
            >
              {/* Header */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                    style={{
                      background: connector.status === "active"
                        ? "rgba(16,185,129,0.1)"
                        : connector.status === "error"
                        ? "rgba(239,68,68,0.1)"
                        : "rgba(107,114,128,0.1)",
                      border: connector.status === "active"
                        ? "1px solid rgba(16,185,129,0.3)"
                        : connector.status === "error"
                        ? "1px solid rgba(239,68,68,0.3)"
                        : "1px solid rgba(107,114,128,0.3)",
                    }}
                  >
                    {connectorIcons[connector.connector_type ?? connector.source_type] ?? "⚙️"}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">{connector.display_name}</h3>
                    <p className="text-xs text-muted-foreground">{connector.description}</p>
                  </div>
                </div>
                <div className={cn("flex items-center gap-1 px-2 py-1 rounded-lg border text-xs font-medium", status.color)}>
                  <StatusIcon className="w-3 h-3" />
                  {status.label}
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-muted/60 px-3 py-2">
                  <p className="text-[10px] text-muted-foreground">Total collecté</p>
                  <p className="text-sm font-bold text-foreground">{formatNumber(connector.logs_collected)}</p>
                </div>
                <div className="rounded-lg bg-muted/60 px-3 py-2">
                  <p className="text-[10px] text-muted-foreground">Dernières 24h</p>
                  <p className={cn("text-sm font-bold", connector.logs_collected_24h > 0 ? "text-foreground" : "text-muted-foreground")}>
                    {formatNumber(connector.logs_collected_24h)}
                  </p>
                </div>
              </div>

              {/* Last job */}
              <div className="flex items-center gap-2">
                {connector.last_job_status === "success" ? (
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                ) : connector.last_job_status === "failed" ? (
                  <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                ) : (
                  <Clock className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                )}
                <span className="text-xs text-muted-foreground">
                  Dernier job : {connector.last_job_at ? timeAgo(connector.last_job_at) : "Jamais"}
                </span>
              </div>

              {/* Divider */}
              <div className="border-t border-border" />

              {/* Actions */}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => handleCollect(connector)}
                  disabled={isCollecting || connector.status === "error"}
                  loading={isCollecting}
                  className="flex-1 gap-1.5 text-xs"
                >
                  <Play className="w-3 h-3" />
                  Collecter
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleTestConnection(connector)}
                  disabled={isTesting}
                  loading={isTesting}
                  className="gap-1.5 text-xs"
                >
                  <Wifi className="w-3 h-3" />
                  Tester
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setConfirmDeleteId(connector.id)}
                  disabled={deletingId === connector.id}
                  loading={deletingId === connector.id}
                  className="gap-1.5 text-xs text-destructive hover:text-destructive"
                  title="Supprimer"
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Add connector modal */}
      <AddConnectorModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onCreated={() => refetch()}
      />

      {/* Confirmation de suppression */}
      <ConfirmDialog
        open={confirmDeleteId !== null}
        onClose={() => setConfirmDeleteId(null)}
        onConfirm={() => {
          const connector = connectors.find((c) => c.id === confirmDeleteId);
          if (connector) handleDelete(connector);
        }}
        title="Supprimer le connecteur"
        description={
          confirmDeleteId
            ? `Êtes-vous sûr de vouloir supprimer « ${connectors.find((c) => c.id === confirmDeleteId)?.display_name ?? ""} » ? La collecte de logs pour cette source s'arrêtera immédiatement. Cette action est irréversible.`
            : ""
        }
        confirmLabel="Supprimer"
        loading={deletingId !== null}
      />

      {/* Jobs history */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="rounded-xl border border-border"
        style={{ background: "hsl(var(--card))" }}
      >
        <div className="p-5 pb-3 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">Historique des jobs</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Dernières exécutions</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Connecteur</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Statut</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Logs collectés</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Début</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Durée</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Erreur</th>
              </tr>
            </thead>
            <tbody>
              {(apiJobs ?? []).map((job, i) => (
                <motion.tr
                  key={job.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.6 + i * 0.03 }}
                  className="border-b border-border hover:bg-secondary/50 transition-colors"
                >
                  <td className="px-4 py-2.5 font-medium text-foreground">{job.connector_name}</td>
                  <td className="px-4 py-2.5">
                    <div className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[10px] font-medium",
                      job.status === "success" ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30" :
                      job.status === "failed" ? "text-red-400 bg-red-400/10 border-red-400/30" :
                      "text-amber-400 bg-amber-400/10 border-amber-400/30"
                    )}>
                      {job.status === "success" ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      {job.status === "success" ? "Succès" : job.status === "failed" ? "Échec" : "En cours"}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 font-medium">{job.logs_collected.toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{timeAgo(job.started_at)}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{job.duration_seconds ? `${job.duration_seconds}s` : "—"}</td>
                  <td className="px-4 py-2.5 text-red-400 max-w-xs truncate">{job.error_message || "—"}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
