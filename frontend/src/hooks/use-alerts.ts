import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi, type AlertsQueryParams } from "@/lib/api";
import toast from "react-hot-toast";
import type { Alert } from "@/types";

export function useAlerts(params: AlertsQueryParams = {}) {
  return useQuery({
    queryKey: ["alerts", params],
    queryFn: () => alertsApi.getAlerts(params),
    staleTime: 30_000,
  });
}

export function useAlertStats() {
  return useQuery({
    queryKey: ["alert-stats"],
    queryFn: () => alertsApi.getStats(),
    staleTime: 60_000,
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Partial<Alert> }) =>
      alertsApi.updateAlert(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["alert-stats"] });
    },
    onError: () => {
      toast.error("Erreur lors de la mise à jour");
    },
  });
}
