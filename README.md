# Argus — SIEM SaaS multi-tenant, self-service

Plateforme SIEM (collecte de logs, corrélation MITRE ATT&CK, détection
d'anomalies par Machine Learning, threat intelligence, réponse SOAR,
ticketing) pensée pour être **déployée et prise en main par une PME sans
support externe** — jusqu'à l'agent de collecte, qui est natif au projet
(aucun logiciel tiers requis).

📖 **Documentation complète** : [argussiem.com/docs](https://argussiem.com/docs)
(ou `/docs` sur votre propre instance auto-hébergée) — création
d'organisation, déploiement d'agents, architecture, modèle de sécurité,
référence API.

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
- Documentation : **http://localhost:3000/docs** (ou port du service `docs` en dev)
- API : http://localhost:8000

### Installation manuelle

```bash
cp .env.example .env
# éditer .env si besoin (intégrations optionnelles)
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

---

## Fonctionnalités

- **Multi-tenant SaaS** : isolation stricte par organisation (données,
  WebSocket, agents) — une instance peut héberger plusieurs entreprises
  clientes sans qu'elles se voient entre elles.
- **Agent de collecte natif** (Linux & Windows) : binaire unique compilé en
  Go, aucune dépendance externe (pas de NXLog, pas de rsyslog à
  configurer) — installation en une commande depuis le tableau de bord.
  Alternatives compatibles (rsyslog, NXLog, Fluent Bit) toujours
  supportées via l'endpoint HTTP authentifié.
- **Ingestion multi-source** : Microsoft 365, Google Workspace, Wazuh,
  syslog (UDP + agent natif), API HTTP.
- **Corrélation & détection** : moteur de règles mappées MITRE ATT&CK
  (brute force, déplacement impossible, séquences suspectes...) + modèle
  de détection d'anomalies par Machine Learning (Isolation Forest).
- **Threat Intelligence** : enrichissement IP (AbuseIPDB, VirusTotal,
  géolocalisation, empreinte interne) avec verdict de synthèse, même sans
  clé API configurée.
- **SOAR** : playbooks de réponse automatisée déclenchés par sévérité,
  règle de corrélation ou anomalie ML (blocage IP, email, webhook,
  création de ticket...).
- **Ticketing SOC** : suivi des investigations en Kanban, lié aux alertes.
- **Authentification renforcée** : connexion en deux étapes (mot de passe
  + code OTP par email), OAuth (Google, Microsoft, GitHub), détection de
  déplacement impossible sur les connexions à la plateforme elle-même.
- **Rapports de conformité** exportables (PDF).
- **Interface** : tableau de bord temps réel (WebSocket), responsive
  mobile, multilingue (FR/EN/ES/RU/ZH), thème clair/sombre.
- **Documentation intégrée** (`/docs`) : recherche, guides d'installation,
  référence API, modèle de sécurité — accessible sans compte.

## Architecture

| Composant | Rôle |
|-----------|------|
| `frontend` | Interface web (Next.js) |
| `backend` | API (Django + DRF, WebSocket via Daphne) |
| `celery_worker` / `celery_beat` | Tâches asynchrones (collecte, corrélation, ML, threat intel) |
| `syslog_receiver` | Réception de logs syslog (UDP 514) |
| `docs` | Site de documentation (Next.js/Fumadocs), servi sous `/docs` |
| `db` | PostgreSQL |
| `redis` | Cache, broker Celery, WebSocket |
| `agent/` | Agent de collecte natif (Go, Linux/Windows) — voir [la doc agents](https://argussiem.com/docs/agents) |

Toutes les commandes `docker compose ...` se lancent depuis la racine du projet,
qui contient le `docker-compose.yml` unique pour l'ensemble de la stack.

## Mode développement (hot-reload)

La surcouche de développement se trouve dans `docker-compose.dev.yml`
(**jamais fusionnée automatiquement** — elle doit être demandée explicitement).
Elle active :

- **Frontend** : `npm run dev` avec le code monté en volume → les modifications
  dans `frontend/src` sont reflétées immédiatement dans le navigateur.
- **Backend** : `manage.py runserver` (autoreload Django) au lieu de Daphne →
  les modifications Python sont prises en compte sans reconstruire l'image.

```bash
# Lancer la stack en mode développement
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# (Optionnel, poste de dev uniquement) fusion automatique par "docker compose up" :
cp docker-compose.dev.yml docker-compose.override.yml   # gitignoré
```

> ⚠️ `docker-compose.override.yml` est gitignoré et ne doit **jamais** exister
> sur le serveur de production : Docker Compose le fusionnerait silencieusement
> et relancerait la stack en mode dev (`runserver`, `DEBUG=True`).

En production (VPS), utiliser exclusivement :

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Commandes utiles

```bash
docker compose ps              # état des services
docker compose logs -f backend # logs en direct
docker compose down             # arrêter
docker compose down -v          # arrêter + supprimer les données (reset complet)
```

## Agent de collecte natif

Le dossier [`agent/`](agent/) contient le code source de l'agent Argus (Go,
compilation statique, sans dépendance externe). Pour builder les binaires :

```bash
cd agent && ./build.sh   # génère dist/argus-agent-{linux-amd64,linux-arm64,windows-amd64.exe} + sommes SHA-256
```

Les binaires sont servis par nginx sous `/agents/` et téléchargés
automatiquement par la commande d'installation générée depuis le tableau de
bord (page **Agents** → **Générer un token**). Détails complets : voir la
[documentation agents](https://argussiem.com/docs/agents).

## Configuration avancée

Les intégrations optionnelles (Microsoft 365, Google Workspace, Wazuh, OAuth,
AbuseIPDB, VirusTotal, email...) se configurent dans `.env` — voir les
commentaires de `.env.example`. Elles sont désactivées par défaut et
n'empêchent pas le démarrage de la plateforme.

Pour plus de détails sur le backend (modèles, API, tests), voir
[`backend/README.md`](backend/README.md). Pour tout le reste (architecture,
sécurité, agents, API), voir le [site de documentation](https://argussiem.com/docs).
