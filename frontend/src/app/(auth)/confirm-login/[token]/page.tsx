"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Globe,
  Loader2,
  Lock,
  Monitor,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { loginConfirmationApi } from "@/lib/api";
import type { LoginConfirmationDetails } from "@/types";

type Stage = "loading" | "ready" | "submitting" | "done" | "error";

export default function ConfirmLoginPage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const search = useSearchParams();
  const token = params?.token || "";
  const preselected = search?.get("action") as "approve" | "reject" | null;

  const [stage, setStage] = useState<Stage>("loading");
  const [error, setError] = useState("");
  const [details, setDetails] = useState<LoginConfirmationDetails | null>(null);
  const [chosen, setChosen] = useState<"approve" | "reject" | null>(null);

  useEffect(() => {
    if (!token) return;
    loginConfirmationApi
      .describe(token)
      .then((d) => {
        setDetails(d.confirmation);
        setStage("ready");
      })
      .catch((err: unknown) => {
        const e = err as { response?: { status?: number; data?: { message?: string } } };
        setError(e?.response?.data?.message || "Lien invalide ou expiré.");
        setStage("error");
      });
  }, [token]);

  const submit = async (action: "approve" | "reject") => {
    setStage("submitting");
    setChosen(action);
    try {
      await loginConfirmationApi.respond(token, action);
      setStage("done");
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      setError(e?.response?.data?.message || "Erreur lors de l'enregistrement de la réponse.");
      setStage("error");
    }
  };

  // Pre-clic depuis l'email (?action=approve|reject)
  useEffect(() => {
    if (stage === "ready" && preselected === "approve") submit("approve");
    if (stage === "ready" && preselected === "reject") submit("reject");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, preselected]);

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
        className="card card-glass"
        style={{ width: "100%", maxWidth: 520, padding: 32, position: "relative" }}
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
          <Lock size={12} /> Log+ — confirmation de connexion
        </div>

        {stage === "loading" && (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <Loader2 size={28} className="spin" style={{ color: "var(--primary)" }} />
            <div style={{ marginTop: 16, color: "var(--text-2)" }}>Vérification du lien…</div>
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
              Retour à la connexion <ChevronRight size={14} />
            </button>
          </div>
        )}

        {stage === "done" && (
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            {chosen === "approve" ? (
              <>
                <CheckCircle2 size={42} style={{ color: "var(--secondary)" }} />
                <div className="font-display" style={{ fontSize: 18, fontWeight: 700, marginTop: 14 }}>
                  Merci, c’est bien noté.
                </div>
                <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 6 }}>
                  La connexion a été confirmée comme légitime. Aucune action n’est requise.
                </div>
              </>
            ) : (
              <>
                <ShieldAlert size={42} style={{ color: "var(--danger)" }} />
                <div className="font-display" style={{ fontSize: 18, fontWeight: 700, marginTop: 14 }}>
                  Compte mis en pause
                </div>
                <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 6, lineHeight: 1.5 }}>
                  Nous avons mis en pause le compte lié et vous avons envoyé une notification.
                  Changez immédiatement votre mot de passe côté provider et révoquez les sessions actives.
                </div>
              </>
            )}
            <button
              className="btn btn-primary"
              style={{ marginTop: 22, justifyContent: "center", padding: "10px 18px" }}
              onClick={() => router.push("/dashboard")}
            >
              Aller au SOC <ChevronRight size={14} />
            </button>
          </div>
        )}

        {(stage === "ready" || stage === "submitting") && details && (
          <ConfirmationCard
            details={details}
            disabled={stage === "submitting"}
            onApprove={() => submit("approve")}
            onReject={() => submit("reject")}
            chosen={chosen}
          />
        )}
      </div>

      <style jsx>{`
        @keyframes spinning { to { transform: rotate(360deg); } }
        :global(.spin) { animation: spinning 0.8s linear infinite; }
      `}</style>
    </div>
  );
}

function ConfirmationCard({
  details,
  onApprove,
  onReject,
  disabled,
  chosen,
}: {
  details: LoginConfirmationDetails;
  onApprove: () => void;
  onReject: () => void;
  disabled: boolean;
  chosen: "approve" | "reject" | null;
}) {
  const expired = details.status !== "pending" || new Date(details.expires_at) <= new Date();
  const device = [details.browser, details.os, details.device_type].filter(Boolean).join(" · ") || "Inconnu";
  const geo = [details.geo_city, details.geo_country].filter(Boolean).join(", ") || "Localisation inconnue";

  return (
    <>
      <div
        className="font-display"
        style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", marginBottom: 4 }}
      >
        Est-ce bien vous&nbsp;?
      </div>
      <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 22, lineHeight: 1.55 }}>
        Une nouvelle connexion vient d’être détectée sur votre compte{" "}
        <strong style={{ color: "var(--text)" }}>{details.provider || "lié"}</strong>{" "}
        ({details.provider_email}). Confirmez-la pour rassurer Log+, ou signalez-la pour
        verrouiller le compte immédiatement.
      </div>

      <div
        style={{
          padding: 14,
          border: "1px solid var(--border)",
          borderRadius: 11,
          background: "color-mix(in srgb, var(--surface) 60%, transparent)",
          fontSize: 13,
          marginBottom: 18,
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", rowGap: 8 }}>
          <span style={{ color: "var(--text-2)" }}>
            <Monitor size={12} style={{ marginRight: 6, verticalAlign: -1 }} /> Appareil
          </span>
          <span>{device}</span>
          <span style={{ color: "var(--text-2)" }}>
            <Globe size={12} style={{ marginRight: 6, verticalAlign: -1 }} /> Localisation
          </span>
          <span>{geo}</span>
          <span style={{ color: "var(--text-2)" }}>Adresse IP</span>
          <span className="font-mono">{details.ip_address || "—"}</span>
          <span style={{ color: "var(--text-2)" }}>Survenu</span>
          <span className="font-mono">
            {new Date(details.created_at).toLocaleString("fr-FR")}
          </span>
        </div>
      </div>

      {expired && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: 12,
            borderRadius: 9,
            background: "color-mix(in srgb, var(--warning) 10%, transparent)",
            border: "1px solid color-mix(in srgb, var(--warning) 30%, transparent)",
            color: "var(--warning)",
            fontSize: 12.5,
            marginBottom: 14,
          }}
        >
          <AlertCircle size={14} />
          {details.status !== "pending"
            ? `Cette confirmation a déjà été ${details.status === "approved" ? "approuvée" : "rejetée"}.`
            : "Ce lien a expiré. Reconnectez-vous pour générer une nouvelle confirmation."}
        </div>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <button
          className="btn btn-primary"
          style={{
            flex: 1,
            justifyContent: "center",
            padding: "12px 14px",
            background: "var(--secondary)",
            opacity: expired || disabled ? 0.5 : 1,
          }}
          onClick={onApprove}
          disabled={expired || disabled}
        >
          {chosen === "approve" && disabled ? <Loader2 size={14} className="spin" /> : <ShieldCheck size={14} />}
          C’est bien moi
        </button>
        <button
          className="btn"
          style={{
            flex: 1,
            justifyContent: "center",
            padding: "12px 14px",
            background: "var(--danger)",
            color: "white",
            border: "none",
            opacity: expired || disabled ? 0.5 : 1,
          }}
          onClick={onReject}
          disabled={expired || disabled}
        >
          {chosen === "reject" && disabled ? <Loader2 size={14} className="spin" /> : <ShieldAlert size={14} />}
          Ce n’est pas moi
        </button>
      </div>

      <div
        style={{
          marginTop: 16,
          fontSize: 11.5,
          color: "var(--text-2)",
          lineHeight: 1.55,
          display: "flex",
          gap: 8,
          alignItems: "flex-start",
        }}
      >
        <Lock size={12} style={{ marginTop: 3, color: "var(--primary)" }} />
        <span>
          Si vous signalez cette connexion, le compte {details.provider || "lié"} sera mis en pause
          côté SIEM et vous recevrez une notification critique pour suivre la révocation côté provider.
        </span>
      </div>
    </>
  );
}
