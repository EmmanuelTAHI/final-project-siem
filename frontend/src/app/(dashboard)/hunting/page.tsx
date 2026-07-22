"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, Play, Save, Trash2, BookOpen, Clock, Target, Plus,
  ChevronDown, ChevronUp, Filter,
} from "lucide-react";
import { huntingApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import toast from "react-hot-toast";
import { FlagBadge } from "@/components/common/country-flag";
import type { NormalizedLog } from "@/types";

const SAVED_QUERIES_TEMPLATES = [
  {
    name: "Brute Force détection",
    mitre_tactic: "TA0006 - Credential Access",
    mitre_technique: "T1110 - Brute Force",
    query_params: { outcome: "failure", action: "login_failure" },
  },
  {
    name: "Connexions hors heures",
    mitre_tactic: "TA0001 - Initial Access",
    mitre_technique: "T1078 - Valid Accounts",
    query_params: { outcome: "success", action: "login_success" },
  },
  {
    name: "Activité depuis pays à risque",
    mitre_tactic: "TA0001 - Initial Access",
    mitre_technique: "T1133 - External Remote Services",
    query_params: { geo_country: "RU" },
  },
  {
    name: "Escalade de privilèges",
    mitre_tactic: "TA0004 - Privilege Escalation",
    mitre_technique: "T1078.003 - Local Accounts",
    query_params: { action: "privilege_change" },
  },
];

const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-500/20 text-blue-400",
  low: "bg-green-500/20 text-green-400",
  medium: "bg-yellow-500/20 text-yellow-400",
  high: "bg-orange-500/20 text-orange-400",
  critical: "bg-red-500/20 text-red-400",
};

export default function HuntingPage() {
  const qc = useQueryClient();
  const [showFilters, setShowFilters] = useState(false);
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveMitreTactic, setSaveMitreTactic] = useState("");

  const [filters, setFilters] = useState({
    action: "",
    outcome: "",
    severity: "",
    source_type: "",
    geo_country: "",
    user_email: "",
    source_ip: "",
    date_from: "",
    date_to: "",
  });

  const [results, setResults] = useState<{ count: number; returned: number; results: NormalizedLog[] } | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const { data: queriesData, isLoading: queriesLoading } = useQuery({
    queryKey: ["hunting-queries"],
    queryFn: huntingApi.getQueries,
  });

  const createMutation = useMutation({
    mutationFn: huntingApi.createQuery,
    onSuccess: () => {
      toast.success("Requête sauvegardée");
      qc.invalidateQueries({ queryKey: ["hunting-queries"] });
      setShowSaveForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: huntingApi.deleteQuery,
    onSuccess: () => {
      toast.success("Requête supprimée");
      qc.invalidateQueries({ queryKey: ["hunting-queries"] });
    },
  });

  const executeQueryMutation = useMutation({
    mutationFn: huntingApi.executeQuery,
    onSuccess: (data) => setResults(data),
  });

  const cleanFilters = () =>
    Object.fromEntries(Object.entries(filters).filter(([_, v]) => v !== ""));

  const handleRun = async () => {
    setIsRunning(true);
    try {
      const data = await huntingApi.runAdHoc(cleanFilters(), 500);
      setResults(data);
      toast.success(`${data.count} résultat${data.count !== 1 ? "s" : ""} trouvé${data.count !== 1 ? "s" : ""}`);
    } catch {
      toast.error("Erreur lors de la recherche");
    } finally {
      setIsRunning(false);
    }
  };

  const handleSaveQuery = () => {
    if (!saveName.trim()) return;
    createMutation.mutate({
      name: saveName,
      query_params: cleanFilters(),
      mitre_tactic: saveMitreTactic,
    });
  };

  const applyTemplate = (template: typeof SAVED_QUERIES_TEMPLATES[0]) => {
    setFilters({ ...filters, ...(template.query_params as any) });
    setSaveMitreTactic(template.mitre_tactic);
    toast(`Filtres appliqués: ${template.name}`);
  };

  const savedQueries = queriesData?.results ?? [];

  return (
    <div className="page p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Threat Hunting</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Recherche proactive de menaces dans les logs normalisés
        </p>
      </div>

      {/* Templates MITRE */}
      <Card className="card-gradient border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Target className="w-4 h-4 text-primary" />
            Templates MITRE ATT&CK
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {SAVED_QUERIES_TEMPLATES.map((t) => (
              <button
                key={t.name}
                onClick={() => applyTemplate(t)}
                className="p-3 rounded-lg border border-border/50 bg-secondary/20 hover:bg-secondary/40 text-left transition-all group"
              >
                <p className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{t.name}</p>
                <p className="text-[10px] text-muted-foreground mt-1">{t.mitre_technique}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Filtres */}
      <Card className="card-gradient border-border/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Filter className="w-4 h-4 text-primary" />
              Filtres de recherche
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={() => setShowFilters(!showFilters)}>
              {showFilters ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </Button>
          </div>
        </CardHeader>
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
            >
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { key: "action", placeholder: "Action (ex: login_failure)" },
                    { key: "outcome", placeholder: "Résultat (success/failure)" },
                    { key: "severity", placeholder: "Sévérité (high, critical...)" },
                    { key: "source_type", placeholder: "Source (microsoft365...)" },
                    { key: "geo_country", placeholder: "Pays (FR, US, RU...)" },
                    { key: "user_email", placeholder: "Email utilisateur" },
                    { key: "source_ip", placeholder: "IP source" },
                    { key: "date_from", placeholder: "Depuis (YYYY-MM-DD)" },
                  ].map(({ key, placeholder }) => (
                    <Input
                      key={key}
                      placeholder={placeholder}
                      value={filters[key as keyof typeof filters]}
                      onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}
                    />
                  ))}
                </div>
              </CardContent>
            </motion.div>
          )}
        </AnimatePresence>
        <CardContent className={showFilters ? "pt-0" : undefined}>
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              onClick={handleRun}
              disabled={isRunning}
              className="flex items-center gap-2"
            >
              {isRunning ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {isRunning ? "Recherche..." : "Lancer la chasse"}
            </Button>
            <Button
              variant="outline"
              onClick={() => { setShowFilters(true); setShowSaveForm(!showSaveForm); }}
              className="flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              Sauvegarder
            </Button>
            <Button
              variant="ghost"
              onClick={() => setFilters({ action: "", outcome: "", severity: "", source_type: "", geo_country: "", user_email: "", source_ip: "", date_from: "", date_to: "" })}
              className="text-muted-foreground"
            >
              Effacer
            </Button>
            {Object.values(cleanFilters()).length > 0 && (
              <span className="text-xs text-muted-foreground">
                {Object.values(cleanFilters()).length} filtre{Object.values(cleanFilters()).length > 1 ? "s" : ""} actif{Object.values(cleanFilters()).length > 1 ? "s" : ""}
              </span>
            )}
          </div>

          <AnimatePresence>
            {showSaveForm && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mt-3 flex gap-3 flex-wrap"
              >
                <Input className="flex-1 min-w-[160px]" placeholder="Nom de la requête" value={saveName} onChange={(e) => setSaveName(e.target.value)} />
                <Input className="flex-1 min-w-[160px]" placeholder="Tactique MITRE (optionnel)" value={saveMitreTactic} onChange={(e) => setSaveMitreTactic(e.target.value)} />
                <Button onClick={handleSaveQuery} disabled={!saveName.trim()}>Sauvegarder</Button>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Résultats */}
        <div className="lg:col-span-2">
          <Card className="card-gradient border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Search className="w-4 h-4 text-primary" />
                Résultats {results && <span className="text-muted-foreground font-normal">({results.count} trouvés, {results.returned} affichés)</span>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!results ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Search className="w-10 h-10 mx-auto mb-3 opacity-20" />
                  <p className="font-medium">Prêt pour la chasse</p>
                  <p className="text-xs mt-1">Définissez vos filtres et lancez la recherche</p>
                </div>
              ) : results.results.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>Aucun log correspondant aux critères</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {results.results.map((log: NormalizedLog, i) => (
                    <motion.div
                      key={log.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: Math.min(i * 0.03, 0.5) }}
                      className="p-3 rounded-lg border border-border/30 bg-secondary/20 hover:bg-secondary/30 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${SEVERITY_COLORS[log.severity] ?? "bg-secondary"}`}>
                              {log.severity?.toUpperCase()}
                            </span>
                            <span className="text-sm font-medium text-foreground">{log.action}</span>
                            <Badge variant="outline" className="text-[10px]">{log.source_type}</Badge>
                          </div>
                          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                            {log.user_email && <span>👤 {log.user_email}</span>}
                            {log.source_ip && <span>🌐 {log.source_ip}</span>}
                            {log.geo_country_code && (
                              <FlagBadge code={log.geo_country_code} label={log.geo_country ?? log.geo_country_code} />
                            )}
                          </div>
                        </div>
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString("fr-FR") : "—"}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Requêtes sauvegardées */}
        <Card className="card-gradient border-border/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-muted-foreground" />
              Requêtes sauvegardées
            </CardTitle>
          </CardHeader>
          <CardContent>
            {queriesLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <div key={i} className="h-16 bg-muted rounded animate-pulse" />)}
              </div>
            ) : savedQueries.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                Aucune requête sauvegardée
              </p>
            ) : (
              <div className="space-y-2">
                {savedQueries.map((q) => (
                  <div key={q.id} className="p-3 rounded-lg border border-border/30 bg-secondary/20">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-foreground truncate">{q.name}</p>
                        {q.mitre_tactic && (
                          <p className="text-[10px] text-muted-foreground">{q.mitre_tactic}</p>
                        )}
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {q.run_count} exécution{q.run_count !== 1 ? "s" : ""}
                          {q.last_results_count > 0 && (
                            <span>· {q.last_results_count} résultat{q.last_results_count !== 1 ? "s" : ""}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-1 ml-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => executeQueryMutation.mutate(q.id)}
                          className="text-primary hover:text-primary p-1"
                        >
                          <Play className="w-3 h-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => { if (confirm("Supprimer ?")) deleteMutation.mutate(q.id); }}
                          className="text-muted-foreground hover:text-red-400 p-1"
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
