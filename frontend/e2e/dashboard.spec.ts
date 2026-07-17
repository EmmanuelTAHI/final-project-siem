/**
 * Tests E2E de la page Dashboard (frontend/src/app/(dashboard)/dashboard/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir e2e/playwright.config.ts).
 */
import { test, expect } from "./fixtures";

test.describe("Dashboard", () => {
  test("affiche le header et les 4 KPI cards", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/dashboard");

    await expect(page.getByText("Tableau de bord SOC")).toBeVisible();
    await expect(page.getByText("Alertes ouvertes")).toBeVisible();
    await expect(page.getByText("Logs collectés / 24h")).toBeVisible();
    await expect(page.getByText("Connecteurs actifs")).toBeVisible();
    await expect(page.getByText("Anomalies ML / 24h")).toBeVisible();
  });

  test("clic sur Actualiser relance la requête de résumé sans casser la page", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/dashboard");
    await expect(page.getByText("Alertes ouvertes")).toBeVisible();

    const refreshBtn = page.getByRole("button", { name: /Actualiser/ });
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();

    // La page reste fonctionnelle : les KPIs sont toujours affichés après refetch.
    await expect(page.getByText("Alertes ouvertes")).toBeVisible();
  });

  test("clic sur le KPI Alertes ouvertes navigue vers /alerts", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/dashboard");

    await page.getByText("Alertes ouvertes").click();
    await expect(page).toHaveURL(/\/alerts/);
  });

  test("clic sur le KPI Connecteurs actifs navigue vers /collectors", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/dashboard");

    await page.getByText("Connecteurs actifs").click();
    await expect(page).toHaveURL(/\/collectors/);
  });

  test("clic sur le KPI Anomalies ML navigue vers /ml", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/dashboard");

    await page.getByText("Anomalies ML / 24h").click();
    await expect(page).toHaveURL(/\/ml/);
  });

  test("clic sur Exporter déclenche la requête réseau de génération de rapport", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/dashboard");

    const [request] = await Promise.all([
      page.waitForRequest((req) => req.url().includes("/api/reports/generate/")),
      page.getByRole("button", { name: /Exporter/ }).click(),
    ]);

    expect(request.url()).toContain("/api/reports/generate/");
    expect(request.url()).toContain("type=soc_weekly");
  });
});
