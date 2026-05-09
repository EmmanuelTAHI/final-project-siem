"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { useAuthStore } from "@/stores/auth-store";
import { notificationsApi } from "@/lib/api";
import type { SecurityNotification, WSNotification } from "@/types";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

/**
 * Hook unifié pour la cloche de notification.
 * - charge les SecurityNotifications persistées (REST)
 * - écoute le WebSocket pour les évènements live (alerte, CTI, SOAR, sécurité comptes liés)
 * - expose markRead / markAllRead / clearTransient
 */
export function useNotifications() {
  const { user, isAuthenticated } = useAuthStore();
  const qc = useQueryClient();
  const [transient, setTransient] = useState<WSNotification[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);

  // ── REST: notifications persistées ─────────────────────────────────────────
  const { data: persisted } = useQuery({
    queryKey: ["security-notifications"],
    queryFn: () => notificationsApi.list(false),
    enabled: isAuthenticated,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  const persistedItems: SecurityNotification[] = persisted?.notifications ?? [];
  const persistedUnread = persisted?.unread_count ?? 0;

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["security-notifications"] }),
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["security-notifications"] }),
  });

  // ── WebSocket: notifications temps réel ────────────────────────────────────
  const connect = useCallback(() => {
    if (!isAuthenticated || !user?.id) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE}/ws/notifications/${user.id}/`;
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      setWsConnected(false);
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSNotification;
        const withTs = { ...msg, timestamp: msg.timestamp || new Date().toISOString() };

        // Garde les 50 derniers évènements transitoires
        setTransient((prev) => [withTs, ...prev.slice(0, 49)]);

        // Toasts contextuels
        if (msg.type === "new_alert" && msg.alert) {
          const sev = msg.alert.severity;
          const toastFn = sev === "critical" || sev === "high" ? toast.error : toast;
          toastFn(`🚨 Nouvelle alerte ${sev?.toUpperCase()}: ${msg.alert.title}`, {
            duration: sev === "critical" ? 8000 : 5000,
          });
        } else if (msg.type === "cti_threat") {
          toast.error(`⚠ CTI: Menace détectée — ${(msg.data as { title?: string })?.title || "IP malveillante"}`, {
            duration: 6000,
          });
        } else if (msg.type === "playbook_executed") {
          toast.success("✓ Playbook SOAR exécuté", { duration: 4000 });
        } else if ((msg as { type?: string }).type === "security_notification") {
          // Alerte compte lié — invalider le cache pour rafraîchir la cloche
          qc.invalidateQueries({ queryKey: ["security-notifications"] });
          toast(`🔔 ${(msg as { notification?: { title?: string } }).notification?.title || "Alerte de sécurité"}`, {
            duration: 5000,
          });
        }
      } catch {
        /* ignore */
      }
    };

    ws.onclose = (event) => {
      setWsConnected(false);
      wsRef.current = null;
      if (event.code !== 1000 && reconnectAttempts.current < 8) {
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        reconnectAttempts.current += 1;
        reconnectRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      try { ws.close(); } catch { /* noop */ }
    };
  }, [isAuthenticated, user?.id, qc]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      try { wsRef.current?.close(1000); } catch { /* noop */ }
    };
  }, [connect]);

  // ── API publique ───────────────────────────────────────────────────────────
  const clearTransient = useCallback(() => setTransient([]), []);

  // Compteur unifié : notifications DB non-lues + alertes live transitoires
  const transientUnread = transient.filter((n) =>
    ["new_alert", "cti_threat", "security_notification"].includes(n.type as string)
  ).length;
  const unreadCount = persistedUnread + transientUnread;

  return {
    /** Évènements WebSocket récents (non persistés) */
    notifications: transient,
    /** Notifications de sécurité persistées en base */
    persisted: persistedItems,
    /** Nombre total non-lues (DB + transient) */
    unreadCount,
    /** Nombre persisté non-lu (depuis DB) */
    persistedUnread,
    /** WebSocket actif (alertes live actuellement reçues) */
    wsConnected,
    /** Compatibilité ancienne API */
    connected: wsConnected,
    markRead: (id: string) => markReadMutation.mutate(id),
    markAllRead: () => markAllReadMutation.mutate(),
    clearTransient,
    clearAll: clearTransient,
  };
}
