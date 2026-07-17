import { useQuery } from "@tanstack/react-query";
import { logsApi, type LogsQueryParams } from "@/lib/api";

export function useLogs(params: LogsQueryParams = {}) {
  return useQuery({
    queryKey: ["logs", params],
    queryFn: () => logsApi.getLogs(params),
    staleTime: 30_000,
  });
}

// Séparé de useLogs : l'histogramme n'a pas besoin de pagination/tri, mais
// doit se recalculer sur les mêmes filtres (recherche, sévérité, plage de
// dates...) pour rester cohérent avec les résultats affichés dans le tableau.
export function useLogHistogram(params: LogsQueryParams = {}) {
  return useQuery({
    queryKey: ["logs-histogram", params],
    queryFn: () => logsApi.getHistogram(params),
    staleTime: 30_000,
  });
}
