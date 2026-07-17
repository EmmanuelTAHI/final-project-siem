/**
 * Tests E2E de la page Rapports (frontend/src/app/(dashboard)/reports/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir playwright.config.ts).
 *
 * Toutes les actions de génération/téléchargement retournent un blob
 * (responseType: "blob" côté reportsApi, frontend/src/lib/api.ts) — on
 * n'inspecte donc jamais le contenu du fichier téléchargé, seulement la
 * requête réseau interceptée via `page.waitForResponse` :
 *   - GET /api/reports/generate/?type=...&period=...   (rapports prédéfinis)
 *   - GET /api/reports/export/?sources=...&period=...&format=...  (personnalisé)
 *   - GET /api/reports/history/{id}/download/          (depuis l'historique)
 * `triggerDownload()` (frontend, reports/page.tsx) crée un <a download> cliqué
 * en synthèse : pas de popup navigateur natif à gérer, `waitForResponse` suffit.
 *
 * Limite notée : les sources de données sont des <label> englobant un
 * checkbox visuellement masqué (style display:none) — on interagit donc via
 * le texte du label plutôt que via getByRole("checkbox").
 */
import { test, expect } from "./fixtures";

test.describe("Rapports", () => {
  test("génère un rapport prédéfini (SOC hebdomadaire) et intercepte la requête", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/reports");

    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/reports/generate/") && r.request().method() === "GET"),
      page
        .locator("div")
        .filter({ hasText: "Rapport hebdomadaire SOC" })
        .getByRole("button", { name: /Générer/ })
        .click(),
    ]);

    expect(response.ok()).toBeTruthy();
    await expect(page.getByText(/Rapport « Rapport hebdomadaire SOC » généré et téléchargé/)).toBeVisible();
  });

  test("change la période et le format puis génère un rapport personnalisé", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/reports");

    // Période 30j
    await page.getByRole("button", { name: "30j", exact: true }).click();
    // Format CSV
    await page.getByRole("button", { name: "csv", exact: true }).click();

    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/reports/export/") && r.request().method() === "GET"),
      page.getByRole("button", { name: "Générer le rapport" }).click(),
    ]);

    expect(response.ok()).toBeTruthy();
    expect(response.url()).toContain("format=csv");
    expect(response.url()).toContain("period=30");
    await expect(page.getByText("Rapport personnalisé généré et téléchargé")).toBeVisible();
  });

  test("décoche toutes les sources : le bouton de génération personnalisée est désactivé", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/reports");

    // Décoche les 5 sources (le clic sur le <label> bascule le checkbox caché)
    const sourceLabels = ["Microsoft 365", "Google Workspace", "Wazuh", "Syslog", "Agent Log+"];
    for (const label of sourceLabels) {
      await page.getByText(label, { exact: true }).click();
    }

    await expect(page.getByRole("button", { name: "Générer le rapport" })).toBeDisabled();
  });

  test("télécharge un rapport depuis l'historique en interceptant la requête", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/reports");

    // Génère d'abord un rapport pour garantir une entrée d'historique récente
    const [genResponse] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/reports/generate/") && r.request().method() === "GET"),
      page
        .locator("div")
        .filter({ hasText: "Top menaces détectées" })
        .getByRole("button", { name: /Générer/ })
        .click(),
    ]);
    expect(genResponse.ok()).toBeTruthy();
    await expect(page.getByText(/généré et téléchargé/)).toBeVisible();

    // L'historique est invalidé (react-query) après génération ; on recharge
    // par sécurité pour repartir d'un état serveur propre.
    await page.reload();

    const historyCard = page.locator(".card").filter({ hasText: "Historique" });
    const firstEntry = historyCard.locator("button").first();
    await expect(firstEntry).toBeVisible();

    const [dlResponse] = await Promise.all([
      page.waitForResponse((r) => /\/api\/reports\/history\/.+\/download\//.test(r.url())),
      firstEntry.click(),
    ]);

    expect(dlResponse.ok()).toBeTruthy();
  });
});
