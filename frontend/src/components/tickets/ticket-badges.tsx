import { Badge } from "@/components/ui/badge";
import { AlertTriangle, ArrowUp, Minus, ArrowDown } from "lucide-react";
import type { TicketPriority, TicketStatus } from "@/types";
import { cn } from "@/lib/utils";

const PRIORITY_META: Record<TicketPriority, { label: string; variant: "danger" | "warning" | "info" | "secondary"; icon: React.ElementType }> = {
  critical: { label: "Critique", variant: "danger", icon: AlertTriangle },
  high: { label: "Élevée", variant: "warning", icon: ArrowUp },
  medium: { label: "Moyenne", variant: "info", icon: Minus },
  low: { label: "Faible", variant: "secondary", icon: ArrowDown },
};

export function TicketPriorityBadge({ priority, className }: { priority: TicketPriority; className?: string }) {
  const meta = PRIORITY_META[priority];
  const Icon = meta.icon;
  return (
    <Badge variant={meta.variant} className={cn("gap-1", className)}>
      <Icon className="w-3 h-3" />
      {meta.label}
    </Badge>
  );
}

export const TICKET_STATUS_META: Record<TicketStatus, { label: string; color: string; dot: string }> = {
  open: { label: "Ouvert", color: "text-blue-400", dot: "bg-blue-400" },
  in_progress: { label: "En cours", color: "text-amber-400", dot: "bg-amber-400" },
  pending: { label: "En attente", color: "text-purple-400", dot: "bg-purple-400" },
  resolved: { label: "Résolu", color: "text-emerald-400", dot: "bg-emerald-400" },
  closed: { label: "Fermé", color: "text-gray-400", dot: "bg-gray-400" },
};

export function TicketStatusBadge({ status, className }: { status: TicketStatus; className?: string }) {
  const meta = TICKET_STATUS_META[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", meta.color, className)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}
