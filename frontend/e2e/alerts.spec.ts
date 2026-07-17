/**
 * Tests E2E de la page Alertes (frontend/src/app/(dashboard)/alerts/page.tsx).
 * Contre la prod https://logplus.duckdns.org.
 *
 * Note importante sur les rôles : ce fichier ne fait AUCUNE distinction de
 * rôle côté rendu (pas de `if (role === ...)` autour des boutons "Créer
 * règle" / changement de statut / export). Les boutons sont donc visibles et
 * cliquables pour tous les rôles authentifiés côté UI — toute restriction
 * réelle ne peut venir que du backend (403 sur le PATCH/POST). Le test
 * "viewerA" ci-dessous vérifie donc le comportement du backend via l'API
 * directe plutôt que d'inventer un état désactivé qui n'existe pas dans le JSX.
 */
import { test, expect } from "./fixtures";
import type { APIResponse } from "@playwright/test";

test.describe("Alertes", () => {
  test("filtrage par sévérité met à jour la liste", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/alerts");
    await expect(page.getByText("Gestion des alertes")).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET"),
      page.locator(".pill", { hasText: "Critique" }).click(),
    ]);
    expect(response.ok()).toBeTruthy();
    await expect(page.locator(".pill", { hasText: "Critique" })).toHaveClass(/active/);

    // Remise à "Toutes" pour ne pas polluer l'état visuel des tests suivants.
    await page.locator(".pill", { hasText: "Toutes" }).click();
  });

  test("filtrage par statut met à jour la liste", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/alerts");
    await expect(page.getByText("Gestion des alertes")).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET"),
      page.locator(".pill", { hasText: "Résolu" }).click(),
    ]);
    expect(response.ok()).toBeTruthy();
    await expect(page.locator(".pill", { hasText: "Résolu" })).toHaveClass(/active/);

    await page.locator(".pill", { hasText: "Tous" }).click();
  });

  test("recherche instantanée filtre la liste", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/alerts");

    const searchInput = page.getByPlaceholder("Recherche instantanée : titre, description…");
    await expect(searchInput).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET", {
        timeout: 10_000,
      }),
      searchInput.fill("QA_AUDIT_recherche_inexistante_xyz"),
    ]);
    expect(response.ok()).toBeTruthy();
    await expect(page.getByText("Aucune alerte ne correspond aux filtres.")).toBeVisible({ timeout: 10_000 });

    await searchInput.fill("");
  });

  test("expansion d'une AlertCard affiche les détails et commentaires", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/alerts");
    await page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET");

    const emptyState = page.getByText("Aucune alerte ne correspond aux filtres.");
    if (await emptyState.isVisible().catch(() => false)) {
      test.skip(true, "Aucune alerte en prod actuellement : impossible de tester l'expansion.");
    }

    const firstCardHeader = page.locator(".card").filter({ has: page.locator("text=R-") }).first();
    await expect(firstCardHeader).toBeVisible({ timeout: 10_000 });
    await firstCardHeader.click();

    await expect(page.getByText("Détails techniques").first()).toBeVisible();
    await expect(page.getByText(/Commentaires/).first()).toBeVisible();
    await expect(page.getByPlaceholder("Ajouter une note d'investigation…").first()).toBeVisible();

    // Referme pour laisser la page dans un état propre.
    await firstCardHeader.click();
  });

  test("changement de statut d'une alerte réelle puis remise à l'état d'origine (adminA)", async ({
    page,
    authAs,
    apiAs,
  }) => {
    await authAs("adminA");
    const api = await apiAs("adminA");

    const list = await api.get<{ results: Array<{ id: number; status: string }> }>(
      "/api/alerts/?status=open&page_size=1"
    );
    if (!list.results?.[0]) {
      test.skip(true, "Aucune alerte au statut 'open' en prod : impossible de tester le changement de statut.");
      return;
    }

    await page.goto("/alerts");
    await page.locator(".pill", { hasText: "Nouveau" }).click();
    await page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET");

    const card = page.locator(".card").filter({ has: page.locator("text=R-") }).first();
    await expect(card).toBeVisible({ timeout: 10_000 });

    const takeChargeBtn = card.getByTitle("Prendre en charge");
    const [patchResponse] = await Promise.all([
      page.waitForResponse((res) => /\/api\/alerts\/\d+\/$/.test(res.url()) && res.request().method() === "PATCH"),
      takeChargeBtn.click(),
    ]);
    await expect(page.getByText(/Statut mis à jour : En cours/)).toBeVisible({ timeout: 10_000 });

    // On extrait l'ID de la VRAIE alerte modifiée depuis l'URL du PATCH
    // intercepté (au lieu de supposer que c'est la même que celle lue plus
    // haut, dont l'ordre n'est pas garanti identique à celui du tri client).
    const alertId = Number(patchResponse.url().match(/\/api\/alerts\/(\d+)\//)?.[1]);
    expect(alertId).toBeGreaterThan(0);

    // Remise à l'état d'origine ("open") directement via l'API (plus fiable que l'UI).
    await api.patch(`/api/alerts/${alertId}/`, { status: "open" });
    const verify = await api.get<{ status: string }>(`/api/alerts/${alertId}/`);
    expect(verify.status).toBe("open");
  });

  test("analystA peut changer le statut d'une alerte (puis remise à l'état d'origine)", async ({
    page,
    authAs,
    apiAs,
  }) => {
    await authAs("analystA");
    const api = await apiAs("analystA");

    const list = await api.get<{ results: Array<{ id: number; status: string }> }>(
      "/api/alerts/?status=open&page_size=1"
    );
    if (!list.results?.[0]) {
      test.skip(true, "Aucune alerte au statut 'open' en prod : impossible de tester le changement de statut.");
      return;
    }

    await page.goto("/alerts");
    await page.locator(".pill", { hasText: "Nouveau" }).click();
    await page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET");

    const card = page.locator(".card").filter({ has: page.locator("text=R-") }).first();
    await expect(card).toBeVisible({ timeout: 10_000 });

    const takeChargeBtn = card.getByTitle("Prendre en charge");
    const [patchResponse] = await Promise.all([
      page.waitForResponse((res) => /\/api\/alerts\/\d+\/$/.test(res.url()) && res.request().method() === "PATCH"),
      takeChargeBtn.click(),
    ]);
    await expect(page.getByText(/Statut mis à jour : En cours/)).toBeVisible({ timeout: 10_000 });

    const alertId = Number(patchResponse.url().match(/\/api\/alerts\/(\d+)\//)?.[1]);
    expect(alertId).toBeGreaterThan(0);
    await api.patch(`/api/alerts/${alertId}/`, { status: "open" });
  });

  test("viewerA : le JSX n'interdit aucun bouton, mais le backend doit refuser un PATCH de statut", async ({
    request,
    authAs,
    apiAs,
  }) => {
    const auth = await authAs("viewerA");
    const api = await apiAs("adminA"); // adminA sert uniquement à lire une alerte existante
    const list = await api.get<{ results: Array<{ id: number; status: string }> }>("/api/alerts/?page_size=1");
    const target = list.results?.[0];
    if (!target) {
      test.skip(true, "Aucune alerte en prod : impossible de vérifier la permission backend pour viewerA.");
      return;
    }

    const base = process.env.E2E_BASE_URL || "https://logplus.duckdns.org";
    const res: APIResponse = await request.patch(`${base}/api/alerts/${target.id}/`, {
      headers: { Authorization: `Bearer ${auth.access}` },
      data: { status: "resolved" },
    });
    expect(res.status(), "Le rôle viewer ne devrait pas pouvoir modifier le statut d'une alerte (403 attendu)").toBe(
      403
    );
  });

  test("export CSV affiche un toast de succès", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/alerts");
    await page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET");

    const emptyState = page.getByText("Aucune alerte ne correspond aux filtres.");
    const isEmpty = await emptyState.isVisible().catch(() => false);

    await page.getByRole("button", { name: /Exporter CSV/ }).click();

    if (isEmpty) {
      await expect(page.getByText("Aucune alerte à exporter")).toBeVisible();
    } else {
      await expect(page.getByText(/alertes exportées/)).toBeVisible();
    }
  });

  test("bouton Créer règle navigue vers /correlation?new=1", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/alerts");

    await page.getByRole("button", { name: /Créer règle/ }).click();
    await expect(page).toHaveURL(/\/correlation\?new=1/);
  });

  test("pagination Préc./Suiv. si plusieurs pages existent", async ({ page, authAs, apiAs }) => {
    await authAs("adminA");
    const api = await apiAs("adminA");
    const stats = await api.get<{ count: number }>("/api/alerts/?page_size=25");
    const totalCount = stats.count ?? 0;

    if (totalCount <= 25) {
      test.skip(true, `Une seule page d'alertes en prod (${totalCount} alertes) : pagination non testable.`);
      return;
    }

    await page.goto("/alerts");
    await page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET");

    const nextBtn = page.locator(".pill", { hasText: "Suiv." });
    await expect(nextBtn).toBeEnabled();
    await Promise.all([
      page.waitForResponse((res) => res.url().includes("/api/alerts/") && res.request().method() === "GET"),
      nextBtn.click(),
    ]);
    await expect(page.getByText("2 / ")).toBeVisible();

    const prevBtn = page.locator(".pill", { hasText: "Préc." });
    await prevBtn.click();
  });
});
