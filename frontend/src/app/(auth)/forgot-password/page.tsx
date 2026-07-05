"use client";

import { useState } from "react";
import { Shield, Mail, AlertCircle, ChevronRight, RefreshCw, ArrowLeft, CheckCircle2 } from "lucide-react";
import { authApi } from "@/lib/api";

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

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { setError("Veuillez entrer votre adresse email"); return; }
    setIsLoading(true);
    setError("");
    try {
      await authApi.requestPasswordReset(email);
      setSent(true);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { message?: string } }; code?: string };
      const isNet = ax?.code === "ERR_NETWORK" || !ax?.response;
      setError(
        isNet
          ? "Impossible de joindre le serveur. Vérifiez que le backend est lancé."
          : ax?.response?.data?.message || "Une erreur est survenue."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg)" }}>
      <div className="card card-glass" style={{ width: "100%", maxWidth: 420, padding: 36 }}>
        <a
          href="/login"
          style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "none", color: "var(--text-2)", cursor: "pointer", fontSize: 12.5, marginBottom: 20, textDecoration: "none" }}
        >
          <ArrowLeft size={14} /> Retour à la connexion
        </a>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <div
            style={{
              width: 36, height: 36, borderRadius: 9,
              background: "linear-gradient(135deg, #3B82F6, #06D6A0)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}
          >
            <Shield size={16} color="white" />
          </div>
          <div className="font-display" style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>
            Mot de passe oublié
          </div>
        </div>

        {sent ? (
          <>
            <div style={{ fontSize: 13, color: "var(--text-2)", margin: "20px 0", lineHeight: 1.55 }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <CheckCircle2 size={18} color="#06D6A0" style={{ flexShrink: 0, marginTop: 2 }} />
                <span>
                  Si un compte existe avec l&apos;adresse <strong style={{ color: "var(--text)" }}>{email}</strong>,
                  un email de réinitialisation vient d&apos;être envoyé. Le lien est valide 30 minutes.
                </span>
              </div>
            </div>
            <a href="/login" className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "11px 14px", fontSize: 13.5, textDecoration: "none" }}>
              Retour à la connexion
            </a>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 26, lineHeight: 1.55 }}>
              Entrez votre adresse email. Si un compte existe, vous recevrez un lien
              de réinitialisation valide 30 minutes.
            </div>

            {error && <ErrorBanner message={error} />}

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)", marginBottom: 6, display: "block" }}>Email</label>
                <div style={{ position: "relative" }}>
                  <Mail size={15} style={{ position: "absolute", top: "50%", left: 12, transform: "translateY(-50%)", color: "var(--text-2)" }} />
                  <input
                    className="input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    style={{ paddingLeft: 36 }}
                    autoComplete="email"
                    autoFocus
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "11px 14px", fontSize: 13.5, marginTop: 4 }}
              >
                {isLoading ? (
                  <><RefreshCw size={14} style={{ animation: "spin 0.8s linear infinite" }} /> Envoi…</>
                ) : (
                  <>Envoyer le lien <ChevronRight size={14} /></>
                )}
              </button>
            </div>
          </form>
        )}
      </div>

      <style jsx>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
