# Log+ Backend — PFE 2025-2026

**Auteur** : TAHI Ezan Franck Emmanuel  
**Projet** : Log+  
**Niveau** : Licence 3, 2025-2026  
**Sujet** : Conception et Implémentation d'une Log+

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
User.objects.create_user(email='admin@logplus.ci', password='Admin@2025!', first_name='Admin', last_name='Log+', role='admin', is_staff=True, is_superuser=True)
User.objects.create_user(email='analyst@logplus.ci', password='Analyst@2025!', first_name='Analyste', last_name='SOC', role='analyst')
User.objects.create_user(email='viewer@logplus.ci', password='Viewer@2025!', first_name='Observateur', last_name='Log+', role='viewer')
print('Utilisateurs créés.')
"
```

| Email | Mot de passe | Rôle |
|-------|-------------|------|
| admin@logplus.ci | Admin@2025! | Administrateur |
| analyst@logplus.ci | Analyst@2025! | Analyste SOC |
| viewer@logplus.ci | Viewer@2025! | Observateur |

---

## API Endpoints

### Authentification (`/api/auth/`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/login/` | Connexion JWT |
| POST | `/api/auth/token/refresh/` | Renouvellement token |
| POST | `/api/auth/logout/` | Déconnexion (blacklist) |
| GET | `/api/auth/oauth/microsoft/initiate/` | Initiation OAuth2 Microsoft |
| GET | `/api/auth/oauth/microsoft/callback/` | Callback OAuth2 Microsoft |
| GET | `/api/auth/oauth/google/initiate/` | Initiation OAuth2 Google |
| GET | `/api/auth/oauth/google/callback/` | Callback OAuth2 Google |

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

| Règle | Sévérité | MITRE |
|-------|---------|-------|
| Brute Force | HIGH | T1110 |
| Impossible Travel | CRITICAL | T1078 |
| Off-Hours Login | MEDIUM | T1078 |
| Privilege Escalation | HIGH | T1078.003 |
| MFA Bypass | CRITICAL | T1556 |

---

## Sécurité

- **Chiffrement** : Tous les credentials et tokens OAuth2 sont chiffrés avec Fernet AES-256 avant stockage
- **JWT** : Access token (15 min) + Refresh token (7 jours) avec blacklist
- **CORS** : Restreint à `FRONTEND_URL` uniquement
- **Audit Trail** : Toutes les mutations critiques sont tracées
- **Variables d'environnement** : Aucune valeur sensible dans le code source

---

## Structure du projet

```
backend/
├── config/              # Configuration Django + Celery
├── apps/
│   ├── authentication/  # JWT + OAuth2 PKCE
│   ├── users/           # Utilisateurs SOC + Audit Trail
│   ├── collectors/      # Collecteurs Microsoft/Google/Wazuh
│   ├── logs/            # Logs bruts + normalisés (CEF)
│   ├── correlation/     # Moteur de corrélation (5 règles)
│   ├── alerts/          # Alertes SOC
│   ├── ml/              # Isolation Forest
│   └── dashboard/       # KPIs et métriques
└── utils/               # Utilitaires partagés
```

---

*PFE Log+ — TAHI Ezan Franck Emmanuel — 2025-2026*
