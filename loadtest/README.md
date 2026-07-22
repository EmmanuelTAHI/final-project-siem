# Test de charge Argus

Script k6 (`k6-script.js`) simulant un usage SOC réaliste (login, dashboard,
alertes, logs) avec une montée en charge progressive de 0 à 100 utilisateurs
virtuels concurrents.

## Ne jamais lancer contre la production sans prévenir

L'instance de démonstration (`https://logplus.duckdns.org`) sert de vitrine
de soutenance — un test de charge dessus, même modeste, risque de la
dégrader ou de déclencher les protections anti-bruteforce (fail2ban, rate
limiting Django) sur le compte de test. Utiliser une instance locale
(`docker-compose.dev.yml`) ou un environnement de staging dédié.

## Installation de k6

```bash
# Windows (winget)
winget install k6

# macOS
brew install k6

# Linux (Debian/Ubuntu)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

## Créer un compte de test dédié (sans OTP)

Le flux de login normal exige un code OTP par email — inadapté à un script
automatisé. Créer un compte de test avec le 2FA désactivé, ou générer un
JWT directement :

```bash
docker compose exec backend python manage.py shell -c "
from apps.authentication.serializers import CustomTokenObtainPairSerializer
from apps.users.models import User
user = User.objects.get(email='loadtest@argus.local')
token = CustomTokenObtainPairSerializer.get_token(user)
print(str(token.access_token))
"
```

## Lancer le test

```bash
BASE_URL=http://localhost:8000 \
TEST_EMAIL=loadtest@argus.local \
TEST_PASSWORD=change-me \
k6 run k6-script.js
```

## Interpréter les résultats

k6 affiche en fin d'exécution :
- `http_req_duration` : p95 doit rester sous 800ms (seuil défini dans le script).
- `http_req_failed` : taux d'échec doit rester sous 1%.
- `vus_max` : nombre max d'utilisateurs virtuels simultanés atteint.

Si les seuils échouent (exit code non-zéro), identifier le goulot
d'étranglement : `docker stats` pendant le test pour voir CPU/RAM par
conteneur, `docker compose logs celery_worker` pour repérer des tâches
lentes, requêtes Postgres lentes via `pg_stat_statements` si activé.
