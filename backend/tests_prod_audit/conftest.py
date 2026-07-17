"""
Fixtures partagées pour la suite d'audit HTTP réelle contre la prod Log+
(https://logplus.duckdns.org). Ces tests ne touchent JAMAIS Django ou une DB
de test — tout passe par `requests` en HTTP pur contre BASE_URL.

Comptes utilisés (voir .env.test, chemin fourni par SIEM_TEST_ENV_FILE) :
- ADMIN         : superuser plateforme, org "Log+ (Legacy)"
- QA_ADMIN_A    : admin, org A ("Log+ (Legacy)")
- QA_ANALYST_A  : analyst, org A
- QA_VIEWER_A   : viewer, org A
- QA_ADMIN_B    : admin, org B ("QA Test Org B")
- QA_ANALYST_B  : analyst, org B

Les access tokens expirent en 15 min : chaque fixture de token fait un
POST /api/auth/token/refresh/ une seule fois par session pytest (mise en
cache par `pytest.fixture(scope="session")`), à partir du refresh token
stocké dans .env.test. Comme SIMPLE_JWT a ROTATE_REFRESH_TOKENS=True et
BLACKLIST_AFTER_ROTATION=True, chaque refresh blackliste l'ancien refresh
token et en émet un nouveau : ce nouveau refresh token est réécrit dans
.env.test après coup, pour que la prochaine exécution de la suite reste
utilisable sans re-générer les tokens à la main.
"""
import os
import time
from pathlib import Path

import pytest
import requests

# ─────────────────────────────────────────────────────────────────────────────
# Chargement de .env.test
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_ENV_FILE = (
    Path.home()
    / "AppData/Local/Temp/claude/C--Users-emman-OneDrive-Desktop-PFE"
    / "6c1e6cec-634e-447a-973f-d6c6966d61b0/scratchpad/siem_audit/.env.test"
)

ACCOUNTS = ["ADMIN", "QA_ADMIN_A", "QA_ANALYST_A", "QA_VIEWER_A", "QA_ADMIN_B", "QA_ANALYST_B"]


def _env_file_path() -> Path:
    return Path(os.environ.get("SIEM_TEST_ENV_FILE", str(DEFAULT_ENV_FILE)))


def _parse_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier d'environnement de test introuvable : {path}\n"
            "Définissez SIEM_TEST_ENV_FILE pour pointer vers votre .env.test "
            "(format NOM_ACCESS_TOKEN=... / NOM_REFRESH_TOKEN=...)."
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _rewrite_env_file(path: Path, updates: dict) -> None:
    """Réécrit les paires clé=valeur données dans le fichier .env.test, en
    conservant l'ordre et les lignes non concernées. Best-effort : si
    l'écriture échoue (permissions, fichier en lecture seule...), on avale
    l'erreur — ce n'est qu'une commodité pour les runs suivants, pas un
    prérequis fonctionnel de la session en cours."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        seen = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}")
                    seen.add(key)
                    continue
            new_lines.append(line)
        for key, value in updates.items():
            if key not in seen:
                new_lines.append(f"{key}={value}")
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass


@pytest.fixture(scope="session")
def env_values():
    return _parse_env_file(_env_file_path())


@pytest.fixture(scope="session")
def base_url(env_values):
    return env_values.get("BASE_URL", "https://logplus.duckdns.org").rstrip("/")


@pytest.fixture(scope="session")
def _refreshed_tokens(env_values, base_url):
    """
    Rafraîchit UNE fois par session les tokens de chaque compte listé dans
    ACCOUNTS, à partir de son refresh token dans .env.test. Retourne un dict
    {NOM: {"access": ..., "refresh": ...}}. Écrit aussi les nouveaux refresh
    tokens dans .env.test (rotation JWT oblige) pour les prochains runs.
    """
    tokens = {}
    updates = {}
    for name in ACCOUNTS:
        refresh_key = f"{name}_REFRESH_TOKEN"
        refresh_token = env_values.get(refresh_key)
        if not refresh_token:
            # Compte non fourni dans .env.test : on saute, les fixtures qui en
            # dépendent échoueront explicitement (skip) à l'usage.
            continue
        resp = requests.post(
            f"{base_url}/api/auth/token/refresh/",
            json={"refresh": refresh_token},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Impossible de rafraîchir le token pour {name} "
                f"({resp.status_code}) : {resp.text[:300]}"
            )
        data = resp.json()["data"]
        tokens[name] = {
            "access": data["access_token"],
            "refresh": data["refresh_token"],
        }
        updates[refresh_key] = data["refresh_token"]
        # Anti rate-limit : espace les refresh successifs.
        time.sleep(0.3)

    _rewrite_env_file(_env_file_path(), updates)
    return tokens


def _make_token_fixture(name: str):
    @pytest.fixture(scope="session")
    def _token(_refreshed_tokens):
        if name not in _refreshed_tokens:
            pytest.skip(f"Compte {name} absent de .env.test (clé {name}_REFRESH_TOKEN manquante).")
        return _refreshed_tokens[name]["access"]

    return _token


# Une fixture de token d'accès par compte, ex: admin_token, qa_admin_a_token...
admin_token = _make_token_fixture("ADMIN")
qa_admin_a_token = _make_token_fixture("QA_ADMIN_A")
qa_analyst_a_token = _make_token_fixture("QA_ANALYST_A")
qa_viewer_a_token = _make_token_fixture("QA_VIEWER_A")
qa_admin_b_token = _make_token_fixture("QA_ADMIN_B")
qa_analyst_b_token = _make_token_fixture("QA_ANALYST_B")


@pytest.fixture(scope="session")
def api_client(base_url):
    """
    Factory de session `requests` authentifiée : api_client(token) renvoie une
    requests.Session avec Authorization: Bearer <token> déjà posé et l'URL de
    base préfixée automatiquement via un petit wrapper `.url(path)`.
    """

    def _make(token: str | None = None) -> "ApiClient":
        return ApiClient(base_url, token)

    return _make


class ApiClient:
    """Petit wrapper autour de requests.Session qui préfixe BASE_URL et pose
    le header Authorization si un token est fourni. Les méthodes renvoient
    directement l'objet requests.Response — les assertions restent dans les
    tests pour rester explicites."""

    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.session.headers["Accept"] = "application/json"

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base_url}{path if path.startswith('/') else '/' + path}"

    def get(self, path, **kwargs):
        return self.session.get(self._url(path), timeout=kwargs.pop("timeout", 30), **kwargs)

    def post(self, path, **kwargs):
        return self.session.post(self._url(path), timeout=kwargs.pop("timeout", 30), **kwargs)

    def patch(self, path, **kwargs):
        return self.session.patch(self._url(path), timeout=kwargs.pop("timeout", 30), **kwargs)

    def put(self, path, **kwargs):
        return self.session.put(self._url(path), timeout=kwargs.pop("timeout", 30), **kwargs)

    def delete(self, path, **kwargs):
        return self.session.delete(self._url(path), timeout=kwargs.pop("timeout", 30), **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Clients HTTP prêts à l'emploi par rôle — évite de répéter
# `api_client(xxx_token)` dans chaque test.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def anon_client(base_url):
    return ApiClient(base_url, token=None)


@pytest.fixture
def admin_client(api_client, admin_token):
    return api_client(admin_token)


@pytest.fixture
def qa_admin_a_client(api_client, qa_admin_a_token):
    return api_client(qa_admin_a_token)


@pytest.fixture
def qa_analyst_a_client(api_client, qa_analyst_a_token):
    return api_client(qa_analyst_a_token)


@pytest.fixture
def qa_viewer_a_client(api_client, qa_viewer_a_token):
    return api_client(qa_viewer_a_token)


@pytest.fixture
def qa_admin_b_client(api_client, qa_admin_b_token):
    return api_client(qa_admin_b_token)


@pytest.fixture
def qa_analyst_b_client(api_client, qa_analyst_b_token):
    return api_client(qa_analyst_b_token)


QA_PREFIX = "QA_AUDIT_"
