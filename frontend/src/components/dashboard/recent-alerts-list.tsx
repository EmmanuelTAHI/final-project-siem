"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { cn, timeAgo, severityHex, statusLabels } from "@/lib/utils";
import type { Alert } from "@/types";

interface RecentAlertsListProps {
  alerts: Alert[];
}

export function RecentAlertsList({ alerts }: RecentAlertsListProps) {
  const router = useRouter();
  const recent = alerts.slice(0, 10);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.6 }}
      className="rounded-xl border border-border flex flex-col"
      style={{ background: "hsl(var(--card))" }}
    >
      <div className="flex items-center justify-between p-5 pb-3 border-b border-border">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Alertes récentes</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Dernières alertes ouvertes</p>
        </div>
        <button
          onClick={() => router.push("/alerts")}
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          Voir tout <ChevronRight className="w-3 h-3" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-border">
        {recent.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            Aucune alerte récente
          </div>
        ) : (
          recent.map((alert, i) => (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.7 + i * 0.05 }}
              onClick={() => router.push("/alerts")}
              className="flex items-center gap-3 px-5 py-3 hover:bg-secondary/50 transition-colors cursor-pointer group"
            >
              {/* Severity icon */}
              <div
                className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center"
                style={{
                  background: `${severityHex[alert.severity]}15`,
                  border: `1px solid ${severityHex[alert.severity]}30`,
                }}
              >
                <AlertTriangle
                  className="w-3.5 h-3.5"
                  style={{ color: severityHex[alert.severity] }}
                />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-foreground truncate group-hover:text-primary transition-colors">
                  {alert.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-muted-foreground truncate">
                    {alert.rule_name}
                  </span>
                  <span className="text-[10px] text-muted-foreground">•</span>
                  <span className="text-[10px] text-muted-foreground">
                    {timeAgo(alert.created_at)}
                  </span>
                </div>
              </div>

              {/* Status */}
              <div className="flex-shrink-0">
                <span
                  className={cn(
                    "text-[10px] font-medium px-1.5 py-0.5 rounded border",
                    alert.status === "open"
                      ? "text-red-400 bg-red-400/10 border-red-400/30"
                      : alert.status === "in_progress"
                      ? "text-blue-400 bg-blue-400/10 border-blue-400/30"
                      : alert.status === "resolved"
                      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30"
                      : "text-gray-400 bg-gray-400/10 border-gray-400/30"
                  )}
                >
                  {statusLabels[alert.status]}
                </span>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </motion.div>
  );
}
