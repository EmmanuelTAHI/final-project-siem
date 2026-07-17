/**
 * Tests E2E de la page Organisations — vue plateforme
 * (frontend/src/app/(dashboard)/platform/organizations/page.tsx).
 * Contre la prod https://logplus.duckdns.org (voir playwright.config.ts).
 *
 * IMPORTANT sécurité : cette page n'a AUCUN bouton de modification/suppression
 * (lecture seule par construction — seul un expand/collapse par organisation).
 * Avec platformSuperuser (compte réel emmanueltahi14@gmail.com), on se
 * contente donc de vérifier le chargement et l'affichage, sans jamais
 * modifier l'état d'aucune organisation.
 */
import { test, expect } from "./fixtures";

test.describe("Plateforme — Organisations", () => {
  test("platformSuperuser : la vue cross-org charge et affiche la liste des organisations (lecture seule)", async ({
    page,
    authAs,
  }) => {
    await authAs("platformSuperuser");
    await page.goto("/platform/organizations");

    await expect(page.getByRole("heading", { name: "Organisations — vue plateforme" })).toBeVisible();

    // KPIs cross-org
    await expect(page.getByText("Organisations actives")).toBeVisible();
    await expect(page.getByText("Staff plateforme")).toBeVisible();

    // Au moins une organisation listée (l'org A "Log+ (Legacy)" existe en prod).
    // On filtre sur "· plan" (texte unique aux cartes org, absent des cartes KPI
    // qui partagent la même classe .rounded-xl.border) pour éviter de matcher
    // les tuiles de statistiques en haut de page.
    const orgRows = page.locator(".rounded-xl.border").filter({ hasText: "· plan" });
    await expect(orgRows.first()).toBeVisible();

    // Expand en lecture seule : affiche les stats détaillées de la 1ère org, sans aucune action de mutation.
    await orgRows.first().getByRole("button").click();
    await expect(orgRows.first().getByText("Connecteurs actifs")).toBeVisible();
  });

  test("adminA : l'accès à /platform/organizations est refusé côté client (redirection, pas de crash)", async ({
    page,
    authAs,
  }) => {
    await authAs("adminA");
    await page.goto("/platform/organizations");

    // PlatformOrganizationsPage redirige côté client (router.replace("/dashboard"))
    // dès que _hasHydrated && !user?.is_superuser. On tolère un court affichage
    // du message "Accès réservé..." avant la redirection effective.
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 });

    // Aucune donnée cross-org n'a fuité avant la redirection.
    await expect(page.getByText("Organisations — vue plateforme")).not.toBeVisible();
  });
});
