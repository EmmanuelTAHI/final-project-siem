"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Shield, Eye, EyeOff, Lock, Mail, AlertCircle, ChevronRight, RefreshCw } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { authApi } from "@/lib/api";
import toast from "react-hot-toast";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";
  const { setAuth, isAuthenticated } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAuthenticated) router.replace(redirect);
  }, [isAuthenticated, router, redirect]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Veuillez remplir tous les champs");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const data = await authApi.login({ email, password });
      setAuth(data.user, data.access, data.refresh);
      toast.success(`Bienvenue, ${data.user.first_name} !`);
      router.replace(redirect);
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { data?: { message?: string; detail?: string } };
        code?: string;
      };
      const isNetworkError = axiosError?.code === "ERR_NETWORK" || !axiosError?.response;
      const msg = isNetworkError
        ? "Impossible de joindre le serveur. Vérifiez que le backend est lancé."
        : axiosError?.response?.data?.message ||
          axiosError?.response?.data?.detail ||
          "Email ou mot de passe incorrect";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="login-grid"
      style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", minHeight: "100vh" }}
    >
      {/* Left panel */}
      <div
        className="login-left"
        style={{ display: "flex", flexDirection: "column", padding: 50, color: "white", position: "relative", zIndex: 1 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, position: "relative", zIndex: 2 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 11,
              background: "linear-gradient(135deg, #3B82F6, #06D6A0)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
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
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            position: "relative",
            zIndex: 2,
            maxWidth: 480,
          }}
        >
          <div className="chip" style={{ alignSelf: "flex-start", marginBottom: 24, color: "white", borderColor: "rgba(255,255,255,0.15)" }}>
            <span className="dot live" style={{ width: 7, height: 7 }} />
            Centre opérationnel de sécurité
          </div>
          <div
            className="font-display"
            style={{ fontSize: 44, fontWeight: 800, lineHeight: 1.05, letterSpacing: "-0.03em" }}
          >
            Détection, corrélation et réponse
            <br />
            <span style={{ color: "#06D6A0" }}>en temps réel.</span>
          </div>
          <div style={{ fontSize: 15, color: "#8B9EC7", marginTop: 18, lineHeight: 1.55 }}>
            Ingestion multi-source — Microsoft 365, Google Workspace, Wazuh, Syslog, EDR — et moteur
            de corrélation MITRE ATT&CK couplé à un détecteur d&apos;anomalies ML.
          </div>
          <div style={{ display: "flex", gap: 28, marginTop: 36 }}>
            {[
              ["Multi-source", "ingestion"],
              ["MITRE ATT&CK", "corrélation"],
              ["ML", "détection"],
            ].map(([n, l]) => (
              <div key={l}>
                <div className="font-display font-mono" style={{ fontSize: 18, fontWeight: 700, color: "white" }}>
                  {n}
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    color: "#8B9EC7",
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    marginTop: 2,
                  }}
                >
                  {l}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          className="font-mono"
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 11,
            color: "#8B9EC7",
            position: "relative",
            zIndex: 2,
          }}
        >
          <span>cluster-01 · region eu-west-3</span>
          <span>© 2026 Log+ · TAHI Ezan Franck Emmanuel</span>
        </div>
      </div>

      {/* Right panel */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 40,
          background: "var(--bg)",
        }}
      >
        <form onSubmit={handleSubmit} className="card card-glass" style={{ width: "100%", maxWidth: 420, padding: 36 }}>
          <div className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Connexion
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 4, marginBottom: 26 }}>
            Accédez à la console SOC
          </div>

          {error && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: 12,
                borderRadius: 9,
                marginBottom: 14,
                background: "color-mix(in srgb, var(--danger) 10%, transparent)",
                border: "1px solid color-mix(in srgb, var(--danger) 30%, transparent)",
                color: "var(--danger)",
                fontSize: 12.5,
              }}
            >
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--text-2)",
                  marginBottom: 6,
                  display: "block",
                }}
              >
                Email
              </label>
              <div style={{ position: "relative" }}>
                <Mail
                  size={15}
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: 12,
                    transform: "translateY(-50%)",
                    color: "var(--text-2)",
                  }}
                />
                <input
                  className="input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{ paddingLeft: 36 }}
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)" }}>Mot de passe</label>
                <a style={{ fontSize: 12, color: "var(--primary)", textDecoration: "none", cursor: "pointer" }}>
                  Mot de passe oublié ?
                </a>
              </div>
              <div style={{ position: "relative" }}>
                <Lock
                  size={15}
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: 12,
                    transform: "translateY(-50%)",
                    color: "var(--text-2)",
                  }}
                />
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
                  style={{
                    position: "absolute",
                    top: "50%",
                    right: 10,
                    transform: "translateY(-50%)",
                    background: "transparent",
                    border: "none",
                    color: "var(--text-2)",
                    cursor: "pointer",
                    display: "flex",
                  }}
                  aria-label={showPassword ? "Masquer" : "Afficher"}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12.5,
                color: "var(--text-2)",
                cursor: "pointer",
              }}
            >
              <input type="checkbox" defaultChecked /> Maintenir la session (appareil de confiance)
            </label>

            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary"
              style={{
                width: "100%",
                justifyContent: "center",
                padding: "11px 14px",
                fontSize: 13.5,
                marginTop: 4,
              }}
            >
              {isLoading ? (
                <>
                  <RefreshCw size={14} style={{ animation: "spin 0.8s linear infinite" }} />
                  Connexion…
                </>
              ) : (
                <>
                  Se connecter <ChevronRight size={14} />
                </>
              )}
            </button>
          </div>

        </form>
      </div>

      <style jsx>{`
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
        @media (max-width: 900px) {
          :global(.login-grid) {
            grid-template-columns: 1fr !important;
          }
          :global(.login-left) {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
