"use client";

import { useRouter } from "next/navigation";
import { ScanSearch } from "lucide-react";

/**
 * Affiche une IP cliquable qui pivote vers le Threat Intelligence.
 * Un clic ouvre /threat-intel?ip=<ip> et lance le lookup automatiquement.
 * Placé partout où une IP apparaît (logs, alertes) pour investiguer en 1 clic.
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
  if (!ip || ip === "—") return <span className={className}>—</span>;

  const isPrivate =
    /^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1|fe80:)/.test(ip);

  const go = (e: React.MouseEvent) => {
    if (stopPropagation) e.stopPropagation();
    router.push(`/threat-intel?ip=${encodeURIComponent(ip)}`);
  };

  return (
    <button
      type="button"
      onClick={go}
      title={isPrivate ? `${ip} — IP privée (analyse limitée)` : `Analyser ${ip} dans le Threat Intelligence`}
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
  );
}
