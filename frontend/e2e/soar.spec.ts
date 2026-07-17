/**
 * Tests E2E de la page SOAR (frontend/src/app/(dashboard)/soar/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir playwright.config.ts).
 *
 * Limite notée : le bouton toggle et le bouton delete de chaque playbook sont
 * des icônes sans texte accessible (ghost Button avec juste un <svg>), donc on
 * les cible en scopant sur la carte du playbook (filtrée par nom unique
 * QA_AUDIT_) puis en prenant le n-ième bouton de cette carte plutôt que par
 * un nom de rôle. La suppression déclenche `window.confirm("Supprimer ce
 * playbook ?")` (pas le composant ConfirmDialog) — géré via l'event "dialog".
 */
import { test, expect } from "./fixtures";
import { qaName } from "./utils/api";

test.describe("SOAR", () => {
  test.afterEach(async ({ apiAs }) => {
    // Filet de sécurité si l'UI n'a pas nettoyé (échec en cours de test).
    const api = await apiAs("adminA");
    await api.deletePlaybooksMatchingPrefix();
  });

  test("créer un playbook QA_AUDIT, le toggler puis le supprimer via l'UI", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/soar");

    const playbookName = qaName("playbook");

    // Ouvre la dialog de création
    await page.getByRole("button", { name: "Nouveau Playbook" }).click();
    await expect(page.getByRole("heading", { name: "Nouveau Playbook SOAR" })).toBeVisible();

    // Nom (obligatoire)
    await page.getByPlaceholder("Ex: Blocage brute force critique").fill(playbookName);
    // Description (facultative)
    await page.getByPlaceholder("Décrivez l'objectif de ce playbook…").fill("Créé par la suite E2E QA_AUDIT");

    // Change le type de déclencheur (Select custom) vers "Règle de corrélation"
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "Règle de corrélation" }).click();

    // Charge un modèle d'action ("Bloquer l'IP source") pour remplir le JSON actions
    await page.getByRole("button", { name: "Bloquer l'IP source" }).click();

    // Crée le playbook
    await page.getByRole("button", { name: "Créer le playbook" }).click();

    // Apparaît dans la liste, avec son badge de déclencheur et le statut actif (créé is_active:true)
    const card = page.locator(".rounded-lg.border").filter({ hasText: playbookName });
    await expect(card).toBeVisible();
    await expect(card.getByText("Règle de corrélation")).toBeVisible();
    await expect(card.locator("span.bg-green-500")).toBeVisible();

    // Toggle : is_active passe à false -> le point devient gris
    await card.getByRole("button").nth(0).click();
    await expect(card.locator("span.bg-gray-500")).toBeVisible();

    // Suppression via l'UI : déclenche window.confirm("Supprimer ce playbook ?")
    page.once("dialog", (dialog) => dialog.accept());
    await card.getByRole("button").nth(1).click();
    await expect(page.getByText(playbookName)).not.toBeVisible();
  });

  test("le formulaire de création refuse un JSON invalide dans conditions/actions", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/soar");

    await page.getByRole("button", { name: "Nouveau Playbook" }).click();
    await page.getByPlaceholder("Ex: Blocage brute force critique").fill(qaName("playbook-invalid"));

    // Casse le JSON des conditions
    const conditionsTextarea = page.locator("textarea").first();
    await conditionsTextarea.fill("{ceci n'est pas du json}");

    await page.getByRole("button", { name: "Créer le playbook" }).click();

    // Toast d'erreur explicite, aucune requête réseau de création envoyée
    await expect(page.getByText("JSON invalide dans les conditions ou actions")).toBeVisible();
    // La dialog reste ouverte (pas de fermeture sur erreur de parsing)
    await expect(page.getByRole("heading", { name: "Nouveau Playbook SOAR" })).toBeVisible();
  });
});
