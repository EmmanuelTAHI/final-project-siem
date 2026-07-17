/**
 * Tests E2E de la page Threat Hunting (frontend/src/app/(dashboard)/hunting/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir playwright.config.ts).
 *
 * Limite notée : le bouton qui révèle le formulaire de sauvegarde et le
 * bouton qui soumet ce formulaire portent tous les deux le texte exact
 * "Sauvegarder" (un avec l'icône <Save>, l'autre nu) — on les distingue via
 * `.filter({ has/hasNot: page.locator("svg") })`. Les boutons "exécuter" et
 * "supprimer" d'une requête sauvegardée sont aussi des icônes sans texte
 * accessible, ciblés en scopant sur la carte contenant le nom unique
 * QA_AUDIT_. La suppression déclenche `window.confirm("Supprimer ?")`.
 */
import { test, expect } from "./fixtures";
import { qaName } from "./utils/api";

test.describe("Threat Hunting", () => {
  test.afterEach(async ({ apiAs }) => {
    const api = await apiAs("adminA");
    await api.deleteHuntingQueriesMatchingPrefix();
  });

  test("lance une chasse ad-hoc avec des filtres", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/hunting");

    // Déplie les filtres : le bouton chevron de la carte "Filtres de recherche"
    // est un ghost Button sans texte (accessible name vide), unique dans cette carte.
    const filtersCard = page.locator(".card-gradient").filter({ hasText: "Filtres de recherche" });
    await filtersCard.getByRole("button", { name: "" }).click();
    await page.getByPlaceholder("Action (ex: login_failure)").fill("login_failure");

    await page.getByRole("button", { name: "Lancer la chasse" }).click();

    // Résultats affichés (avec ou sans match, la carte "Résultats" se met à jour)
    await expect(page.getByText(/Résultats/)).toBeVisible();
  });

  test("applique un template MITRE ATT&CK", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/hunting");

    await page.getByRole("button", { name: /Brute Force détection/ }).click();

    // Toast de confirmation d'application des filtres
    await expect(page.getByText("Filtres appliqués: Brute Force détection")).toBeVisible();
  });

  test("sauvegarde une requête QA_AUDIT, l'exécute puis la supprime via l'UI", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/hunting");

    const queryName = qaName("hunt");

    // Ouvre le formulaire de sauvegarde (bouton avec icône Save)
    const openSaveForm = page
      .getByRole("button", { name: "Sauvegarder" })
      .filter({ has: page.locator("svg") });
    await openSaveForm.click();

    await page.getByPlaceholder("Nom de la requête").fill(queryName);
    await page.getByPlaceholder("Tactique MITRE (optionnel)").fill("TA0006 - Credential Access");

    // Soumet (bouton texte nu, sans icône)
    const submitSave = page
      .getByRole("button", { name: "Sauvegarder", exact: true })
      .filter({ hasNot: page.locator("svg") });
    await submitSave.click();

    await expect(page.getByText("Requête sauvegardée")).toBeVisible();

    const card = page.locator(".rounded-lg.border").filter({ hasText: queryName });
    await expect(card).toBeVisible();

    // Exécute la requête sauvegardée (bouton icône Play)
    await card.getByRole("button").first().click();
    // L'exécution recharge les résultats sans crash ; la carte reste visible.
    await expect(card).toBeVisible();

    // Supprime via l'UI (window.confirm("Supprimer ?"))
    page.once("dialog", (dialog) => dialog.accept());
    await card.getByRole("button").last().click();
    await expect(page.getByText(queryName)).not.toBeVisible();
  });
});
