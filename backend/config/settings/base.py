"""
Base settings partagés par tous les environnements.
PFE Argus — TAHI Ezan Franck Emmanuel — 2025-2026
"""
import os
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ─── Sécurité ─────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ─── Applications installées ─────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "channels",
]

LOCAL_APPS = [
    "apps.organizations",
    "apps.users",
    "apps.authentication",
    "apps.collectors",
    "apps.logs",
    "apps.correlation",
    "apps.alerts",
    "apps.ml",
    "apps.dashboard",
    "apps.threat_intel",
    "apps.soar",
    "apps.reports",
    "apps.notifications.apps.NotificationsConfig",
    "apps.hunting",
    "apps.tickets",
    "apps.copilot",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "utils.blocklist_middleware.BlockedIPMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "utils.demo_readonly_middleware.DemoSpectatorReadOnlyMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ─── Base de données ──────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="siem_db"),
        "USER": env("DB_USER", default="siem_user"),
        "PASSWORD": env("DB_PASSWORD", default="siem_password"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "OPTIONS": {"connect_timeout": 10},
    }
}

# ─── Modèle utilisateur personnalisé ─────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

# ─── Validation des mots de passe ────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─── Fichiers statiques et médias ─────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "utils.tenant.OrganizationFilterBackend",
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "utils.pagination.StandardResultsPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": env("THROTTLE_RATE_LOGIN", default="10/min"),
        "password_reset": env("THROTTLE_RATE_PASSWORD_RESET", default="5/hour"),
        "otp": env("THROTTLE_RATE_OTP", default="5/min"),
        "register": env("THROTTLE_RATE_REGISTER", default="5/hour"),
        "agent_ingest": env("THROTTLE_RATE_AGENT_INGEST", default="10000/min"),
    },
}

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(env("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(env("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "apps.authentication.serializers.CustomTokenObtainPairSerializer",
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
).split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

# ─── Redis ────────────────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True

# ─── Chiffrement ──────────────────────────────────────────────────────────────
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="")

# ─── OAuth2 Microsoft ─────────────────────────────────────────────────────────
MICROSOFT_CLIENT_ID = env("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = env("MICROSOFT_CLIENT_SECRET", default="")
MICROSOFT_TENANT_ID = env("MICROSOFT_TENANT_ID", default="common")
MICROSOFT_REDIRECT_URI = env(
    "MICROSOFT_REDIRECT_URI",
    default="http://localhost:8000/api/auth/oauth/microsoft/callback/",
)
MICROSOFT_SCOPES = env(
    "MICROSOFT_SCOPES",
    default="AuditLog.Read.All SecurityAlert.Read.All offline_access",
).split()

# ─── OAuth2 Google ────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
# Client dédié au collecteur Admin SDK (peut être identique à GOOGLE_CLIENT_ID)
GOOGLE_COLLECTOR_CLIENT_ID = env("GOOGLE_COLLECTOR_CLIENT_ID", default="") or GOOGLE_CLIENT_ID
GOOGLE_COLLECTOR_CLIENT_SECRET = env("GOOGLE_COLLECTOR_CLIENT_SECRET", default="") or GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI = env(
    "GOOGLE_REDIRECT_URI",
    default="http://localhost:8000/api/auth/oauth/google/callback/",
)
GOOGLE_SCOPES = env(
    "GOOGLE_SCOPES",
    default="https://www.googleapis.com/auth/admin.reports.audit.readonly",
).split()

# ─── Wazuh ────────────────────────────────────────────────────────────────────
WAZUH_API_URL = env("WAZUH_API_URL", default="https://localhost:55000")
WAZUH_USERNAME = env("WAZUH_USERNAME", default="wazuh-wui")
WAZUH_PASSWORD = env("WAZUH_PASSWORD", default="")
WAZUH_VERIFY_SSL = env.bool("WAZUH_VERIFY_SSL", default=False)

# ─── Django Channels (WebSockets) ────────────────────────────────────────────
# RedisPubSubChannelLayer (et non le core RedisChannelLayer) : le layer "core"
# lit les messages via BRPOP et lève redis.TimeoutError avec redis-py 5+/8,
# ce qui tue le consumer et fait boucler le WebSocket (connect/disconnect).
# Le layer pub/sub s'appuie sur SUBSCRIBE et reste stable.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379/0")],
        },
    }
}

# ─── Machine Learning ─────────────────────────────────────────────────────────
ML_MODELS_DIR = env("ML_MODELS_DIR", default=str(BASE_DIR / "ml_models"))
ML_CONTAMINATION_RATE = float(env("ML_CONTAMINATION_RATE", default=0.05))

# ─── Threat Intelligence ──────────────────────────────────────────────────────
ABUSEIPDB_API_KEY = env("ABUSEIPDB_API_KEY", default="")
VIRUSTOTAL_API_KEY = env("VIRUSTOTAL_API_KEY", default="")
CRIMINALIP_API_KEY = env("CRIMINALIP_API_KEY", default="")
SHODAN_API_KEY = env("SHODAN_API_KEY", default="")
# NVD (National Vulnerability Database) — fonctionne sans clé (5 req/30s),
# une clé gratuite relève la limite à 50 req/30s.
NVD_API_KEY = env("NVD_API_KEY", default="")

# ─── SOC Copilot IA (Anthropic Claude, ou Google Gemini en repli si pas de clé Anthropic) ──
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-4-5")
GOOGLE_AI_API_KEY = env("GOOGLE_AI_API_KEY", default="")
GOOGLE_AI_MODEL = env("GOOGLE_AI_MODEL", default="gemini-flash-lite-latest")

# ─── Démon de blocage réseau réel (scripts/host-firewall-agent) ───────────────
# Tourne sur l'hôte VPS, hors Docker — protégé par la politique par défaut
# d'ufw (deny incoming) plutôt qu'un bind loopback, voir firewall_agent.py —
# atteint depuis les conteneurs via host.docker.internal (voir extra_hosts
# dans docker-compose.prod.yml). Vide par défaut : sans configuration, l'action
# SOAR block_ip retombe sur le blocage applicatif seul (BlockedIP + middleware),
# jamais d'erreur si le démon n'est pas installé.
HOST_FIREWALL_URL = env("HOST_FIREWALL_URL", default="")
HOST_FIREWALL_TOKEN = env("HOST_FIREWALL_TOKEN", default="")

# ─── Frontend ─────────────────────────────────────────────────────────────────
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
BACKEND_URL = env("BACKEND_URL", default="http://localhost:8000")

# ─── OAuth2 Liaison de comptes personnels ────────────────────────────────────
# Réutilise GOOGLE_CLIENT_ID / MICROSOFT_CLIENT_ID. Redirect URI dédié au flow "link".
GOOGLE_LINK_REDIRECT_URI = env(
    "GOOGLE_LINK_REDIRECT_URI",
    default=f"{BACKEND_URL}/api/auth/oauth/link/google/callback/",
)
MICROSOFT_LINK_REDIRECT_URI = env(
    "MICROSOFT_LINK_REDIRECT_URI",
    default=f"{BACKEND_URL}/api/auth/oauth/link/microsoft/callback/",
)
GITHUB_CLIENT_ID = env("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = env("GITHUB_CLIENT_SECRET", default="")
GITHUB_LINK_REDIRECT_URI = env(
    "GITHUB_LINK_REDIRECT_URI",
    default=f"{BACKEND_URL}/api/auth/oauth/link/github/callback/",
)

# ─── Email (notifications de sécurité) ───────────────────────────────────────
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = int(env("EMAIL_PORT", default=587))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Argus <noreply@argussiem.com>")

# ─── Syslog Receiver ─────────────────────────────────────────────────────────
# UDP, non chiffré, authentifié seulement par allowlist IP par connecteur —
# réservé au self-host mono-organisation sur réseau privé. Sur la plateforme
# SaaS mutualisée, laisser à False et utiliser l'ingestion HTTP par token
# d'agent (/api/ingest/agent/logs/) à la place.
SYSLOG_RECEIVER_ENABLED = env.bool("SYSLOG_RECEIVER_ENABLED", default=True)
SYSLOG_HOST = env("SYSLOG_HOST", default="0.0.0.0")
SYSLOG_PORT = int(env("SYSLOG_PORT", default=5140))

# ─── Rétention des logs ───────────────────────────────────────────────────────
LOG_RETENTION_DAYS = int(env("LOG_RETENTION_DAYS", default=90))

# ─── Headers de sécurité HTTP ─────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
