/**
 * Test de la page de réinitialisation de mot de passe
 * (frontend/src/app/(auth)/reset-password/page.tsx).
 *
 * On ne dispose d'aucun vrai token de reset (envoyé par email, illisible
 * depuis Playwright — voir e2e/utils/auth.ts pour la même limite sur l'OTP).
 * On teste donc uniquement les deux cas d'erreur observables :
 *   1. Aucun token dans l'URL -> message d'erreur purement côté client
 *      ("Lien invalide ou incomplet...", page.tsx ligne 98), sans appel réseau.
 *   2. Un token présent mais invalide -> le formulaire s'affiche (le composant
 *      ne vérifie que la présence du param, pas sa validité), la soumission
 *      appelle authApi.confirmPasswordReset et le backend renvoie l'erreur de
 *      signature invalide. Message exact confirmé côté backend
 *      (backend/apps/authentication/views.py, PasswordResetConfirmView) :
 *      "Lien de réinitialisation invalide." pour un jeton syntaxiquement
 *      invalide (signing.BadSignature).
 */
import { test, expect } from "./fixtures";

test.describe("Réinitialisation de mot de passe — sans token valide", () => {
  test("sans paramètre token, affiche l'erreur cliente et aucun formulaire", async ({ page }) => {
    await page.goto("/reset-password");

    await expect(
      page.getByText("Lien invalide ou incomplet. Redemandez une réinitialisation depuis la page de connexion.")
    ).toBeVisible();
    await expect(page.getByLabel("Nouveau mot de passe")).toHaveCount(0);
  });

  test("avec un token bidon, la soumission renvoie l'erreur backend 'lien invalide'", async ({ page }) => {
    await page.goto("/reset-password?token=QA_AUDIT_bogus_token_not_a_real_signature");

    await page.getByLabel("Nouveau mot de passe").fill("QA_AUDIT_MotDePasse123!");
    await page.getByLabel("Confirmer le mot de passe").fill("QA_AUDIT_MotDePasse123!");
    await page.getByRole("button", { name: /Réinitialiser/i }).click();

    await expect(page.getByText(/Lien de réinitialisation invalide\.|Une erreur est survenue\./i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
