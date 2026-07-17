/**
 * Fixture Playwright partagée par tous les fichiers e2e/*.spec.ts.
 *
 * Fournit `authAs(key)` : connecte silencieusement le contexte de navigateur
 * courant en tant que l'un des comptes QA (voir e2e/utils/auth.ts), en
 * contournant l'UI de login (injection localStorage). À appeler AVANT tout
 * `page.goto()` vers une route protégée.
 *
 * Fournit aussi `apiAs(key)` : un client API léger (voir e2e/utils/api.ts)
 * authentifié avec les mêmes tokens, pratique pour le nettoyage
 * (afterEach/afterAll) des ressources QA_AUDIT_* créées pendant un test,
 * sans dépendre de l'UI qui vient d'être exercée.
 */
import { test as base, expect } from "@playwright/test";
import { loginAndGetTokens, injectAuthState, TEST_ACCOUNTS, type AccountKey, type AuthResult } from "./utils/auth";
import { ApiClient } from "./utils/api";

type Fixtures = {
  authAs: (key: AccountKey) => Promise<AuthResult>;
  apiAs: (key: AccountKey) => Promise<ApiClient>;
};

export const test = base.extend<Fixtures>({
  // eslint-disable-next-line no-empty-pattern
  authAs: async ({ request, context }, use) => {
    const cache = new Map<AccountKey, AuthResult>();
    await use(async (key: AccountKey) => {
      let auth = cache.get(key);
      if (!auth) {
        auth = await loginAndGetTokens(request, TEST_ACCOUNTS[key]);
        cache.set(key, auth);
      }
      await injectAuthState(context, auth);
      return auth;
    });
  },

  apiAs: async ({ request }, use) => {
    const cache = new Map<AccountKey, ApiClient>();
    await use(async (key: AccountKey) => {
      let client = cache.get(key);
      if (!client) {
        const auth = await loginAndGetTokens(request, TEST_ACCOUNTS[key]);
        client = new ApiClient(request, auth.access);
        cache.set(key, client);
      }
      return client;
    });
  },
});

export { expect };
