"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Shield, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { authApi } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [state, setState] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("Lien invalide : jeton manquant.");
      return;
    }
    authApi
      .verifyEmail(token)
      .then(() => setState("success"))
      .catch((err: unknown) => {
        const ax = err as { response?: { data?: { message?: string } } };
        setState("error");
        setMessage(ax?.response?.data?.message || "Ce lien de confirmation est invalide ou a expiré.");
      });
  }, [token]);

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg)", padding: 16 }}>
      <div className="card card-glass auth-card" style={{ width: "100%", maxWidth: 420, padding: 36, textAlign: "center" }}>
        <div
          style={{
            width: 36, height: 36, borderRadius: 9, margin: "0 auto 16px",
            background: "linear-gradient(135deg, #3B82F6, #06D6A0)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <Shield size={16} color="white" />
        </div>

        {state === "loading" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, color: "var(--text-2)", fontSize: 13 }}>
            <RefreshCw size={20} className="animate-spin" />
            Vérification de votre adresse email…
          </div>
        )}

        {state === "success" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <CheckCircle2 size={28} color="#06D6A0" />
            <div style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.55 }}>
              Adresse email confirmée. Votre compte administrateur est actif.
            </div>
            <Link href="/login" className="btn btn-primary" style={{ marginTop: 6 }}>
              Se connecter
            </Link>
          </div>
        )}

        {state === "error" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <XCircle size={28} color="var(--danger, #EF4444)" />
            <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.55 }}>{message}</div>
            <Link href="/register" style={{ color: "var(--primary, #3B82F6)", fontSize: 13 }}>
              Recommencer l&apos;inscription
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
