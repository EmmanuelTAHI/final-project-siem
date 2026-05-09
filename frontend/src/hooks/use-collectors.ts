import { useQuery } from "@tanstack/react-query";
import { collectorsApi } from "@/lib/api";

export function useConnectors() {
  return useQuery({
    queryKey: ["connectors"],
    queryFn: () => collectorsApi.getConnectors(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useCollectorJobs() {
  return useQuery({
    queryKey: ["collector-jobs"],
    queryFn: () => collectorsApi.getJobs(),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}
