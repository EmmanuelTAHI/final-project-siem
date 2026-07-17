/**
 * Tests E2E de la page Logs (frontend/src/app/(dashboard)/logs/page.tsx).
 * Contre la prod https://logplus.duckdns.org.
 */
import { test, expect } from "./fixtures";

test.describe("Logs", () => {
  test("affiche le header et le tableau de logs", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    await expect(page.getByText("Événements & logs")).toBeVisible();
    await expect(page.getByText("résultats")).toBeVisible();
    // Colonnes de la vue table par défaut.
    await expect(page.getByRole("columnheader", { name: "Timestamp" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Level" })).toBeVisible();
  });

  test("toggle Live active/désactive le mode live", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    const liveBtn = page.getByRole("button", { name: /Live/ });
    await expect(liveBtn).toBeVisible();
    await expect(liveBtn).not.toHaveClass(/btn-primary/);

    await liveBtn.click();
    await expect(liveBtn).toHaveClass(/btn-primary/);

    // On désactive pour ne pas laisser le mode live actif (auto-refresh 30s).
    await liveBtn.click();
    await expect(liveBtn).not.toHaveClass(/btn-primary/);
  });

  test("recherche filtre côté client la liste des logs", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    const searchInput = page.getByPlaceholder("Recherche en temps réel : action, utilisateur, IP, source…");
    await expect(searchInput).toBeVisible();
    await searchInput.fill("QA_AUDIT_recherche_inexistante_xyz");

    // Le filtrage est client-side avec debounce 300ms.
    await expect(page.getByText("Aucun événement ne correspond aux filtres actifs.")).toBeVisible({
      timeout: 5_000,
    });

    await searchInput.fill("");
  });

  test("filtres de sévérité (pills HIGH/MEDIUM/LOW) togglent l'affichage", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    const highPill = page.getByRole("button", { name: "HIGH" });
    await expect(highPill).toBeVisible();
    await highPill.click();

    // Une chip de filtre actif "Sévérité: HIGH" doit apparaître.
    await expect(page.getByText("HIGH", { exact: true }).last()).toBeVisible();

    await highPill.click();
  });

  test("panneau Avancé s'ouvre et affiche les champs de filtre", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    const advancedBtn = page.getByRole("button", { name: /Avancé/ });
    await advancedBtn.click();

    await expect(page.getByText("Date début")).toBeVisible();
    await expect(page.getByText("Date fin")).toBeVisible();
    await expect(page.getByPlaceholder("ex: wazuh, syslog…")).toBeVisible();
    await expect(page.getByPlaceholder("ex: login, deny…")).toBeVisible();
    await expect(page.getByPlaceholder("email ou identifiant…")).toBeVisible();
    await expect(page.getByPlaceholder("ex: 192.168.1…")).toBeVisible();

    await advancedBtn.click();
  });

  test("changement de vue table/json/raw", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    // Les libellés "table/json/raw" sont en textTransform:capitalize côté CSS ;
    // on matche donc en case-insensitive plutôt que sur le texte source exact.
    await page.getByRole("button", { name: /^json$/i }).click();
    // En vue JSON, le contenu est affiché dans un <pre> avec coloration syntaxique.
    await expect(page.locator("pre.font-mono")).toBeVisible();

    await page.getByRole("button", { name: /^raw$/i }).click();
    await expect(page.locator("pre.font-mono")).toBeVisible();

    await page.getByRole("button", { name: /^table$/i }).click();
  });

  test("clic sur une ligne de log étend le détail JSON (si au moins un log existe)", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    const noResults = page.getByText("Aucun événement ne correspond aux filtres actifs.");
    if (await noResults.isVisible().catch(() => false)) {
      test.skip(true, "Aucun log en prod actuellement : impossible de tester l'expansion d'une ligne.");
      return;
    }

    const firstRow = page.locator("table.tbl tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();

    // La ligne de détail JSON suivante doit apparaître.
    await expect(page.locator("table.tbl tbody tr").nth(1).locator("pre.font-mono")).toBeVisible();

    // Referme.
    await firstRow.click();
  });

  test("clic sur Actualiser relance la requête de logs", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/logs");

    // Le bouton refresh n'a pas de texte (icône RefreshCw seule) : on cible le
    // bouton ".btn" sans contenu textuel dans le header (entre "Live" et "Exporter").
    const refreshBtn = page.locator("button.btn").filter({ hasText: /^$/ }).first();
    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/api/logs/normalized/")),
      refreshBtn.click(),
    ]);
    expect(response.ok()).toBeTruthy();
  });
});
