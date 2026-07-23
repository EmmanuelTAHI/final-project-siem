"use client";

import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ScanSearch, Ban, ShieldOff, Copy, Radar } from "lucide-react";
import toast from "react-hot-toast";
import { soarApi } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Affiche une IP cliquable qui ouvre un menu d'actions rapides
 * (Threat Intelligence, blocage, trafic, copie). Placé partout où une IP
 * apparaît (logs, alertes, trafic) pour investiguer/agir en 1 clic.
 * La liste des IP bloquées est partagée (même queryKey que BlockedIPsPanel)
 * donc une seule requête réseau alimente toutes les IpLink de la page.
 */
export function IpLink({
  ip,
  className = "",
  stopPropagation = true,
}: {
  ip?: string | null;
  className?: string;
  stopPropagation?: boolean;
}) {
  const router = useRouter();
  const qc = useQueryClient();

  const { data: blockedData } = useQuery({
    queryKey: ["blocked-ips"],
    queryFn: () => soarApi.getBlockedIPs({ is_active: true, page_size: 1000 }),
    staleTime: 15000,
    refetchInterval: 30000,
  });

  const blockMutation = useMutation({
    mutationFn: (address: string) => soarApi.blockIP(address, "Blocage manuel depuis une vue IP"),
    onSuccess: () => {
      toast.success(`IP ${ip} bloquée — effective sur toute la plateforme`);
      qc.invalidateQueries({ queryKey: ["blocked-ips"] });
    },
    onError: () => toast.error("Erreur lors du blocage de l'IP"),
  });

  const unblockMutation = useMutation({
    mutationFn: (id: string) => soarApi.unblockIP(id),
    onSuccess: () => {
      toast.success(`IP ${ip} débloquée`);
      qc.invalidateQueries({ queryKey: ["blocked-ips"] });
    },
    onError: () => toast.error("Erreur lors du déblocage de l'IP"),
  });

  if (!ip || ip === "—") return <span className={className}>—</span>;

  const isPrivate =
    /^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1|fe80:)/.test(ip);

  const blockedEntry = blockedData?.results.find((b) => b.ip_address === ip);
  const isBlocked = !!blockedEntry;

  const stop = (e: React.MouseEvent | React.PointerEvent) => {
    if (stopPropagation) e.stopPropagation();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          onClick={stop}
          onPointerDown={stop}
          title={
            isBlocked
              ? `${ip} — bloquée sur la plateforme`
              : isPrivate
                ? `${ip} — IP privée (analyse limitée)`
                : `Actions sur ${ip}`
          }
          className={`group inline-flex items-center gap-1 font-mono transition-colors cursor-pointer ${
            isBlocked ? "text-red-400/80 hover:text-red-400" : "hover:text-primary"
          } ${className}`}
          style={{ background: "transparent", border: "none", padding: 0 }}
        >
          <span
            className={`underline decoration-dotted decoration-transparent group-hover:decoration-current underline-offset-2 ${
              isBlocked ? "opacity-60 line-through decoration-solid decoration-red-400/60" : ""
            }`}
          >
            {ip}
          </span>
          {isBlocked ? (
            <Ban size={12} className="opacity-70 flex-shrink-0" />
          ) : (
            <ScanSearch
              size={12}
              className="opacity-0 group-hover:opacity-70 transition-opacity flex-shrink-0"
            />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" onClick={stop}>
        <DropdownMenuLabel className="font-mono flex items-center gap-1.5">
          {ip}
          {isBlocked && <Ban className="w-3 h-3 text-red-400" />}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push(`/threat-intel?ip=${encodeURIComponent(ip)}`)}>
          <ScanSearch className="w-3.5 h-3.5" /> Analyser (Threat Intelligence)
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => router.push(`/ip-traffic?search=${encodeURIComponent(ip)}`)}>
          <Radar className="w-3.5 h-3.5" /> Voir le trafic de cette IP
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => {
            navigator.clipboard.writeText(ip);
            toast.success("IP copiée");
          }}
        >
          <Copy className="w-3.5 h-3.5" /> Copier l&apos;adresse IP
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {isBlocked ? (
          <DropdownMenuItem
            onClick={() => blockedEntry && unblockMutation.mutate(blockedEntry.id)}
            disabled={unblockMutation.isPending}
            className="text-emerald-400 focus:text-emerald-400 focus:bg-emerald-500/10"
          >
            <ShieldOff className="w-3.5 h-3.5" /> Débloquer cette IP
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem
            onClick={() => blockMutation.mutate(ip)}
            disabled={isPrivate || blockMutation.isPending}
            className="text-red-400 focus:text-red-400 focus:bg-red-500/10"
          >
            <Ban className="w-3.5 h-3.5" /> Bloquer cette IP
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
