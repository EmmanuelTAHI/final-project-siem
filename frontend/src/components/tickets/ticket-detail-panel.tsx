"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Clock,
  User,
  AlertOctagon,
  MessageSquare,
  Send,
  History,
  Trash2,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TicketPriorityBadge, TicketStatusBadge } from "./ticket-badges";
import { cn, timeAgo, formatDate, getInitials } from "@/lib/utils";
import { useAssignableUsers, useUpdateTicket, useAddTicketComment, useDeleteTicket } from "@/hooks/use-tickets";
import { useAuthStore } from "@/stores/auth-store";
import type { Ticket, TicketPriority, TicketStatus } from "@/types";
import toast from "react-hot-toast";
import Link from "next/link";

interface TicketDetailPanelProps {
  ticket: Ticket | null;
  onClose: () => void;
}

const STATUS_OPTIONS: TicketStatus[] = ["open", "in_progress", "pending", "resolved", "closed"];
const PRIORITY_OPTIONS: TicketPriority[] = ["low", "medium", "high", "critical"];

export function TicketDetailPanel({ ticket, onClose }: TicketDetailPanelProps) {
  const [comment, setComment] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { user } = useAuthStore();
  const { data: users = [] } = useAssignableUsers();
  const updateMutation = useUpdateTicket();
  const commentMutation = useAddTicketComment();
  const deleteMutation = useDeleteTicket();

  if (!ticket) return null;

  const handleStatusChange = async (status: TicketStatus) => {
    try {
      await updateMutation.mutateAsync({ id: ticket.id, updates: { status } });
      toast.success(`Statut mis à jour`);
    } catch {
      toast.error("Erreur lors de la mise à jour du statut.");
    }
  };

  const handlePriorityChange = async (priority: TicketPriority) => {
    try {
      await updateMutation.mutateAsync({ id: ticket.id, updates: { priority } });
      toast.success("Priorité mise à jour");
    } catch {
      toast.error("Erreur lors de la mise à jour de la priorité.");
    }
  };

  const handleAssigneeChange = async (assigneeId: string) => {
    try {
      await updateMutation.mutateAsync({ id: ticket.id, updates: { assignee: assigneeId === "__none__" ? null : assigneeId } });
      toast.success("Assignation mise à jour");
    } catch {
      toast.error("Erreur lors de l'assignation.");
    }
  };

  const handleAddComment = async () => {
    if (!comment.trim()) return;
    try {
      await commentMutation.mutateAsync({ id: ticket.id, content: comment.trim() });
      setComment("");
      toast.success("Commentaire ajouté");
    } catch {
      toast.error("Erreur lors de l'ajout du commentaire.");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(ticket.id);
      toast.success(`${ticket.display_id} supprimé.`);
      setConfirmDelete(false);
      onClose();
    } catch {
      toast.error("Erreur lors de la suppression (réservé aux administrateurs).");
    }
  };

  // Fusionne commentaires + activités en un seul fil chronologique, façon
  // Jira/ServiceNow : on voit "qui a fait quoi et quand" dans l'ordre réel.
  const timeline = [
    ...(ticket.comments ?? []).map((c) => ({ type: "comment" as const, at: c.created_at, data: c })),
    ...(ticket.activities ?? []).filter((a) => a.action !== "commented").map((a) => ({ type: "activity" as const, at: a.created_at, data: a })),
  ].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());

  return (
    <AnimatePresence>
      {ticket && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />
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
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span className="text-xs font-mono text-muted-foreground">{ticket.display_id}</span>
                  <TicketStatusBadge status={ticket.status} />
                  <TicketPriorityBadge priority={ticket.priority} />
                </div>
                <h2 className="text-sm font-semibold text-foreground leading-snug">{ticket.title}</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Créé {timeAgo(ticket.created_at)}
                  {ticket.reporter && ` par ${ticket.reporter.full_name}`}
                </p>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                <X className="w-4 h-4" />
              </button>
            </div>

            <ScrollArea className="flex-1">
              <div className="p-5 space-y-5">
                {ticket.description && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Description</p>
                    <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{ticket.description}</p>
                  </div>
                )}

                {ticket.alert && (
                  <Link
                    href={`/alerts?ticket_alert=${ticket.alert}`}
                    className="flex items-center gap-2 p-2.5 rounded-lg bg-orange-500/10 border border-orange-500/20 text-xs text-orange-300 hover:bg-orange-500/15 transition-colors"
                  >
                    <AlertOctagon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="flex-1 truncate">Alerte liée : {ticket.alert_title}</span>
                    <ExternalLink className="w-3 h-3 flex-shrink-0" />
                  </Link>
                )}

                {/* Status / priority / assignee controls */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Statut</p>
                    <Select value={ticket.status} onValueChange={(v) => handleStatusChange(v as TicketStatus)}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUS_OPTIONS.map((s) => (
                          <SelectItem key={s} value={s}>
                            <TicketStatusBadge status={s} />
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Priorité</p>
                    <Select value={ticket.priority} onValueChange={(v) => handlePriorityChange(v as TicketPriority)}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PRIORITY_OPTIONS.map((p) => (
                          <SelectItem key={p} value={p}>
                            <TicketPriorityBadge priority={p} />
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5 col-span-2">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Assigné à</p>
                    <Select value={ticket.assignee?.id ?? "__none__"} onValueChange={handleAssigneeChange}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue placeholder="Non assigné" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">
                          <span className="text-muted-foreground">Non assigné</span>
                        </SelectItem>
                        {users.map((u) => (
                          <SelectItem key={u.id} value={u.id}>
                            {u.full_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {ticket.due_date && (
                  <div className={cn("flex items-center gap-2 p-2.5 rounded-lg bg-secondary/40 text-xs", ticket.is_overdue && "bg-red-500/10 text-red-400")}>
                    <Clock className="w-3.5 h-3.5 flex-shrink-0" />
                    Échéance : {formatDate(ticket.due_date, "dd/MM/yyyy HH:mm")}
                    {ticket.is_overdue && <span className="font-semibold">· En retard</span>}
                  </div>
                )}

                {/* Timeline : activité + commentaires fusionnés chronologiquement */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1">
                    <History className="w-3 h-3" /> Activité
                  </p>
                  <div className="space-y-3 mb-3">
                    {timeline.map((item, i) =>
                      item.type === "comment" ? (
                        <div key={`c-${item.data.id}`} className="flex gap-2.5">
                          <Avatar className="w-6 h-6 flex-shrink-0">
                            <AvatarFallback className="text-[10px]">
                              {getInitials(item.data.author_full_name ?? "?")}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-medium text-foreground">{item.data.author_full_name ?? "Utilisateur supprimé"}</span>
                              <span className="text-[10px] text-muted-foreground">{timeAgo(item.data.created_at)}</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed bg-secondary/30 rounded-lg px-2.5 py-2">{item.data.content}</p>
                          </div>
                        </div>
                      ) : (
                        <div key={`a-${item.data.id ?? i}`} className="flex items-center gap-2.5 pl-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-border flex-shrink-0" />
                          <p className="text-[11px] text-muted-foreground flex-1">
                            <span className="font-medium text-foreground">{item.data.actor_full_name ?? "Système"}</span>{" "}
                            {activityVerb(item.data.action)}
                            {item.data.from_value && item.data.to_value && (
                              <>
                                {" "}<span className="opacity-70">{item.data.from_value}</span> → <span className="font-medium">{item.data.to_value}</span>
                              </>
                            )}
                            {!item.data.from_value && item.data.to_value && <> <span className="font-medium">{item.data.to_value}</span></>}
                          </p>
                          <span className="text-[10px] text-muted-foreground flex-shrink-0">{timeAgo(item.data.created_at)}</span>
                        </div>
                      )
                    )}
                    {timeline.length === 0 && <p className="text-xs text-muted-foreground text-center py-4">Aucune activité pour le moment</p>}
                  </div>

                  <div className="flex gap-2">
                    <Textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="Ajouter un commentaire…"
                      rows={2}
                      className="flex-1"
                    />
                    <Button size="icon" onClick={handleAddComment} disabled={!comment.trim() || commentMutation.isPending} loading={commentMutation.isPending} className="self-end">
                      <Send className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>

                {user?.role === "admin" && (
                  <div className="pt-3 border-t border-border">
                    <Button variant="outline" size="sm" onClick={() => setConfirmDelete(true)} className="text-xs gap-1.5 text-destructive hover:text-destructive">
                      <Trash2 className="w-3 h-3" />
                      Supprimer ce ticket
                    </Button>
                  </div>
                )}
              </div>
            </ScrollArea>
          </motion.div>

          <ConfirmDialog
            open={confirmDelete}
            onClose={() => setConfirmDelete(false)}
            onConfirm={handleDelete}
            title="Supprimer le ticket"
            description={`Êtes-vous sûr de vouloir supprimer ${ticket.display_id} ? Cette action est irréversible.`}
            confirmLabel="Supprimer"
            loading={deleteMutation.isPending}
          />
        </>
      )}
    </AnimatePresence>
  );
}

function activityVerb(action: string): string {
  switch (action) {
    case "created":
      return "a créé le ticket ·";
    case "status_changed":
      return "a changé le statut :";
    case "priority_changed":
      return "a changé la priorité :";
    case "assigned":
      return "a réassigné :";
    case "updated":
      return "a mis à jour le ticket";
    default:
      return action;
  }
}
