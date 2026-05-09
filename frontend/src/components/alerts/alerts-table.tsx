"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  ExternalLink,
  CheckSquare,
  Square,
} from "lucide-react";
import { SeverityBadge } from "./severity-badge";
import { cn, timeAgo, statusColors, statusLabels } from "@/lib/utils";
import { NoAlertsState } from "@/components/common/empty-state";
import { TableRowSkeleton } from "@/components/common/loading-skeleton";
import type { Alert, AlertStatus } from "@/types";

interface AlertsTableProps {
  alerts: Alert[];
  isLoading?: boolean;
  selectedIds: number[];
  onSelectId: (id: number) => void;
  onSelectAll: () => void;
  onAlertClick: (alert: Alert) => void;
  onClearFilters?: () => void;
}

type SortKey = "created_at" | "severity" | "status" | "title";
type SortDir = "asc" | "desc";

const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
const statusOrder: Record<AlertStatus, number> = { open: 4, in_progress: 3, resolved: 2, false_positive: 1 };

export function AlertsTable({
  alerts,
  isLoading,
  selectedIds,
  onSelectId,
  onSelectAll,
  onAlertClick,
  onClearFilters,
}: AlertsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = [...alerts].sort((a, b) => {
    let cmp = 0;
    switch (sortKey) {
      case "created_at":
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        break;
      case "severity":
        cmp = severityOrder[a.severity] - severityOrder[b.severity];
        break;
      case "status":
        cmp = statusOrder[a.status] - statusOrder[b.status];
        break;
      case "title":
        cmp = a.title.localeCompare(b.title);
        break;
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  const allSelected = alerts.length > 0 && selectedIds.length === alerts.length;

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <ChevronsUpDown className="w-3 h-3 opacity-40" />;
    return sortDir === "asc" ? (
      <ChevronUp className="w-3 h-3 text-primary" />
    ) : (
      <ChevronDown className="w-3 h-3 text-primary" />
    );
  };

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-secondary/30">
              <th className="px-4 py-3 w-10" />
              {["Sévérité", "Titre", "Règle", "Source IP", "Créé", "Statut", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 8 }).map((_, i) => (
              <TableRowSkeleton key={i} cols={8} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (alerts.length === 0) {
    return <NoAlertsState onClear={onClearFilters} />;
  }

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/30">
              {/* Checkbox all */}
              <th className="px-4 py-3 w-10">
                <button onClick={onSelectAll} className="text-muted-foreground hover:text-foreground transition-colors">
                  {allSelected ? (
                    <CheckSquare className="w-4 h-4 text-primary" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                </button>
              </th>
              {/* Sévérité */}
              <th
                className="px-4 py-3 text-left text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("severity")}
              >
                <div className="flex items-center gap-1">
                  Sévérité <SortIcon k="severity" />
                </div>
              </th>
              {/* Titre */}
              <th
                className="px-4 py-3 text-left text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("title")}
              >
                <div className="flex items-center gap-1">
                  Titre <SortIcon k="title" />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Règle</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Source IP</th>
              {/* Date */}
              <th
                className="px-4 py-3 text-left text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("created_at")}
              >
                <div className="flex items-center gap-1">
                  Créé <SortIcon k="created_at" />
                </div>
              </th>
              {/* Statut */}
              <th
                className="px-4 py-3 text-left text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("status")}
              >
                <div className="flex items-center gap-1">
                  Statut <SortIcon k="status" />
                </div>
              </th>
              <th className="px-4 py-3 w-10" />
            </tr>
          </thead>
          <tbody>
            <AnimatePresence>
              {sorted.map((alert, i) => {
                const isSelected = selectedIds.includes(alert.id);
                return (
                  <motion.tr
                    key={alert.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className={cn(
                      "border-b border-border transition-colors cursor-pointer",
                      isSelected ? "bg-primary/5" : "hover:bg-secondary/50"
                    )}
                    onClick={() => onAlertClick(alert)}
                  >
                    {/* Checkbox */}
                    <td className="px-4 py-3" onClick={(e) => { e.stopPropagation(); onSelectId(alert.id); }}>
                      <button className="text-muted-foreground hover:text-foreground transition-colors">
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-primary" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>

                    {/* Severity */}
                    <td className="px-4 py-3">
                      <SeverityBadge severity={alert.severity} size="sm" />
                    </td>

                    {/* Title */}
                    <td className="px-4 py-3 max-w-xs">
                      <div>
                        <p className="font-medium text-foreground truncate text-xs">{alert.title}</p>
                        {alert.user_email && (
                          <p className="text-[10px] text-muted-foreground truncate">{alert.user_email}</p>
                        )}
                      </div>
                    </td>

                    {/* Rule */}
                    <td className="px-4 py-3">
                      <span className="text-xs text-muted-foreground">{alert.rule_name}</span>
                    </td>

                    {/* Source IP */}
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-foreground">{alert.source_ip}</span>
                    </td>

                    {/* Created */}
                    <td className="px-4 py-3">
                      <span className="text-xs text-muted-foreground whitespace-nowrap">{timeAgo(alert.created_at)}</span>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "text-[10px] font-medium px-1.5 py-0.5 rounded border",
                          statusColors[alert.status]
                        )}
                      >
                        {statusLabels[alert.status]}
                      </span>
                    </td>

                    {/* Action */}
                    <td className="px-4 py-3">
                      <ExternalLink className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}
