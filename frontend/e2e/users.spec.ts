/**
 * Tests E2E de la page Utilisateurs (frontend/src/app/(dashboard)/users/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir playwright.config.ts).
 *
 * IMPORTANT sécurité : ce fichier ne crée/modifie/supprime QUE des comptes
 * créés par le test lui-même (préfixe QA_AUDIT_ dans le prénom, email
 * qa-audit-user-<timestamp>@test.local). Il ne touche JAMAIS aux comptes
 * qa-admin-a / qa-analyst-a / qa-viewer-a / qa-admin-b / qa-analyst-b ni au
 * compte réel emmanueltahi14@gmail.com.
 *
 * Limite notée sur le rôle viewer : ni UsersPage (users/page.tsx) ni le
 * Sidebar (components/layout/sidebar.tsx) n'ont de logique conditionnelle
 * basée sur le rôle pour /users — le lien "Utilisateurs" et les boutons
 * créer/modifier/supprimer sont rendus pour tout utilisateur authentifié,
 * quel que soit son rôle. On documente donc le comportement réel plutôt que
 * de deviner une restriction non codée : on vérifie juste l'absence de crash
 * et la visibilité effective des contrôles pour viewerA, sans jamais cliquer
 * dessus avec ce compte (pour ne pas dépendre d'une éventuelle restriction
 * uniquement côté API qui romprait le test).
 */
import { test, expect } from "./fixtures";
import { qaName } from "./utils/api";

test.describe("Utilisateurs", () => {
  test.afterEach(async ({ apiAs }) => {
    const api = await apiAs("adminA");
    await api.deleteUsersMatchingPrefix();
  });

  test("créer, modifier puis supprimer un utilisateur QA_AUDIT via l'UI", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/users");

    const firstName = qaName("user");
    const email = `qa-audit-user-${Date.now()}@test.local`;

    // Création
    await page.getByRole("button", { name: "Nouvel utilisateur" }).click();
    await expect(page.getByRole("heading", { name: "Nouvel utilisateur" })).toBeVisible();

    await page.getByPlaceholder("Jean").fill(firstName);
    await page.getByPlaceholder("Dupont").fill("E2E");
    await page.getByPlaceholder("jean.dupont@example.com").fill(email);
    await page.getByPlaceholder("••••••••").fill("TestQA123!");

    await page.getByRole("button", { name: "Créer le compte" }).click();
    await expect(page.getByText("Utilisateur créé")).toBeVisible();

    const row = page.locator("tr").filter({ hasText: email });
    await expect(row).toBeVisible();
    await expect(row.getByText(firstName, { exact: false })).toBeVisible();

    // Modification (prénom -> ajoute un suffixe, reste préfixé QA_AUDIT_)
    await row.getByRole("button").nth(0).click(); // bouton Edit (icône seule)
    await expect(page.getByRole("heading", { name: "Modifier l'utilisateur" })).toBeVisible();
    const updatedFirstName = `${firstName}_edited`;
    await page.getByPlaceholder("Jean").fill(updatedFirstName);
    await page.getByRole("button", { name: "Mettre à jour" }).click();
    await expect(page.getByText("Utilisateur mis à jour")).toBeVisible();

    const updatedRow = page.locator("tr").filter({ hasText: email });
    await expect(updatedRow.getByText(updatedFirstName, { exact: false })).toBeVisible();

    // Suppression via ConfirmDialog (composant partagé components/ui/confirm-dialog.tsx)
    await updatedRow.getByRole("button").nth(1).click(); // bouton Trash (icône seule)
    await expect(page.getByRole("heading", { name: "Supprimer l'utilisateur" })).toBeVisible();
    await page.getByRole("button", { name: "Supprimer", exact: true }).click();
    await expect(page.getByText("Utilisateur supprimé")).toBeVisible();
    await expect(page.locator("tr").filter({ hasText: email })).not.toBeVisible();
  });

  test("viewerA : accès à /users sans crash, contrôles observés en lecture seule", async ({ page, authAs }) => {
    await authAs("viewerA");
    await page.goto("/users");

    // La page charge sans erreur JS et affiche bien le tableau utilisateurs.
    await expect(page.getByRole("heading", { name: "Gestion des utilisateurs" })).toBeVisible();

    // NOTE : voir le commentaire d'en-tête — aucune restriction RBAC
    // frontend n'existe sur cette page. On documente que le bouton reste
    // visible plutôt que de supposer une restriction non implémentée.
    await expect(page.getByRole("button", { name: "Nouvel utilisateur" })).toBeVisible();

    // On ne clique volontairement sur aucune action créer/modifier/supprimer
    // avec ce compte : le but est uniquement de documenter l'absence de
    // garde-fou visuel, pas d'exercer une suppression avec un rôle restreint.
  });
});
