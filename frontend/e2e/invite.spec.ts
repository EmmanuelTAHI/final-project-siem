/**
 * Test de la page d'acceptation d'invitation
 * (frontend/src/app/(auth)/invite/page.tsx).
 *
 * Le token d'invitation est généré côté backend (send_invite_email,
 * backend/apps/authentication/views.py, InviteUserView) et envoyé uniquement
 * par email : la réponse HTTP de POST /api/users/invite/ ne contient que
 * { message: "Invitation envoyée à ..." } (vérifié dans le code de la vue :
 * aucun champ token/uid dans success_response), donc même en appelant
 * apiAs('adminA').post('/api/users/invite/', ...) on ne peut PAS récupérer un
 * vrai token exploitable depuis Playwright. On se limite donc au cas token
 * invalide/absent :
 *   1. Aucun token -> erreur purement côté client ("Lien invalide ou
 *      incomplet...", page.tsx ligne 92), sans appel réseau.
 *   2. Token bidon -> le formulaire s'affiche (le composant ne vérifie que la
 *      présence du param), la soumission déclenche authApi.acceptInvite et le
 *      backend renvoie signing.BadSignature -> message exact confirmé côté
 *      backend (AcceptInviteView) : "Lien d'invitation invalide."
 */
import { test, expect } from "./fixtures";

test.describe("Acceptation d'invitation — sans token valide", () => {
  test("sans paramètre token, affiche l'erreur cliente et aucun formulaire", async ({ page }) => {
    await page.goto("/invite");

    await expect(
      page.getByText("Lien invalide ou incomplet. Demandez à votre administrateur de vous réinviter.")
    ).toBeVisible();
    await expect(page.getByLabel("Mot de passe", { exact: true })).toHaveCount(0);
  });

  test("avec un token bidon, la soumission renvoie l'erreur backend 'lien d'invitation invalide'", async ({
    page,
  }) => {
    await page.goto("/invite?token=QA_AUDIT_bogus_token_not_a_real_signature");

    await page.getByLabel("Mot de passe", { exact: true }).fill("QA_AUDIT_MotDePasse123!");
    await page.getByLabel("Confirmer le mot de passe").fill("QA_AUDIT_MotDePasse123!");
    await page.getByRole("button", { name: /Activer mon compte/i }).click();

    await expect(page.getByText(/Lien d'invitation invalide\.|Une erreur est survenue\./i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
