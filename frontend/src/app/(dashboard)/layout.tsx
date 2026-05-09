"use client";

import { useRef, useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { CommandPalette } from "@/components/common/command-palette";
import { useAuthStore } from "@/stores/auth-store";

const SCROLL_KEY = "logplus_scroll";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const { isAuthenticated, _hasHydrated } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const mainRef = useRef<HTMLElement>(null);

  // ── Auth guard — wait for hydration before acting ──────────────────────────
  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      // Preserve current path so login can redirect back after success
      const currentPath =
        typeof window !== "undefined"
          ? window.location.pathname + window.location.search
          : "/settings";
      router.replace(
        `/login?redirect=${encodeURIComponent(currentPath)}`
      );
    }
  }, [isAuthenticated, _hasHydrated, router]);

  // ── Scroll position save/restore across navigation and reloads ─────────────
  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;

    // Restore saved scroll for this path
    const saved = sessionStorage.getItem(`${SCROLL_KEY}:${pathname}`);
    if (saved) {
      const y = parseInt(saved, 10);
      if (!isNaN(y)) el.scrollTop = y;
    }

    // Save scroll on scroll events
    const onScroll = () => {
      sessionStorage.setItem(
        `${SCROLL_KEY}:${pathname}`,
        el.scrollTop.toString()
      );
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [pathname]);

  // ── Keyboard shortcut for command palette ──────────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // While the store is still reading from localStorage, render nothing to avoid
  // a flash of unauthenticated content or a spurious redirect to /login.
  if (!_hasHydrated) return null;
  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex flex-shrink-0">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      </div>

      {/* Mobile sidebar overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/60 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.div
              initial={{ x: -240 }}
              animate={{ x: 0 }}
              exit={{ x: -240 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="fixed left-0 top-0 bottom-0 z-50 lg:hidden"
            >
              <Sidebar
                collapsed={false}
                onToggle={() => setMobileOpen(false)}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar
          onMobileMenuToggle={() => setMobileOpen(true)}
          onCommandPaletteOpen={() => setCommandOpen(true)}
        />

        <main ref={mainRef} className="flex-1 overflow-y-auto">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="h-full"
          >
            {children}
          </motion.div>
        </main>
      </div>

      {/* Command Palette */}
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
    </div>
  );
}
