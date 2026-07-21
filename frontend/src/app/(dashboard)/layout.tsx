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
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const { isAuthenticated, _hasHydrated, user } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      const currentPath =
        typeof window !== "undefined"
          ? window.location.pathname + window.location.search
          : "/settings";
      router.replace(
        `/login?redirect=${encodeURIComponent(currentPath)}`
      );
    }
  }, [isAuthenticated, _hasHydrated, router]);

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;

    const saved = sessionStorage.getItem(`${SCROLL_KEY}:${pathname}`);
    if (saved) {
      const y = parseInt(saved, 10);
      if (!isNaN(y)) el.scrollTop = y;
    }

    const onScroll = () => {
      sessionStorage.setItem(
        `${SCROLL_KEY}:${pathname}`,
        el.scrollTop.toString()
      );
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [pathname]);

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

  if (!_hasHydrated) return null;
  if (!isAuthenticated) return null;

  return (
    <div
      className="flex h-screen overflow-hidden bg-background"
      style={user?.is_demo ? { paddingTop: 28 } : undefined}
    >
      {user?.is_demo && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 60,
            textAlign: "center",
            padding: "6px 12px",
            fontSize: 12.5,
            fontWeight: 600,
            letterSpacing: "0.02em",
            color: "#111",
            background: "linear-gradient(90deg, #fbbf24, #f59e0b)",
          }}
        >
          Mode démonstration — vous êtes connecté au tenant public de présentation. Aucune action réelle
          (email, webhook, blocage IP) n&apos;est effectuée et ces données sont réinitialisées régulièrement.
        </div>
      )}
      {/* Desktop sidebar — hover-controlled, self-managed.
          Largeur réservée fixe (64px, état replié) : la sidebar elle-même se
          positionne en absolu par-dessus le contenu quand elle s'étend au
          survol, pour ne jamais pousser/redimensionner la page à côté. */}
      <div className="hidden lg:block relative flex-shrink-0" style={{ width: 64 }}>
        <Sidebar />
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
              <Sidebar forceExpanded={true} onClose={() => setMobileOpen(false)} />
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

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
    </div>
  );
}
