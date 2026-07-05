import { create } from "zustand";

/**
 * État temps réel partagé (WebSocket unique ouvert par la cloche de
 * notifications). Les pages lisent ce store pour afficher l'indicateur
 * LIVE et surligner les alertes fraîchement arrivées, sans ouvrir de
 * second socket.
 */
interface RealtimeState {
  connected: boolean;
  lastEventAt: number | null;
  /** IDs des alertes reçues en live récemment (pour l'animation d'entrée). */
  recentAlertIds: Set<string>;

  setConnected: (v: boolean) => void;
  pushRecentAlert: (id: string) => void;
}

const RECENT_TTL_MS = 2 * 60 * 1000;

export const useRealtimeStore = create<RealtimeState>((set, get) => ({
  connected: false,
  lastEventAt: null,
  recentAlertIds: new Set(),

  setConnected: (v) => set({ connected: v }),

  pushRecentAlert: (id) => {
    const next = new Set(get().recentAlertIds);
    next.add(id);
    set({ recentAlertIds: next, lastEventAt: Date.now() });
    // L'ID sort du set après le TTL → l'animation ne rejoue pas indéfiniment.
    setTimeout(() => {
      const cleaned = new Set(get().recentAlertIds);
      if (cleaned.delete(id)) set({ recentAlertIds: cleaned });
    }, RECENT_TTL_MS);
  },
}));
