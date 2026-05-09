"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Shield,
  User,
  Globe,
  Clock,
  Tag,
  MessageSquare,
  Send,
  CheckCircle,
  XCircle,
  UserPlus,
  FileText,
  ChevronDown,
} from "lucide-react";
import { SeverityBadge } from "./severity-badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn, timeAgo, formatDate, statusColors, statusLabels } from "@/lib/utils";
import type { Alert, AlertStatus } from "@/types";
import toast from "react-hot-toast";
import { alertsApi } from "@/lib/api";

interface AlertDetailPanelProps {
  alert: Alert | null;
  onClose: () => void;
  onUpdate: (updated: Alert) => void;
}

export function AlertDetailPanel({ alert, onClose, onUpdate }: AlertDetailPanelProps) {
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [expandedLog, setExpandedLog] = useState<number | null>(null);

  const handleStatusChange = async (status: AlertStatus) => {
    if (!alert) return;
    try {
      // Use mock in case API not available
      onUpdate({ ...alert, status });
      toast.success(`Statut mis à jour : ${statusLabels[status]}`);
    } catch {
      toast.error("Erreur lors de la mise à jour");
    }
  };

  const handleAddComment = async () => {
    if (!alert || !comment.trim()) return;
    setIsSubmitting(true);
    try {
      const updated = await alertsApi.addComment(alert.id, comment.trim());
      onUpdate(updated);
      setComment("");
      toast.success("Commentaire ajouté");
    } catch {
      toast.error("Erreur lors de l'ajout du commentaire");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolve = () => handleStatusChange("resolved");
  const handleFalsePositive = () => handleStatusChange("false_positive");
  const handleInProgress = () => handleStatusChange("in_progress");

  return (
    <AnimatePresence>
      {alert && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-xl flex flex-col border-l border-border"
            style={{ background: "hsl(var(--card))" }}
          >
            {/* Header */}
            <div className="flex items-start gap-3 p-5 border-b border-border">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <SeverityBadge severity={alert.severity} />
                  <span
                    className={cn(
                      "text-xs font-medium px-2 py-0.5 rounded border",
                      statusColors[alert.status]
                    )}
                  >
                    {statusLabels[alert.status]}
                  </span>
                </div>
                <h2 className="text-sm font-semibold text-foreground leading-snug">{alert.title}</h2>
                <p className="text-xs text-muted-foreground mt-1">{timeAgo(alert.created_at)}</p>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable content */}
            <ScrollArea className="flex-1">
              <div className="p-5 space-y-5">
                {/* Description */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Description</p>
                  <p className="text-sm text-foreground leading-relaxed">{alert.description}</p>
                </div>

                {/* Details grid */}
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { icon: Globe, label: "IP Source", value: alert.source_ip, mono: true },
                    { icon: Globe, label: "IP Dest.", value: alert.destination_ip || "—", mono: true },
                    { icon: User, label: "Utilisateur", value: alert.user_email || "—" },
                    { icon: Shield, label: "Règle", value: alert.rule_name },
                    { icon: Clock, label: "Créé", value: formatDate(alert.created_at, "dd/MM/yyyy HH:mm") },
                    { icon: Clock, label: "Mis à jour", value: formatDate(alert.updated_at, "dd/MM/yyyy HH:mm") },
                  ].map(({ icon: Icon, label, value, mono }) => (
                    <div key={label} className="flex items-start gap-2 p-2.5 rounded-lg bg-secondary/40">
                      <Icon className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-[10px] text-muted-foreground">{label}</p>
                        <p className={cn("text-xs font-medium text-foreground truncate", mono && "font-mono")}>
                          {value}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* MITRE tags */}
                {(alert.mitre_tactic || alert.mitre_technique) && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
                      <Tag className="w-3 h-3" /> MITRE ATT&CK
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {alert.mitre_tactic && (
                        <span className="text-xs px-2 py-1 rounded border border-blue-500/30 bg-blue-500/10 text-blue-400">
                          {alert.mitre_tactic}
                        </span>
                      )}
                      {alert.mitre_technique && (
                        <span className="text-xs px-2 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 font-mono">
                          {alert.mitre_technique}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Change status */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Changer le statut</p>
                  <Select value={alert.status} onValueChange={(v) => handleStatusChange(v as AlertStatus)}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="open">Ouvert</SelectItem>
                      <SelectItem value="in_progress">En cours</SelectItem>
                      <SelectItem value="resolved">Résolu</SelectItem>
                      <SelectItem value="false_positive">Faux positif</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Quick actions */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Actions rapides</p>
                  <div className="flex gap-2 flex-wrap">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleInProgress}
                      className="text-xs h-7 gap-1.5"
                    >
                      <UserPlus className="w-3 h-3" />
                      Prendre en charge
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleResolve}
                      className="text-xs h-7 gap-1.5 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                    >
                      <CheckCircle className="w-3 h-3" />
                      Résoudre
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleFalsePositive}
                      className="text-xs h-7 gap-1.5 border-gray-500/30 text-gray-400 hover:bg-gray-500/10"
                    >
                      <XCircle className="w-3 h-3" />
                      Faux positif
                    </Button>
                  </div>
                </div>

                {/* Log sources */}
                {alert.log_sources.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
                      <FileText className="w-3 h-3" /> Logs sources ({alert.log_sources.length})
                    </p>
                    <div className="space-y-2">
                      {alert.log_sources.map((log) => (
                        <div key={log.id} className="rounded-lg border border-border overflow-hidden">
                          <button
                            className="w-full flex items-center justify-between px-3 py-2 bg-secondary/40 text-left"
                            onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-foreground">{log.source_type}</span>
                              <span className="text-[10px] text-muted-foreground">•</span>
                              <span className="text-[10px] text-muted-foreground">{log.action}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-muted-foreground">{timeAgo(log.timestamp)}</span>
                              <ChevronDown
                                className={cn(
                                  "w-3 h-3 text-muted-foreground transition-transform",
                                  expandedLog === log.id && "rotate-180"
                                )}
                              />
                            </div>
                          </button>
                          <AnimatePresence>
                            {expandedLog === log.id && (
                              <motion.div
                                initial={{ height: 0 }}
                                animate={{ height: "auto" }}
                                exit={{ height: 0 }}
                                className="overflow-hidden"
                              >
                                <pre className="p-3 text-[10px] font-mono text-muted-foreground overflow-x-auto bg-background/50">
                                  {JSON.stringify(log.raw_data, null, 2)}
                                </pre>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Comments */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1">
                    <MessageSquare className="w-3 h-3" /> Commentaires ({alert.comments.length})
                  </p>

                  {/* Existing comments */}
                  <div className="space-y-3 mb-3">
                    {alert.comments.map((c) => (
                      <div key={c.id} className="flex gap-2.5">
                        <div className="w-6 h-6 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0 text-[10px] font-bold text-primary">
                          {c.author.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-foreground">{c.author}</span>
                            <span className="text-[10px] text-muted-foreground">{timeAgo(c.created_at)}</span>
                          </div>
                          <p className="text-xs text-muted-foreground leading-relaxed">{c.content}</p>
                        </div>
                      </div>
                    ))}
                    {alert.comments.length === 0 && (
                      <p className="text-xs text-muted-foreground text-center py-4">Aucun commentaire</p>
                    )}
                  </div>

                  {/* Add comment */}
                  <div className="flex gap-2">
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="Ajouter un commentaire..."
                      rows={2}
                      className="flex-1 text-xs rounded-lg border border-border bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <Button
                      size="icon"
                      onClick={handleAddComment}
                      disabled={!comment.trim() || isSubmitting}
                      loading={isSubmitting}
                      className="self-end"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
