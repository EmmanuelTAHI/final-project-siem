import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ticketsApi, type TicketsQueryParams, type TicketCreateInput } from "@/lib/api";
import type { Ticket } from "@/types";

export function useTickets(params: TicketsQueryParams = {}) {
  return useQuery({
    queryKey: ["tickets", params],
    queryFn: () => ticketsApi.getTickets(params),
    staleTime: 15_000,
  });
}

export function useTicket(id: string | null) {
  return useQuery({
    queryKey: ["ticket", id],
    queryFn: () => ticketsApi.getTicket(id as string),
    enabled: !!id,
  });
}

export function useTicketStats() {
  return useQuery({
    queryKey: ["tickets-stats"],
    queryFn: () => ticketsApi.getStats(),
    staleTime: 15_000,
  });
}

export function useAssignableUsers() {
  return useQuery({
    queryKey: ["tickets-assignable-users"],
    queryFn: () => ticketsApi.getAssignableUsers(),
    staleTime: 60_000,
  });
}

export function useCreateTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TicketCreateInput) => ticketsApi.createTicket(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["tickets-stats"] });
    },
  });
}

export interface TicketUpdateInput extends Partial<Omit<Ticket, "assignee">> {
  assignee?: string | null;
}

export function useUpdateTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: TicketUpdateInput }) =>
      ticketsApi.updateTicket(id, updates),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["tickets-stats"] });
      qc.setQueryData(["ticket", updated.id], updated);
    },
  });
}

export function useDeleteTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ticketsApi.deleteTicket(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["tickets-stats"] });
    },
  });
}

export function useAddTicketComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) => ticketsApi.addComment(id, content),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.setQueryData(["ticket", updated.id], updated);
    },
  });
}

export function useLinkAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ticketId, alertId }: { ticketId: string; alertId: string }) =>
      ticketsApi.linkAlert(ticketId, alertId),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.setQueryData(["ticket", updated.id], updated);
    },
  });
}

export function useUnlinkAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ticketId, alertId }: { ticketId: string; alertId: string }) =>
      ticketsApi.unlinkAlert(ticketId, alertId),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.setQueryData(["ticket", updated.id], updated);
    },
  });
}
