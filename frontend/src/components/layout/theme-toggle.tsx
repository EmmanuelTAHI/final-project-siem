"use client";

import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

interface ThemeToggleProps {
  collapsed?: boolean;
}

export function ThemeToggle({ collapsed = false }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div style={{ height: collapsed ? 36 : 30 }} />
    );
  }

  const isDark = theme === "dark";
  const toggle = () => setTheme(isDark ? "light" : "dark");

  if (collapsed) {
    return (
      <div
        className="tip"
        data-tip={isDark ? "Mode clair" : "Mode sombre"}
        style={{ display: "flex", justifyContent: "center" }}
      >
        <button
          onClick={toggle}
          aria-label="Basculer le thème"
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--text-2)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {isDark ? <Moon size={16} /> : <Sun size={16} />}
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 10px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          color: "var(--text-2)",
          fontSize: 12.5,
        }}
      >
        {isDark ? <Moon size={14} /> : <Sun size={14} />}
        <span>{isDark ? "Mode sombre" : "Mode clair"}</span>
      </div>
      <div
        className="theme-track"
        onClick={toggle}
        role="switch"
        aria-checked={isDark}
        tabIndex={0}
      >
        <div className="theme-knob">
          {isDark ? <Moon size={11} /> : <Sun size={11} />}
        </div>
      </div>
    </div>
  );
}
