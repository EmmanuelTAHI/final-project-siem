# Suite E2E Playwright — Log+ (test direct sur la production)

Cette suite exécute des tests Playwright **directement contre le VPS de
production** https://logplus.duckdns.org. Il n'existe pas d'environnement de
staging distinct pour ce projet ; le propriétaire de la plateforme a validé
explicitement ce mode de test.

## Prérequis

```bash
cd frontend
npm install
npx playwright install chromium   # télécharge le navigateur (une seule fois)
```

Le domaine `logplus.duckdns.org` doit être résolvable/joignable depuis la
machine qui lance les tests (DNS correct, pas de VPN qui bloque l'accès...).
Vérifiez avec :

```bash
curl -I https://logplus.duckdns.org
```

Si cette commande échoue, ce n'est pas un problème de la suite — corrigez
d'abord votre réseau/DNS local.

## Authentification — pourquoi c'est particulier ici

Le vrai login (`/login`) est un flux à 2 étapes avec OTP par email :
email+password → `pre_auth_token`, puis code à 6 chiffres → JWT. Pour les
comptes de test `@test.local`, **aucun email n'est réellement envoyé** —
l'OTP n'existe que dans le cache Redis du backend, qu'on ne peut lire que par
SSH côté serveur. Playwright, exécuté depuis un poste client, n'y a pas
accès.

Convention adoptée :

1. **`e2e/login.spec.ts`** est le seul fichier qui exerce le vrai flux UI. Il
   s'arrête à l'écran OTP (vérifie que les bons éléments s'affichent : 6
   cases, bouton renvoyer + cooldown, bouton retour, mention d'expiration) et
   teste aussi le cas credentials invalides. Il ne peut PAS aller jusqu'au
   bout (pas d'accès à l'OTP réel).

2. **Tous les autres tests** contournent l'UI de login via
   `e2e/utils/auth.ts` (`loginAndGetTokens` + `injectAuthState`, exposées
   comme fixture `authAs(key)` dans `e2e/fixtures.ts`). Le principe :

   - Si la variable d'env `E2E_OTP_BYPASS` est définie, on tente le flux
     complet login+verify-otp avec ce code. **Ce chemin n'est PAS actif
     actuellement** : `backend/apps/authentication/views.py` n'expose aucun
     mode debug qui renverrait un OTP prévisible (`if settings.DEBUG: ...`
     n'existe pas dans le code de login/OTP). Ce n'est pas notre rôle de
     l'ajouter côté backend — le code est prêt si ce bypass est ajouté un
     jour, mais échoue explicitement (erreur claire) s'il est activé sans
     support backend réel.
   - Sinon (cas normal), on lit des tokens JWT **déjà obtenus par un autre
     moyen** (typiquement un script pytest côté backend qui, lui, a accès à
     Redis) dans le fichier `.env.test` : `QA_<COMPTE>_ACCESS_TOKEN` /
     `QA_<COMPTE>_REFRESH_TOKEN` (voir `.env.test.example` à la racine de
     `frontend/`). L'access token JWT expire au bout de 15 minutes ; la
     fonction vérifie sa validité (`GET /api/users/me/`) et le rafraîchit
     automatiquement via `POST /api/auth/token/refresh/` avec le refresh
     token (valide 7 jours) si besoin.

### Mettre en place `.env.test`

```bash
cp .env.test.example .env.test
# puis éditer .env.test et renseigner au moins les REFRESH_TOKEN
# (les ACCESS_TOKEN sont optionnels : s'ils sont absents/expirés, ils seront
# régénérés automatiquement à partir du refresh token)
```

Charger les variables avant de lancer les tests :

```bash
# bash / git-bash
set -a; source .env.test; set +a
npx playwright test

# PowerShell
Get-Content .env.test | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) }
}
npx playwright test
```

## Comptes utilisés

| Clé (`AccountKey`) | Email | Org | Rôle | Usage |
|---|---|---|---|---|
| `platformSuperuser` | emmanueltahi14@gmail.com | — | superuser plateforme | **LECTURE SEULE**, jamais d'action destructive |
| `adminA` | qa-admin-a@test.local | Log+ (Legacy) | admin | compte principal — création/suppression QA_AUDIT_* |
| `analystA` | qa-analyst-a@test.local | Log+ (Legacy) | analyst | vérifications de permissions |
| `viewerA` | qa-viewer-a@test.local | Log+ (Legacy) | viewer | vérifie l'absence de boutons create/delete |
| `adminB` | qa-admin-b@test.local | QA Test Org B | admin | non-visibilité cross-org |
| `analystB` | qa-analyst-b@test.local | QA Test Org B | analyst | non-visibilité cross-org |

## Lancer les tests

```bash
npx playwright test --list     # liste les tests collectés, sans navigation réseau
npx playwright test            # exécute toute la suite (headless, contre la prod !)
npx playwright test --ui       # mode interactif
npx playwright test e2e/alerts.spec.ts   # un seul fichier
npx playwright show-report     # rapport HTML du dernier run
```

`playwright.config.ts` : 1 seul worker (`fullyParallel: false`) pour éviter
les courses entre tests qui créent/suppriment des ressources `QA_AUDIT_*` sur
la même prod partagée, `retries: 1` en local, `trace: 'on-first-retry'`,
`ignoreHTTPSErrors: true`.

## Convention de nettoyage

Toute ressource créée par un test (connecteur, règle de corrélation,
playbook SOAR, requête de hunting, token d'agent, utilisateur...) est nommée
avec le préfixe `QA_AUDIT_` (voir `qaName()` dans `e2e/utils/api.ts`) et
supprimée :

1. via l'UI dans le test lui-même (c'est aussi une fonctionnalité à tester),
2. **et** via un filet de sécurité `test.afterEach`/`afterAll` qui appelle
   l'API directement (`apiAs('adminA').deleteXxxMatchingPrefix()`), au cas où
   l'assertion UI échoue avant la suppression.

Aucun test ne doit jamais supprimer/modifier une ressource qui ne porte pas
ce préfixe, ni toucher aux comptes `qa-*`/`emmanueltahi14@gmail.com` en
dehors des cas explicitement documentés (modification réversible d'un champ
anodin, remise à l'état d'origine en fin de test).

## Structure

```
frontend/
├── playwright.config.ts
├── .env.test.example
└── e2e/
    ├── README.md                 (ce fichier)
    ├── fixtures.ts               (test/expect étendus : authAs, apiAs)
    ├── utils/
    │   ├── auth.ts                (loginAndGetTokens, injectAuthState, TEST_ACCOUNTS)
    │   └── api.ts                 (ApiClient, qaName, nettoyage par préfixe)
    ├── login.spec.ts              (canary du vrai flux UI)
    ├── register.spec.ts
    ├── forgot-password.spec.ts
    ├── reset-password.spec.ts
    ├── verify-email.spec.ts
    ├── invite.spec.ts
    ├── confirm-login.spec.ts
    ├── dashboard.spec.ts
    ├── alerts.spec.ts
    ├── logs.spec.ts
    ├── ml.spec.ts
    ├── collectors.spec.ts
    ├── agents.spec.ts
    ├── correlation.spec.ts
    ├── threat-intel.spec.ts
    ├── soar.spec.ts
    ├── hunting.spec.ts
    ├── reports.spec.ts
    ├── users.spec.ts
    ├── platform-organizations.spec.ts
    └── settings.spec.ts
```
