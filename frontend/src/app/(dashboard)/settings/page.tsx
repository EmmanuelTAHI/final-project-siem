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
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth-store";
import { useConnectors } from "@/hooks/use-collectors";
import { authApi, collectorsApi, usersApi } from "@/lib/api";
import { getInitials } from "@/lib/utils";
import { SUPPORTED_LANGUAGES, getCurrentLanguage, setLanguage } from "@/lib/i18n";
import { validatePasswordChange } from "@/lib/validation";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { LinkedAccountsPanel } from "@/components/settings/linked-accounts-panel";
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
  const [currentLang, setCurrentLang] = useState<string>("fr");
  useEffect(() => {
    setCurrentLang(getCurrentLanguage());
  }, []);

  const [profile, setProfile] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    email: user?.email || "",
  });

  const [pwd, setPwd] = useState({ current: "", next: "", confirm: "" });
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);

  const [prefs, setPrefs] = useState({
    emailNotifs: user?.email_notifications ?? true,
    criticalAlerts: user?.critical_alert_emails ?? true,
    weeklyReport: user?.weekly_report_email ?? false,
  });

  const handleTogglePref = async (
    key: "emailNotifs" | "criticalAlerts" | "weeklyReport",
    field: "email_notifications" | "critical_alert_emails" | "weekly_report_email",
    value: boolean
  ) => {
    const previous = prefs[key];
    setPrefs((p) => ({ ...p, [key]: value }));
    try {
      const updated = await usersApi.updateMe({ [field]: value });
      if (user) setUser({ ...user, ...updated });
    } catch {
      setPrefs((p) => ({ ...p, [key]: previous }));
      toast.error("Erreur lors de l'enregistrement de la préférence");
    }
  };

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: authApi.getSessions,
    enabled: tab === "security",
    staleTime: 10_000,
  });
  const sessions = sessionsData?.sessions ?? [];

  const handleRevokeSession = async (id: string) => {
    try {
      await authApi.revokeSession(id);
      toast.success("Session révoquée");
      qc.invalidateQueries({ queryKey: ["sessions"] });
    } catch {
      toast.error("Erreur lors de la révocation de la session");
    }
  };

  const handleToggleConnector = async (id: string, nextActive: boolean) => {
    try {
      await collectorsApi.updateConnector(id, { is_active: nextActive });
      toast.success(nextActive ? "Connecteur activé" : "Connecteur désactivé");
      qc.invalidateQueries({ queryKey: ["connectors"] });
    } catch {
      toast.error("Erreur lors de la mise à jour du connecteur");
    }
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const updated = await usersApi.updateMe({
        first_name: profile.first_name,
        last_name: profile.last_name,
        email: profile.email,
      });
      setUser(updated);
      toast.success("Profil mis à jour");
    } catch {
      toast.error("Erreur lors de la mise à jour du profil");
    } finally {
      setSaving(false);
    }
  };

  const handleChangePwd = async () => {
    const validationError = validatePasswordChange(pwd.current, pwd.next, pwd.confirm);
    if (validationError) return toast.error(validationError);
    setSaving(true);
    try {
      await usersApi.changePassword(pwd.current, pwd.next);
      setPwd({ current: "", next: "", confirm: "" });
      toast.success("Mot de passe changé");
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; errors?: Record<string, string[]> } } })
        ?.response?.data;
      // Remonter l'erreur de validation précise (mdp actuel incorrect,
      // mdp trop court/commun selon les validateurs Django…) plutôt
      // que le générique "Données invalides".
      const firstFieldError = data?.errors
        ? Object.values(data.errors).flat()[0]
        : undefined;
      toast.error(firstFieldError ?? data?.message ?? "Mot de passe actuel incorrect");
    } finally {
      setSaving(false);
    }
  };

  const { data: connectorsData = [] } = useConnectors();
  const sources = Array.isArray(connectorsData) ? connectorsData : [];

  return (
    <div className="page" style={{ padding: 24 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="font-display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
          Paramètres
        </div>
        <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 2 }}>
          Configuration de votre consoArgus
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
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  <div className="space-y-2">
                    <Label>Prénom</Label>
                    <Input
                      value={profile.first_name}
                      onChange={(e) => setProfile((p) => ({ ...p, first_name: e.target.value }))}
                      placeholder="Prénom"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Nom</Label>
                    <Input
                      value={profile.last_name}
                      onChange={(e) => setProfile((p) => ({ ...p, last_name: e.target.value }))}
                      placeholder="Nom de famille"
                    />
                  </div>
                </div>

                {/* Email */}
                <div className="space-y-2 mb-6">
                  <Label>Adresse email</Label>
                  <Input
                    type="email"
                    value={profile.email}
                    onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
                    placeholder="votre@email.com"
                  />
                  <p className="text-xs text-muted-foreground">
                    Utilisée pour les notifications et l&apos;authentification
                  </p>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-4 border-t border-border">
                  <Button
                    variant="outline"
                    onClick={() =>
                      setProfile({
                        first_name: user?.first_name || "",
                        last_name: user?.last_name || "",
                        email: user?.email || "",
                      })
                    }
                  >
                    Annuler
                  </Button>
                  <Button onClick={handleSaveProfile} disabled={saving}>
                    <Save size={13} />
                    {saving ? "Enregistrement…" : "Enregistrer"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {tab === "security" && (
            <>
              <Card title="Changer le mot de passe" desc="Min. 8 caractères, une majuscule et un chiffre recommandés">
                <div className="flex flex-col gap-3 mt-3">
                  <div className="space-y-2">
                    <Label>Actuel</Label>
                    <Input
                      type="password"
                      value={pwd.current}
                      onChange={(e) => setPwd((p) => ({ ...p, current: e.target.value }))}
                      placeholder="••••••••"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Nouveau</Label>
                    <Input
                      type="password"
                      value={pwd.next}
                      onChange={(e) => setPwd((p) => ({ ...p, next: e.target.value }))}
                      placeholder="Min. 8 caractères"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Confirmer</Label>
                    <Input
                      type="password"
                      value={pwd.confirm}
                      onChange={(e) => setPwd((p) => ({ ...p, confirm: e.target.value }))}
                      placeholder="••••••••"
                    />
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Button onClick={handleChangePwd} disabled={saving}>
                    <Key size={13} />
                    Mettre à jour
                  </Button>
                </div>
              </Card>

              <Card title="Authentification" desc="Une vérification par code envoyé par email est exigée à chaque connexion pour tous les comptes.">
                <div style={{ fontSize: 12.5, color: "var(--text-2)", padding: "6px 0" }}>
                  Aucune configuration nécessaire — le second facteur (OTP email) est actif en permanence.
                </div>
              </Card>

              <Card title="Sessions actives" desc="Connexions en cours sur votre compte">
                <div className="tbl-scroll">
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
                    {sessionsLoading && (
                      <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-2)", padding: 20 }}>Chargement…</td></tr>
                    )}
                    {!sessionsLoading && sessions.length === 0 && (
                      <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-2)", padding: 20 }}>Aucune session active</td></tr>
                    )}
                    {sessions.map((s) => (
                      <tr key={s.id}>
                        <td style={{ fontWeight: 500 }}>{s.device}</td>
                        <td className="font-mono">{s.ip}</td>
                        <td className="font-mono text-xs" style={{ color: "var(--text-2)" }}>{s.location}</td>
                        <td>
                          <span className={s.current ? "badge badge-ok" : "badge badge-info"}>
                            {s.current ? "Actuelle" : "Active"}
                          </span>
                        </td>
                        <td>
                          {s.current ? (
                            <span className="chip">Vous</span>
                          ) : (
                            <button className="btn" style={{ fontSize: 11.5, padding: "5px 10px" }} onClick={() => handleRevokeSession(s.id)}>
                              Déconnecter
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
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
                          <Toggle on={isActive} onChange={(v) => handleToggleConnector(s.id, v)} />
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
              <Card title="Langue" desc="Langue d'affichage de l'interface — traduction fournie par Google Translate">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                    gap: 10,
                    marginTop: 12,
                  }}
                >
                  {SUPPORTED_LANGUAGES.map((lang) => {
                    const active = currentLang === lang.code;
                    return (
                      <button
                        key={lang.code}
                        onClick={() => {
                          if (!active) setLanguage(lang.code);
                        }}
                        className="notranslate"
                        style={{
                          padding: "14px 10px",
                          borderRadius: 12,
                          border: `2px solid ${active ? "var(--primary)" : "var(--border)"}`,
                          background: active
                            ? "color-mix(in srgb, var(--primary) 8%, transparent)"
                            : "var(--surface)",
                          cursor: active ? "default" : "pointer",
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          gap: 8,
                          color: "var(--text)",
                          fontWeight: active ? 600 : 500,
                          fontSize: 13,
                          transition: "all 140ms ease",
                        }}
                      >
                        <span
                          className={`fi fi-${lang.flag}`}
                          style={{ fontSize: 22, borderRadius: 4 }}
                        />
                        {lang.label}
                        {active && (
                          <span
                            className="badge badge-info"
                            style={{ fontSize: 9.5 }}
                          >
                            Actif
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </Card>

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
                  <Toggle on={prefs.emailNotifs} onChange={(v) => handleTogglePref("emailNotifs", "email_notifications", v)} />
                </SettingRow>
                <SettingRow label="Alertes critiques" desc="Notification immédiate pour les alertes critiques">
                  <Toggle on={prefs.criticalAlerts} onChange={(v) => handleTogglePref("criticalAlerts", "critical_alert_emails", v)} />
                </SettingRow>
                <SettingRow label="Rapport hebdomadaire" desc="Résumé hebdomadaire de l'activité Argus">
                  <Toggle on={prefs.weeklyReport} onChange={(v) => handleTogglePref("weeklyReport", "weekly_report_email", v)} />
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
                  Argus
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
