/**
 * Test de la page de confirmation d'email
 * (frontend/src/app/(auth)/verify-email/page.tsx).
 *
 * Comme pour reset-password, aucun vrai token de vérification n'est
 * accessible depuis Playwright (envoyé par email lors de /register). On
 * couvre donc uniquement :
 *   1. Absence de token -> erreur purement côté client ("Lien invalide :
 *      jeton manquant.", page.tsx ligne 18), sans appel réseau.
 *   2. Token bidon -> le composant appelle authApi.verifyEmail, le backend
 *      renvoie signing.BadSignature -> message exact confirmé côté backend
 *      (backend/apps/authentication/views.py, VerifyEmailView) :
 *      "Lien de confirmation invalide."
 * Le cas nominal (token réel -> "Adresse email confirmée...") nécessiterait
 * un email réel non accessible ici ; non testé.
 */
import { test, expect } from "./fixtures";

test.describe("Confirmation d'email — sans token valide", () => {
  test("sans paramètre token, affiche l'erreur cliente et le lien de recommencer", async ({ page }) => {
    await page.goto("/verify-email");

    await expect(page.getByText("Lien invalide : jeton manquant.")).toBeVisible();
    await expect(page.getByRole("link", { name: /Recommencer l'inscription/i })).toBeVisible();
  });

  test("avec un token bidon, affiche l'erreur backend 'lien de confirmation invalide'", async ({ page }) => {
    await page.goto("/verify-email?token=QA_AUDIT_bogus_token_not_a_real_signature");

    // Passe par l'état "loading" (spinner) avant l'erreur.
    await expect(
      page.getByText(/Lien de confirmation invalide\.|Ce lien de confirmation est invalide ou a expiré\./i)
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: /Recommencer l'inscription/i })).toBeVisible();
  });
});
