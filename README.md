# Log+ — SIEM tout-en-un

Plateforme SIEM (collecte de logs, corrélation, alertes, détection d'anomalies par
Machine Learning, réponse SOAR) pensée pour être **installée et prise en main
facilement**, même par des équipes non spécialistes en sécurité.

---

## Démarrage en 5 minutes

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) et Docker Compose (inclus dans Docker Desktop)

### Installation automatique (recommandé)

**Linux / macOS / WSL**
```bash
./install.sh
```

**Windows (PowerShell)**
```powershell
.\install.ps1
```

Ce script :
1. vérifie que Docker est installé,
2. crée le fichier `.env` à partir de `.env.example` et **génère automatiquement**
   les secrets nécessaires (clé Django, mots de passe base de données, clé de
   chiffrement, mot de passe administrateur),
3. construit et démarre l'ensemble de la stack (`docker compose up -d --build`),
4. affiche les identifiants du compte administrateur à la fin.

Une fois terminé :
- Interface web : **http://localhost:3000**
- API : http://localhost:8000

### Installation manuelle

```bash
cp .env.example .env
# éditer .env si besoin (intégrations optionnelles)
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

---

## Architecture

| Composant | Rôle |
|-----------|------|
| `frontend` | Interface web (Next.js) |
| `backend` | API (Django + DRF, WebSocket via Daphne) |
| `celery_worker` / `celery_beat` | Tâches asynchrones (collecte, corrélation, ML) |
| `syslog_receiver` | Réception de logs syslog (UDP 514) |
| `db` | PostgreSQL |
| `redis` | Cache, broker Celery, WebSocket |

Toutes les commandes `docker compose ...` se lancent depuis la racine du projet,
qui contient le `docker-compose.yml` unique pour l'ensemble de la stack.

## Mode développement (hot-reload)

Le fichier `docker-compose.override.yml` est **fusionné automatiquement** par
`docker compose up` (et donc par `install.sh` / `install.ps1`). Il active :

- **Frontend** : `npm run dev` avec le code monté en volume → les modifications
  dans `frontend/src` sont reflétées immédiatement dans le navigateur.
- **Backend** : `manage.py runserver` (autoreload Django) au lieu de Daphne →
  les modifications Python sont prises en compte sans reconstruire l'image.

Pour lancer la stack en mode "production" (sans hot-reload, images optimisées) :

```bash
docker compose -f docker-compose.yml up -d --build
```

## Commandes utiles

```bash
docker compose ps              # état des services
docker compose logs -f backend # logs en direct
docker compose down             # arrêter
docker compose down -v          # arrêter + supprimer les données (reset complet)
```

## Configuration avancée

Les intégrations optionnelles (Microsoft 365, Google Workspace, Wazuh, AbuseIPDB,
VirusTotal, email...) se configurent dans `.env` — voir les commentaires de
`.env.example`. Elles sont désactivées par défaut et n'empêchent pas le
démarrage de la plateforme.

Pour plus de détails sur le backend (modèles, API, tests), voir
[`backend/README.md`](backend/README.md).
