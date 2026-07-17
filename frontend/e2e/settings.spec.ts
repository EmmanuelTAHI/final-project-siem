/**
 * Tests E2E de la page Paramètres (frontend/src/app/(dashboard)/settings/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir playwright.config.ts).
 *
 * Toujours exécuté sur analystA (jamais adminA ni platformSuperuser, pour
 * limiter le risque) et toujours remis dans l'état d'origine en fin de test
 * (valeur lue au préalable via `apiAs("analystA").get("/api/users/me/")`).
 *
 * Les onglets sont des <div role="button"> (pas de <button> HTML natif),
 * donc `getByRole("button", { name: <label> })` fonctionne malgré tout grâce
 * au role explicite. Les toggles de préférences sont des <div role="switch">
 * sans texte propre : on les repère par leur ordre d'apparition dans la carte
 * "Notifications" (email, alertes critiques, rapport hebdo — dans cet ordre
 * dans le JSX).
 */
import { test, expect } from "./fixtures";

test.describe("Paramètres", () => {
  test("onglet Profil : modifie le prénom puis le remet à sa valeur d'origine", async ({ page, authAs, apiAs }) => {
    const api = await apiAs("analystA");
    const before = await api.get<{ first_name: string }>("/api/users/me/");
    const originalFirstName = before.first_name;

    await authAs("analystA");
    await page.goto("/settings");

    await expect(page.getByRole("button", { name: "Profil" })).toBeVisible();

    const tempName = `QA_AUDIT_settings_${Date.now()}`;
    const firstNameInput = page.getByPlaceholder("Prénom");
    await firstNameInput.fill(tempName);
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Profil mis à jour")).toBeVisible();
    await expect(firstNameInput).toHaveValue(tempName);

    // Remise en état
    await firstNameInput.fill(originalFirstName);
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Profil mis à jour")).toBeVisible();

    const after = await api.get<{ first_name: string }>("/api/users/me/");
    expect(after.first_name).toBe(originalFirstName);
  });

  test("onglet Sécurité : liste les sessions actives sans jamais révoquer la session courante", async ({
    page,
    authAs,
  }) => {
    await authAs("analystA");
    await page.goto("/settings?tab=security");

    await expect(page.getByRole("button", { name: "Sécurité" })).toBeVisible();
    await expect(page.getByText("Sessions actives")).toBeVisible();

    // La session courante affiche le chip "Vous" et n'a pas de bouton "Déconnecter"
    // (voir settings/page.tsx : `s.current ? <span className="chip">Vous</span> : <button>Déconnecter</button>`).
    const currentSessionRow = page.locator("tr").filter({ hasText: "Actuelle" });
    await expect(currentSessionRow).toBeVisible();
    await expect(currentSessionRow.getByText("Vous")).toBeVisible();
    await expect(currentSessionRow.getByRole("button", { name: "Déconnecter" })).toHaveCount(0);

    // On ne clique volontairement sur aucun bouton "Déconnecter" des autres
    // lignes (le cas échéant) pour ne pas perturber d'autres sessions QA en cours.
  });

  test("onglet Préférences : bascule le thème clair/sombre sans casser l'UI", async ({ page, authAs }) => {
    await authAs("analystA");
    await page.goto("/settings?tab=preferences");

    await expect(page.getByRole("button", { name: "Préférences" })).toBeVisible();
    await expect(page.getByText("Apparence")).toBeVisible();

    const html = page.locator("html");
    const originalTheme = (await html.getAttribute("class"))?.includes("dark") ? "dark" : "light";
    const otherTheme = originalTheme === "dark" ? "light" : "dark";
    const otherLabel = otherTheme === "dark" ? "Mode sombre" : "Mode clair";
    const originalLabel = originalTheme === "dark" ? "Mode sombre" : "Mode clair";

    // Bascule vers l'autre thème
    await page.getByRole("button", { name: otherLabel }).click();
    await expect(page.getByText("Apparence")).toBeVisible(); // pas de crash après le changement

    // Revenir au thème d'origine
    await page.getByRole("button", { name: originalLabel }).click();
    await expect(page.getByText("Apparence")).toBeVisible();
  });

  test("onglet Préférences : bascule les 3 notifications puis remet l'état d'origine", async ({
    page,
    authAs,
    apiAs,
  }) => {
    const api = await apiAs("analystA");
    const before = await api.get<{
      email_notifications: boolean;
      critical_alert_emails: boolean;
      weekly_report_email: boolean;
    }>("/api/users/me/");

    await authAs("analystA");
    await page.goto("/settings?tab=preferences");
    await expect(page.getByText("Notifications")).toBeVisible();

    // Ordre dans le JSX : email, alertes critiques, rapport hebdomadaire.
    const switches = page.getByRole("switch");
    await expect(switches).toHaveCount(3);

    // Bascule les 3, en vérifiant qu'aucune erreur de sauvegarde ne survient.
    for (let i = 0; i < 3; i++) {
      await switches.nth(i).click();
    }
    await expect(page.getByText("Erreur lors de l'enregistrement de la préférence")).not.toBeVisible();

    // Remise en état : re-toggle pour revenir à l'état d'origine lu avant le test.
    for (let i = 0; i < 3; i++) {
      await switches.nth(i).click();
    }
    await expect(page.getByText("Erreur lors de l'enregistrement de la préférence")).not.toBeVisible();

    const after = await api.get<{
      email_notifications: boolean;
      critical_alert_emails: boolean;
      weekly_report_email: boolean;
    }>("/api/users/me/");
    expect(after.email_notifications).toBe(before.email_notifications);
    expect(after.critical_alert_emails).toBe(before.critical_alert_emails);
    expect(after.weekly_report_email).toBe(before.weekly_report_email);
  });
});
