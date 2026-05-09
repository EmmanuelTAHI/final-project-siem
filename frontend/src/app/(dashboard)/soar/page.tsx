"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Play, Plus, ToggleLeft, ToggleRight, CheckCircle, XCircle,
  Clock, Activity, Trash2, Edit, ChevronDown, ChevronUp,
} from "lucide-react";
import { soarApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import toast from "react-hot-toast";
import type { Playbook, TriggerType } from "@/types";

const TRIGGER_LABELS: Record<TriggerType, string> = {
  severity: "Seuil de sévérité",
  rule_match: "Règle de corrélation",
  ml_anomaly: "Anomalie ML",
  cti_match: "Correspondance CTI",
  manual: "Manuel",
};

const ACTION_TEMPLATES = [
  { type: "send_email", label: "Envoyer un email", params: { recipients: [], subject_template: "Alerte Log+: {title}" } },
  { type: "webhook", label: "Appel webhook (Slack/Teams)", params: { url: "", method: "POST" } },
  { type: "block_ip", label: "Bloquer l'IP source", params: { block_duration_hours: 24 } },
  { type: "create_ticket", label: "Créer un ticket ITSM", params: { system: "jira", api_url: "" } },
];

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    success: "bg-green-500/20 text-green-400 border-green-500/30",
    partial: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    failed: "bg-red-500/20 text-red-400 border-red-500/30",
    running: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    pending: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${map[status] ?? map.pending}`}>
      {status.toUpperCase()}
    </span>
  );
}

export default function SOARPage() {
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formTrigger, setFormTrigger] = useState<TriggerType>("severity");
  const [formConditions, setFormConditions] = useState('{"severities":["critical","high"]}');
  const [formActions, setFormActions] = useState('[{"type":"send_email","params":{"recipients":[]}}]');
  const [expandedExec, setExpandedExec] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data: playbooksData, isLoading } = useQuery({
    queryKey: ["playbooks"],
    queryFn: soarApi.getPlaybooks,
    refetchInterval: 15000,
  });

  const { data: statsData } = useQuery({
    queryKey: ["soar-stats"],
    queryFn: soarApi.getStats,
    refetchInterval: 30000,
  });

  const { data: execData } = useQuery({
    queryKey: ["soar-executions"],
    queryFn: () => soarApi.getExecutions({ page_size: 10 }),
    refetchInterval: 15000,
  });

  const createMutation = useMutation({
    mutationFn: soarApi.createPlaybook,
    onSuccess: () => {
      toast.success("Playbook créé");
      qc.invalidateQueries({ queryKey: ["playbooks"] });
      setShowForm(false);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => soarApi.togglePlaybook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["playbooks"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: soarApi.deletePlaybook,
    onSuccess: () => {
      toast.success("Playbook supprimé");
      qc.invalidateQueries({ queryKey: ["playbooks"] });
    },
  });

  const handleCreate = () => {
    try {
      createMutation.mutate({
        name: formName,
        description: formDesc,
        trigger_type: formTrigger,
        trigger_conditions: JSON.parse(formConditions),
        actions: JSON.parse(formActions),
        is_active: true,
      });
    } catch {
      toast.error("JSON invalide dans les conditions ou actions");
    }
  };

  const playbooks = playbooksData?.results ?? [];
  const executions = execData?.results ?? [];
  const stats = statsData;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">SOAR — Réponse Automatisée</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Security Orchestration, Automation and Response
          </p>
        </div>
        <Button onClick={() => setShowForm(true)} className="flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nouveau Playbook
        </Button>
      </div>

      {/* KPIs */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            { label: "Playbooks actifs", value: stats.active_playbooks, color: "text-green-400" },
            { label: "Exécutions 24h", value: stats.executions_24h, color: "text-blue-400" },
            { label: "Exécutions 7j", value: stats.executions_7d, color: "text-purple-400" },
            { label: "Taux de succès", value: `${stats.success_rate}%`, color: "text-emerald-400" },
            { label: "Total playbooks", value: stats.total_playbooks, color: "text-foreground" },
          ].map((kpi) => (
            <Card key={kpi.label} className="card-gradient border-border/50">
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{kpi.label}</p>
                <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Playbooks */}
      <Card className="card-gradient border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            Playbooks ({playbooks.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <div key={i} className="h-16 bg-secondary/30 rounded-lg animate-pulse" />)}
            </div>
          ) : playbooks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Zap className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Aucun playbook configuré. Créez-en un pour automatiser vos réponses.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {playbooks.map((pb) => (
                <motion.div
                  key={pb.id}
                  layout
                  className="flex items-start justify-between p-4 rounded-lg border border-border/50 bg-secondary/20 hover:bg-secondary/30 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-foreground">{pb.name}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {TRIGGER_LABELS[pb.trigger_type]}
                      </Badge>
                      <span className={`w-2 h-2 rounded-full ${pb.is_active ? "bg-green-500" : "bg-gray-500"}`} />
                    </div>
                    {pb.description && (
                      <p className="text-xs text-muted-foreground mb-1">{pb.description}</p>
                    )}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Activity className="w-3 h-3" />
                        {pb.execution_count} exécution{pb.execution_count !== 1 ? "s" : ""}
                      </span>
                      <span>{pb.actions.length} action{pb.actions.length !== 1 ? "s" : ""}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleMutation.mutate(pb.id)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      {pb.is_active ? <ToggleRight className="w-4 h-4 text-green-400" /> : <ToggleLeft className="w-4 h-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { if (confirm("Supprimer ce playbook ?")) deleteMutation.mutate(pb.id); }}
                      className="text-muted-foreground hover:text-red-400"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Exécutions récentes */}
      <Card className="card-gradient border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted-foreground" />
            Exécutions récentes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {executions.map((exec) => (
              <div key={exec.id} className="border border-border/30 rounded-lg overflow-hidden">
                <button
                  className="w-full flex items-center justify-between p-3 text-left hover:bg-secondary/20 transition-colors"
                  onClick={() => setExpandedExec(expandedExec === exec.id ? null : exec.id)}
                >
                  <div className="flex items-center gap-3">
                    <StatusBadge status={exec.status} />
                    <span className="text-sm font-medium text-foreground">{exec.playbook_name}</span>
                    {exec.alert_title && (
                      <span className="text-xs text-muted-foreground truncate max-w-48">→ {exec.alert_title}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{new Date(exec.started_at).toLocaleString("fr-FR")}</span>
                    {expandedExec === exec.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </div>
                </button>
                <AnimatePresence>
                  {expandedExec === exec.id && (
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: "auto" }}
                      exit={{ height: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="p-3 border-t border-border/30 bg-secondary/10">
                        <p className="text-xs font-semibold text-muted-foreground mb-2">Actions exécutées :</p>
                        {exec.actions_taken.map((action, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs mb-1">
                            {action.status === "success" ? (
                              <CheckCircle className="w-3 h-3 text-green-400" />
                            ) : (
                              <XCircle className="w-3 h-3 text-red-400" />
                            )}
                            <span className="text-foreground font-mono">{action.type}</span>
                            <span className="text-muted-foreground">{action.status}</span>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
            {executions.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">Aucune exécution récente</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Dialog création playbook */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl bg-card border-border max-h-[90vh] overflow-y-auto">
          <DialogHeader className="pb-1">
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              <Zap className="w-4 h-4 text-primary" />
              Nouveau Playbook SOAR
            </DialogTitle>
            <p className="text-sm text-muted-foreground pt-1">
              Définissez un déclencheur et les actions automatiques à exécuter.
            </p>
          </DialogHeader>

          <div className="space-y-5 py-3">
            {/* Nom */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground block">
                Nom du playbook <span className="text-destructive">*</span>
              </label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Ex: Blocage brute force critique"
                className="text-sm h-10"
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground block">Description</label>
              <Input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder="Décrivez l'objectif de ce playbook…"
                className="text-sm h-10"
              />
            </div>

            {/* Déclencheur */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground block">Type de déclencheur</label>
              <select
                value={formTrigger}
                onChange={(e) => setFormTrigger(e.target.value as TriggerType)}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            {/* Conditions JSON */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground block">Conditions de déclenchement</label>
              <p className="text-xs text-muted-foreground">
                Exemple pour sévérité :{" "}
                <code className="font-mono bg-muted px-1.5 py-0.5 rounded text-xs">
                  {"{"}&quot;severities&quot;: [&quot;critical&quot;, &quot;high&quot;]{"}"}
                </code>
              </p>
              <textarea
                value={formConditions}
                onChange={(e) => setFormConditions(e.target.value)}
                rows={4}
                className="w-full px-3 py-3 rounded-lg border border-border bg-background text-sm text-foreground font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 leading-relaxed"
              />
            </div>

            {/* Actions JSON */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground block">Actions à exécuter</label>
              <p className="text-xs text-muted-foreground mb-2">
                Cliquez sur un modèle pour le charger, puis personnalisez les paramètres.
              </p>
              <div className="flex flex-wrap gap-2 mb-3">
                {ACTION_TEMPLATES.map((tpl) => (
                  <button
                    key={tpl.type}
                    type="button"
                    onClick={() =>
                      setFormActions(JSON.stringify([{ type: tpl.type, params: tpl.params }], null, 2))
                    }
                    className="px-3 py-1.5 rounded-lg border border-border bg-secondary/40 hover:bg-secondary/70 hover:border-primary/40 text-xs font-medium text-foreground transition-all"
                  >
                    {tpl.label}
                  </button>
                ))}
              </div>
              <textarea
                value={formActions}
                onChange={(e) => setFormActions(e.target.value)}
                rows={7}
                className="w-full px-3 py-3 rounded-lg border border-border bg-background text-sm text-foreground font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 leading-relaxed"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button variant="outline" onClick={() => setShowForm(false)}>
              Annuler
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!formName.trim() || createMutation.isPending}
              className="gap-2"
            >
              {createMutation.isPending ? (
                <Activity className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              {createMutation.isPending ? "Création…" : "Créer le playbook"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
