"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  LayoutDashboard,
  Bell,
  FileText,
  GitBranch,
  Brain,
  Database,
  Users,
  Settings,
  AlertTriangle,
  X,
} from "lucide-react";
import { useAlerts } from "@/hooks/use-alerts";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ElementType;
  action: () => void;
  category: "navigation" | "alert" | "action";
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const { data: alertsData } = useAlerts({ status: "open" });
  const recentAlerts = alertsData?.results?.slice(0, 5) ?? [];

  const navigate = useCallback(
    (href: string) => {
      router.push(href);
      onClose();
      setQuery("");
    },
    [router, onClose]
  );

  const allItems: CommandItem[] = [
    { id: "dash", label: "Dashboard", description: "Vue d'ensemble de Argus", icon: LayoutDashboard, action: () => navigate("/dashboard"), category: "navigation" },
    { id: "alerts", label: "Alertes", description: "Gérer les alertes de sécurité", icon: Bell, action: () => navigate("/alerts"), category: "navigation" },
    { id: "logs", label: "Logs", description: "Explorer les logs normalisés", icon: FileText, action: () => navigate("/logs"), category: "navigation" },
    { id: "correlation", label: "Corrélation", description: "Règles de corrélation", icon: GitBranch, action: () => navigate("/correlation"), category: "navigation" },
    { id: "ml", label: "Machine Learning", description: "Modèles et anomalies ML", icon: Brain, action: () => navigate("/ml"), category: "navigation" },
    { id: "collectors", label: "Collecteurs", description: "Gérer les connecteurs", icon: Database, action: () => navigate("/collectors"), category: "navigation" },
    { id: "users", label: "Utilisateurs", description: "Gestion des utilisateurs", icon: Users, action: () => navigate("/users"), category: "navigation" },
    { id: "settings", label: "Paramètres", description: "Configuration de Argus", icon: Settings, action: () => navigate("/settings"), category: "navigation" },
    // Recent alerts
    ...recentAlerts.map((alert) => ({
      id: `alert-${alert.id}`,
      label: alert.title,
      description: `${alert.severity.toUpperCase()} • ${alert.status}`,
      icon: AlertTriangle,
      action: () => navigate("/alerts"),
      category: "alert" as const,
    })),
  ];

  const filtered = query
    ? allItems.filter(
        (item) =>
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.description?.toLowerCase().includes(query.toLowerCase())
      )
    : allItems;

  useEffect(() => {
    setSelected(0);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return;
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelected((s) => Math.min(s + 1, filtered.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelected((s) => Math.max(s - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (filtered[selected]) {
            filtered[selected].action();
            setQuery("");
          }
          break;
        case "Escape":
          onClose();
          setQuery("");
          break;
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, filtered, selected, onClose]);

  const categories: Record<string, string> = {
    navigation: "Navigation",
    alert: "Alertes récentes",
    action: "Actions",
  };

  let lastCategory = "";

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
          {/* Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => { onClose(); setQuery(""); }}
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.2, ease: [0.175, 0.885, 0.32, 1.275] }}
            className="relative w-full max-w-xl mx-4 rounded-2xl border border-border overflow-hidden"
            style={{
              background: "hsl(var(--card))",
              boxShadow: "0 25px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)",
            }}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
              <Search className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher une page, alerte, action..."
                className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              <kbd className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded bg-secondary border border-border text-muted-foreground font-mono">
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div className="max-h-80 overflow-y-auto py-2">
              {filtered.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  Aucun résultat pour &ldquo;{query}&rdquo;
                </div>
              ) : (
                filtered.map((item, idx) => {
                  const showCategory = item.category !== lastCategory;
                  lastCategory = item.category;
                  const Icon = item.icon;

                  return (
                    <div key={item.id}>
                      {showCategory && (
                        <div className="px-4 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                          {categories[item.category]}
                        </div>
                      )}
                      <button
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                          idx === selected ? "bg-secondary text-foreground" : "text-foreground hover:bg-secondary/50"
                        }`}
                        onClick={() => { item.action(); setQuery(""); }}
                        onMouseEnter={() => setSelected(idx)}
                      >
                        <div
                          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{
                            background: item.category === "alert"
                              ? "rgba(239,68,68,0.1)"
                              : "rgba(59,130,246,0.1)",
                            border: item.category === "alert"
                              ? "1px solid rgba(239,68,68,0.2)"
                              : "1px solid rgba(59,130,246,0.2)",
                          }}
                        >
                          <Icon
                            className={`w-3.5 h-3.5 ${item.category === "alert" ? "text-red-400" : "text-blue-400"}`}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{item.label}</p>
                          {item.description && (
                            <p className="text-xs text-muted-foreground truncate">{item.description}</p>
                          )}
                        </div>
                        {idx === selected && (
                          <kbd className="text-[10px] text-muted-foreground border border-border rounded px-1.5 py-0.5 font-mono">
                            ↵
                          </kbd>
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-border px-4 py-2 flex items-center gap-4 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <kbd className="border border-border rounded px-1 font-mono">↑↓</kbd> naviguer
              </span>
              <span className="flex items-center gap-1">
                <kbd className="border border-border rounded px-1 font-mono">↵</kbd> sélectionner
              </span>
              <span className="flex items-center gap-1">
                <kbd className="border border-border rounded px-1 font-mono">ESC</kbd> fermer
              </span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
