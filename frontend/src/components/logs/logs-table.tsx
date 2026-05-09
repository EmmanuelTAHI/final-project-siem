"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronRight, X } from "lucide-react";
import { cn, timeAgo } from "@/lib/utils";
import { FlagBadge } from "@/components/common/country-flag";
import { NoLogsState } from "@/components/common/empty-state";
import { TableRowSkeleton } from "@/components/common/loading-skeleton";
import type { NormalizedLog } from "@/types";

interface LogsTableProps {
  logs: NormalizedLog[];
  isLoading?: boolean;
  activeFilters?: Record<string, string>;
  onRemoveFilter?: (key: string) => void;
  onClearFilters?: () => void;
}

const severityLogColors: Record<string, string> = {
  info: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  warning: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  error: "text-red-400 bg-red-400/10 border-red-400/30",
  critical: "text-purple-400 bg-purple-400/10 border-purple-400/30",
};

const severityRowColors: Record<string, string> = {
  info: "",
  warning: "bg-amber-400/3",
  error: "bg-red-400/5",
  critical: "bg-purple-400/5",
};

export function LogsTable({ logs, isLoading, activeFilters, onRemoveFilter, onClearFilters }: LogsTableProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {activeFilters && Object.keys(activeFilters).length > 0 && (
          <div className="flex flex-wrap gap-2">
            {Object.entries(activeFilters).map(([k, v]) => (
              <span key={k} className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border border-border bg-secondary/50">
                {k}: {v}
                <X className="w-3 h-3 cursor-pointer" onClick={() => onRemoveFilter?.(k)} />
              </span>
            ))}
          </div>
        )}
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full">
            <tbody>
              {Array.from({ length: 10 }).map((_, i) => (
                <TableRowSkeleton key={i} cols={7} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (logs.length === 0) {
    return <NoLogsState onClear={onClearFilters} />;
  }

  return (
    <div className="space-y-3">
      {/* Active filter chips */}
      {activeFilters && Object.keys(activeFilters).length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-muted-foreground">Filtres actifs:</span>
          {Object.entries(activeFilters).map(([k, v]) => (
            <span
              key={k}
              className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border border-primary/30 bg-primary/10 text-primary"
            >
              <span className="font-medium">{k}:</span> {v}
              <button onClick={() => onRemoveFilter?.(k)}>
                <X className="w-3 h-3 hover:text-foreground transition-colors" />
              </button>
            </span>
          ))}
          <button onClick={onClearFilters} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Tout effacer
          </button>
        </motion.div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="w-8 px-3 py-2.5" />
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">Timestamp</th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">Source</th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">Action</th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">Utilisateur</th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">IP Source</th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">Géo</th>
                <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">Sévérité</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {logs.map((log, i) => (
                  <>
                    <motion.tr
                      key={log.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.01 }}
                      className={cn(
                        "border-b border-border transition-colors cursor-pointer",
                        severityRowColors[log.severity],
                        "hover:bg-secondary/50"
                      )}
                      onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                    >
                      {/* Expand toggle */}
                      <td className="px-3 py-2">
                        {expandedId === log.id ? (
                          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                        )}
                      </td>

                      {/* Timestamp */}
                      <td className="px-3 py-2 font-mono text-muted-foreground whitespace-nowrap">
                        {timeAgo(log.timestamp)}
                      </td>

                      {/* Source */}
                      <td className="px-3 py-2">
                        <span className="px-1.5 py-0.5 rounded bg-secondary text-foreground border border-border">
                          {log.source_type}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="px-3 py-2 font-medium text-foreground">{log.action}</td>

                      {/* User */}
                      <td className="px-3 py-2 text-muted-foreground max-w-[160px] truncate">
                        {log.user_email || "—"}
                      </td>

                      {/* Source IP */}
                      <td className="px-3 py-2 font-mono text-foreground">{log.source_ip || "—"}</td>

                      {/* Geo */}
                      <td className="px-3 py-2">
                        {log.geo_country_code
                          ? <FlagBadge code={log.geo_country_code} label={log.geo_country ?? log.geo_country_code} />
                          : <span className="text-muted-foreground">—</span>}
                      </td>

                      {/* Severity */}
                      <td className="px-3 py-2">
                        <span className={cn("px-1.5 py-0.5 rounded border capitalize", severityLogColors[log.severity])}>
                          {log.severity}
                        </span>
                      </td>
                    </motion.tr>

                    {/* Expanded raw data */}
                    <AnimatePresence>
                      {expandedId === log.id && (
                        <motion.tr
                          key={`expanded-${log.id}`}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                        >
                          <td colSpan={8} className="px-4 py-0">
                            <motion.div
                              initial={{ height: 0 }}
                              animate={{ height: "auto" }}
                              exit={{ height: 0 }}
                              className="overflow-hidden"
                            >
                              <div className="my-2 rounded-lg border border-border overflow-hidden">
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-secondary/50 border-b border-border">
                                  <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                                    Raw Data — Log #{log.id}
                                  </span>
                                </div>
                                <pre className="p-3 text-[10px] font-mono text-muted-foreground overflow-x-auto bg-background/30 max-h-48">
                                  {JSON.stringify({ ...log.raw_data, ...log.metadata }, null, 2)}
                                </pre>
                              </div>
                            </motion.div>
                          </td>
                        </motion.tr>
                      )}
                    </AnimatePresence>
                  </>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
