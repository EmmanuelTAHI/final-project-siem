"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Search, ChevronRight, Menu } from "lucide-react";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { useAuthStore } from "@/stores/auth-store";

const breadcrumbLabels: Record<string, string> = {
  dashboard: "Tableau de bord",
  alerts: "Alertes",
  logs: "Événements",
  correlation: "Corrélation",
  ml: "Machine Learning",
  "threat-intel": "Threat Intelligence",
  soar: "SOAR",
  hunting: "Threat Hunting",
  reports: "Rapports",
  collectors: "Collecteurs",
  users: "Utilisateurs",
  settings: "Paramètres",
};

interface TopbarProps {
  onMobileMenuToggle?: () => void;
  onCommandPaletteOpen?: () => void;
}

const ranges = ["1h", "6h", "24h", "7j", "30j"];

export function Topbar({ onMobileMenuToggle, onCommandPaletteOpen }: TopbarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuthStore();
  void user;

  const [range, setRange] = useState("24h");
  const [searchFocus, setSearchFocus] = useState(false);

  const segments = pathname.split("/").filter(Boolean);
  const crumbs = ["Accueil", ...segments.map((s) => breadcrumbLabels[s] || s)];

  return (
    <header
      className="mesh topbar"
      style={{
        height: 64,
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "0 22px",
        background: "var(--surface)",
        position: "sticky",
        top: 0,
        zIndex: 20,
      }}
    >
      {/* Mobile menu — hidden on desktop, visible on mobile */}
      <button
        onClick={onMobileMenuToggle}
        className="flex lg:hidden items-center justify-center"
        style={{
          width: 36,
          height: 36,
          border: "1px solid var(--border)",
          borderRadius: 10,
          background: "var(--surface)",
          color: "var(--text)",
          cursor: "pointer",
          flexShrink: 0,
        }}
        aria-label="Ouvrir le menu"
      >
        <Menu size={16} />
      </button>

      {/* Breadcrumb */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 13,
          color: "var(--text-2)",
          minWidth: 0,
        }}
      >
        {crumbs.map((c, i) => {
          const isLast = i === crumbs.length - 1;
          const href = "/" + segments.slice(0, i).join("/");
          return (
            <div
              key={i}
              className={isLast ? undefined : "crumb-mid"}
              style={{ display: "flex", alignItems: "center", gap: 8 }}
            >
              <span
                onClick={() => !isLast && i > 0 && router.push(href)}
                style={{
                  color: isLast ? "var(--text)" : "var(--text-2)",
                  fontWeight: isLast ? 600 : 400,
                  whiteSpace: "nowrap",
                  cursor: !isLast && i > 0 ? "pointer" : "default",
                }}
              >
                {c}
              </span>
              {!isLast && <ChevronRight size={13} style={{ opacity: 0.5 }} />}
            </div>
          );
        })}
      </div>

      <div style={{ flex: 1 }} />

      {/* Search */}
      <div
        className="hidden md:block"
        style={{
          width: searchFocus ? 440 : 340,
          maxWidth: "45vw",
          position: "relative",
          transition: "width 200ms ease",
        }}
      >
        <Search
          size={15}
          style={{
            position: "absolute",
            top: "50%",
            left: 12,
            transform: "translateY(-50%)",
            color: "var(--text-2)",
            pointerEvents: "none",
          }}
        />
        <input
          className="input"
          placeholder="Rechercher alertes, hôtes, utilisateurs, IPs…"
          onFocus={() => {
            setSearchFocus(true);
            onCommandPaletteOpen?.();
          }}
          onBlur={() => setSearchFocus(false)}
          style={{ paddingLeft: 36, paddingRight: 72 }}
        />
        <div
          style={{
            position: "absolute",
            top: "50%",
            right: 10,
            transform: "translateY(-50%)",
            display: "flex",
            gap: 4,
          }}
        >
          <kbd>⌘</kbd>
          <kbd>K</kbd>
        </div>
      </div>

      {/* Search icon mobile */}
      <button
        onClick={onCommandPaletteOpen}
        className="md:hidden"
        style={{
          width: 38,
          height: 38,
          borderRadius: 10,
          border: "1px solid var(--border)",
          background: "var(--surface)",
          color: "var(--text)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
        }}
        aria-label="Rechercher"
      >
        <Search size={16} />
      </button>

      {/* Time range */}
      <div
        className="hidden lg:flex"
        style={{
          gap: 2,
          padding: 3,
          background: "color-mix(in srgb, var(--text) 5%, transparent)",
          borderRadius: 10,
        }}
      >
        {ranges.map((r) => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className="font-mono"
            style={{
              padding: "5px 10px",
              borderRadius: 7,
              border: "none",
              cursor: "pointer",
              background: range === r ? "var(--surface)" : "transparent",
              color: range === r ? "var(--text)" : "var(--text-2)",
              fontWeight: range === r ? 600 : 500,
              fontSize: 12,
              boxShadow:
                range === r
                  ? "0 2px 6px -2px color-mix(in srgb, var(--text) 18%, transparent)"
                  : "none",
              transition: "all 160ms ease",
            }}
          >
            {r}
          </button>
        ))}
      </div>

      {/* LIVE chip */}
      <span className="chip hidden lg:inline-flex">
        <span className="dot live" style={{ width: 7, height: 7 }} />
        LIVE
      </span>

      {/* Notifications */}
      <div style={{ position: "relative" }}>
        <NotificationBell />
      </div>

      {/* Fallback bell icon if NotificationBell fails to render */}
      <noscript>
        <Bell size={16} />
      </noscript>
    </header>
  );
}
