"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Shield, Lock, Eye, EyeOff, AlertCircle, ChevronRight, RefreshCw, CheckCircle2 } from "lucide-react";
import { authApi } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

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

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password || !confirmPassword) { setError("Veuillez remplir tous les champs"); return; }
    if (password !== confirmPassword) { setError("Les mots de passe ne correspondent pas"); return; }
    if (!token) { setError("Lien invalide : jeton manquant."); return; }

    setIsLoading(true);
    setError("");
    try {
      await authApi.confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 2500);
    } catch (err: unknown) {
      const ax = err as {
        response?: { data?: { message?: string; errors?: { password?: string[] } } };
        code?: string;
      };
      const isNet = ax?.code === "ERR_NETWORK" || !ax?.response;
      const passwordErrors = ax?.response?.data?.errors?.password;
      setError(
        isNet
          ? "Impossible de joindre le serveur. Vérifiez que le backend est lancé."
          : passwordErrors?.[0] || ax?.response?.data?.message || "Une erreur est survenue."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg)", padding: 16 }}>
      <div className="card card-glass auth-card" style={{ width: "100%", maxWidth: 420, padding: 36 }}>
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
            Nouveau mot de passe
          </div>
        </div>

        {done ? (
          <div style={{ fontSize: 13, color: "var(--text-2)", margin: "20px 0", lineHeight: 1.55, display: "flex", alignItems: "flex-start", gap: 10 }}>
            <CheckCircle2 size={18} color="#06D6A0" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>Mot de passe réinitialisé avec succès. Redirection vers la connexion…</span>
          </div>
        ) : !token ? (
          <ErrorBanner message="Lien invalide ou incomplet. Redemandez une réinitialisation depuis la page de connexion." />
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 26, lineHeight: 1.55 }}>
              Choisissez un nouveau mot de passe pour votre compte Argus.
            </div>

            {error && <ErrorBanner message={error} />}

            <div className="flex flex-col gap-4">
              <div className="space-y-2">
                <Label htmlFor="reset-password">Nouveau mot de passe</Label>
                <Input
                  id="reset-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  leftIcon={<Lock size={15} />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="flex text-muted-foreground hover:text-foreground"
                      aria-label={showPassword ? "Masquer" : "Afficher"}
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  }
                  autoComplete="new-password"
                  autoFocus
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="reset-password-confirm">Confirmer le mot de passe</Label>
                <Input
                  id="reset-password-confirm"
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  leftIcon={<Lock size={15} />}
                  autoComplete="new-password"
                />
              </div>

              <Button type="submit" disabled={isLoading} className="w-full mt-1">
                {isLoading ? (
                  <><RefreshCw size={14} className="animate-spin" /> Réinitialisation…</>
                ) : (
                  <>Réinitialiser <ChevronRight size={14} /></>
                )}
              </Button>
            </div>
          </form>
        )}
      </div>

    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  );
}
