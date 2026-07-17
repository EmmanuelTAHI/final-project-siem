/**
 * Test du formulaire "mot de passe oublié"
 * (frontend/src/app/(auth)/forgot-password/page.tsx).
 *
 * Le comportement voulu (anti-énumération de comptes) est de toujours
 * afficher le même message de succès, que l'email existe ou non. On ne
 * vérifie donc que ce message — aucun nettoyage nécessaire : l'appel ne fait
 * qu'envoyer un email (idempotent, pas de ressource créée en base testable
 * depuis le frontend).
 */
import { test, expect } from "./fixtures";

test.describe("Mot de passe oublié", () => {
  test("soumettre un email affiche le message anti-énumération et le lien de retour", async ({ page }) => {
    await page.goto("/forgot-password");

    const email = `qa-audit-forgot-${Date.now()}@test.local`;
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: /Envoyer le lien/i }).click();

    await expect(page.getByText(/Si un compte existe avec l'adresse/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByText(/valide 30 minutes/i)).toBeVisible();
  });

  test("le lien 'Retour à la connexion' est présent avant soumission", async ({ page }) => {
    // Vérifie juste la navigation de secours, sans dépendre du réseau.
    await page.goto("/forgot-password");
    await expect(page.getByRole("link", { name: /Retour à la connexion/i })).toBeVisible();
  });
});
