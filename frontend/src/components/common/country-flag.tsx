"use client";

interface CountryFlagProps {
  code: string;
  size?: "sm" | "md" | "lg";
  showCode?: boolean;
  showName?: string;
  className?: string;
}

const sizes = {
  sm: { width: 16, height: 12, fontSize: 10, borderRadius: 2 },
  md: { width: 20, height: 15, fontSize: 11, borderRadius: 3 },
  lg: { width: 28, height: 21, fontSize: 12, borderRadius: 3 },
};

export function CountryFlag({
  code,
  size = "md",
  showCode = false,
  showName,
  className = "",
}: CountryFlagProps) {
  if (!code || code.length !== 2) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 ${className}`}
        title="Pays inconnu"
      >
        <span
          style={{
            display: "inline-block",
            width: sizes[size].width,
            height: sizes[size].height,
            background: "hsl(var(--secondary))",
            borderRadius: sizes[size].borderRadius,
            flexShrink: 0,
          }}
        />
        {showCode && (
          <span
            className="font-mono text-muted-foreground uppercase"
            style={{ fontSize: sizes[size].fontSize }}
          >
            —
          </span>
        )}
        {showName && (
          <span className="text-foreground" style={{ fontSize: sizes[size].fontSize }}>
            {showName}
          </span>
        )}
      </span>
    );
  }

  const lower = code.toLowerCase();

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${className}`}
      title={showName ?? code.toUpperCase()}
    >
      {/* flag-icons renders via CSS background-image — the span needs explicit dimensions */}
      <span
        className={`fi fi-${lower}`}
        style={{
          display: "inline-block",
          width: sizes[size].width,
          height: sizes[size].height,
          borderRadius: sizes[size].borderRadius,
          flexShrink: 0,
          boxShadow: "0 0 0 1px rgba(255,255,255,0.08)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
        aria-label={`Drapeau ${code.toUpperCase()}`}
      />
      {showCode && (
        <span
          className="font-mono text-muted-foreground uppercase tracking-wide"
          style={{ fontSize: sizes[size].fontSize }}
        >
          {code.toUpperCase()}
        </span>
      )}
      {showName && (
        <span className="text-foreground truncate" style={{ fontSize: sizes[size].fontSize }}>
          {showName}
        </span>
      )}
    </span>
  );
}

/**
 * Inline version for use inside text flows (logs table, etc.)
 * Renders flag + optional code in a compact pill.
 */
export function FlagBadge({ code, label }: { code: string; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <CountryFlag code={code} size="sm" />
      <span className="font-mono text-xs text-muted-foreground uppercase">
        {label ?? code.toUpperCase()}
      </span>
    </span>
  );
}
