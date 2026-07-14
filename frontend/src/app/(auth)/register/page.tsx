"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, Lock, Mail, User, Building2, Eye, EyeOff, AlertCircle, ChevronRight, RefreshCw, CheckCircle2 } from "lucide-react";
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

export default function RegisterPage() {
  const [organizationName, setOrganizationName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!organizationName || !firstName || !lastName || !email || !password) {
      setError("Veuillez remplir tous les champs.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }

    setIsLoading(true);
    setError("");
    try {
      await authApi.register({
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        organization_name: organizationName,
      });
      setDone(true);
    } catch (err: unknown) {
      const ax = err as {
        response?: { data?: { message?: string; errors?: Record<string, string[]> } };
        code?: string;
      };
      const isNet = ax?.code === "ERR_NETWORK" || !ax?.response;
      const firstFieldError = ax?.response?.data?.errors
        ? Object.values(ax.response.data.errors)[0]?.[0]
        : undefined;
      setError(
        isNet
          ? "Impossible de joindre le serveur. Vérifiez que le backend est lancé."
          : firstFieldError || ax?.response?.data?.message || "Une erreur est survenue."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg)", padding: 16 }}>
      <div className="card card-glass auth-card" style={{ width: "100%", maxWidth: 440, padding: 36 }}>
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
            Créer votre organisation
          </div>
        </div>

        {done ? (
          <div style={{ fontSize: 13, color: "var(--text-2)", margin: "20px 0", lineHeight: 1.55, display: "flex", alignItems: "flex-start", gap: 10 }}>
            <CheckCircle2 size={18} color="#06D6A0" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              Si cette adresse n&apos;est pas déjà utilisée, un email de confirmation vient
              d&apos;être envoyé. Cliquez sur le lien reçu pour activer votre compte administrateur,
              puis <Link href="/login" style={{ color: "var(--primary, #3B82F6)" }}>connectez-vous</Link>.
            </span>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 22, lineHeight: 1.55 }}>
              Votre organisation est isolée des autres : personne d&apos;autre ne verra vos
              données. Vous devenez automatiquement administrateur.
            </div>

            {error && <ErrorBanner message={error} />}

            <div className="flex flex-col gap-4">
              <div className="space-y-2">
                <Label htmlFor="register-org">Nom de l&apos;organisation</Label>
                <Input
                  id="register-org"
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                  leftIcon={<Building2 size={15} />}
                  placeholder="Acme SARL, ou votre nom si vous êtes indépendant"
                  autoFocus
                />
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <div className="space-y-2" style={{ flex: 1 }}>
                  <Label htmlFor="register-firstname">Prénom</Label>
                  <Input
                    id="register-firstname"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    leftIcon={<User size={15} />}
                  />
                </div>
                <div className="space-y-2" style={{ flex: 1 }}>
                  <Label htmlFor="register-lastname">Nom</Label>
                  <Input
                    id="register-lastname"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="register-email">Adresse email</Label>
                <Input
                  id="register-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  leftIcon={<Mail size={15} />}
                  autoComplete="email"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="register-password">Mot de passe</Label>
                <Input
                  id="register-password"
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
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="register-password-confirm">Confirmer le mot de passe</Label>
                <Input
                  id="register-password-confirm"
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  leftIcon={<Lock size={15} />}
                  autoComplete="new-password"
                />
              </div>

              <Button type="submit" disabled={isLoading} className="w-full mt-1">
                {isLoading ? (
                  <><RefreshCw size={14} className="animate-spin" /> Création…</>
                ) : (
                  <>Créer mon organisation <ChevronRight size={14} /></>
                )}
              </Button>

              <div style={{ textAlign: "center", fontSize: 12.5, color: "var(--text-2)", marginTop: 4 }}>
                Déjà un compte ? <Link href="/login" style={{ color: "var(--primary, #3B82F6)" }}>Se connecter</Link>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
