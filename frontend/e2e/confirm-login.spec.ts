/**
 * Test de la page de confirmation de login OAuth
 * (frontend/src/app/(auth)/confirm-login/[token]/page.tsx).
 *
 * Le token est un jeton signé côté backend émis lors d'une notification de
 * connexion suspecte sur un compte lié OAuth (LoginConfirmation, voir
 * loginConfirmationApi.describe/respond dans frontend/src/lib/api.ts), envoyé
 * uniquement par email — aucun moyen de le générer ou de le lire depuis
 * Playwright. On se limite donc au cas token invalide/expiré :
 *   - GET /api/auth/confirm-login/<token>/ (appelé par .describe() dans le
 *     useEffect au chargement) renvoie signing.BadSignature pour un jeton mal
 *     formé -> message exact confirmé côté backend
 *     (backend/apps/authentication/views.py, LoginConfirmationView.get) :
 *     "Lien invalide." La page affiche alors le stage "error" avec le titre
 *     "Lien invalide" et un bouton de retour vers /login.
 * Le cas nominal (token réel, carte de confirmation avec appareil/IP/geo,
 * boutons "C'est bien moi" / "Ce n'est pas moi") nécessiterait un vrai flux
 * OAuth + email non simulable ici ; non testé.
 */
import { test, expect } from "./fixtures";

test.describe("Confirmation de login — token invalide", () => {
  test("un token bidon affiche l'écran d'erreur avec message et retour à la connexion", async ({ page }) => {
    await page.goto("/confirm-login/QA_AUDIT_bogus_token_not_a_real_signature");

    // Passe par le stage "loading" (spinner "Vérification du lien…") avant l'erreur.
    await expect(page.getByText("Lien invalide", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Lien invalide\.|Lien invalide ou expiré\./i)).toBeVisible();

    await page.getByRole("button", { name: /Retour à la connexion/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
