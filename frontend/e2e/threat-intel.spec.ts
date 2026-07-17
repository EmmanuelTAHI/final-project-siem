/**
 * Tests E2E de la page Threat Intelligence (frontend/src/app/(dashboard)/threat-intel/page.tsx).
 * Pas de création/suppression de ressource ici : uniquement un lookup
 * (recherche) d'indicateur en lecture seule (IP / domaine / hash), avec
 * détection automatique du type via detectIndicatorType().
 * Contre la prod https://logplus.duckdns.org (voir e2e/playwright.config.ts).
 */
import { test, expect } from "./fixtures";

test.describe("Threat Intelligence", () => {
  test("lookup d'une IP publique connue affiche un résultat sans crash", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/threat-intel");

    await expect(page.getByRole("heading", { name: "Threat Intelligence" })).toBeVisible();

    const input = page.getByPlaceholder("IP, domaine, hash MD5 / SHA-256 — détection automatique");
    await input.fill("8.8.8.8");

    // Le badge de détection automatique doit reconnaître le type IPv4.
    await expect(page.getByText("Adresse IPv4 détectée")).toBeVisible();

    await page.getByRole("button", { name: "Analyser" }).click();

    // Synthèse globale affichée (verdict quel qu'il soit) + valeur recherchée visible.
    await expect(page.getByText("Synthèse")).toBeVisible();
    await expect(page.getByText("8.8.8.8", { exact: true })).toBeVisible();

    // Les panneaux de sources spécifiques aux IP sont rendus sans planter la page.
    await expect(page.getByText("Empreinte interne (SIEM)")).toBeVisible();
    await expect(page.getByText("Géolocalisation & réseau")).toBeVisible();
    await expect(page.getByText("AbuseIPDB")).toBeVisible();
  });

  test("lookup d'un domaine détecte le type et affiche un résultat", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/threat-intel");

    const input = page.getByPlaceholder("IP, domaine, hash MD5 / SHA-256 — détection automatique");
    await input.fill("example.com");

    await expect(page.getByText("Nom de domaine détecté")).toBeVisible();

    await page.getByRole("button", { name: "Analyser" }).click();

    await expect(page.getByText("Synthèse")).toBeVisible();
    // Pour un domaine, seul le panneau VirusTotal est affiché (les panneaux IP-only sont masqués).
    await expect(page.getByText("Agrégateur multi-AV — analyse domaine")).toBeVisible();
  });

  test("une valeur non reconnue désactive le bouton Analyser (pas de crash)", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/threat-intel");

    const input = page.getByPlaceholder("IP, domaine, hash MD5 / SHA-256 — détection automatique");
    // Ni IP, ni domaine, ni hash : ne matche aucune regex de detectIndicatorType().
    await input.fill("!! not an indicator !!");

    await expect(page.getByText("Type non reconnu — vérifiez la valeur")).toBeVisible();
    await expect(page.getByRole("button", { name: "Analyser" })).toBeDisabled();
  });
});
