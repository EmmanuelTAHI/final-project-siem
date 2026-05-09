"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  ShieldCheck,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertCircle,
  Mail,
} from "lucide-react";
import { linkedAccountsApi } from "@/lib/api";
import toast from "react-hot-toast";

const PROVIDER_META: Record<string, { label: string; color: string }> = {
  google:    { label: "Google",    color: "#EA4335" },
  microsoft: { label: "Microsoft", color: "#0078D4" },
  github:    { label: "GitHub",    color: "#6e40c9" },
};

interface PinEntryInlineProps {
  verificationId: string;
  provider: string;
  email: string;
  initialSecondsLeft?: number;
  onSuccess: (provider: string, email: string) => void;
}

export const PIN_TTL = 5 * 60;

export function PinEntryInline({
  verificationId,
  provider,
  email,
  initialSecondsLeft = PIN_TTL,
  onSuccess,
}: PinEntryInlineProps) {
  const [digits, setDigits] = useState(["", "", "", ""]);
  const [secondsLeft, setSecondsLeft] = useState(
    Math.max(0, Math.min(initialSecondsLeft, PIN_TTL))
  );
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [shake, setShake] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const hasAutoSubmitted = useRef(false);
  const meta = PROVIDER_META[provider] ?? { label: provider, color: "#6366f1" };

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const t = setInterval(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [secondsLeft]);

  const minutes = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const expired = secondsLeft <= 0;
  const timerColor =
    secondsLeft > 60 ? "#22c55e" : secondsLeft > 30 ? "#f59e0b" : "#ef4444";
  const pin = digits.join("");

  const handleVerify = useCallback(async () => {
    if (pin.length !== 4 || expired || loading) return;
    setLoading(true);
    setStatus("idle");
    try {
      const result = await linkedAccountsApi.verifyPin(verificationId, pin);
      setStatus("success");
      setTimeout(() => onSuccess(result.provider, result.email), 900);
    } catch (err: unknown) {
      hasAutoSubmitted.current = false;
      setStatus("error");
      setShake(true);
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message;
      toast.error(msg ?? "Code incorrect. Vérifiez votre email et réessayez.");
      setDigits(["", "", "", ""]);
      setTimeout(() => {
        setShake(false);
        setStatus("idle");
        inputRefs.current[0]?.focus();
      }, 500);
    } finally {
      setLoading(false);
    }
  }, [pin, expired, loading, verificationId, onSuccess]);

  // Auto-submit when all 4 digits entered
  useEffect(() => {
    if (
      pin.length === 4 &&
      !expired &&
      status === "idle" &&
      !loading &&
      !hasAutoSubmitted.current
    ) {
      hasAutoSubmitted.current = true;
      handleVerify();
    }
    if (pin.length < 4) hasAutoSubmitted.current = false;
  }, [pin, expired, status, loading, handleVerify]);

  const handleDigitChange = (idx: number, val: string) => {
    const clean = val.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[idx] = clean;
    setDigits(next);
    if (clean && idx < 3) inputRefs.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !digits[idx] && idx > 0) {
      inputRefs.current[idx - 1]?.focus();
    }
    if (e.key === "Enter" && pin.length === 4) handleVerify();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const pasted = e.clipboardData
      .getData("text")
      .replace(/\D/g, "")
      .slice(0, 4);
    if (pasted.length === 4) {
      setDigits(pasted.split(""));
      requestAnimationFrame(() => inputRefs.current[3]?.focus());
    }
    e.preventDefault();
  };

  return (
    <div style={{ marginTop: 16 }}>
      {/* Divider */}
      <div
        style={{
          height: 1,
          background: "var(--border)",
          margin: "0 -18px 16px",
        }}
      />

      {/* Email hint */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 7,
          marginBottom: 5,
        }}
      >
        <Mail size={13} style={{ color: meta.color, flexShrink: 0 }} />
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>
          Entrez le code reçu par email
        </span>
      </div>
      <p
        style={{
          fontSize: 11.5,
          color: "var(--text-2)",
          marginBottom: 18,
          lineHeight: 1.5,
        }}
      >
        Envoyé à{" "}
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 11,
            color: "var(--text)",
          }}
        >
          {email}
        </span>
      </p>

      {/* OTP inputs */}
      <div
        style={{
          display: "flex",
          gap: 10,
          justifyContent: "center",
          marginBottom: 14,
          animation: shake
            ? "pin-shake 0.4s cubic-bezier(.36,.07,.19,.97)"
            : "none",
        }}
      >
        {digits.map((d, i) => (
          <input
            key={i}
            ref={(el) => {
              inputRefs.current[i] = el;
            }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={d}
            onChange={(e) => handleDigitChange(i, e.target.value)}
            onKeyDown={(e) => handleKeyDown(i, e)}
            onPaste={i === 0 ? handlePaste : undefined}
            disabled={loading || expired || status === "success"}
            autoFocus={i === 0}
            style={{
              width: 52,
              height: 56,
              textAlign: "center",
              fontSize: 24,
              fontWeight: 800,
              fontFamily: "monospace",
              letterSpacing: 0,
              background:
                status === "success"
                  ? "color-mix(in srgb,#22c55e 10%,var(--surface))"
                  : status === "error"
                  ? "color-mix(in srgb,#ef4444 10%,var(--surface))"
                  : d
                  ? `color-mix(in srgb,${meta.color} 10%,var(--surface))`
                  : "var(--surface)",
              border: `2px solid ${
                status === "success"
                  ? "#22c55e"
                  : status === "error"
                  ? "#ef4444"
                  : d
                  ? meta.color
                  : "var(--border)"
              }`,
              borderRadius: 10,
              color: status === "success" ? "#22c55e" : "var(--text)",
              outline: "none",
              transition: "border-color 0.15s, background 0.15s, box-shadow 0.15s",
              cursor: expired ? "not-allowed" : "text",
              boxShadow:
                d && status === "idle"
                  ? `0 0 0 3px color-mix(in srgb,${meta.color} 14%,transparent)`
                  : "none",
            }}
          />
        ))}
      </div>

      {/* Timer */}
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        {expired ? (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11.5,
              color: "#ef4444",
              fontWeight: 600,
            }}
          >
            <AlertCircle size={12} /> Code expiré — relancez la liaison
          </span>
        ) : (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11.5,
              color: timerColor,
              fontFamily: "monospace",
              fontWeight: 600,
            }}
          >
            <Clock size={11} />
            Expire dans {minutes}:{secs.toString().padStart(2, "0")}
          </span>
        )}
      </div>

      {/* Confirm button */}
      <button
        className="btn btn-primary"
        style={{
          width: "100%",
          fontSize: 12,
          padding: "8px 10px",
          justifyContent: "center",
          background:
            status === "success"
              ? "#22c55e"
              : pin.length === 4 && !expired
              ? `linear-gradient(135deg,${meta.color},${meta.color}cc)`
              : undefined,
          opacity: pin.length < 4 || expired ? 0.45 : 1,
        }}
        onClick={handleVerify}
        disabled={pin.length < 4 || loading || expired || status === "success"}
      >
        {status === "success" ? (
          <>
            <CheckCircle size={13} /> Lié avec succès !
          </>
        ) : loading ? (
          <>
            <RefreshCw size={12} className="animate-spin" /> Vérification…
          </>
        ) : (
          <>
            <ShieldCheck size={13} /> Confirmer
          </>
        )}
      </button>

      <style jsx>{`
        @keyframes pin-shake {
          0%   { transform: translateX(0); }
          15%  { transform: translateX(-5px); }
          45%  { transform: translateX(5px); }
          75%  { transform: translateX(-3px); }
          100% { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
