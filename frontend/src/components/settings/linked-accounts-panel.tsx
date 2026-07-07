"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  Link2,
  Loader2,
  RefreshCw,
  Trash2,
  UserCheck,
  Wifi,
} from "lucide-react";
import toast from "react-hot-toast";
import { linkedAccountsApi } from "@/lib/api";
import { GoogleIcon, MicrosoftIcon, GitHubIcon } from "@/components/common/brand-icons";
import { PinEntryInline, PIN_TTL } from "./pin-verification-modal";
import type { LinkedAccount, OAuthProvider, ProviderLoginEvent } from "@/types";

// ─── sessionStorage key for PIN persistence across reloads ───────────────────
const PIN_SESSION_KEY = "logplus_pin_pending";

const PROVIDER_META: Record<
  OAuthProvider,
  { label: string; color: string; icon: React.ElementType }
> = {
  google:    { label: "Google",    color: "#EA4335", icon: GoogleIcon },
  microsoft: { label: "Microsoft", color: "#0078D4", icon: MicrosoftIcon },
  github:    { label: "GitHub",    color: "#E5E9F2", icon: GitHubIcon },
};

interface PinState {
  verificationId: string;
  provider: OAuthProvider;
  email: string;
  startedAt: number; // ms timestamp — lets us recompute remaining time on restore
}

function statusBadge(status: LinkedAccount["status"]) {
  const map: Record<LinkedAccount["status"], { className: string; label: string }> = {
    active:  { className: "badge badge-ok",   label: "Actif" },
    paused:  { className: "badge badge-med",  label: "En pause" },
    revoked: { className: "badge badge-low",  label: "Révoqué" },
    error:   { className: "badge badge-crit", label: "Erreur" },
  };
  const info = map[status];
  return <span className={info.className}>{info.label}</span>;
}

function eventBadge(type: ProviderLoginEvent["event_type"]) {
  if (type === "login_success")      return <span className="badge badge-ok">OK</span>;
  if (type === "login_failure")      return <span className="badge badge-crit">ÉCHEC</span>;
  if (type === "mfa_challenge")      return <span className="badge badge-info">MFA</span>;
  if (type === "mfa_failure")        return <span className="badge badge-high">MFA KO</span>;
  if (type === "suspicious_activity") return <span className="badge badge-high">SUSPECT</span>;
  return <span className="badge badge-low">{type}</span>;
}

function timeAgo(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - d);
  const m = Math.round(diff / 60000);
  if (m < 1) return "à l'instant";
  if (m < 60) return `il y a ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `il y a ${h} h`;
  return new Date(iso).toLocaleDateString("fr-FR");
}

/** Compute how many seconds are left for a PIN that started at `startedAt`. */
function computeSecondsLeft(startedAt: number): number {
  const elapsed = Math.floor((Date.now() - startedAt) / 1000);
  return Math.max(0, PIN_TTL - elapsed);
}

/** Read + validate pinState from sessionStorage. Returns null if expired/invalid. */
function restoreFromSession(): (PinState & { secondsLeft: number }) | null {
  try {
    const raw = sessionStorage.getItem(PIN_SESSION_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as PinState;
    const secondsLeft = computeSecondsLeft(data.startedAt);
    if (secondsLeft <= 5) {
      sessionStorage.removeItem(PIN_SESSION_KEY);
      return null;
    }
    return { ...data, secondsLeft };
  } catch {
    sessionStorage.removeItem(PIN_SESSION_KEY);
    return null;
  }
}

/** Persist pin state to sessionStorage. */
function saveToSession(state: PinState) {
  sessionStorage.setItem(PIN_SESSION_KEY, JSON.stringify(state));
}

/** Clear pin state from sessionStorage. */
function clearSession() {
  sessionStorage.removeItem(PIN_SESSION_KEY);
}

// ─── Provider Card ──────────────────────────────────────────────────────────

function ProviderCard({
  provider,
  account,
  onLink,
  onUnlink,
  onPoll,
  onSelect,
  selected,
  pinData,
  onPinSuccess,
}: {
  provider: OAuthProvider;
  account: LinkedAccount | null;
  onLink: (p: OAuthProvider) => void;
  onUnlink: (a: LinkedAccount) => void;
  onPoll: (a: LinkedAccount) => void;
  onSelect: (a: LinkedAccount | null) => void;
  selected: boolean;
  pinData: { verificationId: string; email: string; secondsLeft: number } | null;
  onPinSuccess: (provider: string, email: string) => void;
}) {
  const meta = PROVIDER_META[provider];
  const Icon = meta.icon;
  const linked = !!account;
  const awaitingPin = !!pinData;

  const borderColor = awaitingPin
    ? meta.color
    : selected
    ? "var(--primary)"
    : undefined;

  const boxShadow = awaitingPin
    ? `0 0 0 1px ${meta.color}55, 0 0 28px -8px ${meta.color}44`
    : selected
    ? "0 0 0 1px var(--primary), 0 0 24px -8px var(--glow)"
    : undefined;

  const isClickable = linked && !awaitingPin;

  return (
    <div
      className={`card ${isClickable ? "card-hover" : ""}`}
      style={{
        padding: 18,
        borderColor,
        boxShadow,
        cursor: isClickable ? "pointer" : "default",
        transition: "border-color 0.2s, box-shadow 0.2s",
      }}
      onClick={() => isClickable && onSelect(selected ? null : account!)}
    >
      {/* Header — always visible */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: `color-mix(in srgb, ${meta.color} 18%, transparent)`,
            color: meta.color,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
            {meta.label}
          </div>
          <div
            className="font-mono"
            style={{
              fontSize: 11.5,
              color: "var(--text-2)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {awaitingPin
              ? pinData!.email
              : linked
              ? account!.provider_email
              : "Non lié"}
          </div>
        </div>
        {awaitingPin ? (
          <span className="badge badge-info">En cours…</span>
        ) : linked ? (
          statusBadge(account!.status)
        ) : null}
      </div>

      {/* Body */}
      {awaitingPin ? (
        <PinEntryInline
          verificationId={pinData!.verificationId}
          provider={provider}
          email={pinData!.email}
          initialSecondsLeft={pinData!.secondsLeft}
          onSuccess={onPinSuccess}
        />
      ) : linked ? (
        <>
          <div
            style={{
              fontSize: 11.5,
              color: "var(--text-2)",
              marginTop: 12,
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span>
              <Wifi size={11} style={{ marginRight: 4, verticalAlign: -1 }} />
              Dernier poll : {timeAgo(account!.last_polled_at)}
            </span>
            <span>· Lié {timeAgo(account!.linked_at)}</span>
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
            <button
              className="btn btn-ghost"
              style={{ fontSize: 12, padding: "7px 10px", flex: 1 }}
              onClick={(e) => {
                e.stopPropagation();
                onPoll(account!);
              }}
            >
              <RefreshCw size={12} /> Vérifier
            </button>
            <button
              className="btn btn-ghost"
              style={{
                fontSize: 12,
                padding: "7px 10px",
                color: "var(--danger)",
              }}
              onClick={(e) => {
                e.stopPropagation();
                onUnlink(account!);
              }}
            >
              <Trash2 size={12} /> Délier
            </button>
          </div>
        </>
      ) : (
        <button
          className="btn btn-primary"
          style={{
            width: "100%",
            justifyContent: "center",
            marginTop: 14,
          }}
          onClick={() => onLink(provider)}
        >
          <Link2 size={14} /> Lier {meta.label}
        </button>
      )}
    </div>
  );
}

// ─── Main Panel ──────────────────────────────────────────────────────────────

export function LinkedAccountsPanel() {
  const router = useRouter();
  const params = useSearchParams();

  const [accounts, setAccounts] = useState<LinkedAccount[]>([]);
  const [events, setEvents] = useState<Record<string, ProviderLoginEvent[]>>({});
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinState, setPinState] = useState<
    (PinState & { secondsLeft: number }) | null
  >(null);

  const accountByProvider = useMemo(() => {
    const map: Partial<Record<OAuthProvider, LinkedAccount>> = {};
    for (const a of accounts) map[a.provider] = a;
    return map;
  }, [accounts]);

  const selectedAccount = accounts.find((a) => a.id === selectedId) || null;
  const selectedEvents = (selectedId && events[selectedId]) || [];

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await linkedAccountsApi.list();
      setAccounts(data.accounts || []);
    } catch {
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  // ── 1. On mount: restore PIN from sessionStorage (survives page reload) ───
  useEffect(() => {
    const restored = restoreFromSession();
    if (restored) {
      setPinState(restored);
      // No toast on restore — user knows they had the form open
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 2. On OAuth callback: read URL params, persist to sessionStorage ───────
  useEffect(() => {
    if (!params) return;

    const pinRequired = params.get("pin_required");
    const linkSuccess = params.get("link_success");
    const linkError   = params.get("link_error");

    if (pinRequired === "1") {
      const verificationId = params.get("verification_id");
      const provider       = params.get("provider") as OAuthProvider | null;
      const email          = params.get("email") || "";

      const valid: OAuthProvider[] = ["google", "microsoft", "github"];
      if (verificationId && provider && valid.includes(provider)) {
        const newState: PinState & { secondsLeft: number } = {
          verificationId,
          provider,
          email,
          startedAt: Date.now(),
          secondsLeft: PIN_TTL,
        };
        setPinState(newState);
        saveToSession(newState);

        // Clean URL params immediately
        router.replace("/settings?tab=linked_accounts");

        // Notify user
        toast(
          (t) => (
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                cursor: "pointer",
              }}
              onClick={() => toast.dismiss(t.id)}
            >
              <span style={{ fontSize: 18, lineHeight: 1, marginTop: 1 }}>📧</span>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  Email de vérification envoyé
                </div>
                <div
                  style={{
                    fontSize: 12,
                    opacity: 0.75,
                    marginTop: 2,
                  }}
                >
                  Consultez{" "}
                  <strong style={{ fontFamily: "monospace" }}>{email}</strong>{" "}
                  et entrez le code ci-dessous.
                </div>
              </div>
            </div>
          ),
          { duration: 8000 }
        );
      }
    } else if (linkSuccess === "1") {
      const provider = params.get("provider");
      const email    = params.get("email");
      toast.success(`${provider ?? "Compte"} lié${email ? ` (${email})` : ""}`);
      router.replace("/settings?tab=linked_accounts");
      refresh();
    } else if (linkError) {
      toast.error(`Échec liaison : ${linkError}`);
      router.replace("/settings?tab=linked_accounts");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  // Load events when a card is selected
  useEffect(() => {
    if (!selectedId || events[selectedId]) return;
    linkedAccountsApi
      .detail(selectedId)
      .then((d) =>
        setEvents((prev) => ({ ...prev, [selectedId]: d.events || [] }))
      )
      .catch(() => {});
  }, [selectedId, events]);

  const handleLink = async (provider: OAuthProvider) => {
    try {
      const { authorization_url } = await linkedAccountsApi.initiate(provider);
      window.location.href = authorization_url;
    } catch (err: unknown) {
      const e = err as {
        response?: { data?: { message?: string } };
        message?: string;
        code?: string;
      };
      const serverMsg  = e?.response?.data?.message;
      const networkMsg =
        e?.code === "ERR_NETWORK" || !e?.response
          ? "Impossible de joindre le serveur. Vérifiez que le backend est lancé."
          : null;
      toast.error(
        serverMsg || networkMsg || `Erreur lors de l'initialisation OAuth ${provider}`
      );
    }
  };

  const handleUnlink = async (a: LinkedAccount) => {
    const ok = window.confirm(
      `Délier ${PROVIDER_META[a.provider].label} (${a.provider_email}) ?\n` +
        `Log+ cessera de surveiller ce compte.`
    );
    if (!ok) return;
    try {
      await linkedAccountsApi.unlink(a.id);
      toast.success(`${PROVIDER_META[a.provider].label} délié`);
      setSelectedId((cur) => (cur === a.id ? null : cur));
      refresh();
    } catch {
      toast.error("Erreur lors du déliement");
    }
  };

  const handlePoll = async (a: LinkedAccount) => {
    const t = toast.loading(`Vérification ${PROVIDER_META[a.provider].label}…`);
    try {
      const r = await linkedAccountsApi.poll(a.id);
      toast.success(`+${r.new_events} événements`, { id: t });
      setEvents((prev) => ({ ...prev, [a.id]: [] }));
      refresh();
    } catch {
      toast.error("Erreur lors du poll", { id: t });
    }
  };

  const handlePinSuccess = (provider: string, email: string) => {
    clearSession();
    setPinState(null);
    toast.success(`Compte ${provider} (${email}) lié avec succès !`, {
      duration: 5000,
    });
    refresh();
  };

  const handlePinCancel = () => {
    clearSession();
    setPinState(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="card" style={{ padding: 22 }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <div>
            <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>
              Comptes liés
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: "var(--text-2)",
                marginTop: 2,
                maxWidth: 520,
                lineHeight: 1.5,
              }}
            >
              Liez vos comptes Google, Microsoft et GitHub. Log+ surveille les
              connexions pour détecter les tentatives de brute-force, les nouveaux
              appareils et les géolocalisations inhabituelles.
            </div>
          </div>
          <button
            className="btn btn-ghost"
            onClick={refresh}
            disabled={loading}
          >
            {loading ? (
              <Loader2 size={14} className="spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            Rafraîchir
          </button>
        </div>

        <div
          style={{
            marginTop: 18,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 14,
          }}
        >
          {(Object.keys(PROVIDER_META) as OAuthProvider[]).map((p) => (
            <ProviderCard
              key={p}
              provider={p}
              account={accountByProvider[p] || null}
              pinData={
                pinState?.provider === p
                  ? {
                      verificationId: pinState.verificationId,
                      email: pinState.email,
                      secondsLeft: computeSecondsLeft(pinState.startedAt),
                    }
                  : null
              }
              onPinSuccess={handlePinSuccess}
              onLink={handleLink}
              onUnlink={handleUnlink}
              onPoll={handlePoll}
              onSelect={(a) => setSelectedId(a?.id || null)}
              selected={selectedAccount?.provider === p}
            />
          ))}
        </div>
      </div>

      {/* Activity detail panel */}
      {selectedAccount && (
        <div className="card" style={{ padding: 22 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <div>
              <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
                Activité — {PROVIDER_META[selectedAccount.provider].label}
              </div>
              <div className="font-mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>
                {selectedAccount.provider_email}
              </div>
            </div>
            <span style={{ fontSize: 11.5, color: "var(--text-2)" }}>
              30 derniers événements
            </span>
          </div>

          {selectedEvents.length === 0 ? (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                color: "var(--text-2)",
                fontSize: 13,
                border: "1px dashed var(--border)",
                borderRadius: 9,
              }}
            >
              Aucun événement pour l&apos;instant. Cliquez sur « Vérifier » pour
              déclencher un poll.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="tbl" style={{ width: "100%", fontSize: 12.5 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "10px 8px" }}>Quand</th>
                    <th style={{ textAlign: "left", padding: "10px 8px" }}>Type</th>
                    <th style={{ textAlign: "left", padding: "10px 8px" }}>Appareil</th>
                    <th style={{ textAlign: "left", padding: "10px 8px" }}>IP</th>
                    <th style={{ textAlign: "left", padding: "10px 8px" }}>Localisation</th>
                    <th style={{ textAlign: "left", padding: "10px 8px" }}>Risque</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedEvents.map((ev) => (
                    <tr key={ev.id}>
                      <td className="font-mono" style={{ padding: "8px" }}>
                        {new Date(ev.occurred_at).toLocaleString("fr-FR")}
                      </td>
                      <td style={{ padding: "8px" }}>{eventBadge(ev.event_type)}</td>
                      <td style={{ padding: "8px" }}>
                        {[ev.browser, ev.os, ev.device_type]
                          .filter(Boolean)
                          .join(" · ") || "—"}
                        {!ev.is_known_device && (
                          <AlertTriangle
                            size={11}
                            style={{
                              marginLeft: 6,
                              color: "var(--warning)",
                              verticalAlign: -1,
                            }}
                          />
                        )}
                      </td>
                      <td className="font-mono" style={{ padding: "8px" }}>
                        {ev.ip_address || "—"}
                      </td>
                      <td style={{ padding: "8px" }}>
                        {[ev.geo_city, ev.geo_country].filter(Boolean).join(", ") ||
                          "—"}
                        {!ev.is_known_location && ev.geo_country && (
                          <AlertTriangle
                            size={11}
                            style={{
                              marginLeft: 6,
                              color: "var(--warning)",
                              verticalAlign: -1,
                            }}
                          />
                        )}
                      </td>
                      <td style={{ padding: "8px" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            color:
                              ev.risk_score >= 80
                                ? "var(--danger)"
                                : ev.risk_score >= 50
                                ? "var(--warning)"
                                : "var(--text-2)",
                          }}
                        >
                          <UserCheck size={11} />
                          {ev.risk_score}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        @keyframes spinning {
          to { transform: rotate(360deg); }
        }
        :global(.spin) {
          animation: spinning 0.8s linear infinite;
        }
      `}</style>
    </div>
  );
}
