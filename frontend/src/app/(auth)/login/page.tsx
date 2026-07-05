"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Shield,
  Eye,
  EyeOff,
  Lock,
  Mail,
  AlertCircle,
  ChevronRight,
  RefreshCw,
  ArrowLeft,
  KeyRound,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { authApi } from "@/lib/api";
import toast from "react-hot-toast";

// ─── Session OTP persistée (survit aux rechargements) ─────────────────────────
const SESSION_KEY = "logplus_otp_session";

interface OtpSession {
  preAuthToken: string;
  email: string;
  expiresAt: number; // ms timestamp
  sentAt: number;    // ms timestamp — pour calculer le cooldown restant
}

function saveOtpSession(s: OtpSession) {
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(s)); } catch { /* private/incognito */ }
}

function loadOtpSession(): OtpSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s: OtpSession = JSON.parse(raw);
    if (Date.now() > s.expiresAt) {
      sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return s;
  } catch {
    return null;
  }
}

function clearOtpSession() {
  try { sessionStorage.removeItem(SESSION_KEY); } catch { /* */ }
}

// ─── Composant 6 cases OTP ────────────────────────────────────────────────────

function OtpInput({
  value,
  onChange,
  disabled,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);

  const handleKeyDown = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (value[i]) {
        onChange(value.slice(0, i) + value.slice(i + 1));
      } else if (i > 0) {
        refs.current[i - 1]?.focus();
        onChange(value.slice(0, i - 1) + value.slice(i));
      }
    } else if (e.key === "ArrowLeft" && i > 0) {
      refs.current[i - 1]?.focus();
    } else if (e.key === "ArrowRight" && i < 5) {
      refs.current[i + 1]?.focus();
    }
  };

  const handleChange = (i: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, "");
    if (!raw) return;
    if (raw.length > 1) {
      // paste via input onChange
      const filled = (value.slice(0, i) + raw).slice(0, 6);
      onChange(filled);
      refs.current[Math.min(i + raw.length, 5)]?.focus();
      return;
    }
    const next = (value.slice(0, i) + raw + value.slice(i + 1)).slice(0, 6);
    onChange(next);
    if (i < 5) refs.current[i + 1]?.focus();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    onChange(pasted);
    refs.current[Math.min(pasted.length, 5)]?.focus();
  };

  return (
    <div style={{ display: "flex", gap: 10, justifyContent: "center" }} onPaste={handlePaste}>
      {Array.from({ length: 6 }).map((_, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={2}
          value={value[i] || ""}
          disabled={disabled}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onFocus={(e) => e.target.select()}
          style={{
            width: 46,
            height: 54,
            textAlign: "center",
            fontSize: 22,
            fontWeight: 700,
            fontFamily: "monospace",
            borderRadius: 10,
            border: `2px solid ${value[i] ? "var(--primary, #3B82F6)" : "var(--border, #2A3550)"}`,
            background: "var(--bg-card, #111A30)",
            color: "var(--text)",
            outline: "none",
            transition: "border-color 0.15s",
            caretColor: "transparent",
            cursor: disabled ? "not-allowed" : "text",
            opacity: disabled ? 0.6 : 1,
          }}
        />
      ))}
    </div>
  );
}

// ─── Bannière d'erreur ────────────────────────────────────────────────────────

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: 12,
        borderRadius: 9,
        marginBottom: 14,
        background: "color-mix(in srgb, var(--danger, #EF4444) 10%, transparent)",
        border: "1px solid color-mix(in srgb, var(--danger, #EF4444) 30%, transparent)",
        color: "var(--danger, #EF4444)",
        fontSize: 12.5,
      }}
    >
      <AlertCircle size={14} style={{ flexShrink: 0 }} />
      <span>{message}</span>
    </div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────

type Step = "credentials" | "otp";

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";
  const { setAuth, isAuthenticated } = useAuthStore();

  const [step, setStep] = useState<Step>("credentials");

  // Step 1
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Step 2
  const [preAuthToken, setPreAuthToken] = useState("");
  const [otp, setOtp] = useState("");
  const [resendCooldown, setResendCooldown] = useState(0);
  const [sessionExpired, setSessionExpired] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // ── Restauration depuis sessionStorage au montage ────────────────────────────
  useEffect(() => {
    const stored = loadOtpSession();
    if (stored) {
      setEmail(stored.email);
      setPreAuthToken(stored.preAuthToken);
      // Cooldown restant basé sur le moment d'envoi
      const elapsed = Math.floor((Date.now() - stored.sentAt) / 1000);
      const remaining = Math.max(0, 60 - elapsed);
      setResendCooldown(remaining);
      setStep("otp");
    }
  }, []);

  // Redirection si déjà authentifié
  useEffect(() => {
    if (isAuthenticated) router.replace(redirect);
  }, [isAuthenticated, router, redirect]);

  // Compte à rebours renvoi
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCooldown]);

  // ── Étape 1 : credentials ────────────────────────────────────────────────────
  const handleCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError("Veuillez remplir tous les champs"); return; }
    setIsLoading(true);
    setError("");
    try {
      const result = await authApi.login({ email, password });
      const now = Date.now();
      const session: OtpSession = {
        preAuthToken: result.pre_auth_token,
        email,
        expiresAt: now + 10 * 60 * 1000, // 10 min — correspond au max_age backend
        sentAt: now,
      };
      saveOtpSession(session);
      setPreAuthToken(result.pre_auth_token);
      setOtp("");
      setResendCooldown(60);
      setSessionExpired(false);
      setStep("otp");
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { message?: string; detail?: string } }; code?: string };
      const isNet = ax?.code === "ERR_NETWORK" || !ax?.response;
      setError(
        isNet
          ? "Impossible de joindre le serveur. Vérifiez que le backend est lancé."
          : ax?.response?.data?.message || ax?.response?.data?.detail || "Email ou mot de passe incorrect"
      );
    } finally {
      setIsLoading(false);
    }
  };

  // ── Étape 2 : vérification OTP ───────────────────────────────────────────────
  const handleOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (otp.length !== 6) { setError("Entrez le code à 6 chiffres reçu par email"); return; }
    setIsLoading(true);
    setError("");
    try {
      const data = await authApi.verifyOtp(otp, preAuthToken);
      clearOtpSession();
      setAuth(data.user, data.access, data.refresh);
      toast.success(`Bienvenue, ${data.user.first_name} !`);
      router.replace(redirect);
    } catch (err: unknown) {
      const ax = err as {
        response?: { status?: number; data?: { message?: string; detail?: string } };
        code?: string;
      };
      const httpStatus = ax?.response?.status;
      const msg =
        ax?.response?.data?.message ||
        ax?.response?.data?.detail ||
        "Code invalide ou expiré";

      // Session expirée (pre_auth_token périmé) ou trop de tentatives → retour forcé
      if (httpStatus === 401 || httpStatus === 429) {
        clearOtpSession();
        setSessionExpired(true);
        setStep("credentials");
        setOtp("");
        setPreAuthToken("");
        setError(msg);
      } else {
        setError(msg);
        setOtp("");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ── Renvoi OTP ───────────────────────────────────────────────────────────────
  const handleResend = useCallback(async () => {
    if (resendCooldown > 0) return;
    setError("");
    try {
      await authApi.resendOtp(preAuthToken);
      // Mettre à jour le sentAt dans sessionStorage
      const stored = loadOtpSession();
      if (stored) saveOtpSession({ ...stored, sentAt: Date.now() });
      toast.success("Nouveau code envoyé par email");
      setResendCooldown(60);
      setOtp("");
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { message?: string } } };
      const msg = ax?.response?.data?.message || "Impossible de renvoyer le code";
      // Si le pre_auth_token a expiré lors du renvoi
      if ((err as { response?: { status?: number } })?.response?.status === 401) {
        clearOtpSession();
        setSessionExpired(true);
        setStep("credentials");
        setPreAuthToken("");
        setOtp("");
        setError("Session expirée. Veuillez vous reconnecter.");
      } else {
        toast.error(msg);
      }
    }
  }, [resendCooldown, preAuthToken]);

  // ── Retour vers credentials ──────────────────────────────────────────────────
  const handleBack = () => {
    clearOtpSession();
    setStep("credentials");
    setOtp("");
    setPreAuthToken("");
    setError("");
    setSessionExpired(false);
  };

  // ─────────────────────────────────────────────────────────────────────────────

  return (
    <div
      className="login-grid"
      style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", minHeight: "100vh" }}
    >
      {/* Panneau gauche */}
      <div
        className="login-left"
        style={{ display: "flex", flexDirection: "column", padding: 50, color: "white", position: "relative", zIndex: 1 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, position: "relative", zIndex: 2 }}>
          <div
            style={{
              width: 42, height: 42, borderRadius: 11,
              background: "linear-gradient(135deg, #3B82F6, #06D6A0)",
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 10px 30px -10px rgba(59,130,246,0.5)",
            }}
          >
            <Shield size={20} />
          </div>
          <div className="font-display" style={{ fontWeight: 800, fontSize: 18, letterSpacing: "-0.02em" }}>
            Log<span style={{ color: "#3B82F6" }}>+</span>
          </div>
        </div>

        <div
          style={{
            flex: 1, display: "flex", flexDirection: "column", justifyContent: "center",
            position: "relative", zIndex: 2, maxWidth: 480,
          }}
        >
          <div className="chip" style={{ alignSelf: "flex-start", marginBottom: 24, color: "white", borderColor: "rgba(255,255,255,0.15)" }}>
            <span className="dot live" style={{ width: 7, height: 7 }} />
            Centre opérationnel de sécurité
          </div>
          <div className="font-display" style={{ fontSize: 44, fontWeight: 800, lineHeight: 1.05, letterSpacing: "-0.03em" }}>
            Détection, corrélation et réponse
            <br />
            <span style={{ color: "#06D6A0" }}>en temps réel.</span>
          </div>
          <div style={{ fontSize: 15, color: "#8B9EC7", marginTop: 18, lineHeight: 1.55 }}>
            Ingestion multi-source — Microsoft 365, Google Workspace, Wazuh, Syslog, EDR — et moteur
            de corrélation MITRE ATT&CK couplé à un détecteur d&apos;anomalies ML.
          </div>
          <div style={{ display: "flex", gap: 28, marginTop: 36 }}>
            {[["Multi-source", "ingestion"], ["MITRE ATT&CK", "corrélation"], ["ML", "détection"]].map(([n, l]) => (
              <div key={l}>
                <div className="font-display font-mono" style={{ fontSize: 18, fontWeight: 700, color: "white" }}>{n}</div>
                <div style={{ fontSize: 11.5, color: "#8B9EC7", letterSpacing: "0.04em", textTransform: "uppercase", marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="font-mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#8B9EC7", position: "relative", zIndex: 2 }}>
          <span>cluster-01 · region eu-west-3</span>
          <span>© 2026 Log+ · TAHI Ezan Franck Emmanuel</span>
        </div>
      </div>

      {/* Panneau droit */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 40, background: "var(--bg)" }}>

        {step === "credentials" ? (
          /* ── Formulaire credentials ─────────────────────────────────────── */
          <form onSubmit={handleCredentials} className="card card-glass" style={{ width: "100%", maxWidth: 420, padding: 36 }}>
            <div className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}>
              Connexion
            </div>
            <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 4, marginBottom: 26 }}>
              Accédez à la console SOC
            </div>

            {sessionExpired && !error && (
              <ErrorBanner message="Votre session a expiré. Veuillez vous reconnecter." />
            )}
            {error && <ErrorBanner message={error} />}

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)", marginBottom: 6, display: "block" }}>Email</label>
                <div style={{ position: "relative" }}>
                  <Mail size={15} style={{ position: "absolute", top: "50%", left: 12, transform: "translateY(-50%)", color: "var(--text-2)" }} />
                  <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} style={{ paddingLeft: 36 }} autoComplete="email" />
                </div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)" }}>Mot de passe</label>
                  <a
                    href="/forgot-password"
                    style={{ fontSize: 12, color: "var(--primary, #3B82F6)", textDecoration: "none" }}
                  >
                    Mot de passe oublié ?
                  </a>
                </div>
                <div style={{ position: "relative" }}>
                  <Lock size={15} style={{ position: "absolute", top: "50%", left: 12, transform: "translateY(-50%)", color: "var(--text-2)" }} />
                  <input
                    className="input"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={{ paddingLeft: 36, paddingRight: 40 }}
                    placeholder="••••••••••••"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{ position: "absolute", top: "50%", right: 10, transform: "translateY(-50%)", background: "transparent", border: "none", color: "var(--text-2)", cursor: "pointer", display: "flex" }}
                    aria-label={showPassword ? "Masquer" : "Afficher"}
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "11px 14px", fontSize: 13.5, marginTop: 4 }}
              >
                {isLoading ? (
                  <><RefreshCw size={14} style={{ animation: "spin 0.8s linear infinite" }} /> Vérification…</>
                ) : (
                  <>Continuer <ChevronRight size={14} /></>
                )}
              </button>
            </div>
          </form>

        ) : (
          /* ── Formulaire OTP ─────────────────────────────────────────────── */
          <form onSubmit={handleOtp} className="card card-glass" style={{ width: "100%", maxWidth: 420, padding: 36 }}>
            <button
              type="button"
              onClick={handleBack}
              style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "none", color: "var(--text-2)", cursor: "pointer", fontSize: 12.5, marginBottom: 20, padding: 0 }}
            >
              <ArrowLeft size={14} /> Retour
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div
                style={{
                  width: 36, height: 36, borderRadius: 9,
                  background: "linear-gradient(135deg, #3B82F6, #06D6A0)",
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}
              >
                <KeyRound size={16} color="white" />
              </div>
              <div className="font-display" style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>
                Code de vérification
              </div>
            </div>

            <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 28, lineHeight: 1.55 }}>
              Un code à 6 chiffres a été envoyé à{" "}
              <span style={{ color: "var(--text)", fontWeight: 600 }}>{email}</span>.
              <br />
              Entrez-le pour finaliser votre connexion.
            </div>

            {error && <ErrorBanner message={error} />}

            <div style={{ marginBottom: 28 }}>
              <OtpInput value={otp} onChange={setOtp} disabled={isLoading} autoFocus />
            </div>

            <button
              type="submit"
              disabled={isLoading || otp.length !== 6}
              className="btn btn-primary"
              style={{ width: "100%", justifyContent: "center", padding: "11px 14px", fontSize: 13.5 }}
            >
              {isLoading ? (
                <><RefreshCw size={14} style={{ animation: "spin 0.8s linear infinite" }} /> Vérification…</>
              ) : (
                <>Se connecter <ChevronRight size={14} /></>
              )}
            </button>

            {/* Renvoi + timer */}
            <div style={{ textAlign: "center", marginTop: 18 }}>
              <button
                type="button"
                onClick={handleResend}
                disabled={resendCooldown > 0 || isLoading}
                style={{
                  background: "transparent", border: "none",
                  cursor: resendCooldown > 0 ? "default" : "pointer",
                  fontSize: 12.5,
                  color: resendCooldown > 0 ? "var(--text-2)" : "var(--primary, #3B82F6)",
                  display: "inline-flex", alignItems: "center", gap: 5,
                  opacity: resendCooldown > 0 ? 0.6 : 1,
                }}
              >
                <RefreshCw size={12} />
                {resendCooldown > 0 ? `Renvoyer le code (${resendCooldown}s)` : "Renvoyer le code"}
              </button>
            </div>

            {/* Expiration info */}
            <div
              style={{
                marginTop: 18, padding: "10px 14px", borderRadius: 8,
                background: "color-mix(in srgb, var(--primary, #3B82F6) 8%, transparent)",
                border: "1px solid color-mix(in srgb, var(--primary, #3B82F6) 20%, transparent)",
                fontSize: 11.5, color: "var(--text-2)", lineHeight: 1.5,
              }}
            >
              Ce code expire dans <strong style={{ color: "var(--text)" }}>10 minutes</strong>.
              Sans ce code, la connexion ne peut pas aboutir.
            </div>
          </form>
        )}
      </div>

      <style jsx>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 900px) {
          :global(.login-grid) { grid-template-columns: 1fr !important; }
          :global(.login-left) { display: none !important; }
        }
      `}</style>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  );
}
