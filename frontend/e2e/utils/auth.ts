/**
 * Authentification pour la suite E2E Playwright.
 *
 * Le vrai flux de login (frontend/src/app/(auth)/login/page.tsx) est en 2
 * étapes : email+password -> pre_auth_token, puis OTP à 6 chiffres envoyé par
 * email -> access/refresh JWT (frontend/src/lib/api.ts, authApi.login /
 * authApi.verifyOtp). Pour les comptes @test.local, aucun vrai email n'est
 * envoyé : l'OTP n'existe que dans le cache Redis du backend, accessible
 * uniquement par SSH côté serveur — donc PAS depuis cette suite Playwright.
 *
 * Convention adoptée ici (voir e2e/README.md) :
 *
 *   1. Un seul test canary (e2e/login.spec.ts) exerce le vrai flux UI
 *      jusqu'à l'écran OTP puis s'arrête là (on ne peut pas lire le code).
 *
 *   2. Tous les autres tests contournent l'UI de login : `loginAndGetTokens`
 *      retourne une paire access/refresh valide, obtenue de deux façons
 *      possibles (dans cet ordre de préférence) :
 *
 *      a. Si `E2E_OTP_BYPASS` est définie dans l'environnement, on tente le
 *         flux complet login -> verify-otp en utilisant cette valeur comme
 *         code OTP. Ceci suppose que le backend expose, dans un mode debug
 *         non-prod, un OTP fixe/prévisible — recherche effectuée dans
 *         backend/apps/authentication/views.py (LoginView, VerifyOtp...) :
 *         AUCUN comportement `if settings.DEBUG: response['otp_debug'] = ...`
 *         n'existe dans le code actuel. Cette branche est donc du code mort
 *         tant que le backend n'expose pas un tel bypass — elle ne doit pas
 *         être activée sur la prod réelle, et n'échouera jamais silencieusement
 *         (elle lève une erreur explicite si le call verify-otp échoue).
 *
 *      b. Sinon (cas par défaut en prod), on lit des JWT déjà obtenus par un
 *         autre moyen (ex: un script pytest côté backend qui a lui accès à
 *         Redis) et stockés dans `.env.test` sous les noms
 *         `QA_<ROLE>_<ORG>_ACCESS_TOKEN` / `_REFRESH_TOKEN` (voir la liste
 *         `TEST_ACCOUNTS` ci-dessous et .env.test.example à la racine de
 *         frontend/). L'access token JWT ne vit que 15 minutes : avant
 *         chaque run, on vérifie sa validité via GET /api/users/me/, et s'il
 *         est expiré/absent on rafraîchit via POST /api/auth/token/refresh/
 *         avec le refresh token (valide 7 jours).
 *
 * Une fois les tokens obtenus, `injectAuthState` les pose dans
 * localStorage AVANT toute navigation vers une page protégée, avec le même
 * format que celui utilisé par le store zustand persistant
 * (frontend/src/stores/auth-store.ts) :
 *   - clé "access_token" / "refresh_token" (lues par l'intercepteur axios)
 *   - clé "logplus-auth" (lue par zustand persist), au format
 *     { state: { user, accessToken, refreshToken, isAuthenticated: true },
 *       version: 0 }
 */

import type { APIRequestContext, BrowserContext, Page } from "@playwright/test";

// ─── Comptes QA connus (voir contexte de la tâche) ─────────────────────────

export type AccountKey =
  | "platformSuperuser"
  | "adminA"
  | "analystA"
  | "viewerA"
  | "adminB"
  | "analystB";

export interface TestAccount {
  email: string;
  password: string;
  /** Préfixe des variables d'env contenant les tokens pré-obtenus. */
  envPrefix: string;
  /** true pour le compte réel du propriétaire — jamais d'action destructive. */
  readOnly?: boolean;
}

export const TEST_ACCOUNTS: Record<AccountKey, TestAccount> = {
  // Compte réel du propriétaire de la plateforme. Lecture seule uniquement :
  // ne jamais changer son mot de passe/email, ne jamais le supprimer, ne
  // jamais déconnecter toutes ses sessions.
  platformSuperuser: {
    email: "emmanueltahi14@gmail.com",
    password: "TestAdmin123!",
    envPrefix: "QA_SUPERUSER",
    readOnly: true,
  },
  // Org A ("Log+ (Legacy)") — compte principal pour la majorité des tests
  // E2E (création/suppression de ressources QA_AUDIT_*).
  adminA: {
    email: "qa-admin-a@test.local",
    password: "TestQA123!",
    envPrefix: "QA_ADMIN_A",
  },
  analystA: {
    email: "qa-analyst-a@test.local",
    password: "TestQA123!",
    envPrefix: "QA_ANALYST_A",
  },
  viewerA: {
    email: "qa-viewer-a@test.local",
    password: "TestQA123!",
    envPrefix: "QA_VIEWER_A",
  },
  // Org B ("QA Test Org B") — utile pour vérifier la non-visibilité cross-org.
  adminB: {
    email: "qa-admin-b@test.local",
    password: "TestQA123!",
    envPrefix: "QA_ADMIN_B",
  },
  analystB: {
    email: "qa-analyst-b@test.local",
    password: "TestQA123!",
    envPrefix: "QA_ANALYST_B",
  },
};

export interface AuthResult {
  access: string;
  refresh: string;
  user: Record<string, unknown>;
}

function baseURLFromEnv(): string {
  return process.env.E2E_BASE_URL || "https://logplus.duckdns.org";
}

function unwrap<T>(data: unknown): T {
  if (data && typeof data === "object" && "data" in (data as Record<string, unknown>)) {
    return (data as { data: T }).data;
  }
  return data as T;
}

/**
 * Tentative de login complet via le bypass OTP optionnel (E2E_OTP_BYPASS).
 * Ne fait rien (retourne null) si la variable n'est pas définie. Si elle est
 * définie mais que le backend refuse le code, lève une erreur explicite
 * plutôt que d'échouer silencieusement.
 */
async function tryOtpBypassLogin(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<AuthResult | null> {
  const otpBypass = process.env.E2E_OTP_BYPASS;
  if (!otpBypass) return null;

  const base = baseURLFromEnv();
  const loginRes = await request.post(`${base}/api/auth/login/`, {
    data: { email, password },
  });
  if (!loginRes.ok()) {
    throw new Error(
      `E2E_OTP_BYPASS défini mais le login credentials a échoué pour ${email} (${loginRes.status()}). ` +
        `Vérifiez le mot de passe ou retirez E2E_OTP_BYPASS pour retomber sur les tokens .env.test.`
    );
  }
  const loginBody = unwrap<{ pre_auth_token: string }>(await loginRes.json());

  const otpRes = await request.post(`${base}/api/auth/verify-otp/`, {
    data: { otp: otpBypass, pre_auth_token: loginBody.pre_auth_token },
  });
  if (!otpRes.ok()) {
    throw new Error(
      `E2E_OTP_BYPASS défini (valeur="${otpBypass}") mais verify-otp a été rejeté pour ${email} ` +
        `(${otpRes.status()}). Le backend n'expose probablement pas de code OTP fixe/prévisible — ` +
        `retirez E2E_OTP_BYPASS et utilisez la convention .env.test à la place.`
    );
  }
  const otpBody = unwrap<{ access_token: string; refresh_token: string; user: Record<string, unknown> }>(
    await otpRes.json()
  );
  return { access: otpBody.access_token, refresh: otpBody.refresh_token, user: otpBody.user };
}

/** Vérifie qu'un access token est encore valide en appelant /api/users/me/. */
async function isAccessTokenValid(request: APIRequestContext, accessToken: string): Promise<boolean> {
  const base = baseURLFromEnv();
  const res = await request.get(`${base}/api/users/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    failOnStatusCode: false,
  });
  return res.ok();
}

/** Rafraîchit un access token expiré à partir du refresh token (valide 7 jours). */
async function refreshAccessToken(
  request: APIRequestContext,
  refreshToken: string
): Promise<{ access: string; refresh: string }> {
  const base = baseURLFromEnv();
  const res = await request.post(`${base}/api/auth/token/refresh/`, {
    data: { refresh: refreshToken },
  });
  if (!res.ok()) {
    throw new Error(
      `Impossible de rafraîchir le token (${res.status()}). Le refresh_token stocké dans .env.test ` +
        `est probablement expiré (7 jours) ou révoqué — il faut en régénérer un côté pytest/SSH et ` +
        `mettre à jour .env.test.`
    );
  }
  const body = unwrap<{ access_token?: string; access?: string; refresh_token?: string; refresh?: string }>(
    await res.json()
  );
  return {
    access: body.access_token ?? body.access ?? "",
    refresh: body.refresh_token ?? body.refresh ?? refreshToken,
  };
}

/**
 * Point d'entrée principal : retourne des tokens JWT valides + l'utilisateur
 * courant pour le compte demandé, sans jamais passer par l'UI de login.
 *
 * Ordre de résolution :
 *   1. E2E_OTP_BYPASS (si défini) — flux complet login+otp.
 *   2. Sinon : QA_<PREFIX>_ACCESS_TOKEN / QA_<PREFIX>_REFRESH_TOKEN dans
 *      .env.test, avec refresh automatique si l'access token est expiré.
 */
export async function loginAndGetTokens(
  request: APIRequestContext,
  account: TestAccount
): Promise<AuthResult> {
  const bypassResult = await tryOtpBypassLogin(request, account.email, account.password);
  if (bypassResult) return bypassResult;

  const accessEnvKey = `${account.envPrefix}_ACCESS_TOKEN`;
  const refreshEnvKey = `${account.envPrefix}_REFRESH_TOKEN`;
  const storedAccess = process.env[accessEnvKey];
  const storedRefresh = process.env[refreshEnvKey];

  if (!storedRefresh) {
    throw new Error(
      `Aucun token disponible pour ${account.email}. Définissez ${accessEnvKey} et ${refreshEnvKey} ` +
        `dans .env.test (voir .env.test.example), ou E2E_OTP_BYPASS si le backend expose un OTP de test. ` +
        `Ces tokens ne peuvent pas être obtenus depuis Playwright seul car l'OTP réel n'est visible que ` +
        `côté serveur (Redis, via SSH).`
    );
  }

  let access = storedAccess;
  let refresh = storedRefresh;

  if (!access || !(await isAccessTokenValid(request, access))) {
    const refreshed = await refreshAccessToken(request, refresh);
    access = refreshed.access;
    refresh = refreshed.refresh;
  }

  const base = baseURLFromEnv();
  const meRes = await request.get(`${base}/api/users/me/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const user = unwrap<Record<string, unknown>>(await meRes.json());

  return { access, refresh, user };
}

/** Sucre pour appeler loginAndGetTokens directement avec une AccountKey. */
export async function loginAs(request: APIRequestContext, key: AccountKey): Promise<AuthResult> {
  return loginAndGetTokens(request, TEST_ACCOUNTS[key]);
}

/**
 * Injecte l'état d'authentification dans localStorage AVANT toute navigation,
 * en reproduisant exactement ce que fait useAuthStore.setAuth() côté client
 * (frontend/src/stores/auth-store.ts) : les clés brutes "access_token" /
 * "refresh_token" (lues par l'intercepteur axios), et la clé zustand-persist
 * "logplus-auth" (lue par le layout dashboard pour isAuthenticated/_hasHydrated).
 *
 * Utilise `context.addInitScript` : fonctionne pour toute page ouverte dans
 * ce BrowserContext, y compris après un reload.
 */
export async function injectAuthState(
  contextOrPage: BrowserContext | Page,
  auth: AuthResult
): Promise<void> {
  const persisted = JSON.stringify({
    state: {
      user: auth.user,
      accessToken: auth.access,
      refreshToken: auth.refresh,
      isAuthenticated: true,
    },
    version: 0,
  });

  await contextOrPage.addInitScript(
    ({ access, refresh, persistedState }) => {
      window.localStorage.setItem("access_token", access);
      window.localStorage.setItem("refresh_token", refresh);
      window.localStorage.setItem("logplus-auth", persistedState);
    },
    { access: auth.access, refresh: auth.refresh, persistedState: persisted }
  );
}
