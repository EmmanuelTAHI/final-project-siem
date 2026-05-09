import { useQuery } from "@tanstack/react-query";
import { logsApi, type LogsQueryParams } from "@/lib/api";

export function useLogs(params: LogsQueryParams = {}) {
  return useQuery({
    queryKey: ["logs", params],
    queryFn: () => logsApi.getLogs(params),
    staleTime: 30_000,
  });
}
