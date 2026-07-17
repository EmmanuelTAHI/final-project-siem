"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  Search,
  Ticket as TicketIcon,
  Clock,
  UserX,
  ListChecks,
  Timer,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useTickets, useTicket, useTicketStats, useUpdateTicket } from "@/hooks/use-tickets";
import { TicketCard } from "@/components/tickets/ticket-card";
import { TicketDetailPanel } from "@/components/tickets/ticket-detail-panel";
import { CreateTicketModal } from "@/components/tickets/create-ticket-modal";
import { TICKET_STATUS_META } from "@/components/tickets/ticket-badges";
import { cn, formatNumber } from "@/lib/utils";
import type { Ticket, TicketPriority, TicketStatus } from "@/types";
import toast from "react-hot-toast";

const COLUMNS: TicketStatus[] = ["open", "in_progress", "pending", "resolved", "closed"];

type QuickFilter = "all" | "unassigned" | "overdue" | "mine";

export default function TicketsPage() {
  const [search, setSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<TicketStatus | null>(null);

  const { data: stats } = useTicketStats();
  const { data: ticketsData, isFetching } = useTickets({
    search: search || undefined,
    priority: priorityFilter !== "all" ? priorityFilter : undefined,
    unassigned: quickFilter === "unassigned" ? true : undefined,
    overdue: quickFilter === "overdue" ? true : undefined,
    page_size: 200,
    ordering: "-created_at",
  });
  const updateMutation = useUpdateTicket();
  // Le détail complet (commentaires + activité) n'est PAS inclus dans le
  // serializer de liste (plus léger pour le board) — on le recharge à part
  // à l'ouverture du panneau, plutôt que de réutiliser la ligne "brève".
  const { data: selectedTicketDetail } = useTicket(selectedTicketId);

  const tickets = ticketsData?.results ?? [];

  const byColumn = useMemo(() => {
    const map: Record<TicketStatus, Ticket[]> = { open: [], in_progress: [], pending: [], resolved: [], closed: [] };
    for (const t of tickets) map[t.status]?.push(t);
    return map;
  }, [tickets]);

  const handleDragStart = (e: React.DragEvent, ticket: Ticket) => {
    setDraggingId(ticket.id);
    e.dataTransfer.setData("text/plain", ticket.id);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragEnd = () => {
    setDraggingId(null);
    setDragOverColumn(null);
  };

  const handleDrop = async (e: React.DragEvent, status: TicketStatus) => {
    e.preventDefault();
    const ticketId = e.dataTransfer.getData("text/plain");
    setDragOverColumn(null);
    setDraggingId(null);
    const ticket = tickets.find((t) => t.id === ticketId);
    if (!ticket || ticket.status === status) return;
    try {
      await updateMutation.mutateAsync({ id: ticketId, updates: { status } });
      toast.success(`${ticket.display_id} → ${TICKET_STATUS_META[status].label}`);
    } catch {
      toast.error("Erreur lors du changement de statut.");
    }
  };

  const statCards = [
    { label: "Ouverts", value: stats?.open_count ?? 0, icon: ListChecks, color: "text-blue-400" },
    { label: "Non assignés", value: stats?.unassigned_count ?? 0, icon: UserX, color: "text-amber-400" },
    { label: "En retard", value: stats?.overdue_count ?? 0, icon: Clock, color: "text-red-400" },
    { label: "MTTR moyen", value: stats?.mttr_hours != null ? `${stats.mttr_hours}h` : "—", icon: Timer, color: "text-emerald-400" },
  ];

  return (
    <div className="page p-4 lg:p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground flex items-center gap-2">
            <TicketIcon className="w-5 h-5 text-primary" />
            Tickets
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {formatNumber(stats?.total ?? 0)} ticket{(stats?.total ?? 0) > 1 ? "s" : ""} au total
            {isFetching && " · actualisation…"}
          </p>
        </div>
        <button className="btn btn-primary gap-2" onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4" />
          Créer un ticket
        </button>
      </motion.div>

      {/* Stats bar */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.05 }} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <div key={s.label} className="rounded-xl border border-border p-4" style={{ background: "hsl(var(--card))" }}>
            <div className="flex items-center gap-2 mb-2">
              <s.icon className={cn("w-4 h-4", s.color)} />
              <span className="text-xs text-muted-foreground">{s.label}</span>
            </div>
            <p className="text-2xl font-bold text-foreground">{s.value}</p>
          </div>
        ))}
      </motion.div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Rechercher un ticket…" className="pl-9 h-9 text-sm" />
        </div>
        <Select value={priorityFilter} onValueChange={setPriorityFilter}>
          <SelectTrigger className="h-9 text-sm w-[160px]">
            <SelectValue placeholder="Priorité" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes priorités</SelectItem>
            {(["critical", "high", "medium", "low"] as TicketPriority[]).map((p) => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex gap-1.5">
          {([
            { key: "all", label: "Tous" },
            { key: "unassigned", label: "Non assignés" },
            { key: "overdue", label: "En retard" },
          ] as { key: QuickFilter; label: string }[]).map((f) => (
            <button
              key={f.key}
              onClick={() => setQuickFilter(f.key)}
              className={cn(
                "text-xs px-3 py-1.5 rounded-lg border transition-colors",
                quickFilter === f.key ? "border-primary/40 bg-primary/10 text-primary font-medium" : "border-border text-muted-foreground hover:text-foreground"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Kanban board */}
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-3 items-start">
        {COLUMNS.map((status) => {
          const meta = TICKET_STATUS_META[status];
          const columnTickets = byColumn[status];
          return (
            <div
              key={status}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOverColumn(status);
              }}
              onDragLeave={() => setDragOverColumn((c) => (c === status ? null : c))}
              onDrop={(e) => handleDrop(e, status)}
              className={cn(
                "rounded-xl border border-border p-2.5 space-y-2.5 min-h-[200px] transition-colors",
                dragOverColumn === status && "border-primary/50 bg-primary/5"
              )}
              style={{ background: "color-mix(in srgb, var(--card, hsl(var(--card))) 60%, transparent)" }}
            >
              <div className="flex items-center justify-between px-1 pt-1">
                <div className="flex items-center gap-1.5">
                  <span className={cn("w-1.5 h-1.5 rounded-full", meta.dot)} />
                  <span className="text-xs font-semibold text-foreground">{meta.label}</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">{columnTickets.length}</span>
              </div>
              <div className="space-y-2">
                {columnTickets.map((t) => (
                  <TicketCard
                    key={t.id}
                    ticket={t}
                    onClick={() => setSelectedTicketId(t.id)}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                    dragging={draggingId === t.id}
                  />
                ))}
                {columnTickets.length === 0 && (
                  <p className="text-[11px] text-muted-foreground text-center py-6">Aucun ticket</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <CreateTicketModal open={showCreateModal} onClose={() => setShowCreateModal(false)} />
      <TicketDetailPanel ticket={selectedTicketDetail ?? null} onClose={() => setSelectedTicketId(null)} />
    </div>
  );
}
