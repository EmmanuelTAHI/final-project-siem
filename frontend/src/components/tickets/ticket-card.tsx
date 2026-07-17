"use client";

import { MessageSquare, Paperclip, Clock, AlertOctagon } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TicketPriorityBadge } from "./ticket-badges";
import { getInitials, timeAgo, cn } from "@/lib/utils";
import type { Ticket } from "@/types";

interface TicketCardProps {
  ticket: Ticket;
  onClick: () => void;
  onDragStart: (e: React.DragEvent, ticket: Ticket) => void;
  onDragEnd: () => void;
  dragging: boolean;
}

export function TicketCard({ ticket, onClick, onDragStart, onDragEnd, dragging }: TicketCardProps) {
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, ticket)}
      onDragEnd={onDragEnd}
      onClick={onClick}
      className={cn(
        "rounded-lg border border-border bg-card p-3 space-y-2.5 cursor-pointer transition-all hover:border-primary/40 hover:shadow-md",
        dragging && "opacity-40"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-[10px] font-mono text-muted-foreground">{ticket.display_id}</span>
        <TicketPriorityBadge priority={ticket.priority} className="text-[10px] px-1.5 py-0" />
      </div>

      <p className="text-xs font-medium text-foreground leading-snug line-clamp-2">{ticket.title}</p>

      {ticket.alert_title && (
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <AlertOctagon className="w-3 h-3 flex-shrink-0 text-orange-400" />
          <span className="truncate">{ticket.alert_title}</span>
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-2.5 text-[10px] text-muted-foreground">
          {ticket.comments_count > 0 && (
            <span className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              {ticket.comments_count}
            </span>
          )}
          {ticket.is_overdue && (
            <span className="flex items-center gap-1 text-red-400 font-medium">
              <Clock className="w-3 h-3" />
              En retard
            </span>
          )}
          {!ticket.is_overdue && (
            <span className="flex items-center gap-1">
              <Paperclip className="w-3 h-3 opacity-0" />
              {timeAgo(ticket.created_at)}
            </span>
          )}
        </div>
        {ticket.assignee ? (
          <Avatar className="w-5 h-5" title={ticket.assignee.full_name}>
            <AvatarFallback className="text-[9px]">{getInitials(ticket.assignee.full_name)}</AvatarFallback>
          </Avatar>
        ) : (
          <span className="text-[10px] text-muted-foreground italic">Non assigné</span>
        )}
      </div>
    </div>
  );
}
