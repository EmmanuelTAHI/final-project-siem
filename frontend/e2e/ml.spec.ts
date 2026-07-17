/**
 * Tests E2E de la page ML (frontend/src/app/(dashboard)/ml/page.tsx).
 * Contre la prod https://logplus.duckdns.org.
 *
 * L'entraînement (POST /api/ml/train/) est asynchrone côté Celery : on
 * vérifie uniquement que la requête part bien au clic, sans attendre la fin
 * réelle de l'entraînement.
 */
import { test, expect } from "./fixtures";

test.describe("Machine Learning", () => {
  test("affiche le header et la carte de statut du modèle", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/ml");

    await expect(page.getByRole("heading", { name: "Machine Learning" })).toBeVisible();
    await expect(page.getByText("Détection d'anomalies par Isolation Forest")).toBeVisible();
    await expect(page.getByText("Précision")).toBeVisible();
    await expect(page.getByText("F1-Score")).toBeVisible();
    await expect(page.getByText("Recall")).toBeVisible();
  });

  test("affiche les charts de distribution des scores et le résumé des prédictions", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/ml");

    await expect(page.getByText("Distribution des scores d'anomalie")).toBeVisible();
    await expect(page.getByText("Résumé des prédictions")).toBeVisible();
    await expect(page.getByText("Anomalies récentes détectées")).toBeVisible();
  });

  test("le slider de contamination met à jour le libellé affiché", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/ml");

    await expect(page.getByText("Contamination: 5%")).toBeVisible();
    const slider = page.locator('input[type="range"]');
    await slider.fill("10");
    await expect(page.getByText("Contamination: 10%")).toBeVisible();

    // Remise à la valeur par défaut.
    await slider.fill("5");
  });

  test("clic sur Lancer l'entraînement déclenche bien le POST /api/ml/train/", async ({ page, authAs }) => {
    await authAs("adminA");
    await page.goto("/ml");

    const trainBtn = page.getByRole("button", { name: /Lancer l'entraînement/ });
    await expect(trainBtn).toBeVisible();
    await expect(trainBtn).toBeEnabled();

    const [request] = await Promise.all([
      page.waitForRequest(
        (req) => req.url().includes("/api/ml/train/") && req.method() === "POST"
      ),
      trainBtn.click(),
    ]);

    expect(request.url()).toContain("/api/ml/train/");
    const postData = request.postDataJSON();
    expect(postData).toHaveProperty("contamination");

    // On ne vérifie pas la fin de l'entraînement (asynchrone Celery) : le
    // bouton passe simplement en "Entraînement..." pendant que la requête
    // reste en vol côté hook.
    await expect(page.getByRole("button", { name: /Entraînement\.\.\./ })).toBeVisible({ timeout: 5_000 });
  });
});
