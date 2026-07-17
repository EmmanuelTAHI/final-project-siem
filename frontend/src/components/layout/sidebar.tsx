"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ShieldAlert,
  FileText,
  GitBranch,
  Brain,
  Database,
  Users,
  Settings,
  Shield,
  LogOut,
  Zap,
  Globe,
  Search,
  FileCheck,
  Sun,
  Moon,
  Cpu,
  BookOpen,
} from "lucide-react";
import { cn, getInitials, getDocsUrl } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { authApi } from "@/lib/api";
import { useAlertStats } from "@/hooks/use-alerts";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: boolean;
}

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

const sections: NavSection[] = [
  {
    id: "core",
    label: "Vue d'ensemble",
    items: [
      { label: "Tableau de bord", href: "/dashboard", icon: LayoutDashboard },
    ],
  },
  {
    id: "detection",
    label: "Détection",
    items: [
      { label: "Alertes", href: "/alerts", icon: ShieldAlert, badge: true },
      { label: "Logs", href: "/logs", icon: FileText },
      { label: "Corrélation", href: "/correlation", icon: GitBranch },
      { label: "Machine Learning", href: "/ml", icon: Brain },
    ],
  },
  {
    id: "operations",
    label: "Opérations",
    items: [
      { label: "Threat Intel", href: "/threat-intel", icon: Globe },
      { label: "SOAR", href: "/soar", icon: Zap },
      { label: "Threat Hunting", href: "/hunting", icon: Search },
    ],
  },
  {
    id: "reports",
    label: "Rapports & Données",
    items: [
      { label: "Rapports", href: "/reports", icon: FileCheck },
      { label: "Collecteurs", href: "/collectors", icon: Database },
      { label: "Agents", href: "/agents", icon: Cpu },
    ],
  },
  {
    id: "admin",
    label: "Administration",
    items: [
      { label: "Utilisateurs", href: "/users", icon: Users },
      { label: "Paramètres", href: "/settings", icon: Settings },
    ],
  },
];

function NavTooltip({
  label,
  show,
  children,
}: {
  label: string;
  show: boolean;
  children: React.ReactNode;
}) {
  if (!show) return <>{children}</>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={10} className="font-ui">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export interface SidebarProps {
  forceExpanded?: boolean;
  onClose?: () => void;
}

export function Sidebar({ forceExpanded = false, onClose: _onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const router = useRouter();
  const { data: alertStats } = useAlertStats();
  const openAlerts = alertStats?.open ?? 0;

  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    return () => {
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
    };
  }, []);

  const isDark = theme === "dark";
  const collapsed = !forceExpanded && !isHovered;

  const handleMouseEnter = () => {
    hoverTimer.current = setTimeout(() => setIsHovered(true), 120);
  };

  const handleMouseLeave = () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    setIsHovered(false);
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    } finally {
      logout();
      toast.success("Déconnexion réussie");
      router.replace("/login");
    }
  };

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  // Vue cross-org réservée au staff plateforme (is_superuser) — jamais
  // visible pour un admin d'organisation normal.
  const visibleSections: NavSection[] = user?.is_superuser
    ? [
        ...sections,
        {
          id: "platform",
          label: "Plateforme",
          items: [{ label: "Organisations", href: "/platform/organizations", icon: Shield }],
        },
      ]
    : sections;

  return (
    <TooltipProvider delayDuration={200}>
      <aside
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          width: collapsed ? 64 : 240,
          transition: "width 260ms cubic-bezier(.2,.8,.2,1), box-shadow 260ms ease, background-color 260ms ease",
          // Légèrement transparente + flou de fond : discret en permanence,
          // et surtout utile en overlay (survol) où elle recouvre le
          // contenu sans le masquer complètement.
          background: "color-mix(in srgb, var(--surface) 92%, transparent)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          // Positionnée en absolu (par-dessus le contenu) plutôt qu'en flux
          // normal : son parent (frontend/src/app/(dashboard)/layout.tsx)
          // réserve une largeur fixe de 64px, donc l'expansion au survol ne
          // pousse jamais la page à côté — elle se superpose simplement.
          position: "absolute",
          top: 0,
          left: 0,
          zIndex: 30,
          flexShrink: 0,
          height: "100%",
          boxShadow: collapsed ? "none" : "6px 0 24px -8px rgba(0,0,0,0.25)",
        }}
      >
        {/* ── Logo ────────────────────────────────────────────────── */}
        <div
          style={{
            height: 60,
            padding: collapsed ? "0 15px" : "0 16px",
            display: "flex",
            alignItems: "center",
            gap: 10,
            borderBottom: "1px solid var(--border)",
            flexShrink: 0,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              background: "linear-gradient(135deg, var(--primary), var(--secondary))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              flexShrink: 0,
              boxShadow: "0 4px 14px -4px var(--glow)",
            }}
          >
            <Shield size={17} strokeWidth={2.2} />
          </div>
          <div
            style={{
              overflow: "hidden",
              opacity: collapsed ? 0 : 1,
              width: collapsed ? 0 : "auto",
              transition: "opacity 180ms ease, width 180ms ease",
              whiteSpace: "nowrap",
            }}
          >
            <div
              className="font-display"
              style={{ fontWeight: 800, fontSize: 15.5, letterSpacing: "-0.03em", lineHeight: 1 }}
            >
              Log<span style={{ color: "var(--primary)" }}>+</span>
            </div>
            <div
              className="font-mono"
              style={{ fontSize: 9.5, color: "var(--text-2)", marginTop: 3, letterSpacing: "0.04em" }}
            >
              cluster-01 · v4.7
            </div>
          </div>
        </div>

        {/* ── Nav ─────────────────────────────────────────────────── */}
        <nav
          style={{
            flex: 1,
            padding: "8px 8px",
            display: "flex",
            flexDirection: "column",
            gap: 0,
            overflowY: "auto",
            overflowX: "hidden",
          }}
        >
          {visibleSections.map((section, si) => (
            <div key={section.id} style={{ marginTop: si === 0 ? 4 : 12 }}>
              {!collapsed && (
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    color: "var(--text-2)",
                    padding: "0 10px 5px",
                    textTransform: "uppercase",
                    opacity: 0.7,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                  }}
                >
                  {section.label}
                </div>
              )}
              {collapsed && si > 0 && (
                <div
                  style={{
                    height: 1,
                    background: "var(--border)",
                    margin: "4px 8px 8px",
                    opacity: 0.6,
                  }}
                />
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                {section.items.map((item) => {
                  const active = isActive(item.href);
                  const badge = item.badge ? openAlerts : 0;
                  const Icon = item.icon;

                  return (
                    <NavTooltip key={item.href} label={item.label} show={collapsed}>
                      <Link
                        href={item.href}
                        className={cn("nav-item", active && "nav-item-active")}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: collapsed ? "9px 0" : "8px 10px",
                          justifyContent: collapsed ? "center" : "flex-start",
                          borderRadius: 9,
                          color: active ? "var(--primary)" : "var(--text-2)",
                          background: active
                            ? "color-mix(in srgb, var(--primary) 9%, transparent)"
                            : "transparent",
                          fontWeight: active ? 600 : 400,
                          fontSize: 13,
                          position: "relative",
                          transition: "background 140ms ease, color 140ms ease",
                          textDecoration: "none",
                          overflow: "hidden",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {active && (
                          <span
                            style={{
                              position: "absolute",
                              left: 0,
                              top: "20%",
                              bottom: "20%",
                              width: 3,
                              borderRadius: "0 3px 3px 0",
                              background: "var(--primary)",
                            }}
                          />
                        )}

                        <Icon
                          size={17}
                          strokeWidth={active ? 2.2 : 1.8}
                          style={{ flexShrink: 0 }}
                        />

                        {!collapsed && (
                          <span style={{ flex: 1, lineHeight: 1.3 }}>{item.label}</span>
                        )}

                        {!collapsed && badge > 0 && (
                          <span
                            className="font-mono"
                            style={{
                              background: "var(--danger)",
                              color: "white",
                              fontSize: 10,
                              fontWeight: 700,
                              padding: "1px 6px",
                              borderRadius: 999,
                              lineHeight: "16px",
                              letterSpacing: "0.02em",
                              flexShrink: 0,
                            }}
                          >
                            {badge > 99 ? "99+" : badge}
                          </span>
                        )}

                        {collapsed && badge > 0 && (
                          <span
                            className="dot crit"
                            style={{
                              position: "absolute",
                              top: 7,
                              right: 9,
                              width: 7,
                              height: 7,
                            }}
                          />
                        )}
                      </Link>
                    </NavTooltip>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* ── Footer ──────────────────────────────────────────────── */}
        <div
          style={{
            borderTop: "1px solid var(--border)",
            padding: "10px 8px 10px",
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          {mounted && (
            <NavTooltip label={isDark ? "Mode clair" : "Mode sombre"} show={collapsed}>
              <button
                onClick={() => setTheme(isDark ? "light" : "dark")}
                aria-label="Basculer le thème"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: collapsed ? "9px 0" : "8px 10px",
                  justifyContent: collapsed ? "center" : "flex-start",
                  borderRadius: 9,
                  border: "none",
                  background: "transparent",
                  color: "var(--text-2)",
                  cursor: "pointer",
                  fontSize: 13,
                  width: "100%",
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  transition: "background 140ms ease, color 140ms ease",
                }}
              >
                {isDark ? <Moon size={17} strokeWidth={1.8} style={{ flexShrink: 0 }} /> : <Sun size={17} strokeWidth={1.8} style={{ flexShrink: 0 }} />}
                {!collapsed && (
                  <>
                    <span style={{ flex: 1, textAlign: "left" }}>
                      {isDark ? "Mode sombre" : "Mode clair"}
                    </span>
                    <div
                      style={{
                        width: 32,
                        height: 18,
                        borderRadius: 999,
                        background: isDark ? "var(--primary)" : "var(--border)",
                        position: "relative",
                        flexShrink: 0,
                        transition: "background 220ms ease",
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          top: 2,
                          left: 2,
                          width: 14,
                          height: 14,
                          borderRadius: 999,
                          background: "white",
                          transform: isDark ? "translateX(14px)" : "translateX(0)",
                          transition: "transform 220ms cubic-bezier(.2,.8,.2,1)",
                          boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
                        }}
                      />
                    </div>
                  </>
                )}
              </button>
            </NavTooltip>
          )}

          {user && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 9,
                padding: collapsed ? "6px 0" : "7px 10px",
                justifyContent: collapsed ? "center" : "flex-start",
                borderRadius: 9,
                overflow: "hidden",
              }}
            >
              <NavTooltip label={user.full_name} show={collapsed}>
                <div
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 999,
                    background: "linear-gradient(135deg, #A78BFA, #60A5FA)",
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 11,
                    flexShrink: 0,
                    letterSpacing: "0.02em",
                    cursor: "default",
                  }}
                >
                  {getInitials(user.full_name)}
                </div>
              </NavTooltip>
              {!collapsed && (
                <>
                  <div style={{ flex: 1, overflow: "hidden", lineHeight: 1.25 }}>
                    <div
                      style={{
                        fontSize: 12.5,
                        fontWeight: 600,
                        color: "var(--text)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {user.full_name}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--text-2)",
                        textTransform: "capitalize",
                      }}
                    >
                      {user.role}
                    </div>
                  </div>
                  <a
                    href={getDocsUrl()}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Documentation"
                    title="Documentation"
                    style={{
                      padding: "5px",
                      border: "none",
                      background: "transparent",
                      color: "var(--text-2)",
                      borderRadius: 7,
                      display: "flex",
                      alignItems: "center",
                      transition: "color 140ms ease, background 140ms ease",
                      flexShrink: 0,
                    }}
                    className="btn-ghost"
                  >
                    <BookOpen size={15} strokeWidth={1.8} />
                  </a>
                  <button
                    onClick={handleLogout}
                    aria-label="Se déconnecter"
                    style={{
                      padding: "5px",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      color: "var(--text-2)",
                      borderRadius: 7,
                      display: "flex",
                      alignItems: "center",
                      transition: "color 140ms ease, background 140ms ease",
                      flexShrink: 0,
                    }}
                    className="btn-ghost"
                  >
                    <LogOut size={15} strokeWidth={1.8} />
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
}
