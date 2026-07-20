"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Cpu, Plus, KeyRound, Copy, Check, Trash2, RefreshCw, AlertTriangle, ShieldCheck,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { timeAgo, getDocsUrl, cn } from "@/lib/utils";
import { useAgentTokens } from "@/hooks/use-agent-tokens";
import { agentsApi } from "@/lib/api";
import toast from "react-hot-toast";

interface GenerateTokenModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

type AgentPlatform = "linux" | "windows";

function installCommand(platform: AgentPlatform, origin: string, token: string): string {
  if (platform === "linux") {
    return `curl -fsSL ${origin}/agents/install-linux.sh | sudo bash -s -- --url ${origin} --token ${token}`;
  }
  return `$s = Invoke-WebRequest -UseBasicParsing ${origin}/agents/install-windows.ps1; Set-Content -Path "$env:TEMP\\install-windows.ps1" -Value $s.Content; & "$env:TEMP\\install-windows.ps1" -Url "${origin}" -Token "${token}"`;
}

function GenerateTokenModal({ open, onClose, onCreated }: GenerateTokenModalProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [rawToken, setRawToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [platform, setPlatform] = useState<AgentPlatform>("linux");

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const handleGenerate = async () => {
    if (!name.trim()) { toast.error("Le nom est requis"); return; }
    setSaving(true);
    try {
      const result = await agentsApi.generate(name.trim());
      setRawToken(result.token);
      onCreated();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? "Erreur lors de la génération du token");
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = async () => {
    if (!rawToken) return;
    await navigator.clipboard.writeText(rawToken);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyCmd = async () => {
    if (!rawToken) return;
    await navigator.clipboard.writeText(installCommand(platform, origin, rawToken));
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleClose = () => {
    setName("");
    setRawToken(null);
    setCopied(false);
    setCopiedCmd(false);
    setPlatform("linux");
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader className="pb-1">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <Plus className="w-4 h-4 text-primary" />
            {rawToken ? "Token généré" : "Générer un token d'agent"}
          </DialogTitle>
          {!rawToken && (
            <p className="text-sm text-muted-foreground pt-1">
              Ce token permet à un agent (rsyslog, NXLog, Fluent Bit…) déployé sur vos machines
              d&apos;envoyer des logs vers Log+, rattachés uniquement à votre organisation.
            </p>
          )}
        </DialogHeader>

        {rawToken ? (
          <div className="space-y-5 px-6 py-5">
            <div className="flex items-start gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2.5 text-xs text-amber-200">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>
                Ce token ne sera plus jamais affiché. La commande ci-dessous l&apos;intègre déjà —
                copiez-la et exécutez-la sur le poste à surveiller avant de fermer cette fenêtre.
              </span>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium text-foreground">
                Installer l&apos;agent Log+ natif
              </Label>
              <div className="flex gap-1.5">
                {(["linux", "windows"] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPlatform(p)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg border text-xs font-medium capitalize transition-all",
                      platform === p
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border bg-secondary/20 text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {p === "linux" ? "Linux" : "Windows"}
                  </button>
                ))}
              </div>
              <div className="flex items-start gap-2">
                <code className="flex-1 rounded-lg border border-border bg-secondary/30 px-3 py-2.5 text-[11px] font-mono break-all leading-relaxed">
                  {installCommand(platform, origin, rawToken)}
                </code>
                <Button size="sm" variant="outline" onClick={handleCopyCmd} className="gap-1.5 flex-shrink-0">
                  {copiedCmd ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedCmd ? "Copié" : "Copier"}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {platform === "linux"
                  ? "À exécuter dans un terminal root (sudo). Installe et démarre le service systemd."
                  : "À exécuter dans PowerShell (élévation administrateur demandée automatiquement). Installe et démarre le service Windows."}
                {" "}Le script vérifie l&apos;intégrité du binaire (SHA-256) avant de l&apos;exécuter.
              </p>
              <a
                href={`${origin}/agents/logplus-agent-${platform === "linux" ? "linux-amd64" : "windows-amd64.exe"}`}
                className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
              >
                <Download className="w-3.5 h-3.5" />
                Télécharger le binaire seul ({platform === "linux" ? "linux/amd64" : "windows/amd64"})
              </a>
            </div>

            <details className="group">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
                Token brut (usage avancé : rsyslog, NXLog, Fluent Bit…)
              </summary>
              <div className="flex items-center gap-2 mt-2">
                <code className="flex-1 rounded-lg border border-border bg-secondary/30 px-3 py-2.5 text-xs break-all">
                  {rawToken}
                </code>
                <Button size="sm" variant="outline" onClick={handleCopy} className="gap-1.5 flex-shrink-0">
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? "Copié" : "Copier"}
                </Button>
              </div>
            </details>

            <div className="flex justify-end pt-2 border-t border-border">
              <Button onClick={handleClose} className="text-sm">J&apos;ai copié la commande</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-6 px-6 py-5">
            <div className="space-y-2">
              <Label className="text-sm font-medium text-foreground">
                Nom <span className="text-destructive">*</span>
              </Label>
              <Input
                placeholder="Ex: Serveurs web prod, Parc Windows siège"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">Identifie le parc de machines qui utilisera ce token — vous pourrez le révoquer à tout moment.</p>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <Button variant="outline" onClick={handleClose} className="text-sm">
                Annuler
              </Button>
              <Button onClick={handleGenerate} disabled={saving} className="gap-2 text-sm">
                {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                {saving ? "Génération…" : "Générer le token"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function AgentsPage() {
  const { data: tokens = [], refetch } = useAgentTokens();
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  const handleRevoke = async (id: string, name: string) => {
    if (!confirm(`Révoquer le token « ${name} » ? Les agents qui l'utilisent ne pourront plus envoyer de logs.`)) return;
    setRevokingId(id);
    try {
      await agentsApi.revoke(id);
      toast.success(`Token « ${name} » révoqué`);
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? "Erreur lors de la révocation");
    } finally {
      setRevokingId(null);
    }
  };

  const activeTokens = tokens.filter((t) => t.is_active).length;

  return (
    <div className="page p-4 lg:p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">Agents de collecte</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {activeTokens}/{tokens.length} tokens actifs · déployez des agents sur vos machines pour envoyer vos logs
          </p>
        </div>
        <Button className="gap-2" onClick={() => setShowGenerateModal(true)}>
          <Plus className="w-4 h-4" />
          Générer un token
        </Button>
      </motion.div>

      {/* Info banner */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="rounded-xl border border-border p-4 flex items-start gap-3"
        style={{ background: "hsl(var(--card))" }}
      >
        <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-muted-foreground leading-relaxed">
          Chaque token identifie de façon unique votre organisation : les logs envoyés avec ce
          token ne sont jamais visibles par une autre organisation. L&apos;agent Log+ natif
          (Linux &amp; Windows, aucune dépendance externe) s&apos;installe en une commande générée
          automatiquement après création d&apos;un token — voir la{" "}
          <a href={getDocsUrl("agents")} target="_blank" rel="noopener noreferrer" className="text-primary underline">
            documentation
          </a>{" "}
          pour le détail et les méthodes alternatives (rsyslog, NXLog, Fluent Bit).
        </div>
      </motion.div>

      {/* Stats bar */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border p-4" style={{ background: "hsl(var(--card))" }}>
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-muted-foreground">Tokens générés</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{tokens.length}</p>
        </div>
        <div className="rounded-xl border border-border p-4" style={{ background: "hsl(var(--card))" }}>
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-muted-foreground">Tokens actifs</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{activeTokens}</p>
        </div>
      </motion.div>

      {/* Tokens grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {tokens.map((token, i) => (
          <motion.div
            key={token.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.05 }}
            className="rounded-xl border border-border p-5 flex flex-col gap-4"
            style={{ background: "hsl(var(--card))" }}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{
                    background: token.is_active ? "rgba(16,185,129,0.1)" : "rgba(107,114,128,0.1)",
                    border: token.is_active ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(107,114,128,0.3)",
                  }}
                >
                  <Cpu className={cn("w-5 h-5", token.is_active ? "text-emerald-400" : "text-gray-400")} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{token.name}</h3>
                  <p className="text-xs text-muted-foreground font-mono">{token.token_prefix}…</p>
                </div>
              </div>
              <div
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-lg border text-xs font-medium",
                  token.is_active
                    ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30"
                    : "text-gray-400 bg-gray-400/10 border-gray-400/30"
                )}
              >
                {token.is_active ? "Actif" : "Révoqué"}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 text-xs text-muted-foreground">
              <div>
                Connecteur : <span className="text-foreground">{token.connector_name ?? "Pas encore utilisé"}</span>
              </div>
              <div>
                Dernier usage : {token.last_used_at ? timeAgo(token.last_used_at) : "Jamais"}
                {token.last_used_ip ? ` (${token.last_used_ip})` : ""}
              </div>
              <div>Créé {timeAgo(token.created_at)} par {token.created_by_email ?? "—"}</div>
            </div>

            <div className="border-t border-border" />

            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleRevoke(token.id, token.name)}
                disabled={!token.is_active || revokingId === token.id}
                loading={revokingId === token.id}
                className="flex-1 gap-1.5 text-xs text-destructive hover:text-destructive"
              >
                <Trash2 className="w-3 h-3" />
                Révoquer
              </Button>
            </div>
          </motion.div>
        ))}

        {tokens.length === 0 && (
          <div className="col-span-full text-center py-12 text-sm text-muted-foreground">
            Aucun token d&apos;agent pour le moment. Générez-en un pour commencer à envoyer des logs.
          </div>
        )}
      </div>

      <GenerateTokenModal
        open={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        onCreated={() => refetch()}
      />
    </div>
  );
}
