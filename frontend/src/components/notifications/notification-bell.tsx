"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, BellRing, Wifi, WifiOff, CheckCheck, AlertTriangle, Shield } from "lucide-react";
import { useNotifications } from "@/hooks/use-notifications";
import type { SecurityNotification, WSNotification } from "@/types";

type CombinedItem =
  | { kind: "persisted"; n: SecurityNotification; ts: number }
  | { kind: "transient"; n: WSNotification; ts: number; key: string };

function PersistedItem({
  notif,
  onRead,
}: {
  notif: SecurityNotification;
  onRead: (id: string) => void;
}) {
  const tone =
    notif.level === "critical" ? "border-l-red-500 bg-red-500/5"
    : notif.level === "warning" ? "border-l-orange-500 bg-orange-500/5"
    : "border-l-blue-500";
  const Icon = notif.level === "critical" ? AlertTriangle : Shield;

  return (
    <button
      onClick={() => !notif.is_read && onRead(notif.id)}
      className={`w-full text-left p-3 border-l-2 rounded-r transition-colors ${tone} ${
        notif.is_read ? "opacity-60" : "bg-secondary/30"
      } hover:bg-secondary/40`}
    >
      <div className="flex items-start gap-2">
        <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
          notif.level === "critical" ? "text-red-400"
          : notif.level === "warning" ? "text-orange-400"
          : "text-blue-400"
        }`} />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-foreground font-medium truncate">{notif.title}</p>
          {notif.body && (
            <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">{notif.body}</p>
          )}
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {new Date(notif.created_at).toLocaleString("fr-FR")}
          </p>
        </div>
        {!notif.is_read && (
          <span className="w-2 h-2 rounded-full bg-primary mt-1 flex-shrink-0" />
        )}
      </div>
    </button>
  );
}

function TransientItem({ notif }: { notif: WSNotification }) {
  const icons: Record<string, string> = {
    new_alert: "🚨",
    alert_updated: "🔄",
    cti_threat: "⚠️",
    playbook_executed: "⚡",
    system: "ℹ️",
    security_notification: "🔔",
  };
  const tone =
    notif.type === "new_alert" ? "border-l-red-500"
    : notif.type === "cti_threat" ? "border-l-orange-500"
    : notif.type === "playbook_executed" ? "border-l-green-500"
    : notif.type === "alert_updated" ? "border-l-blue-500"
    : "border-l-gray-500";

  const title =
    notif.type === "new_alert" ? `Nouvelle alerte: ${notif.alert?.title ?? ""}`
    : notif.type === "alert_updated" ? `Alerte mise à jour: ${notif.alert?.title ?? ""}`
    : notif.type === "cti_threat" ? "Menace CTI détectée"
    : notif.type === "playbook_executed" ? "Playbook SOAR exécuté"
    : notif.message ?? "Notification système";

  return (
    <div className={`p-3 border-l-2 bg-secondary/20 rounded-r ${tone}`}>
      <div className="flex items-start gap-2">
        <span className="text-sm">{icons[notif.type as string] ?? "•"}</span>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-foreground font-medium truncate">{title}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {new Date(notif.timestamp).toLocaleString("fr-FR")}
          </p>
        </div>
        {notif.alert?.severity && (
          <span className={`text-[9px] font-bold px-1 rounded ${
            notif.alert.severity === "critical" ? "bg-red-500/20 text-red-400"
            : notif.alert.severity === "high" ? "bg-orange-500/20 text-orange-400"
            : "bg-yellow-500/20 text-yellow-400"
          }`}>
            {notif.alert.severity.toUpperCase()}
          </span>
        )}
      </div>
    </div>
  );
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const {
    notifications,
    persisted,
    unreadCount,
    persistedUnread,
    wsConnected,
    markRead,
    markAllRead,
    clearTransient,
  } = useNotifications();

  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Combiner DB + WS, triés par date desc, dédupliqués
  const combined: CombinedItem[] = [
    ...persisted.map((p) => ({ kind: "persisted" as const, n: p, ts: new Date(p.created_at).getTime() })),
    ...notifications.map((t, i) => ({
      kind: "transient" as const,
      n: t,
      ts: new Date(t.timestamp).getTime(),
      key: `t-${t.timestamp}-${i}`,
    })),
  ].sort((a, b) => b.ts - a.ts).slice(0, 30);

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-all"
        aria-label="Notifications"
        title={
          wsConnected
            ? "Notifications en temps réel actives"
            : "Flux temps réel hors ligne — les notifications restent visibles depuis la base"
        }
      >
        {unreadCount > 0 ? (
          <BellRing className="w-4 h-4 text-primary animate-pulse" />
        ) : (
          <Bell className="w-4 h-4" />
        )}
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center"
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </motion.span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -8 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-10 w-96 max-w-[calc(100vw-24px)] bg-card border border-border rounded-xl shadow-2xl z-50 overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-primary" />
                <span className="text-sm font-semibold text-foreground">Notifications</span>
                {persistedUnread > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary font-bold">
                    {persistedUnread} non lue{persistedUnread > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <span
                className={`flex items-center gap-1 text-[10px] ${wsConnected ? "text-emerald-500" : "text-amber-500"}`}
                title={wsConnected
                  ? "Connecté au flux temps réel — les nouvelles alertes apparaissent instantanément"
                  : "Flux temps réel indisponible — la liste se rafraîchit toutes les 30 s"}
              >
                {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {wsConnected ? "Temps réel" : "Mode pull"}
              </span>
            </div>

            <div className="px-3 py-2 border-b border-border/50 flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">
                {wsConnected
                  ? "Flux WebSocket actif. Les alertes s'affichent instantanément."
                  : "Le flux WebSocket est hors ligne. La cloche reste alimentée par la base."}
              </span>
              <div className="flex gap-2">
                {persistedUnread > 0 && (
                  <button
                    onClick={() => markAllRead()}
                    className="flex items-center gap-1 text-[10px] text-primary hover:underline"
                  >
                    <CheckCheck className="w-3 h-3" />
                    Tout marquer lu
                  </button>
                )}
                {notifications.length > 0 && (
                  <button
                    onClick={clearTransient}
                    className="text-[10px] text-muted-foreground hover:text-foreground"
                  >
                    Effacer flux
                  </button>
                )}
              </div>
            </div>

            <div className="max-h-96 overflow-y-auto">
              {combined.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground">
                  <Bell className="w-7 h-7 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">Aucune notification</p>
                  {wsConnected && <p className="text-[10px] mt-1 text-emerald-500">En écoute…</p>}
                </div>
              ) : (
                <div className="p-2 space-y-1">
                  {combined.map((item) =>
                    item.kind === "persisted" ? (
                      <PersistedItem key={`p-${item.n.id}`} notif={item.n} onRead={markRead} />
                    ) : (
                      <TransientItem key={item.key} notif={item.n} />
                    )
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
