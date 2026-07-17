/**
 * Tests E2E de la page Agents de collecte (frontend/src/app/(dashboard)/agents/page.tsx),
 * qui contient la modal inline GenerateTokenModal.
 * Contre la prod https://logplus.duckdns.org (voir e2e/playwright.config.ts).
 */
import { test, expect } from "./fixtures";
import { qaName } from "./utils/api";

test.describe("Agents de collecte", () => {
  test.afterEach(async ({ apiAs }) => {
    const api = await apiAs("adminA");
    await api.deleteEnrollmentTokensMatchingPrefix();
  });

  test("générer un token QA_AUDIT, le copier, puis le révoquer via l'UI", async ({ page, context, authAs }) => {
    // Autorise l'accès au presse-papier avant navigation (nécessaire pour
    // navigator.clipboard.writeText/readText dans Chromium).
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);

    await authAs("adminA");
    await page.goto("/agents");

    const tokenName = qaName("agent");

    // Ouvre la modal de génération
    await page.getByRole("button", { name: "Générer un token" }).click();
    await expect(page.getByRole("heading", { name: "Générer un token d'agent" })).toBeVisible();

    // Remplit le nom et génère
    await page.getByPlaceholder("Ex: Serveurs web prod, Parc Windows siège").fill(tokenName);
    await page.getByRole("button", { name: "Générer le token" }).click();

    // Le token brut s'affiche, avec le bouton Copier
    await expect(page.getByRole("heading", { name: "Token généré" })).toBeVisible();
    const copyButton = page.getByRole("button", { name: "Copier" });
    await expect(copyButton).toBeVisible();

    await copyButton.click();
    // Le libellé du bouton passe à "Copié" après le clic (état `copied`).
    await expect(page.getByRole("button", { name: "Copié" })).toBeVisible();

    // Vérifie que le contenu a bien été écrit dans le presse-papier.
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText.length).toBeGreaterThan(0);

    // Ferme la modal
    await page.getByRole("button", { name: "J'ai copié le token" }).click();

    // Le token apparaît dans la liste, actif
    await expect(page.getByText(tokenName)).toBeVisible();

    // Révoque le token via l'UI — handleRevoke() utilise window.confirm().
    page.once("dialog", (dialog) => dialog.accept());
    const tokenCard = page.locator(".rounded-xl.border").filter({ hasText: tokenName });
    await tokenCard.getByRole("button", { name: "Révoquer" }).click();

    // Le badge de statut passe à "Révoqué" et le bouton Révoquer se désactive
    // (disabled dès que is_active === false).
    await expect(tokenCard.getByText("Révoqué")).toBeVisible();
    await expect(tokenCard.getByRole("button", { name: "Révoquer" })).toBeDisabled();
  });
});
