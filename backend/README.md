# Argus Backend — PFE 2025-2026

**Auteur** : TAHI Ezan Franck Emmanuel  
**Projet** : Argus  
**Niveau** : Licence 3, 2025-2026  
**Sujet** : Conception et Implémentation d'une Argus

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Framework | Django 5.x + Django REST Framework |
| Base de données | PostgreSQL 16 |
| Cache & Broker | Redis 7 |
| Tâches asynchrones | Celery 5 + Celery Beat |
| Authentification | JWT (simplejwt) + OAuth2 PKCE (RFC 7636) |
| Chiffrement | Fernet AES-256 (cryptography) |
| Machine Learning | Isolation Forest (scikit-learn) |
| Containerisation | Docker + docker-compose |

---

## Démarrage rapide

> Pour une installation en une commande (frontend + backend), voir le
> [README à la racine du projet](../README.md) et lancer `./install.sh` (ou
> `install.ps1` sous Windows). La section ci-dessous détaille le backend, dont
> le `docker-compose.yml` se trouve désormais à la racine du projet.

### 1. Prérequis

- Docker et docker-compose installés
- Python 3.12+ (pour le développement local)

### 2. Configuration de l'environnement

Depuis la racine du projet :

```bash
cp .env.example .env
```

Editez `.env` et renseignez :
- `SECRET_KEY` : clé secrète Django (min. 50 caractères)
- `ENCRYPTION_KEY` : clé Fernet pour le chiffrement

Générer une clé Fernet :
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Lancement avec Docker

Depuis la racine du projet :

```bash
docker compose pull && docker compose up -d   # images pré-construites (GHCR), rapide
# ou, pour reconstruire depuis le code source :
docker compose up --build
```

Services démarrés :
- Backend Django : http://localhost:8000
- Frontend : http://localhost:3000
- PostgreSQL : port 5432
- Redis : port 6379
- Celery Worker (4 concurrents)
- Celery Beat (planificateur)

### 4. Migrations et données initiales

```bash
# Migrations (automatiques au démarrage via entrypoint.sh)
docker compose exec backend python manage.py migrate

# Charger les données de démonstration
docker compose exec backend python manage.py loaddata initial_users default_rules
```

### 5. Création d'un superutilisateur

Un compte administrateur est créé automatiquement au démarrage si
`DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD` sont définis dans `.env`
(c'est le cas par défaut). Pour en créer un supplémentaire :

```bash
docker compose exec backend python manage.py createsuperuser
```

---

## Comptes de démonstration

Après `loaddata initial_users` :

> **Note** : Les mots de passe des fixtures sont des hashes de démonstration.
> Utilisez la commande ci-dessous pour créer des comptes avec de vrais mots de passe.

```bash
docker compose exec backend python manage.py shell -c "
from apps.users.models import User
User.objects.create_user(email='admin@argussiem.com', password='Admin@2025!', first_name='Admin', last_name='Argus', role='admin', is_staff=True, is_superuser=True)
User.objects.create_user(email='analyst@argussiem.com', password='Analyst@2025!', first_name='Analyste', last_name='SOC', role='analyst')
User.objects.create_user(email='viewer@argussiem.com', password='Viewer@2025!', first_name='Observateur', last_name='Argus', role='viewer')
print('Utilisateurs créés.')
"
```

| Email | Mot de passe | Rôle |
|-------|-------------|------|
| admin@argussiem.com | Admin@2025! | Administrateur |
| analyst@argussiem.com | Analyst@2025! | Analyste SOC |
| viewer@argussiem.com | Viewer@2025! | Observateur |

---

## API Endpoints

### Authentification (`/api/auth/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/login/` | Connexion — étape 1 (email/mdp), envoie un OTP par email. Throttled (`login`, 10/min/IP) |
| POST | `/api/auth/verify-otp/` | Connexion — étape 2 (OTP), émet les tokens JWT. Throttled (`otp`, 5/min/IP) |
| POST | `/api/auth/resend-otp/` | Renvoie l'OTP (max 3/session). Throttled (`otp`, 5/min/IP) |
| POST | `/api/auth/token/refresh/` | Renouvellement token |
| POST | `/api/auth/logout/` | Déconnexion (blacklist) |
| POST | `/api/auth/password-reset/` | Demande de réinitialisation par email. Throttled (`password_reset`, 5/heure/IP) |
| POST | `/api/auth/password-reset/confirm/` | Confirmation + nouveau mot de passe. Throttled (`password_reset`, 5/heure/IP) |
| GET | `/api/auth/sessions/` | Liste des sessions actives de l'utilisateur |
| POST | `/api/auth/confirm-login/<token>/` | Approuve/rejette une connexion depuis le lien email |
| GET | `/api/auth/notifications/` | Notifications de sécurité de l'utilisateur |
| POST | `/api/auth/notifications/<uuid>/read/` | Marque une notification comme lue |
| POST | `/api/auth/notifications/read-all/` | Marque toutes les notifications comme lues |
| GET | `/api/auth/oauth/microsoft/initiate/` | Initiation OAuth2 Microsoft (connecteur d'ingestion) |
| GET | `/api/auth/oauth/microsoft/callback/` | Callback OAuth2 Microsoft |
| GET | `/api/auth/oauth/google/initiate/` | Initiation OAuth2 Google (connecteur d'ingestion) |
| GET | `/api/auth/oauth/google/callback/` | Callback OAuth2 Google |
| GET | `/api/auth/oauth/link/<provider>/initiate/` | Initiation liaison compte personnel (google/microsoft/github) |
| GET | `/api/auth/oauth/link/<provider>/callback/` | Callback liaison de compte |
| POST | `/api/auth/oauth/link/verify-pin/` | Vérifie le PIN et finalise la liaison du compte |
| GET | `/api/auth/linked-accounts/` | Liste des comptes personnels liés |
| GET/DELETE | `/api/auth/linked-accounts/<uuid>/` | Détail (30 derniers events) / Déliaison |
| POST | `/api/auth/linked-accounts/<uuid>/poll/` | Déclenche un poll manuel du compte lié |

### Utilisateurs (`/api/users/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/users/` | Liste/Création (admin) |
| GET/PUT/DELETE | `/api/users/{id}/` | Détail/MAJ/Suppression (admin) |
| GET | `/api/users/audit-trail/` | Journal d'audit des actions plateforme |

### Connecteurs (`/api/collectors/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/collectors/connectors/` | Liste/Création |
| GET/PUT/DELETE | `/api/collectors/connectors/{id}/` | Détail/MAJ/Suppression |
| POST | `/api/collectors/connectors/{id}/test/` | Test de connexion |
| POST | `/api/collectors/connectors/{id}/collect/` | Collecte manuelle |
| GET | `/api/collectors/jobs/` | Historique des jobs |

### Logs (`/api/logs/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/logs/raw/` | Logs bruts |
| GET | `/api/logs/normalized/` | Logs normalisés (filtrables) |
| GET | `/api/logs/stats/` | Statistiques des logs |

### Alertes (`/api/alerts/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/alerts/` | Liste des alertes |
| PATCH | `/api/alerts/{id}/` | Mise à jour statut |
| GET/POST | `/api/alerts/{id}/comments/` | Commentaires |
| GET | `/api/alerts/stats/` | Métriques SOC |

### Corrélation (`/api/correlation/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/correlation/rules/` | Règles de corrélation |
| POST | `/api/correlation/rules/{id}/toggle/` | Activer/Désactiver |
| POST | `/api/correlation/rules/{id}/test/` | Test de règle |

### Machine Learning (`/api/ml/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/ml/models/` | Modèles entraînés |
| POST | `/api/ml/train/` | Lancer l'entraînement |
| GET | `/api/ml/train/{task_id}/status/` | Statut entraînement |
| GET | `/api/ml/predictions/` | Prédictions |

### Dashboard (`/api/dashboard/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/dashboard/summary/` | KPIs temps réel |
| GET | `/api/dashboard/timeline/` | Timeline (24h/7d/30d) |
| GET | `/api/dashboard/top-threats/` | Top 10 menaces |
| GET | `/api/dashboard/geo-map/` | Carte géographique |

### Threat Intelligence (`/api/threat-intel/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/threat-intel/indicators/` | Indicateurs de compromission (IOC) |
| GET | `/api/threat-intel/enriched-logs/` | Logs enrichis par le CTI |
| GET | `/api/threat-intel/stats/` | Statistiques CTI |

### Threat Hunting (`/api/hunting/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/hunting/queries/` | Requêtes de hunting sauvegardées |
| POST | `/api/hunting/run/` | Exécute une recherche de hunting |

### SOAR (`/api/soar/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/soar/playbooks/` | Playbooks de réponse automatisée |
| GET | `/api/soar/executions/` | Historique des exécutions de playbooks |
| GET | `/api/soar/stats/` | Statistiques SOAR |

### Rapports de conformité (`/api/reports/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/reports/compliance/?framework=&period=` | Génère un rapport PDF (PCI DSS v4.0, RGPD, ISO 27001:2022) |
| GET | `/api/reports/frameworks/` | Référentiels de conformité disponibles |

### SOC Copilot IA (`/api/copilot/`)

Assistant en langage naturel qui interroge en direct logs, alertes, CTI et
statistiques — toujours scopé côté serveur à l'organisation de l'utilisateur
authentifié. Nécessite `ANTHROPIC_API_KEY` ou (à défaut) `GOOGLE_AI_API_KEY`
dans `.env` ; sans clé, répond poliment que le service n'est pas configuré.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/copilot/ask/` | Pose une question au Copilot (boucle d'outils, 4 itérations max) |
| GET | `/api/copilot/conversations/` | Historique des conversations de l'utilisateur |
| POST | `/api/copilot/alerts/{id}/summarize/` | Résumé IA + actions recommandées pour une alerte |

---

## Développement local (sans Docker)

```bash
# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec les informations de votre base PostgreSQL locale

# Migrations
python manage.py migrate

# Lancer le serveur
python manage.py runserver

# Worker Celery (terminal séparé)
celery -A config worker -l info

# Celery Beat (terminal séparé)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Tests

```bash
# Avec Docker
docker compose exec backend pytest

# En local
pytest --cov=apps --cov-report=html

# Tests d'une app spécifique
pytest apps/correlation/tests/ -v
pytest apps/authentication/tests/ -v
```

---

## Architecture du moteur de corrélation

Le moteur tourne via Celery Beat toutes les **2 minutes** :

1. Charge les `NormalizedLog` depuis la dernière exécution
2. Pour chaque règle active, exécute la classe de règle correspondante
3. En cas de correspondance, crée une `Alert` + `RuleMatch`
4. Déduplique : pas de doublon pour la même règle/utilisateur en statut open

### Règles prédéfinies

9 moteurs de règles (`apps/correlation/rules/`), 12 instances de règles chargées par défaut via la fixture `default_rules` :

| Règle | Sévérité | MITRE |
|-------|---------|-------|
| Brute Force | HIGH | T1110 - Brute Force |
| Impossible Travel | CRITICAL | T1078 - Valid Accounts |
| Off-Hours Login | MEDIUM | T1078 - Valid Accounts |
| Privilege Escalation | HIGH | T1078.003 - Local Accounts |
| MFA Bypass | CRITICAL | T1556 - Modify Authentication Process |
| Lateral Movement | HIGH | T1021 - Remote Services |
| C2 Beaconing | CRITICAL | T1071 - Application Layer Protocol |
| Data Exfiltration | CRITICAL | T1048 - Exfiltration Over Alternative Protocol |
| Wazuh Alert (High/Critical) | HIGH / CRITICAL | Variable selon la règle Wazuh déclenchée |

---

## Sécurité

- **Chiffrement** : Tous les credentials et tokens OAuth2 sont chiffrés avec Fernet AES-256 avant stockage
- **JWT** : Access token (15 min) + Refresh token (7 jours) avec blacklist
- **Rate limiting** : Throttling DRF scopé par IP sur les endpoints sensibles — login (`10/min`), reset mot de passe (`5/heure`), OTP (`5/min`). Taux configurables via `THROTTLE_RATE_*` dans `.env`
- **Rétention des logs** : Purge automatique quotidienne (03h00 UTC) des `RawLog`/`NormalizedLog` au-delà de `LOG_RETENTION_DAYS` (défaut 90 jours, configurable via `.env`)
- **CORS** : Restreint à `FRONTEND_URL` uniquement
- **Audit Trail** : Toutes les mutations critiques sont tracées
- **Variables d'environnement** : Aucune valeur sensible dans le code source

---

## Structure du projet

```
backend/
├── config/              # Configuration Django + Celery (beat schedule)
├── apps/
│   ├── authentication/  # JWT + OTP email + OAuth2 PKCE + comptes liés
│   ├── users/            # Utilisateurs SOC + Audit Trail
│   ├── collectors/       # Collecteurs Microsoft/Google/Wazuh
│   ├── logs/              # Logs bruts + normalisés (CEF) + rétention
│   ├── correlation/      # Moteur de corrélation (9 règles)
│   ├── alerts/            # Alertes SOC
│   ├── ml/                # Isolation Forest (détection d'anomalies)
│   ├── dashboard/         # KPIs et métriques
│   ├── threat_intel/      # VirusTotal / AbuseIPDB / CriminalIP / Shodan
│   ├── hunting/           # Threat hunting
│   ├── soar/               # Playbooks de réponse automatisée
│   ├── reports/            # Rapports de conformité (PCI DSS, RGPD, ISO 27001)
│   └── notifications/      # Notifications temps réel (WebSocket)
└── utils/                # Utilitaires partagés
```

---

*PFE Argus — TAHI Ezan Franck Emmanuel — 2025-2026*
