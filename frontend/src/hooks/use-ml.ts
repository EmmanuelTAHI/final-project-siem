import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { mlApi } from "@/lib/api";
import toast from "react-hot-toast";

export function useMLModels() {
  return useQuery({
    queryKey: ["ml-models"],
    queryFn: () => mlApi.getModels(),
    staleTime: 120_000,
  });
}

export function useMLPredictions(anomalyOnly = true) {
  return useQuery({
    queryKey: ["ml-predictions", anomalyOnly],
    queryFn: () => mlApi.getPredictions(anomalyOnly),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
}

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 200; // ~10 min

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Lance l'entraînement puis attend la fin RÉELLE (poll de
 * /api/ml/train/{task_id}/status/) avant de résoudre — le POST /train/
 * ne fait que mettre la tâche Celery en file (202 Accepted), pas
 * entraîner le modèle de façon synchrone.
 */
export function useTrainModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (contamination: number) => {
      const { task_id } = await mlApi.trainModel({ contamination: contamination / 100 });
      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
        await sleep(POLL_INTERVAL_MS);
        const status = await mlApi.getTrainStatus(task_id);
        if (status.status === "SUCCESS") return status;
        if (status.status === "FAILURE") throw new Error(status.error || "Entraînement échoué");
      }
      throw new Error("Délai d'attente dépassé pour l'entraînement");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
      toast.success("Modèle entraîné avec succès");
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : "Erreur lors de l'entraînement";
      toast.error(message);
    },
  });
}
