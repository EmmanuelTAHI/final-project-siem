# tests_prod_audit — suite d'audit HTTP réel contre la prod Log+

Suite pytest **séparée** des tests unitaires Django classiques (`apps/*/tests/`,
qui utilisent le client de test Django + une DB de test). Ici, tout passe par
de vrais appels HTTP (`requests`) contre l'instance de production
**https://logplus.duckdns.org**. Il n'y a pas de DB de test, pas de rollback :
chaque ressource créée par un test est supprimée par ce même test (préfixe
`QA_AUDIT_` pour rester repérable si le nettoyage automatique échouait).

## Installation

```bash
pip install requests pytest
```

## Lancer la suite

```bash
pytest backend/tests_prod_audit -v --tb=short
```

Ou juste la collection (sans réseau, vérifie l'absence d'erreur de syntaxe) :

```bash
pytest backend/tests_prod_audit --collect-only -q
```

## Configuration

La suite lit les tokens depuis un fichier `.env.test` au format :

```
BASE_URL=https://logplus.duckdns.org
ADMIN_EMAIL=...
ADMIN_PASSWORD=...
ADMIN_ACCESS_TOKEN=...
ADMIN_REFRESH_TOKEN=...
QA_ADMIN_A_ACCESS_TOKEN=...
QA_ADMIN_A_REFRESH_TOKEN=...
QA_ANALYST_A_ACCESS_TOKEN=...
QA_ANALYST_A_REFRESH_TOKEN=...
QA_VIEWER_A_ACCESS_TOKEN=...
QA_VIEWER_A_REFRESH_TOKEN=...
QA_ADMIN_B_ACCESS_TOKEN=...
QA_ADMIN_B_REFRESH_TOKEN=...
QA_ANALYST_B_ACCESS_TOKEN=...
QA_ANALYST_B_REFRESH_TOKEN=...
```

Par défaut, `conftest.py` cherche ce fichier dans le scratchpad de la session
Claude qui a écrit cette suite. Pour pointer vers un autre emplacement,
définissez la variable d'environnement :

```bash
export SIEM_TEST_ENV_FILE=/chemin/vers/.env.test
pytest backend/tests_prod_audit -v
```

Les **access tokens** ne sont jamais lus depuis `.env.test` : à chaque
lancement de la suite (une fois par session pytest), `conftest.py` échange
chaque **refresh token** contre un nouveau couple access/refresh via
`POST /api/auth/token/refresh/`, puis réécrit les nouveaux refresh tokens
dans `.env.test` (SIMPLE_JWT a `ROTATE_REFRESH_TOKENS=True` et
`BLACKLIST_AFTER_ROTATION=True` côté backend : l'ancien refresh token est
blacklisté à chaque rotation, donc le fichier doit rester à jour entre deux
runs).

## Ce qui n'est PAS testé et pourquoi

- **OAuth Microsoft/Google/GitHub réel** (callback avec un vrai code
  d'autorisation) : nécessite une interaction humaine avec un IdP tiers,
  impossible à automatiser sans compte de test dédié chez Microsoft/Google.
  Seules les routes d'initiation (`/oauth/*/initiate/`) et les cas d'erreur
  (params manquants) sont couverts indirectement là où c'est sans risque.
- **Confirmation de connexion par email** (`/confirm-login/<token>/`) :
  nécessite un vrai token signé émis par le backend suite à un login
  OAuth suspect — non déclenchable depuis l'extérieur sans lien réel reçu
  par email.
- **Vérification de PIN de liaison de compte** (`/oauth/link/verify-pin/`) :
  même limite, PIN envoyé par email uniquement.
- **`/invite/` avec le cas admin=201 dans `test_permissions_matrix.py`** :
  volontairement non exécuté en boucle paramétrée pour ne pas créer de
  comptes utilisateurs réels non nettoyables (pas de DELETE utilisateur sûr
  à réutiliser ici) ; le cas 403 analyst/viewer et le cas doublon d'email
  (400) restent couverts dans `test_users.py`.
- **`/api/ingest/agent/logs/`** : authentification par token bearer d'agent
  dédiée (pas une session JWT humaine), hors périmètre de cette suite
  centrée sur l'API utilisateur.
- **ML train() en conditions réelles jusqu'à SUCCESS** : on vérifie
  uniquement que le job est accepté (202) — attendre la fin d'un entraînement
  Isolation Forest réel serait long et coûteux en CPU prod.
- **Suppression réelle d'un compte OAuth lié (`LinkedAccountDetailView.delete`)**
  : nécessiterait qu'un compte QA ait un vrai compte OAuth lié au préalable,
  ce qui n'est pas le cas des comptes de test `@test.local`.

## Organisation des fichiers

- `conftest.py` — fixtures `base_url`, tokens par compte (rafraîchis une
  fois par session), factory `api_client(token)` et clients prêts à l'emploi
  (`admin_client`, `qa_admin_a_client`, `qa_analyst_a_client`,
  `qa_viewer_a_client`, `qa_admin_b_client`, `qa_analyst_b_client`,
  `anon_client`).
- Un fichier par app backend (`test_authentication.py`, `test_users.py`,
  `test_collectors.py`, `test_logs.py`, `test_correlation.py`,
  `test_alerts.py`, `test_ml.py`, `test_dashboard.py`,
  `test_threat_intel.py`, `test_soar.py`, `test_reports.py`,
  `test_hunting.py`, `test_organizations_platform.py`).
- `test_tenant_isolation.py` — isolation cross-org dédiée (connectors,
  correlation rules, alerts, users).
- `test_permissions_matrix.py` — matrice systématique admin/analyst/viewer
  sur les endpoints d'écriture sensibles.

## Règles de prudence respectées

- Toute ressource créée est supprimée dans le même test (`try/finally` ou
  fixture avec teardown en `yield`).
- Préfixe `QA_AUDIT_` sur tous les noms de ressources créées.
- Jamais de DELETE/modification sur une ressource préexistante non créée
  par le test — sauf lecture, et un roundtrip PATCH sur une alerte réelle
  qui restaure toujours l'état d'origine dans un `finally`.
- Jamais de changement de mot de passe sur le compte ADMIN réel.
- Jamais de révocation de la session courante utilisée par la suite.
- `time.sleep(1)` entre les appels login/OTP pour respecter le throttling
  (`THROTTLE_RATE_LOGIN`, `THROTTLE_RATE_OTP` côté backend).
