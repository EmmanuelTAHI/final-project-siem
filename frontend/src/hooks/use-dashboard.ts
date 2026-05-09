import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => dashboardApi.getSummary(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useTimeline(period: "24h" | "7d" | "30d") {
  return useQuery({
    queryKey: ["dashboard-timeline", period],
    queryFn: () => dashboardApi.getTimeline(period),
    staleTime: 60_000,
  });
}

export function useTopThreats() {
  return useQuery({
    queryKey: ["dashboard-top-threats"],
    queryFn: () => dashboardApi.getTopThreats(),
    staleTime: 120_000,
  });
}

export function useGeoMap() {
  return useQuery({
    queryKey: ["dashboard-geo"],
    queryFn: () => dashboardApi.getGeoMap(),
    staleTime: 120_000,
  });
}
