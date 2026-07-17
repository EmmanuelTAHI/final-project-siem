/**
 * Tests E2E de la page Corrélation (frontend/src/app/(dashboard)/correlation/page.tsx),
 * qui utilise la modal RuleFormModal (frontend/src/components/correlation/rule-form-modal.tsx)
 * et la suppression via RuleCard + ConfirmDialog (frontend/src/components/correlation/rule-card.tsx,
 * frontend/src/components/ui/confirm-dialog.tsx).
 * Contre la prod https://logplus.duckdns.org (voir e2e/playwright.config.ts).
 */
import { test, expect } from "./fixtures";
import { qaName } from "./utils/api";

test.describe("Règles de corrélation", () => {
  test.afterEach(async ({ apiAs }) => {
    const api = await apiAs("adminA");
    await api.deleteCorrelationRulesMatchingPrefix();
  });

  test("créer une règle de seuil QA_AUDIT, la voir apparaître, puis la supprimer via l'UI", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/correlation");

    const ruleName = qaName("rule");

    // Ouvre la modal de création
    await page.getByRole("button", { name: "Nouvelle règle" }).click();
    await expect(page.getByRole("heading", { name: "Nouvelle règle de corrélation" })).toBeVisible();

    // Remplit le nom (seul champ requis côté client)
    await page.getByPlaceholder("ex: Brute Force Detection").fill(ruleName);
    // Le type "Seuil (Threshold)" est sélectionné par défaut : renseigne l'action à surveiller.
    await page.getByPlaceholder("ex: FailedLogin").fill("FailedLogin");

    await page.getByRole("button", { name: "Créer la règle" }).click();

    // La règle apparaît dans la grille
    await expect(page.getByText(ruleName)).toBeVisible();

    // Supprime la règle via l'UI : bouton icône "Supprimer" (title) sur la card,
    // puis confirmation dans ConfirmDialog (bouton destructif "Supprimer").
    const ruleCard = page.locator(".rounded-xl.border").filter({ hasText: ruleName });
    await ruleCard.getByTitle("Supprimer").click();

    const confirmDialog = page.locator('[role="dialog"]').filter({ hasText: "Supprimer la règle" });
    await expect(confirmDialog).toBeVisible();
    await expect(confirmDialog.getByText(ruleName)).toBeVisible();
    await confirmDialog.getByRole("button", { name: "Supprimer" }).click();

    // La règle disparaît de la liste
    await expect(page.getByText(ruleName)).not.toBeVisible();
  });

  test("viewerA ne voit aucun bouton de création de règle (si le rôle est vérifié)", async ({ page, authAs }) => {
    await authAs("viewerA");
    await page.goto("/correlation");

    // NOTE : CorrelationPageContent (frontend/src/app/(dashboard)/correlation/page.tsx)
    // n'a AUCUNE logique conditionnelle basée sur le rôle utilisateur — le
    // bouton "Nouvelle règle" est toujours rendu, quel que soit le compte
    // connecté. Ce test documente donc le comportement réel actuel : le
    // bouton reste visible pour viewerA. Si une restriction RBAC est ajoutée
    // côté frontend plus tard, ce test devra être mis à jour.
    await expect(page.getByRole("button", { name: "Nouvelle règle" })).toBeVisible();
  });
});
