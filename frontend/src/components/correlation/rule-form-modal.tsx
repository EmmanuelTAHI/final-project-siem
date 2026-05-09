"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { correlationApi } from "@/lib/api";
import toast from "react-hot-toast";
import type { CorrelationRule } from "@/types";

interface RuleFormModalProps {
  open: boolean;
  onClose: () => void;
  rule?: CorrelationRule | null;
  onSave: (rule: CorrelationRule) => void;
}

const mitreTactics = [
  "Initial Access", "Execution", "Persistence", "Privilege Escalation",
  "Defense Evasion", "Credential Access", "Discovery", "Lateral Movement",
  "Collection", "Command and Control", "Exfiltration", "Impact",
];

export function RuleFormModal({ open, onClose, rule, onSave }: RuleFormModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    severity: "medium" as "low" | "medium" | "high" | "critical",
    rule_type: "threshold" as "threshold" | "impossible_travel" | "time_based" | "sequence",
    mitre_tactic: "",
    mitre_technique: "",
    // Threshold fields
    threshold_action: "",
    threshold_count: "5",
    threshold_window: "5",
    threshold_group_by: "source_ip",
    // Impossible travel fields
    it_min_distance: "500",
    it_max_time: "60",
    // Time-based fields
    tb_start_time: "00:00",
    tb_end_time: "06:00",
    tb_action: "",
    // Sequence fields
    seq_min_targets: "3",
    seq_window: "10",
  });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (rule) {
      setFormData((prev) => ({
        ...prev,
        name: rule.name,
        description: rule.description,
        severity: rule.severity,
        rule_type: rule.rule_type,
        mitre_tactic: rule.mitre_tactic || "",
        mitre_technique: rule.mitre_technique || "",
      }));
    } else {
      setFormData({
        name: "",
        description: "",
        severity: "medium",
        rule_type: "threshold",
        mitre_tactic: "",
        mitre_technique: "",
        threshold_action: "",
        threshold_count: "5",
        threshold_window: "5",
        threshold_group_by: "source_ip",
        it_min_distance: "500",
        it_max_time: "60",
        tb_start_time: "00:00",
        tb_end_time: "06:00",
        tb_action: "",
        seq_min_targets: "3",
        seq_window: "10",
      });
    }
  }, [rule, open]);

  const buildConditionLogic = () => {
    const base = { type: formData.rule_type };
    switch (formData.rule_type) {
      case "threshold":
        return {
          ...base,
          action: formData.threshold_action,
          threshold: parseInt(formData.threshold_count),
          window_minutes: parseInt(formData.threshold_window),
          group_by: formData.threshold_group_by,
        };
      case "impossible_travel":
        return {
          ...base,
          min_distance_km: parseInt(formData.it_min_distance),
          max_time_minutes: parseInt(formData.it_max_time),
          action: "Login",
        };
      case "time_based":
        return {
          ...base,
          action: formData.tb_action,
          time_window: { start: formData.tb_start_time, end: formData.tb_end_time },
        };
      case "sequence":
        return {
          ...base,
          min_targets: parseInt(formData.seq_min_targets),
          window_minutes: parseInt(formData.seq_window),
          same_source: true,
        };
      default:
        return base;
    }
  };

  const conditionPreview = JSON.stringify(buildConditionLogic(), null, 2);

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error("Le nom est requis");
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        severity: formData.severity,
        rule_type: formData.rule_type,
        is_active: rule ? rule.is_active : true,
        condition_logic: buildConditionLogic(),
        alert_title_template:
          (rule as { alert_title_template?: string } | null)?.alert_title_template ||
          `[${formData.name.trim() || "Règle"}] alerte sur {user_email} ({source_ip})`,
        mitre_tactic: formData.mitre_tactic || undefined,
        mitre_technique: formData.mitre_technique || undefined,
      };

      let saved: CorrelationRule;
      if (rule) {
        saved = await correlationApi.updateRule(rule.id, payload as Partial<CorrelationRule>);
      } else {
        saved = await correlationApi.createRule(payload as Partial<CorrelationRule>);
      }
      onSave(saved);
      toast.success(rule ? "Règle mise à jour" : "Règle créée");
      onClose();
    } catch (err: unknown) {
      const r = (err as { response?: { data?: { message?: string; errors?: Record<string, unknown> } } })?.response?.data;
      const fieldErrors = r?.errors;
      let detail = r?.message ?? "";
      if (fieldErrors && typeof fieldErrors === "object") {
        const flat = Object.entries(fieldErrors)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
          .join(" · ");
        detail = detail ? `${detail} — ${flat}` : flat;
      }
      toast.error(detail || "Erreur lors de la sauvegarde de la règle");
    } finally {
      setIsSaving(false);
    }
  };

  const update = (key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            {rule ? "Modifier la règle" : "Nouvelle règle de corrélation"}
          </DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">
            {rule
              ? "Modifiez les paramètres de la règle de détection."
              : "Configurez une nouvelle règle pour détecter des comportements suspects."}
          </p>
        </DialogHeader>

        <div className="space-y-6 px-6 py-4">
          {/* Section : Informations générales */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-primary" />
              <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Informations générales</span>
            </div>

            <div className="space-y-2">
              <Label>
                Nom de la règle <span className="text-red-400">*</span>
              </Label>
              <Input
                placeholder="ex: Brute Force Detection"
                value={formData.name}
                onChange={(e) => update("name", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <textarea
                placeholder="Décrivez le comportement que cette règle détecte..."
                value={formData.description}
                onChange={(e) => update("description", e.target.value)}
                rows={3}
                className="w-full text-sm rounded-lg border border-border bg-background px-3 py-2.5 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring transition-shadow"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Sévérité</Label>
                <Select value={formData.severity} onValueChange={(v) => update("severity", v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">🟢 Faible</SelectItem>
                    <SelectItem value="medium">🟡 Moyen</SelectItem>
                    <SelectItem value="high">🟠 Élevé</SelectItem>
                    <SelectItem value="critical">🔴 Critique</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Type de condition</Label>
                <Select value={formData.rule_type} onValueChange={(v) => update("rule_type", v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="threshold">Seuil (Threshold)</SelectItem>
                    <SelectItem value="impossible_travel">Déplacement impossible</SelectItem>
                    <SelectItem value="time_based">Basé sur l&apos;heure</SelectItem>
                    <SelectItem value="sequence">Séquence</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="border-t border-border" />

          {/* Section : Configuration de la condition */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-amber-400" />
              <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Configuration de la condition</span>
            </div>

            <div className="rounded-xl border border-border bg-secondary/20 p-5 space-y-4">
              {formData.rule_type === "threshold" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Action à surveiller</Label>
                    <Input placeholder="ex: FailedLogin" value={formData.threshold_action} onChange={(e) => update("threshold_action", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Grouper par</Label>
                    <Select value={formData.threshold_group_by} onValueChange={(v) => update("threshold_group_by", v)}>
                      <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="source_ip">IP Source</SelectItem>
                        <SelectItem value="user_email">Utilisateur</SelectItem>
                        <SelectItem value="destination_ip">IP Destination</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Seuil (nombre d&apos;occurrences)</Label>
                    <Input type="number" value={formData.threshold_count} onChange={(e) => update("threshold_count", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Fenêtre temporelle (minutes)</Label>
                    <Input type="number" value={formData.threshold_window} onChange={(e) => update("threshold_window", e.target.value)} className="h-9 text-sm" />
                  </div>
                </div>
              )}

              {formData.rule_type === "impossible_travel" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Distance minimum (km)</Label>
                    <Input type="number" value={formData.it_min_distance} onChange={(e) => update("it_min_distance", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Délai maximum (minutes)</Label>
                    <Input type="number" value={formData.it_max_time} onChange={(e) => update("it_max_time", e.target.value)} className="h-9 text-sm" />
                  </div>
                </div>
              )}

              {formData.rule_type === "time_based" && (
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Action à surveiller</Label>
                    <Input placeholder="ex: AdminAction" value={formData.tb_action} onChange={(e) => update("tb_action", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Début de plage</Label>
                    <Input type="time" value={formData.tb_start_time} onChange={(e) => update("tb_start_time", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Fin de plage</Label>
                    <Input type="time" value={formData.tb_end_time} onChange={(e) => update("tb_end_time", e.target.value)} className="h-9 text-sm" />
                  </div>
                </div>
              )}

              {formData.rule_type === "sequence" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Cibles minimum</Label>
                    <Input type="number" value={formData.seq_min_targets} onChange={(e) => update("seq_min_targets", e.target.value)} className="h-9 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Fenêtre (minutes)</Label>
                    <Input type="number" value={formData.seq_window} onChange={(e) => update("seq_window", e.target.value)} className="h-9 text-sm" />
                  </div>
                </div>
              )}

              <div className="space-y-2 pt-1">
                <Label className="text-xs text-muted-foreground">Aperçu JSON de la condition</Label>
                <pre className="text-[11px] font-mono bg-background/60 border border-border/60 rounded-lg px-4 py-3 text-muted-foreground overflow-x-auto leading-relaxed">
                  {conditionPreview}
                </pre>
              </div>
            </div>
          </div>

          <div className="border-t border-border" />

          {/* Section : MITRE ATT&CK */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-blue-400" />
              <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Mapping MITRE ATT&amp;CK</span>
              <span className="text-xs text-muted-foreground">(optionnel)</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Tactique</Label>
                <Select value={formData.mitre_tactic} onValueChange={(v) => update("mitre_tactic", v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Sélectionner..." />
                  </SelectTrigger>
                  <SelectContent>
                    {mitreTactics.map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Technique</Label>
                <Input
                  placeholder="ex: T1110"
                  value={formData.mitre_technique}
                  onChange={(e) => update("mitre_technique", e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={handleSave} loading={isSaving}>
            {rule ? "Mettre à jour" : "Créer la règle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
