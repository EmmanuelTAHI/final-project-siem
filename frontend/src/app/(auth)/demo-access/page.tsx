"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Lock, ShieldCheck, XCircle } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import type { AuthUser } from "@/types";

type Stage = "loading" | "error";

interface DemoAuthPayload {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
}

function DemoAccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setAuth } = useAuthStore();

  const [stage, setStage] = useState<Stage>("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    // Le backend (DemoAccessView) redirige ici avec les tokens dans le
    // FRAGMENT d'URL (#payload=...), jamais en query string, pour qu'ils
    // n'atterrissent pas dans les logs d'accès nginx.
    const errorParam = searchParams.get("error");
    if (errorParam) {
      setError(
        errorParam === "expired"
          ? "Ce lien de démonstration a expiré."
          : "Ce lien de démonstration est invalide."
      );
      setStage("error");
      return;
    }

    const hash = typeof window !== "undefined" ? window.location.hash : "";
    const match = hash.match(/payload=([^&]+)/);
    if (!match) {
      setError("Lien de démonstration incomplet.");
      setStage("error");
      return;
    }

    try {
      const decoded = atob(decodeURIComponent(match[1]));
      const payload: DemoAuthPayload = JSON.parse(decoded);
      setAuth(payload.user, payload.access_token, payload.refresh_token);
      // Nettoie le fragment (tokens) de l'URL avant de router.
      window.history.replaceState(null, "", "/demo-access");
      router.replace("/dashboard");
    } catch {
      setError("Impossible de lire le lien de démonstration.");
      setStage("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        background: "var(--bg)",
      }}
    >
      <div
        className="card card-glass auth-card"
        style={{ width: "100%", maxWidth: 480, padding: 32, position: "relative" }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 18,
            color: "var(--text-2)",
            fontSize: 11.5,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          <Lock size={12} /> Log+ — accès démonstration
        </div>

        {stage === "loading" && (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <Loader2 size={28} className="spin" style={{ color: "var(--primary)" }} />
            <div style={{ marginTop: 16, color: "var(--text-2)" }}>
              Connexion au tenant de démonstration…
            </div>
          </div>
        )}

        {stage === "error" && (
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <XCircle size={36} style={{ color: "var(--danger)" }} />
            <div className="font-display" style={{ fontSize: 18, fontWeight: 700, marginTop: 14 }}>
              Lien invalide
            </div>
            <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 6 }}>{error}</div>
            <button
              className="btn btn-primary"
              style={{ marginTop: 20, justifyContent: "center", padding: "10px 18px" }}
              onClick={() => router.push("/login")}
            >
              <ShieldCheck size={14} /> Retour à la connexion
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DemoAccessPage() {
  return (
    <Suspense fallback={null}>
      <DemoAccessContent />
    </Suspense>
  );
}
