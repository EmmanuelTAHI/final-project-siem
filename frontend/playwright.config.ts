import { defineConfig, devices } from "@playwright/test";

/**
 * Configuration Playwright — suite E2E exécutée directement contre le VPS de
 * PRODUCTION (https://logplus.duckdns.org), avec l'accord explicite du
 * propriétaire du projet. Aucun environnement de staging n'existe.
 *
 * IMPORTANT (résolution DNS) :
 *   Le domaine logplus.duckdns.org doit être résolvable/joignable depuis la
 *   machine qui lance les tests (résolveur DNS correct, pas de VPN qui
 *   bloque, etc.). Ce n'est PAS géré par cette config — si `curl -I
 *   https://logplus.duckdns.org` échoue, corrigez d'abord votre réseau avant
 *   de lancer Playwright.
 *
 * Variables d'environnement (voir e2e/README.md et .env.test.example) :
 *   E2E_BASE_URL       — défaut https://logplus.duckdns.org
 *   E2E_OTP_BYPASS      — optionnel, code OTP fixe si jamais le backend expose
 *                         un mode debug (voir e2e/utils/auth.ts)
 *   QA_*_ACCESS_TOKEN / QA_*_REFRESH_TOKEN — JWT pré-obtenus pour chaque
 *                         compte QA (voir e2e/utils/auth.ts)
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false, // prod partagée : on évite les courses entre tests qui créent/suppriment des ressources QA_AUDIT_*
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: process.env.E2E_BASE_URL || "https://logplus.duckdns.org",
    // Le certificat Let's Encrypt du domaine est valide, mais on tolère les
    // erreurs TLS pour rester robuste si l'environnement local a un souci de
    // chaîne de certification (proxy d'entreprise, horloge, etc.).
    ignoreHTTPSErrors: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
