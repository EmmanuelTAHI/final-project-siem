"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Edit, Trash2, Play, Tag, Zap, Clock, ToggleLeft, ToggleRight } from "lucide-react";
import { SeverityBadge } from "@/components/alerts/severity-badge";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { cn, timeAgo } from "@/lib/utils";
import { correlationApi } from "@/lib/api";
import toast from "react-hot-toast";
import type { CorrelationRule } from "@/types";

interface RuleCardProps {
  rule: CorrelationRule;
  onEdit: (rule: CorrelationRule) => void;
  onDelete: (id: number) => void;
  onUpdate: (updated: CorrelationRule) => void;
  delay?: number;
}

const ruleTypeLabels: Record<string, string> = {
  threshold: "Seuil",
  impossible_travel: "Déplacement impossible",
  time_based: "Basé sur l'heure",
  sequence: "Séquence",
};

const ruleTypeColors: Record<string, string> = {
  threshold: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  impossible_travel: "text-purple-400 bg-purple-400/10 border-purple-400/30",
  time_based: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  sequence: "text-cyan-400 bg-cyan-400/10 border-cyan-400/30",
};

export function RuleCard({ rule, onEdit, onDelete, onUpdate, delay = 0 }: RuleCardProps) {
  const [isToggling, setIsToggling] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      const result = await correlationApi.toggleRule(rule.id);
      onUpdate({ ...rule, is_active: result.is_active });
      toast.success(result.is_active ? "Règle activée" : "Règle désactivée");
    } catch {
      toast.error("Erreur lors du changement de statut");
    } finally {
      setIsToggling(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    try {
      const result = await correlationApi.testRule(rule.id);
      toast.success(
        `Test terminé : ${result.matched_logs ?? 0} correspondance${(result.matched_logs ?? 0) !== 1 ? "s" : ""} trouvée${(result.matched_logs ?? 0) !== 1 ? "s" : ""}`
      );
    } catch {
      toast.error("Erreur lors du test de la règle");
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, delay, ease: [0.175, 0.885, 0.32, 1.275] }}
      className={cn(
        "relative rounded-xl border p-5 flex flex-col gap-4 group transition-all duration-200",
        rule.is_active
          ? "border-border hover:border-primary/30"
          : "border-border/50 opacity-70"
      )}
      style={{
        background: "hsl(var(--card))",
        boxShadow: rule.is_active ? undefined : "none",
      }}
    >
      {/* Active indicator */}
      {rule.is_active && (
        <div className="absolute top-4 right-4 w-2 h-2 rounded-full bg-emerald-400">
          <div className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" />
        </div>
      )}

      {/* Header */}
      <div className="flex items-start gap-3 pr-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <SeverityBadge severity={rule.severity} size="sm" />
            <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded border", ruleTypeColors[rule.rule_type])}>
              {ruleTypeLabels[rule.rule_type]}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-foreground">{rule.name}</h3>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{rule.description}</p>
        </div>
      </div>

      {/* MITRE tags */}
      {(rule.mitre_tactic || rule.mitre_technique) && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <Tag className="w-3 h-3 text-muted-foreground flex-shrink-0" />
          {rule.mitre_tactic && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400">
              {rule.mitre_tactic}
            </span>
          )}
          {rule.mitre_technique && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary border border-border text-muted-foreground font-mono">
              {rule.mitre_technique}
            </span>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <Zap className="w-3 h-3 text-amber-400" />
          <span>{rule.alert_count.toLocaleString()} déclenchements</span>
        </div>
        {rule.last_triggered && (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>{timeAgo(rule.last_triggered)}</span>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Footer actions */}
      <div className="flex items-center justify-between">
        {/* Toggle */}
        <div className="flex items-center gap-2">
          <Switch
            checked={rule.is_active}
            onCheckedChange={handleToggle}
            disabled={isToggling}
          />
          <span className="text-xs text-muted-foreground">
            {rule.is_active ? "Active" : "Inactive"}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleTest}
            loading={isTesting}
            title="Tester la règle"
          >
            <Play className="w-3.5 h-3.5 text-emerald-400" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onEdit(rule)}
            title="Modifier"
          >
            <Edit className="w-3.5 h-3.5 text-blue-400" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setConfirmDelete(true)}
            title="Supprimer"
          >
            <Trash2 className="w-3.5 h-3.5 text-red-400" />
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => {
          onDelete(rule.id);
          setConfirmDelete(false);
        }}
        title="Supprimer la règle"
        description={`Êtes-vous sûr de vouloir supprimer la règle « ${rule.name} » ? Cette action est irréversible.`}
        confirmLabel="Supprimer"
      />
    </motion.div>
  );
}
