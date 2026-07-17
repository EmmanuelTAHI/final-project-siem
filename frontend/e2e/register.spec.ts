/**
 * Test du formulaire d'inscription (frontend/src/app/(auth)/register/page.tsx).
 *
 * IMPORTANT — nettoyage impossible : ce test crée un compte utilisateur ET une
 * organisation réels en prod via POST /api/auth/register/. Vérifié dans
 * frontend/src/lib/api.ts (platformApi) : il n'existe aucune méthode
 * deleteOrganization/removeOrganization exposée côté frontend (seulement
 * listOrganizations, getOrganizationsOverview, getOrganizationStats — aucune
 * suppression). Le backend n'expose donc pas non plus de suppression
 * d'organisation utilisable depuis cette suite. On garde volontairement le
 * test actif (plutôt que test.skip) car c'est le seul moyen de couvrir ce
 * flux critique bout-en-bout, mais chaque exécution laisse un résidu
 * QA_AUDIT_ non nettoyable automatiquement : l'email et le nom d'organisation
 * sont préfixés/marqués QA_AUDIT_ pour rester identifiables et pouvoir être
 * purgés manuellement (DB) si besoin. Ne pas lancer ce test en boucle.
 */
import { test, expect } from "./fixtures";

test.describe("Inscription — création d'organisation", () => {
  // Validation cliente pure (pas d'appel réseau) : mots de passe différents.
  test("mots de passe différents affichent une erreur sans appeler le backend", async ({ page }) => {
    await page.goto("/register");

    const unique = Date.now();
    await page.getByLabel("Nom de l'organisation").fill(`QA_AUDIT_Org_NoOp_${unique}`);
    await page.getByLabel("Prénom").fill("QA_AUDIT_Prenom");
    await page.getByLabel("Nom", { exact: true }).fill("QA_AUDIT_Nom");
    await page.getByLabel("Adresse email").fill(`qa-audit-register-noop-${unique}@test.local`);
    await page.getByLabel("Mot de passe", { exact: true }).fill("MotDePasse123!");
    await page.getByLabel("Confirmer le mot de passe").fill("AutreMotDePasse456!");

    await page.getByRole("button", { name: /Créer mon organisation/i }).click();

    await expect(page.getByText("Les mots de passe ne correspondent pas.")).toBeVisible();
    // On reste bien sur le formulaire (pas de message de succès).
    await expect(page.getByText(/Organisation créée/i)).toHaveCount(0);
  });

  // Flux nominal : crée réellement un compte + une organisation en prod.
  // Voir le commentaire de tête de fichier pour la limite de nettoyage.
  test("un formulaire valide crée l'organisation et affiche le message de succès", async ({ page }) => {
    await page.goto("/register");

    const unique = Date.now();
    const email = `qa-audit-register-${unique}@test.local`;
    const orgName = `QA_AUDIT_Org_${unique}`;

    await page.getByLabel("Nom de l'organisation").fill(orgName);
    await page.getByLabel("Prénom").fill("QA_AUDIT_Prenom");
    await page.getByLabel("Nom", { exact: true }).fill("QA_AUDIT_Nom");
    await page.getByLabel("Adresse email").fill(email);
    await page.getByLabel("Mot de passe", { exact: true }).fill("MotDePasseQA123!");
    await page.getByLabel("Confirmer le mot de passe").fill("MotDePasseQA123!");

    await page.getByRole("button", { name: /Créer mon organisation/i }).click();

    await expect(page.getByText(/Organisation créée/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByRole("link", { name: "connectez-vous" })).toBeVisible();
  });
});
