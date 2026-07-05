"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";
import {
  User,
  Lock,
  Settings as Cog,
  Info,
  Shield,
  Bell,
  Moon,
  Sun,
  Save,
  Key,
  Database,
  Link2,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { useConnectors } from "@/hooks/use-collectors";
import { usersApi } from "@/lib/api";
import { getInitials } from "@/lib/utils";
import { LinkedAccountsPanel } from "@/components/settings/linked-accounts-panel";
import { CountryFlag } from "@/components/common/country-flag";
import toast from "react-hot-toast";

type TabId = "profile" | "security" | "linked_accounts" | "preferences" | "sources" | "about";

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: "profile", label: "Profil", icon: User },
  { id: "security", label: "Sécurité", icon: Lock },
  { id: "linked_accounts", label: "Comptes liés", icon: Link2 },
  { id: "sources", label: "Sources logs", icon: Database },
  { id: "preferences", label: "Préférences", icon: Cog },
  { id: "about", label: "À propos", icon: Info },
];

function SettingRow({
  label,
  desc,
  children,
}: {
  label: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 20,
        padding: "14px 0",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500 }}>{label}</div>
        {desc && <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>{desc}</div>}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      className={`switch ${on ? "on" : ""}`}
      onClick={() => onChange(!on)}
      role="switch"
      aria-checked={on}
      tabIndex={0}
    >
      <div />
    </div>
  );
}

function Card({
  title,
  desc,
  children,
}: {
  title?: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card" style={{ padding: 22 }}>
      {title && (
        <div className="font-display" style={{ fontSize: 15, fontWeight: 700 }}>
          {title}
        </div>
      )}
      {desc && <div style={{ fontSize: 12.5, color: "var(--text-2)", marginTop: 2, marginBottom: 8 }}>{desc}</div>}
      <div>{children}</div>
    </div>
  );
}

function SettingsPageContent() {
  const { user } = useAuthStore();
  const { theme, setTheme } = useTheme();
  const params = useSearchParams();
  const initialTab = (params?.get("tab") as TabId | null) || "profile";
  const [tab, setTab] = useState<TabId>(
    (["profile", "security", "linked_accounts", "preferences", "sources", "about"].includes(initialTab as string)
      ? initialTab
      : "profile") as TabId
  );
  const [saving, setSaving] = useState(false);
  const [browser, setBrowser] = useState("Navigateur");
  const [ip, setIp] = useState("—");
  // Fallback hardcodé visible immédiatement — remplacé par les données réelles dès qu'elles arrivent
  const [geo, setGeo] = useState<{ city: string; country: string; countryCode: string }>({
    city: "Abidjan",
    country: "Côte d'Ivoire",
    countryCode: "CI",
  });
  const [geoSource, setGeoSource] = useState<"default" | "browser" | "ip">("default");

  useEffect(() => {
    // ─── Détection navigateur ─────────────────────────────────────────────────
    const ua = navigator.userAgent.toLowerCase();
    let b = "Navigateur";
    if (ua.includes("chrome") && !ua.includes("edg")) b = "Chrome";
    else if (ua.includes("firefox")) b = "Firefox";
    else if (ua.includes("safari") && !ua.includes("chrome")) b = "Safari";
    else if (ua.includes("edg")) b = "Edge";
    setBrowser(b);

    // ─── Fallback IP (pour l'adresse IP affichée) ─────────────────────────────
    const fetchIpOnly = () =>
      fetch("https://api.ipify.org?format=json")
        .then((r) => r.json())
        .then((d) => setIp(d.ip))
        .catch(() => {});

    // ─── Fallback 2 : géolocalisation par IP (pas de popup) ──────────────────
    // ip-api.com (plan gratuit) ne répond qu'en HTTP, pas en HTTPS (403 sinon).
    // Le site étant lui-même servi en HTTP, pas de blocage "mixed content" ici.
    const fetchIpGeo = () =>
      fetch("http://ip-api.com/json/?fields=status,city,country,countryCode,query")
        .then((r) => r.json())
        .then((d) => {
          if (d.status === "success") {
            setIp(d.query);
            setGeo({ city: d.city, country: d.country, countryCode: d.countryCode });
            setGeoSource("ip");
          } else {
            fetchIpOnly();
          }
        })
        .catch(() => fetchIpOnly());

    // ─── Priorité 1 : geolocation navigateur (affiche la popup) ─────────────
    if (typeof navigator !== "undefined" && "geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude, longitude } = pos.coords;
          try {
            const res = await fetch(
              `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=fr`
            );
            const d = await res.json();
            if (d.countryCode) {
              setGeo({
                city: d.city || d.locality || d.principalSubdivision || "—",
                country: d.countryName,
                countryCode: d.countryCode,
              });
              setGeoSource("browser");
            }
          } catch {
            // reverse-geocode a échoué, on essaie par IP
            fetchIpGeo();
          }
          // dans tous les cas on récupère l'IP publique
          fetchIpOnly();
        },
        () => {
          // Permission refusée ou timeout → fallback IP
          fetchIpGeo();
        },
        { timeout: 8000, maximumAge: 300_000 }
      );
    } else {
      fetchIpGeo();
    }
  }, []);

  const [profile, setProfile] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    email: user?.email || "",
  });

  const [pwd, setPwd] = useState({ current: "", next: "", confirm: "" });

  const [prefs, setPrefs] = useState({
    emailNotifs: true,
    criticalAlerts: true,
    weeklyReport: false,
    twofa: true,
    sso: true,
  });

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      await usersApi.updateMe({
        first_name: profile.first_name,
        last_name: profile.last_name,
        email: profile.email,
      });
      toast.success("Profil mis à jour");
    } catch {
      toast.error("Erreur lors de la mise à jour du profil");
    } finally {
      setSaving(false);
    }
  };

  const handleChangePwd = async () => {
    if (!pwd.current || !pwd.next) return toast.error("Remplissez tous les champs");
    if (pwd.next !== pwd.confirm) return toast.error("Les mots de passe ne correspondent pas");
    if (pwd.next.length < 8) return toast.error("Min. 8 caractères");
    setSaving(true);
    try {
      await usersApi.changePassword(pwd.current, pwd.next);
      setPwd({ current: "", next: "", confirm: "" });
      toast.success("Mot de passe changé");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? "Mot de passe actuel incorrect");
    } finally {
      setSaving(false);
    }
  };

  const { data: connectorsData = [] } = useConnectors();
  const sources = Array.isArray(connectorsData) ? connectorsData : [];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
          Paramètres
        </div>
        <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2 }}>
          Configuration de votre consoLog+
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "220px 1fr",
          gap: 20,
        }}
        className="settings-grid"
      >
        {/* Vertical tabs */}
        <div className="card" style={{ padding: 8, alignSelf: "flex-start" }}>
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <div
                key={t.id}
                role="button"
                tabIndex={0}
                onClick={() => setTab(t.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  borderRadius: 9,
                  cursor: "pointer",
                  background: active ? "color-mix(in srgb, var(--primary) 10%, transparent)" : "transparent",
                  color: active ? "var(--primary)" : "var(--text-2)",
                  fontWeight: active ? 600 : 500,
                  fontSize: 13,
                  transition: "all 140ms",
                }}
              >
                <Icon size={16} />
                {t.label}
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          {tab === "profile" && (
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              {/* Avatar hero */}
              <div
                style={{
                  background: "linear-gradient(135deg, color-mix(in srgb, var(--primary) 12%, transparent), color-mix(in srgb, var(--secondary) 7%, transparent))",
                  padding: "36px 28px 28px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 14,
                  borderBottom: "1px solid var(--border)",
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    width: 84,
                    height: 84,
                    borderRadius: 999,
                    background: "linear-gradient(135deg, var(--primary), var(--secondary))",
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 800,
                    fontSize: 30,
                    letterSpacing: "-0.02em",
                    boxShadow: "0 10px 28px -8px color-mix(in srgb, var(--primary) 45%, transparent)",
                    border: "3px solid color-mix(in srgb, var(--primary) 25%, transparent)",
                    flexShrink: 0,
                  }}
                >
                  {user ? getInitials(user.full_name) : "?"}
                </div>
                <div>
                  <div
                    className="font-display"
                    style={{ fontSize: 19, fontWeight: 700, letterSpacing: "-0.01em" }}
                  >
                    {user?.full_name || "Utilisateur"}
                  </div>
                  <div
                    className="font-mono"
                    style={{ fontSize: 13, color: "var(--text-2)", marginTop: 4 }}
                  >
                    {user?.email}
                  </div>
                  <span
                    className="badge badge-info"
                    style={{ marginTop: 10, textTransform: "capitalize", display: "inline-block", fontSize: 11 }}
                  >
                    {user?.role || "viewer"}
                  </span>
                </div>
              </div>

              {/* Form section */}
              <div style={{ padding: "24px 28px" }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: "var(--text-2)",
                    textTransform: "uppercase",
                    letterSpacing: "0.07em",
                    marginBottom: 18,
                  }}
                >
                  Informations personnelles
                </div>

                {/* First + Last name row */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 14,
                    marginBottom: 14,
                  }}
                  className="profile-names"
                >
                  <div>
                    <label
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--text-2)",
                        display: "block",
                        marginBottom: 6,
                      }}
                    >
                      Prénom
                    </label>
                    <input
                      className="input"
                      value={profile.first_name}
                      onChange={(e) => setProfile((p) => ({ ...p, first_name: e.target.value }))}
                      placeholder="Prénom"
                    />
                  </div>
                  <div>
                    <label
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--text-2)",
                        display: "block",
                        marginBottom: 6,
                      }}
                    >
                      Nom
                    </label>
                    <input
                      className="input"
                      value={profile.last_name}
                      onChange={(e) => setProfile((p) => ({ ...p, last_name: e.target.value }))}
                      placeholder="Nom de famille"
                    />
                  </div>
                </div>

                {/* Email */}
                <div style={{ marginBottom: 24 }}>
                  <label
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--text-2)",
                      display: "block",
                      marginBottom: 6,
                    }}
                  >
                    Adresse email
                  </label>
                  <input
                    className="input"
                    type="email"
                    value={profile.email}
                    onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
                    placeholder="votre@email.com"
                  />
                  <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 5 }}>
                    Utilisée pour les notifications et l&apos;authentification
                  </div>
                </div>

                {/* Actions */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: 8,
                    paddingTop: 18,
                    borderTop: "1px solid var(--border)",
                  }}
                >
                  <button
                    className="btn"
                    onClick={() =>
                      setProfile({
                        first_name: user?.first_name || "",
                        last_name: user?.last_name || "",
                        email: user?.email || "",
                      })
                    }
                  >
                    Annuler
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleSaveProfile}
                    disabled={saving}
                  >
                    <Save size={13} />
                    {saving ? "Enregistrement…" : "Enregistrer"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {tab === "security" && (
            <>
              <Card title="Changer le mot de passe" desc="Min. 8 caractères, une majuscule et un chiffre recommandés">
                <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)" }}>Actuel</label>
                    <input
                      className="input"
                      type="password"
                      value={pwd.current}
                      onChange={(e) => setPwd((p) => ({ ...p, current: e.target.value }))}
                      style={{ marginTop: 4 }}
                      placeholder="••••••••"
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)" }}>Nouveau</label>
                    <input
                      className="input"
                      type="password"
                      value={pwd.next}
                      onChange={(e) => setPwd((p) => ({ ...p, next: e.target.value }))}
                      style={{ marginTop: 4 }}
                      placeholder="Min. 8 caractères"
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)" }}>Confirmer</label>
                    <input
                      className="input"
                      type="password"
                      value={pwd.confirm}
                      onChange={(e) => setPwd((p) => ({ ...p, confirm: e.target.value }))}
                      style={{ marginTop: 4 }}
                      placeholder="••••••••"
                    />
                  </div>
                </div>
                <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
                  <button className="btn btn-primary" onClick={handleChangePwd} disabled={saving}>
                    <Key size={13} />
                    Mettre à jour
                  </button>
                </div>
              </Card>

              <Card title="Authentification forte">
                <SettingRow label="2FA obligatoire" desc="Exige TOTP pour tous les comptes">
                  <Toggle on={prefs.twofa} onChange={(v) => setPrefs((p) => ({ ...p, twofa: v }))} />
                </SettingRow>
                <SettingRow label="SSO SAML" desc="Fournisseur : Microsoft Entra ID">
                  <Toggle on={prefs.sso} onChange={(v) => setPrefs((p) => ({ ...p, sso: v }))} />
                </SettingRow>
                <SettingRow label="Durée max de session" desc="Déconnexion forcée après inactivité">
                  <select className="input" defaultValue="8" style={{ width: 160 }}>
                    <option value="4">4 heures</option>
                    <option value="8">8 heures</option>
                    <option value="24">24 heures</option>
                  </select>
                </SettingRow>
              </Card>

              <Card title="Sessions actives" desc="Connexions en cours sur votre compte">
                <table className="tbl" style={{ marginTop: 6 }}>
                  <thead>
                    <tr>
                      <th>Appareil</th>
                      <th>IP</th>
                      <th>Localisation</th>
                      <th>Statut</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 500 }}>{browser} · {typeof navigator !== "undefined" && navigator.platform.includes("Win") ? "Windows" : "Inconnu"}</td>
                      <td className="font-mono">{ip}</td>
                      <td>
                        <span className="inline-flex items-center gap-2">
                          <CountryFlag code={geo.countryCode} size="md" />
                          <span className="font-mono text-xs" style={{ color: "var(--text-2)" }}>
                            {geo.city}, {geo.countryCode}
                          </span>
                          {geoSource === "browser" && (
                            <span
                              title="Localisation précise — permission accordée"
                              style={{ fontSize: 9, color: "var(--secondary)", fontWeight: 600, letterSpacing: "0.04em" }}
                            >
                              GPS
                            </span>
                          )}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-ok">Actuelle</span>
                      </td>
                      <td>
                        <span className="chip">Vous</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </Card>
            </>
          )}

          {tab === "linked_accounts" && <LinkedAccountsPanel />}

          {tab === "sources" && (
            <Card title="Sources de logs" desc="Connecteurs d'ingestion configurés">
              <div style={{ overflowX: "auto" }}>
                <table className="tbl" style={{ marginTop: 6 }}>
                  <thead>
                    <tr>
                      <th>Connecteur</th>
                      <th>Type</th>
                      <th>EPS</th>
                      <th>Dernière sync</th>
                      <th>État</th>
                      <th>Actif</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-2)", padding: 20 }}>Aucun connecteur configuré</td></tr>
                    )}
                    {sources.map((s) => {
                      const isActive = s.status === "active";
                      const isDegraded = s.last_job_status === "failed";
                      return (
                      <tr key={s.id}>
                        <td style={{ fontWeight: 500 }}>{s.display_name || s.name}</td>
                        <td className="font-mono" style={{ fontSize: 12 }}>{s.connector_type}</td>
                        <td className="font-mono">{(s.logs_collected_24h ?? 0).toLocaleString("fr-FR")}</td>
                        <td className="font-mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>{s.last_collected_at ? new Date(s.last_collected_at).toLocaleString("fr-FR") : "—"}</td>
                        <td>
                          {isActive ? (
                            isDegraded ? (
                              <span className="badge badge-high">Dégradé</span>
                            ) : (
                              <span className="badge badge-ok">Actif</span>
                            )
                          ) : (
                            <span className="badge badge-info">Inactif</span>
                          )}
                        </td>
                        <td>
                          <Toggle on={isActive} onChange={() => {}} />
                        </td>
                      </tr>
                    )})}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {tab === "preferences" && (
            <>
              <Card title="Apparence" desc="Thème de l'interface">
                <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
                  {(["dark", "light"] as const).map((t) => {
                    const active = theme === t;
                    const Icon = t === "dark" ? Moon : Sun;
                    return (
                      <button
                        key={t}
                        onClick={() => setTheme(t)}
                        style={{
                          flex: 1,
                          padding: 18,
                          borderRadius: 12,
                          border: `2px solid ${active ? "var(--primary)" : "var(--border)"}`,
                          background: active ? "color-mix(in srgb, var(--primary) 8%, transparent)" : "var(--surface)",
                          cursor: "pointer",
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          gap: 8,
                          color: "var(--text)",
                          fontWeight: 500,
                          fontSize: 13,
                        }}
                      >
                        <Icon size={22} />
                        {t === "dark" ? "Mode sombre" : "Mode clair"}
                      </button>
                    );
                  })}
                </div>
              </Card>

              <Card title="Notifications" desc="Canaux de diffusion des alertes">
                <SettingRow label="Notifications par email" desc="Recevoir les alertes par email">
                  <Toggle on={prefs.emailNotifs} onChange={(v) => setPrefs((p) => ({ ...p, emailNotifs: v }))} />
                </SettingRow>
                <SettingRow label="Alertes critiques" desc="Notification immédiate pour les alertes critiques">
                  <Toggle on={prefs.criticalAlerts} onChange={(v) => setPrefs((p) => ({ ...p, criticalAlerts: v }))} />
                </SettingRow>
                <SettingRow label="Rapport hebdomadaire" desc="Résumé hebdomadaire de l'activité Log+">
                  <Toggle on={prefs.weeklyReport} onChange={(v) => setPrefs((p) => ({ ...p, weeklyReport: v }))} />
                </SettingRow>
              </Card>
            </>
          )}

          {tab === "about" && (
            <Card>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 14,
                  padding: "20px 0",
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 16,
                    background: "linear-gradient(135deg, var(--primary), var(--secondary))",
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 12px 30px -10px color-mix(in srgb, var(--primary) 40%, transparent)",
                  }}
                >
                  <Shield size={28} />
                </div>
                <div className="font-display" style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>
                  Log+
                </div>
                <div style={{ fontSize: 13, color: "var(--text-2)" }}>
                  Security Information &amp; Event Management
                </div>
                <span className="chip">
                  <Bell size={12} /> Version 1.0.0
                </span>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: 12,
                  marginTop: 20,
                }}
              >
                {[
                  { l: "Backend", v: "Django REST Framework" },
                  { l: "Frontend", v: "Next.js 16 · React 18" },
                  { l: "ML Engine", v: "Isolation Forest" },
                  { l: "Base de données", v: "PostgreSQL 16" },
                  { l: "Environnement", v: "Production" },
                  { l: "Région", v: "eu-west-3" },
                ].map((row) => (
                  <div
                    key={row.l}
                    style={{
                      padding: 12,
                      borderRadius: 10,
                      background: "color-mix(in srgb, var(--text) 4%, transparent)",
                    }}
                  >
                    <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {row.l}
                    </div>
                    <div className="font-mono" style={{ fontSize: 12.5, marginTop: 4 }}>
                      {row.v}
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 24, textAlign: "center" }}>
                <div style={{ fontSize: 13, color: "var(--text-2)" }}>Développé par</div>
                <div className="font-display" style={{ fontSize: 17, fontWeight: 700, marginTop: 4 }}>
                  TAHI Ezan Franck Emmanuel
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 800px) {
          :global(.settings-grid) {
            grid-template-columns: 1fr !important;
          }
          :global(.profile-names) {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsPageContent />
    </Suspense>
  );
}
