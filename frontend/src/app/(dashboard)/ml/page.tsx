"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Play,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  BarChart3,
  Cpu,
  Target,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,

} from "recharts";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { formatDate, timeAgo, formatPercent } from "@/lib/utils";
import { useMLModels, useMLPredictions, useTrainModel } from "@/hooks/use-ml";
import toast from "react-hot-toast";

export default function MLPage() {
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [contamination, setContamination] = useState(5);

  const { data: models } = useMLModels();
  const { data: predictionsData } = useMLPredictions(true);
  const trainMutation = useTrainModel();

  const model = models?.[0] ?? {
    name: "IsolationForest Log+",
    version: "—",
    algorithm: "Isolation Forest",
    accuracy: 0,
    precision: 0,
    recall: 0,
    f1_score: 0,
    contamination: 0.05,
    is_active: false,
    trained_at: new Date().toISOString(),
    training_samples: 0,
    features: [],
  };
  const predictions = predictionsData?.results?.slice(0, 15) ?? [];
  const isTraining = trainMutation.isPending;

  // Score distribution computed from real predictions
  const scoreDistribution = Array.from({ length: 20 }, (_, i) => {
    const low = i * 5;
    const high = low + 5;
    return {
      score: `${low}%`,
      count: predictions.filter(
        (p) => p.anomaly_score * 100 >= low && p.anomaly_score * 100 < high
      ).length,
      isAnomaly: low >= 80,
    };
  });

  const handleTrain = () => {
    setTrainingProgress(0);
    toast("Entraînement lancé…", { icon: "🤖" });
    trainMutation.mutate(contamination, {
      onSuccess: () => {
        setTrainingProgress(100);
        toast.success("Modèle entraîné avec succès !");
      },
      onError: () => {
        setTrainingProgress(0);
        toast.error("Erreur lors de l'entraînement");
      },
    });
  };

  return (
    <div className="p-4 lg:p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-foreground">Machine Learning</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Détection d&apos;anomalies par Isolation Forest</p>
      </motion.div>

      {/* Model status card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-xl border border-border p-5"
        style={{ background: "hsl(var(--card))" }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          {/* Model info */}
          <div className="flex items-center gap-4">
            <div
              className="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: "rgba(139,92,246,0.15)", border: "1px solid rgba(139,92,246,0.3)" }}
            >
              <Brain className="w-7 h-7 text-purple-400" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-base font-bold text-foreground">{model.name}</h3>
                <Badge variant="success" className="text-[10px]">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse" />
                  Actif
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Version {model.version} · Entraîné {timeAgo(model.trained_at)} · {model.training_samples.toLocaleString()} échantillons
              </p>
            </div>
          </div>

          {/* Metrics */}
          <div className="flex gap-6 flex-wrap">
            {[
              { label: "Précision", value: formatPercent(model.accuracy * 100), icon: Target },
              { label: "F1-Score", value: formatPercent(model.f1_score * 100), icon: TrendingUp },
              { label: "Recall", value: formatPercent(model.recall * 100), icon: BarChart3 },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="text-center">
                <div className="flex items-center gap-1 justify-center text-muted-foreground mb-1">
                  <Icon className="w-3 h-3" />
                  <span className="text-xs">{label}</span>
                </div>
                <p className="text-xl font-bold text-foreground">{value}</p>
              </div>
            ))}
          </div>

          {/* Train button */}
          <div className="flex flex-col gap-2 min-w-[180px]">
            <Button
              onClick={handleTrain}
              disabled={isTraining}
              loading={isTraining}
              className="gap-2"
              style={{ background: isTraining ? undefined : "linear-gradient(135deg, #8b5cf6, #6d28d9)" }}
            >
              <Play className="w-3.5 h-3.5" />
              {isTraining ? "Entraînement..." : "Lancer l'entraînement"}
            </Button>

            {/* Contamination slider */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground whitespace-nowrap">Contamination: {contamination}%</span>
              <input
                type="range"
                min={1}
                max={20}
                value={contamination}
                onChange={(e) => setContamination(Number(e.target.value))}
                className="flex-1 h-1 appearance-none cursor-pointer rounded-full"
                style={{ accentColor: "#8b5cf6" }}
              />
            </div>
          </div>
        </div>

        {/* Training progress */}
        {isTraining && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-4 pt-4 border-t border-border"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-foreground">Progression de l&apos;entraînement</span>
              <span className="text-xs text-muted-foreground">{trainingProgress}%</span>
            </div>
            <Progress value={trainingProgress} indicatorClassName="bg-purple-500" />
            <div className="flex items-center gap-2 mt-2">
              <Cpu className="w-3 h-3 text-purple-400 animate-spin" />
              <span className="text-xs text-muted-foreground">
                {trainingProgress < 30 ? "Préparation des données..." :
                 trainingProgress < 60 ? "Construction de l'arbre..." :
                 trainingProgress < 90 ? "Calcul des scores..." :
                 "Finalisation du modèle..."}
              </span>
            </div>
          </motion.div>
        )}

        {/* Features */}
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground mb-2">Features utilisées :</p>
          <div className="flex flex-wrap gap-2">
            {model.features.map((f) => (
              <span key={f} className="text-xs px-2 py-0.5 rounded bg-secondary border border-border text-muted-foreground font-mono">
                {f}
              </span>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Score distribution */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-xl border border-border p-5"
          style={{ background: "hsl(var(--card))" }}
        >
          <h3 className="text-sm font-semibold text-foreground mb-1">Distribution des scores d&apos;anomalie</h3>
          <p className="text-xs text-muted-foreground mb-4">Fréquence par plage de score</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={scoreDistribution} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} opacity={0.5} />
              <XAxis dataKey="score" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }}
              />
              <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                {scoreDistribution.map((entry, i) => (
                  <rect key={i} fill={entry.isAnomaly ? "#8b5cf6" : "#3b82f6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-2">
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-blue-500" /><span className="text-xs text-muted-foreground">Normal</span></div>
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-purple-500" /><span className="text-xs text-muted-foreground">Anomalie</span></div>
          </div>
        </motion.div>

        {/* Predictions summary */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border border-border p-5 flex flex-col justify-center"
          style={{ background: "hsl(var(--card))" }}
        >
          <h3 className="text-sm font-semibold text-foreground mb-1">Résumé des prédictions</h3>
          <p className="text-xs text-muted-foreground mb-4">Répartition des {predictions.length} dernières</p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Score moyen", value: predictions.length ? `${(predictions.reduce((s, p) => s + p.anomaly_score, 0) / predictions.length * 100).toFixed(1)}%` : "—", color: "#8b5cf6" },
              { label: "Score max", value: predictions.length ? `${(Math.max(...predictions.map(p => p.anomaly_score)) * 100).toFixed(1)}%` : "—", color: "#ef4444" },
              { label: "Anomalies > 80%", value: String(predictions.filter(p => p.anomaly_score >= 0.8).length), color: "#f59e0b" },
              { label: "Anomalies > 50%", value: String(predictions.filter(p => p.anomaly_score >= 0.5).length), color: "#3b82f6" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg bg-secondary/40 px-3 py-3">
                <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
                <p className="text-xl font-bold" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Predictions table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="rounded-xl border border-border"
        style={{ background: "hsl(var(--card))" }}
      >
        <div className="p-5 pb-3 border-b border-border flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Anomalies récentes détectées</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{predictions.length} dernières prédictions</p>
          </div>
          <Badge variant="critical" className="text-xs">
            <AlertTriangle className="w-3 h-3 mr-1" />
            {predictions.length} anomalies
          </Badge>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Source</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Action</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Utilisateur</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Score</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Top Feature</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Détecté</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Version</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((pred, i) => (
                <motion.tr
                  key={pred.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 + i * 0.02 }}
                  className="border-b border-border hover:bg-secondary/50 transition-colors"
                >
                  <td className="px-4 py-2.5">
                    <span className="px-1.5 py-0.5 rounded bg-secondary border border-border">
                      {pred.log?.source_type || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-medium text-foreground">{pred.log?.action || "—"}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{pred.log?.user_email || "—"}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Progress
                        value={pred.anomaly_score * 100}
                        className="w-16 h-1.5"
                        indicatorClassName="bg-purple-500"
                      />
                      <span className="font-mono font-bold text-purple-400">
                        {(pred.anomaly_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground font-mono">
                    {pred.top_features[0]?.feature || "—"}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{timeAgo(pred.prediction_time)}</td>
                  <td className="px-4 py-2.5">
                    <span className="font-mono text-xs text-muted-foreground">v{pred.model_version}</span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
