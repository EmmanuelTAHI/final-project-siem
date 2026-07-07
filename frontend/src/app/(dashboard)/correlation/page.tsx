"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Plus, Search, GitBranch, Zap, ToggleLeft } from "lucide-react";
import { RuleCard } from "@/components/correlation/rule-card";
import { RuleFormModal } from "@/components/correlation/rule-form-modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NoRulesState } from "@/components/common/empty-state";
import { useCorrelationRules } from "@/hooks/use-correlation";
import { correlationApi } from "@/lib/api";
import type { CorrelationRule } from "@/types";
import toast from "react-hot-toast";

function CorrelationPageContent() {
  const searchParams = useSearchParams();
  const { data: apiRules, refetch } = useCorrelationRules();
  const [localRules, setLocalRules] = useState<CorrelationRule[] | null>(null);
  const rules = localRules ?? apiRules ?? [];
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CorrelationRule | null>(null);

  // Auto-open modal when navigated from Alerts with ?new=1
  useEffect(() => {
    if (searchParams?.get("new") === "1") {
      setEditingRule(null);
      setModalOpen(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initialize local state once API data arrives
  if (apiRules && localRules === null) setLocalRules(apiRules);

  const filtered = rules.filter((r) => {
    if (search && !r.name.toLowerCase().includes(search.toLowerCase()) && !r.description.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterType !== "all" && r.rule_type !== filterType) return false;
    if (filterSeverity !== "all" && r.severity !== filterSeverity) return false;
    return true;
  });

  const handleEdit = (rule: CorrelationRule) => {
    setEditingRule(rule);
    setModalOpen(true);
  };

  const handleDelete = (id: number) => {
    setLocalRules((prev) => (prev ?? []).filter((r) => r.id !== id));
    toast.success("Règle supprimée");
    refetch();
  };

  const handleUpdate = (updated: CorrelationRule) => {
    setLocalRules((prev) => (prev ?? []).map((r) => (r.id === updated.id ? updated : r)));
    correlationApi.updateRule(updated.id, updated).catch(() => null);
  };

  const handleSave = (saved: CorrelationRule) => {
    setLocalRules((prev) => {
      const list = prev ?? [];
      const exists = list.find((r) => r.id === saved.id);
      if (exists) return list.map((r) => (r.id === saved.id ? saved : r));
      return [saved, ...list];
    });
    setEditingRule(null);
    refetch();
  };

  const handleNewRule = () => {
    setEditingRule(null);
    setModalOpen(true);
  };

  const activeCount = rules.filter((r) => r.is_active).length;
  const totalAlerts = rules.reduce((acc, r) => acc + (r.alert_count ?? 0), 0);

  return (
    <div className="page p-4 lg:p-6 space-y-5">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-center justify-between gap-3"
      >
        <div>
          <h1 className="text-xl font-bold text-foreground">Règles de corrélation</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {rules.length} règles · {activeCount} actives · {totalAlerts.toLocaleString()} déclenchements total
          </p>
        </div>
        <Button onClick={handleNewRule} className="gap-2">
          <Plus className="w-4 h-4" />
          Nouvelle règle
        </Button>
      </motion.div>

      {/* Stats */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-2 sm:grid-cols-4 gap-3"
      >
        {[
          { label: "Seuil", count: rules.filter((r) => r.rule_type === "threshold").length, icon: "⚡", color: "text-blue-400 bg-blue-400/10 border-blue-400/20" },
          { label: "Voyage impossible", count: rules.filter((r) => r.rule_type === "impossible_travel").length, icon: "🌍", color: "text-purple-400 bg-purple-400/10 border-purple-400/20" },
          { label: "Temporelles", count: rules.filter((r) => r.rule_type === "time_based").length, icon: "🕐", color: "text-amber-400 bg-amber-400/10 border-amber-400/20" },
          { label: "Séquence", count: rules.filter((r) => r.rule_type === "sequence").length, icon: "🔗", color: "text-cyan-400 bg-cyan-400/10 border-cyan-400/20" },
        ].map((item) => (
          <div key={item.label} className={`rounded-lg border px-3 py-2 flex items-center gap-2 ${item.color}`}>
            <span className="text-lg">{item.icon}</span>
            <div>
              <p className="text-xs font-medium">{item.label}</p>
              <p className="text-lg font-bold">{item.count}</p>
            </div>
          </div>
        ))}
      </motion.div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex flex-wrap gap-2 items-center"
      >
        <div className="flex-1 min-w-48 max-w-sm">
          <Input
            placeholder="Rechercher une règle..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            leftIcon={<Search className="w-3.5 h-3.5" />}
          />
        </div>

        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-40 h-9 text-xs">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous types</SelectItem>
            <SelectItem value="threshold">Seuil</SelectItem>
            <SelectItem value="impossible_travel">Déplacement impossible</SelectItem>
            <SelectItem value="time_based">Basé sur l&apos;heure</SelectItem>
            <SelectItem value="sequence">Séquence</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filterSeverity} onValueChange={setFilterSeverity}>
          <SelectTrigger className="w-36 h-9 text-xs">
            <SelectValue placeholder="Sévérité" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes</SelectItem>
            <SelectItem value="critical">Critique</SelectItem>
            <SelectItem value="high">Élevée</SelectItem>
            <SelectItem value="medium">Moyenne</SelectItem>
            <SelectItem value="low">Faible</SelectItem>
          </SelectContent>
        </Select>
      </motion.div>

      {/* Rules grid */}
      {filtered.length === 0 ? (
        <NoRulesState onCreate={handleNewRule} />
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          {filtered.map((rule, i) => (
            <RuleCard
              key={rule.id}
              rule={rule}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onUpdate={handleUpdate}
              delay={i * 0.05}
            />
          ))}
        </motion.div>
      )}

      {/* Rule form modal */}
      <RuleFormModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditingRule(null);
        }}
        rule={editingRule}
        onSave={handleSave}
      />
    </div>
  );
}

export default function CorrelationPage() {
  return (
    <Suspense fallback={null}>
      <CorrelationPageContent />
    </Suspense>
  );
}
