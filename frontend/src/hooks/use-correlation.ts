import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { correlationApi } from "@/lib/api";
import type { CorrelationRule } from "@/types";
import toast from "react-hot-toast";

export function useCorrelationRules() {
  return useQuery({
    queryKey: ["correlation-rules"],
    queryFn: () => correlationApi.getRules(),
    staleTime: 60_000,
  });
}

export function useToggleRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => correlationApi.toggleRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["correlation-rules"] });
    },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });
}

export function useCreateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rule: Partial<CorrelationRule>) => correlationApi.createRule(rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["correlation-rules"] });
      toast.success("Règle créée");
    },
    onError: () => toast.error("Erreur lors de la création"),
  });
}

export function useUpdateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rule }: { id: number; rule: Partial<CorrelationRule> }) =>
      correlationApi.updateRule(id, rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["correlation-rules"] });
      toast.success("Règle mise à jour");
    },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });
}
