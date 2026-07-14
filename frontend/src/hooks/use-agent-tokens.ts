import { useQuery } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api";

export function useAgentTokens() {
  return useQuery({
    queryKey: ["agent-enrollment-tokens"],
    queryFn: () => agentsApi.list(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
