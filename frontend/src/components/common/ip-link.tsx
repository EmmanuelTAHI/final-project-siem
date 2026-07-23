"use client";

import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ScanSearch, Ban, Copy, Radar } from "lucide-react";
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

  const blockMutation = useMutation({
    mutationFn: (address: string) => soarApi.blockIP(address, "Blocage manuel depuis une vue IP"),
    onSuccess: () => toast.success(`IP ${ip} bloquée — effective sur toute la plateforme`),
    onError: () => toast.error("Erreur lors du blocage de l'IP"),
  });

  if (!ip || ip === "—") return <span className={className}>—</span>;

  const isPrivate =
    /^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1|fe80:)/.test(ip);

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
          title={isPrivate ? `${ip} — IP privée (analyse limitée)` : `Actions sur ${ip}`}
          className={`group inline-flex items-center gap-1 font-mono hover:text-primary transition-colors cursor-pointer ${className}`}
          style={{ background: "transparent", border: "none", padding: 0 }}
        >
          <span className="underline decoration-dotted decoration-transparent group-hover:decoration-current underline-offset-2">
            {ip}
          </span>
          <ScanSearch
            size={12}
            className="opacity-0 group-hover:opacity-70 transition-opacity flex-shrink-0"
          />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" onClick={stop}>
        <DropdownMenuLabel className="font-mono">{ip}</DropdownMenuLabel>
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
        <DropdownMenuItem
          onClick={() => blockMutation.mutate(ip)}
          disabled={isPrivate || blockMutation.isPending}
          className="text-red-400 focus:text-red-400 focus:bg-red-500/10"
        >
          <Ban className="w-3.5 h-3.5" /> Bloquer cette IP
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
