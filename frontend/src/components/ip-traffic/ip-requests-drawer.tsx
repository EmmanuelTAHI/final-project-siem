"use client";

import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, Globe, Clock, ExternalLink } from "lucide-react";
import { logsApi } from "@/lib/api";
import { CountryFlag } from "@/components/common/country-flag";
import { countryName } from "@/lib/country-names";
import { timeAgo } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import type { IPTrafficEntry } from "@/types";

interface IPRequestsDrawerProps {
  entry: IPTrafficEntry | null;
  onClose: () => void;
}

export function IPRequestsDrawer({ entry, onClose }: IPRequestsDrawerProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["ip-traffic-requests", entry?.source_ip],
    queryFn: () => logsApi.getLogs({ source_ip: entry!.source_ip, page: 1 }),
    enabled: !!entry,
  });

  const logs = data?.results ?? [];

  return (
    <AnimatePresence>
      {entry && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-xl flex flex-col border-l border-border"
            style={{ background: "hsl(var(--card))" }}
          >
            <div className="flex items-start gap-3 p-5 border-b border-border">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Globe className="w-4 h-4 text-primary" />
                  <span className="text-sm font-mono font-semibold text-foreground">{entry.source_ip}</span>
                  {entry.is_known_threat && (
                    <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-[10px]">Menace connue</Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {entry.geo_country && <CountryFlag code={entry.geo_country} size="sm" showName={countryName(entry.geo_country)} />}
                  <span>·</span>
                  <span>{entry.count.toLocaleString()} requête(s) sur la période</span>
                </div>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 grid grid-cols-3 gap-3 border-b border-border">
              <div className="rounded-lg bg-secondary/40 p-2.5">
                <p className="text-[10px] text-muted-foreground">Succès</p>
                <p className="text-sm font-bold text-emerald-400 tabular-nums">{entry.success_count.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-secondary/40 p-2.5">
                <p className="text-[10px] text-muted-foreground">Échecs</p>
                <p className="text-sm font-bold text-red-400 tabular-nums">{entry.failure_count.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-secondary/40 p-2.5">
                <p className="text-[10px] text-muted-foreground">Dernière activité</p>
                <p className="text-sm font-bold text-foreground">{entry.last_seen ? timeAgo(entry.last_seen) : "—"}</p>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Requêtes récentes ({logs.length})
                </p>
                <Link
                  href={`/logs?source_ip=${encodeURIComponent(entry.source_ip)}`}
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  Voir tout dans Logs <ExternalLink className="w-3 h-3" />
                </Link>
              </div>

              {isLoading ? (
                <div className="space-y-2">
                  {[...Array(6)].map((_, i) => <div key={i} className="h-10 bg-secondary/40 rounded animate-pulse" />)}
                </div>
              ) : (
                <div className="space-y-1.5">
                  {logs.map((log) => {
                    const isHttp = log.action === "http_request";
                    const method = log.extra_fields?.http_method;
                    const httpStatus = log.extra_fields?.http_status;
                    const referer = log.extra_fields?.http_referer;
                    return (
                      <div key={log.id} className="py-2 px-2.5 rounded-lg bg-secondary/30 border border-border/40">
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            {isHttp ? (
                              <p className="text-xs font-mono text-foreground truncate">
                                <span className="font-semibold text-primary">{method}</span> {log.resource}
                              </p>
                            ) : (
                              <p className="text-xs font-medium text-foreground truncate">{log.action}</p>
                            )}
                            <p className="text-[10px] text-muted-foreground truncate">
                              {isHttp
                                ? `Referer : ${referer || "aucun (accès direct)"}`
                                : `${log.user_email || "utilisateur inconnu"} · ${log.source_type}`}
                            </p>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {isHttp && httpStatus !== undefined && (
                              <span
                                className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${
                                  httpStatus >= 500 ? "bg-red-500/15 text-red-400"
                                  : httpStatus >= 400 ? "bg-amber-500/15 text-amber-400"
                                  : "bg-emerald-500/15 text-emerald-400"
                                }`}
                              >
                                {httpStatus}
                              </span>
                            )}
                            <div className="flex items-center gap-1 text-[10px] text-muted-foreground whitespace-nowrap">
                              <Clock className="w-3 h-3" />
                              {timeAgo(log.event_time || log.timestamp)}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {logs.length === 0 && (
                    <p className="text-xs text-muted-foreground text-center py-6">Aucune requête détaillée trouvée pour cette IP.</p>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
