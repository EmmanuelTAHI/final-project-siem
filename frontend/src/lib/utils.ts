import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format, parseISO, isValid } from "date-fns";
import { fr } from "date-fns/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Date formatters
function parseSafe(date: string | Date | null | undefined): Date | null {
  if (!date) return null;
  try {
    const d = typeof date === "string" ? parseISO(date) : date;
    return isValid(d) ? d : null;
  } catch {
    return null;
  }
}

export function timeAgo(date: string | Date | null | undefined): string {
  const d = parseSafe(date);
  if (!d) return "—";
  try {
    return formatDistanceToNow(d, { addSuffix: true, locale: fr });
  } catch {
    return "—";
  }
}

export function formatDate(date: string | Date | null | undefined, fmt = "dd/MM/yyyy HH:mm"): string {
  const d = parseSafe(date);
  if (!d) return "—";
  try {
    return format(d, fmt);
  } catch {
    return "—";
  }
}

export function formatDateShort(date: string | Date | null | undefined): string {
  return formatDate(date, "dd MMM yyyy");
}

// Number formatters
export function formatNumber(n: number | null | undefined): string {
  const safe = typeof n === "number" && isFinite(n) ? n : 0;
  if (safe >= 1_000_000) return `${(safe / 1_000_000).toFixed(1)}M`;
  if (safe >= 1_000) return `${(safe / 1_000).toFixed(1)}K`;
  return safe.toString();
}

export function formatPercent(n: number, decimals = 1): string {
  return `${n.toFixed(decimals)}%`;
}

// Severity helpers
export type Severity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "in_progress" | "resolved" | "false_positive";

export const severityColors: Record<Severity, string> = {
  low: "text-emerald-400",
  medium: "text-amber-400",
  high: "text-red-400",
  critical: "text-purple-400",
};

export const severityBgColors: Record<Severity, string> = {
  low: "bg-emerald-400/10 border-emerald-400/30",
  medium: "bg-amber-400/10 border-amber-400/30",
  high: "bg-red-400/10 border-red-400/30",
  critical: "bg-purple-400/10 border-purple-400/30",
};

export const severityHex: Record<Severity, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#ef4444",
  critical: "#8b5cf6",
};

export const statusColors: Record<AlertStatus, string> = {
  open: "text-red-400 bg-red-400/10 border-red-400/30",
  in_progress: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  resolved: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  false_positive: "text-gray-400 bg-gray-400/10 border-gray-400/30",
};

export const statusLabels: Record<AlertStatus, string> = {
  open: "Ouvert",
  in_progress: "En cours",
  resolved: "Résolu",
  false_positive: "Faux positif",
};

export const severityLabels: Record<Severity, string> = {
  low: "Faible",
  medium: "Moyen",
  high: "Élevé",
  critical: "Critique",
};

// Country flags
export function getCountryFlag(countryCode: string): string {
  if (!countryCode || countryCode.length !== 2) return "🌍";
  const codePoints = [...countryCode.toUpperCase()].map(
    (c) => 127397 + c.charCodeAt(0)
  );
  return String.fromCodePoint(...codePoints);
}

// Truncate text
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return `${text.slice(0, length)}...`;
}

// Random ID generator
export function randomId(): string {
  return Math.random().toString(36).substring(2, 9);
}

// Debounce
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// Get initials from name
export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

// Calculate percentage
export function calcPercent(value: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((value / total) * 100);
}

// Site de documentation : app Next.js indépendante (basePath=/docs), servie
// sous /docs/ sur le même domaine via nginx (voir nginx.conf). En dev local,
// elle tourne sur son propre port (3001). NEXT_PUBLIC_DOCS_URL permet de
// surcharger explicitement.
export function getDocsUrl(path = ""): string {
  const base = (() => {
    if (process.env.NEXT_PUBLIC_DOCS_URL) return process.env.NEXT_PUBLIC_DOCS_URL;
    if (typeof window !== "undefined") {
      const { hostname } = window.location;
      if (hostname === "localhost" || hostname === "127.0.0.1") {
        return "http://localhost:3001/docs";
      }
    }
    return "/docs";
  })();
  return path ? `${base}/${path.replace(/^\//, "")}` : base;
}
