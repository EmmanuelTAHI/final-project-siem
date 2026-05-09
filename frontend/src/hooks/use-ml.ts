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

export function useTrainModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contamination: number) => mlApi.trainModel({ contamination: contamination / 100 }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
      toast.success("Entraînement lancé en arrière-plan");
    },
    onError: () => toast.error("Erreur lors du lancement de l'entraînement"),
  });
}
