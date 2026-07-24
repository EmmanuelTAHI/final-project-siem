"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { useAuthStore } from "@/stores/auth-store";
import { useRealtimeStore } from "@/stores/realtime-store";
import { notificationsApi } from "@/lib/api";
import type { Alert, PaginatedResponse, SecurityNotification, WSNotification } from "@/types";

// L'URL WebSocket est dérivée de l'origine de la page (nginx proxifie /ws/
// vers le backend). NEXT_PUBLIC_WS_URL ne sert qu'à la surcharger en dev.
function getWsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return "ws://localhost:8000";
}

/**
 * Hook unifié pour la cloche de notification.
 * - charge les SecurityNotifications persistées (REST)
 * - écoute le WebSocket pour les évènements live (alerte, CTI, SOAR, sécurité comptes liés)
 * - expose markRead / markAllRead / clearTransient
 */
export function useNotifications() {
  const { user, isAuthenticated, accessToken } = useAuthStore();
  const qc = useQueryClient();
  const [transient, setTransient] = useState<WSNotification[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const setRtConnected = useRealtimeStore((s) => s.setConnected);
  const pushRecentAlert = useRealtimeStore((s) => s.pushRecentAlert);

  // ── Synchronisation temps réel du cache TanStack Query ─────────────────────
  // Toute création/màj d'alerte reçue par WebSocket est répercutée partout :
  // liste d'alertes, stats, KPIs dashboard — sans rechargement de page.
  const syncAlertCaches = useCallback(
    (alert: Partial<Alert> | undefined, created: boolean) => {
      if (alert?.id) {
        // Anime aussi les mises à jour (attaque en cours fusionnée dans une
        // alerte déjà ouverte) — sinon un test répété contre une IP déjà
        // connue est invisible pour l'utilisateur alors qu'il a bien été pris
        // en compte (voir engine._create_alert_if_new).
        pushRecentAlert(String(alert.id));

        // Insertion/màj optimiste dans les listes déjà en cache → affichage
        // instantané ; le refetch d'invalidation réconcilie juste après.
        qc.setQueriesData<PaginatedResponse<Alert>>(
          { queryKey: ["alerts"] },
          (old) => {
            if (!old?.results) return old;
            if (created) {
              const exists = old.results.some((a) => String(a.id) === String(alert.id));
              if (exists) return old;
              return {
                ...old,
                count: (old.count ?? old.results.length) + 1,
                results: [alert as Alert, ...old.results],
              };
            }
            // Mise à jour (ex: une attaque en cours fusionnée dans une alerte
            // déjà ouverte, voir engine._create_alert_if_new) : la liste est
            // triée par updated_at côté serveur, donc on la remonte aussi en
            // tête ici plutôt que de la laisser à sa position d'origine.
            const idx = old.results.findIndex((a) => String(a.id) === String(alert.id));
            if (idx === -1) return old;
            const merged = { ...old.results[idx], ...alert };
            const rest = old.results.filter((_, i) => i !== idx);
            return { ...old, results: [merged, ...rest] };
          }
        );
      }

      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alert-stats"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["dashboard-timeline"] });
      qc.invalidateQueries({ queryKey: ["dashboard-top-threats"] });
    },
    [qc, pushRecentAlert]
  );

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
    if (!isAuthenticated || !user?.id || !accessToken) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Le navigateur ne peut pas fixer de header Authorization sur un
    // handshake WebSocket : le JWT passe en query string, validé côté
    // serveur par JWTAuthMiddleware (jamais un user_id fourni par le client).
    const url = `${getWsBase()}/ws/notifications/?token=${encodeURIComponent(accessToken)}`;
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
      setRtConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSNotification;
        const withTs = { ...msg, timestamp: msg.timestamp || new Date().toISOString() };

        // Notifications d'alertes désactivées à la demande (toast + cloche) :
        // l'alerte continue d'apparaître/se mettre à jour normalement dans
        // la liste des alertes (syncAlertCaches tourne toujours), seule la
        // notification est coupée. Ne pas l'ajouter aux évènements
        // transitoires de la cloche non plus, sinon elle y apparaît quand
        // même sans toast.
        const isAlertEvent = msg.type === "new_alert" || (msg as { type?: string }).type === "alert_updated";
        if (!isAlertEvent) {
          // Garde les 50 derniers évènements transitoires
          setTransient((prev) => [withTs, ...prev.slice(0, 49)]);
        }

        // Toasts contextuels + synchronisation live des caches
        if (msg.type === "new_alert" && msg.alert) {
          syncAlertCaches(msg.alert, true);
        } else if ((msg as { type?: string }).type === "alert_updated" && msg.alert) {
          syncAlertCaches(msg.alert, false);
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
      setRtConnected(false);
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
  }, [isAuthenticated, user?.id, accessToken, qc, syncAlertCaches, setRtConnected]);

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
