import { keepPreviousData, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi, type AlertsQueryParams } from "@/lib/api";
import { useRealtimeStore } from "@/stores/realtime-store";
import toast from "react-hot-toast";
import type { Alert } from "@/types";

export function useAlerts(params: AlertsQueryParams = {}) {
  const wsConnected = useRealtimeStore((s) => s.connected);
  return useQuery({
    queryKey: ["alerts", params],
    queryFn: () => alertsApi.getAlerts(params),
    // Les nouveautés arrivent par WebSocket (insertion directe dans le cache) ;
    // le polling ne sert que de filet de sécurité quand le socket est coupé.
    refetchInterval: wsConnected ? false : 15_000,
    staleTime: 10_000,
    // Pendant la frappe dans la recherche, garde la liste précédente affichée
    // au lieu d'un flash vide à chaque requête.
    placeholderData: keepPreviousData,
  });
}

export function useAlert(id: number, enabled = true) {
  return useQuery({
    queryKey: ["alert", id],
    queryFn: () => alertsApi.getAlert(id),
    enabled: enabled && !!id,
    staleTime: 5_000,
  });
}

export function useAlertStats() {
  const wsConnected = useRealtimeStore((s) => s.connected);
  return useQuery({
    queryKey: ["alert-stats"],
    queryFn: () => alertsApi.getStats(),
    refetchInterval: wsConnected ? false : 30_000,
    staleTime: 15_000,
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Partial<Alert> }) =>
      alertsApi.updateAlert(id, updates),
    onSuccess: (updated, { id }) => {
      // Écrit la réponse complète directement dans le cache du détail pour
      // un affichage immédiat et stable (pas de « flash » puis disparition).
      queryClient.setQueryData(["alert", id], updated);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["alert-stats"] });
      queryClient.invalidateQueries({ queryKey: ["alert", id] });
    },
    onError: () => {
      toast.error("Erreur lors de la mise à jour");
    },
  });
}

export function useAddAlertComment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content }: { id: number; content: string }) =>
      alertsApi.addComment(id, content),
    onSuccess: (updated, { id }) => {
      queryClient.setQueryData(["alert", id], updated);
      queryClient.invalidateQueries({ queryKey: ["alert", id] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Commentaire ajouté");
    },
    onError: () => {
      toast.error("Erreur lors de l'ajout du commentaire");
    },
  });
}
