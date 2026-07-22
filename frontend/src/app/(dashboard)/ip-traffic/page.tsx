"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { format, parseISO } from "date-fns";
import { fr } from "date-fns/locale";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Radar, Globe2, MapPin, ShieldAlert, Search, ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import { logsApi } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { GeoTable } from "@/components/dashboard/geo-table";
import { CountryDonut } from "@/components/ip-traffic/country-donut";
import { IPSparkline } from "@/components/ip-traffic/ip-sparkline";
import { IPRequestsDrawer } from "@/components/ip-traffic/ip-requests-drawer";
import { CountryFlag } from "@/components/common/country-flag";
import { countryName } from "@/lib/country-names";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { timeAgo } from "@/lib/utils";
import { IpLink } from "@/components/common/ip-link";
import type { IPTrafficPeriod, IPTrafficEntry } from "@/types";

const PERIODS: { value: IPTrafficPeriod; label: string }[] = [
  { value: "1h", label: "1 h" },
  { value: "24h", label: "24 h" },
  { value: "7d", label: "7 j" },
  { value: "30d", label: "30 j" },
];

const PERIOD_TIME_FORMAT: Record<IPTrafficPeriod, string> = {
  "1h": "HH:mm",
  "24h": "HH:mm",
  "7d": "EEE dd",
  "30d": "dd MMM",
};

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-border px-3 py-2 text-sm shadow-xl" style={{ background: "hsl(var(--card))" }}>
      <p className="text-muted-foreground text-xs mb-1">{label}</p>
      <span className="font-semibold text-foreground">{payload[0].value.toLocaleString()} requêtes</span>
    </div>
  );
}

function IPTrafficPageInner() {
  const searchParams = useSearchParams();
  const [period, setPeriod] = useState<IPTrafficPeriod>((searchParams.get("period") as IPTrafficPeriod) || "24h");
  const [search, setSearch] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<IPTrafficEntry | null>(null);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  const { data, isLoading } = useQuery({
    queryKey: ["ip-traffic", period],
    queryFn: () => logsApi.getIPTraffic(period),
    refetchInterval: 30000,
  });

  const timeline = (data?.timeline ?? []).map((p) => {
    try {
      return { time: format(parseISO(p.bucket), PERIOD_TIME_FORMAT[period], { locale: fr }), count: p.count };
    } catch {
      return { time: p.bucket, count: p.count };
    }
  });

  const filteredIPs = (data?.top_ips ?? []).filter(
    (ip) => !search.trim() || ip.source_ip.includes(search.trim())
  );
  const totalPages = Math.max(1, Math.ceil(filteredIPs.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pagedIPs = filteredIPs.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <div className="page p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Radar className="w-6 h-6 text-primary" />
            Trafic & Adresses IP
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Qui contacte votre système, depuis où, et à quelle fréquence — vue de trafic en temps quasi réel
          </p>
        </div>
        <div className="flex gap-1 p-1 rounded-xl border border-border bg-secondary/30">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-colors ${
                period === p.value
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="Requêtes totales" value={data?.summary.total_requests ?? 0} icon={Radar} tone="primary" delay={0} />
        <KpiCard title="IP uniques" value={data?.summary.unique_ips ?? 0} icon={Globe2} tone="info" delay={0.05} />
        <KpiCard title="Pays distincts" value={data?.summary.unique_countries ?? 0} icon={MapPin} tone="secondary" delay={0.1} />
        <KpiCard title="Menaces connues (CTI)" value={data?.summary.known_threats ?? 0} icon={ShieldAlert} tone="danger" delay={0.15} />
      </div>

      {/* Timeline globale */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="card" style={{ padding: 20 }}>
        <div className="mb-4">
          <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>Volume de requêtes dans le temps</div>
          <div style={{ fontSize: 12, color: "var(--text-2)" }}>Toutes IP confondues</div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={timeline} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="trafficGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.35} />
                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} opacity={0.5} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="count" stroke="var(--primary)" strokeWidth={2} fill="url(#trafficGrad)" dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Géo : classement par pays + camembert */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GeoTable
          data={(data?.by_country ?? []).map((c) => ({
            country: countryName(c.country_code),
            country_code: c.country_code,
            count: c.count,
            percentage: c.percentage,
            threat_count: 0,
          }))}
          subtitle={`Sur la période sélectionnée (${PERIODS.find((p) => p.value === period)?.label ?? period})`}
        />
        <CountryDonut data={data?.by_country ?? []} />
      </div>

      {/* Top IPs */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="rounded-xl border border-border" style={{ background: "hsl(var(--card))" }}>
        <div className="p-5 pb-3 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Top IP par volume</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Cliquez une ligne pour voir ses requêtes précises</p>
          </div>
          <div className="w-56">
            <Input
              placeholder="Filtrer par IP..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              leftIcon={<Search className="w-3.5 h-3.5" />}
              className="h-8 text-xs"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-border/60 text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="text-left font-medium px-5 py-2.5">Adresse IP</th>
                <th className="text-left font-medium px-3 py-2.5">Pays</th>
                <th className="text-right font-medium px-3 py-2.5">Requêtes</th>
                <th className="text-center font-medium px-3 py-2.5">Activité</th>
                <th className="text-right font-medium px-3 py-2.5">Échecs</th>
                <th className="text-left font-medium px-3 py-2.5">Statut</th>
                <th className="text-right font-medium px-5 py-2.5">Dernière vue</th>
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                [...Array(6)].map((_, i) => (
                  <tr key={i}><td colSpan={7} className="px-5 py-2"><div className="h-8 bg-muted rounded animate-pulse" /></td></tr>
                ))}
              {!isLoading && pagedIPs.map((ip) => (
                <tr
                  key={ip.source_ip}
                  onClick={() => setSelectedEntry(ip)}
                  className="border-b border-border/30 hover:bg-secondary/30 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-2.5">
                    <span onClick={(e) => e.stopPropagation()}>
                      <IpLink ip={ip.source_ip} className="text-xs" />
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {ip.geo_country ? (
                      <CountryFlag code={ip.geo_country} size="sm" showName={countryName(ip.geo_country)} />
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-semibold text-foreground tabular-nums">{ip.count.toLocaleString()}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex justify-center">
                      <IPSparkline values={ip.sparkline} />
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    <span className={ip.failure_count > 0 ? "text-red-400 font-semibold" : "text-muted-foreground"}>
                      {ip.failure_count.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {ip.is_known_threat ? (
                      <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-[10px]">Menace connue</Badge>
                    ) : ip.failure_count > ip.success_count && ip.failure_count >= 5 ? (
                      <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 text-[10px]">Suspect</Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px]">Normal</Badge>
                    )}
                  </td>
                  <td className="px-5 py-2.5 text-right text-xs text-muted-foreground whitespace-nowrap">
                    {ip.last_seen ? timeAgo(ip.last_seen) : "—"}
                  </td>
                </tr>
              ))}
              {!isLoading && filteredIPs.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-8 text-center text-sm text-muted-foreground">Aucune IP trouvée sur cette période.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {!isLoading && filteredIPs.length > PAGE_SIZE && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-border/60">
            <p className="text-xs text-muted-foreground">
              {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, filteredIPs.length)} sur {filteredIPs.length}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="text-xs text-muted-foreground font-mono">{currentPage} / {totalPages}</span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </motion.div>

      <IPRequestsDrawer entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
    </div>
  );
}

export default function IPTrafficPage() {
  return (
    <Suspense fallback={null}>
      <IPTrafficPageInner />
    </Suspense>
  );
}
