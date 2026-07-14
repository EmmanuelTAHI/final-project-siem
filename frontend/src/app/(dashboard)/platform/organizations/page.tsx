"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { Building2, Users, ShieldCheck, Database, ChevronRight, ShieldAlert } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { platformApi } from "@/lib/api";
import { timeAgo, cn } from "@/lib/utils";
import type { Organization, OrganizationStats } from "@/types";

function OrgStatsRow({ orgId }: { orgId: string }) {
  const { data: stats } = useQuery<OrganizationStats>({
    queryKey: ["platform-org-stats", orgId],
    queryFn: () => platformApi.getOrganizationStats(orgId),
    staleTime: 60_000,
  });

  if (!stats) return <div className="text-xs text-muted-foreground">Chargement…</div>;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
      {[
        { label: "Utilisateurs", value: stats.user_count },
        { label: "Connecteurs actifs", value: `${stats.active_connector_count}/${stats.connector_count}` },
        { label: "Logs", value: stats.log_count.toLocaleString() },
        { label: "Alertes ouvertes", value: stats.open_alert_count },
      ].map((s) => (
        <div key={s.label} className="rounded-lg bg-muted/60 px-3 py-2">
          <p className="text-[10px] text-muted-foreground">{s.label}</p>
          <p className="text-sm font-bold text-foreground">{s.value}</p>
        </div>
      ))}
    </div>
  );
}

export default function PlatformOrganizationsPage() {
  const router = useRouter();
  const { user, _hasHydrated } = useAuthStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!user?.is_superuser) router.replace("/dashboard");
  }, [user, _hasHydrated, router]);

  const { data: overview } = useQuery({
    queryKey: ["platform-overview"],
    queryFn: () => platformApi.getOverview(),
    enabled: !!user?.is_superuser,
    staleTime: 60_000,
  });

  const { data: orgs = [] } = useQuery<Organization[]>({
    queryKey: ["platform-organizations"],
    queryFn: () => platformApi.listOrganizations(),
    enabled: !!user?.is_superuser,
    staleTime: 30_000,
  });

  if (!_hasHydrated || !user?.is_superuser) {
    return (
      <div className="page p-6 flex items-center gap-2 text-sm text-muted-foreground">
        <ShieldAlert className="w-4 h-4" />
        Accès réservé au staff plateforme…
      </div>
    );
  }

  return (
    <div className="page p-4 lg:p-6 space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-foreground">Organisations — vue plateforme</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Vue cross-organisation réservée au staff plateforme. Chaque organisation reste isolée
          pour ses propres utilisateurs.
        </p>
      </motion.div>

      {overview && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {[
            { label: "Organisations", value: overview.organization_count, icon: Building2, color: "text-blue-400" },
            { label: "Organisations actives", value: overview.active_organization_count, icon: ShieldCheck, color: "text-emerald-400" },
            { label: "Utilisateurs (total)", value: overview.total_user_count, icon: Users, color: "text-cyan-400" },
            { label: "Staff plateforme", value: overview.platform_staff_count, icon: ShieldAlert, color: "text-amber-400" },
          ].map((stat) => (
            <div key={stat.label} className="rounded-xl border border-border p-4" style={{ background: "hsl(var(--card))" }}>
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className={`w-4 h-4 ${stat.color}`} />
                <span className="text-xs text-muted-foreground">{stat.label}</span>
              </div>
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
            </div>
          ))}
        </motion.div>
      )}

      <div className="space-y-3">
        {orgs.map((org, i) => (
          <motion.div
            key={org.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.03 }}
            className="rounded-xl border border-border p-4"
            style={{ background: "hsl(var(--card))" }}
          >
            <button
              type="button"
              onClick={() => setExpandedId(expandedId === org.id ? null : org.id)}
              className="w-full flex items-center justify-between gap-3 text-left"
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.3)" }}
                >
                  <Building2 className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    {org.name}
                    {org.is_platform_internal && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded border border-amber-400/30 text-amber-400 bg-amber-400/10">
                        interne
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {org.user_count} utilisateur{org.user_count > 1 ? "s" : ""} · plan {org.plan} · créée {timeAgo(org.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "text-xs px-2 py-1 rounded-lg border font-medium",
                    org.is_active
                      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30"
                      : "text-gray-400 bg-gray-400/10 border-gray-400/30"
                  )}
                >
                  {org.is_active ? "Active" : "Désactivée"}
                </span>
                <ChevronRight
                  className={cn("w-4 h-4 text-muted-foreground transition-transform", expandedId === org.id && "rotate-90")}
                />
              </div>
            </button>

            {expandedId === org.id && <OrgStatsRow orgId={org.id} />}
          </motion.div>
        ))}

        {orgs.length === 0 && (
          <div className="text-center py-12 text-sm text-muted-foreground">
            <Database className="w-6 h-6 mx-auto mb-2 opacity-50" />
            Aucune organisation.
          </div>
        )}
      </div>
    </div>
  );
}
