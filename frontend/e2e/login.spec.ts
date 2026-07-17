/**
 * Test canary du vrai flux de login UI (frontend/src/app/(auth)/login/page.tsx).
 *
 * On ne peut PAS terminer un login réel via l'UI dans cette suite : l'OTP à 6
 * chiffres envoyé par email n'est lisible que côté serveur (Redis, SSH), pas
 * depuis Playwright. Ce fichier vérifie donc uniquement :
 *   - le cas credentials invalides (message d'erreur, on reste à l'étape 1),
 *   - le cas credentials valides -> passage à l'écran OTP, avec les bons
 *     éléments : 6 cases de saisie, bouton "Renvoyer le code" avec cooldown,
 *     bouton "Retour", texte d'expiration.
 * Tous les autres tests (dashboard, alerts, etc.) contournent cette UI via
 * e2e/utils/auth.ts (injection localStorage) — voir e2e/README.md.
 */
import { test, expect } from "@playwright/test";
import { TEST_ACCOUNTS } from "./utils/auth";

test.describe("Login — flux UI réel (canary)", () => {
  test("credentials invalides affichent un message d'erreur et restent sur l'étape 1", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email").fill("qa-admin-a@test.local");
    await page.locator('input[type="password"]').fill("MotDePasseCompletementFaux!23");
    await page.getByRole("button", { name: /Continuer/i }).click();

    // Reste bien sur l'étape credentials (pas de champ OTP visible)
    await expect(page.getByRole("heading", { name: "Connexion" }).or(page.getByText("Connexion"))).toBeVisible();
    await expect(page.getByText(/Email ou mot de passe incorrect|serveur/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("input.otp-box")).toHaveCount(0);
  });

  test("credentials valides affichent l'écran OTP avec les bons éléments", async ({ page }) => {
    const account = TEST_ACCOUNTS.adminA;
    await page.goto("/login");

    await page.getByLabel("Email").fill(account.email);
    await page.locator('input[type="password"]').fill(account.password);
    await page.getByRole("button", { name: /Continuer/i }).click();

    // Écran OTP : titre, description avec l'email, 6 cases, bouton renvoyer,
    // bouton retour, mention d'expiration.
    await expect(page.getByText("Code de vérification")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(account.email)).toBeVisible();

    const otpBoxes = page.locator("input.otp-box");
    await expect(otpBoxes).toHaveCount(6);

    await expect(page.getByRole("button", { name: /Retour/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Renvoyer le code/i })).toBeVisible();
    // Juste après l'envoi, le cooldown de 60s est actif : le bouton est désactivé.
    await expect(page.getByRole("button", { name: /Renvoyer le code/i })).toBeDisabled();
    await expect(page.getByText(/expire dans/i)).toBeVisible();

    // Bouton de soumission désactivé tant que les 6 chiffres ne sont pas saisis.
    await expect(page.getByRole("button", { name: /Se connecter/i })).toBeDisabled();

    // On ne peut pas aller plus loin (pas d'accès à l'OTP réel) : retour pour
    // ne pas laisser de session OTP entamée qui gênerait un run suivant.
    await page.getByRole("button", { name: /Retour/i }).click();
    await expect(page.getByText("Connexion")).toBeVisible();
  });
});
