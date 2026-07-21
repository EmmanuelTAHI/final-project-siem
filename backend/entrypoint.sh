#!/bin/bash

set -e

mkdir -p /app/logs /app/ml_models

echo "Waiting for PostgreSQL..."
while ! nc -z ${DB_HOST:-db} ${DB_PORT:-5432}; do
  sleep 0.5
done
echo "PostgreSQL is up."

echo "Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
  sleep 0.5
done
echo "Redis is up."

# Migrations, statiques, fixtures et compte admin : exécutés uniquement par le
# service backend (RUN_MIGRATIONS=1 dans docker-compose.yml). Les workers
# celery/syslog partagent ce même entrypoint mais démarrent en parallèle :
# sans ce garde-fou, quatre "migrate"/"loaddata" concurrents se disputent la
# base au premier déploiement.
if [ "${RUN_MIGRATIONS:-0}" != "1" ]; then
  exec "$@"
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

# Charge les règles de corrélation par défaut (brute force, impossible travel,
# off-hours, élévation de privilèges, MFA bypass, etc.) pour chaque
# organisation qui ne les a pas encore — idempotent. Remplace l'ancien
# fixture global (incompatible avec le multi-tenant : les règles sont
# maintenant scopées par organisation). Les nouvelles organisations créées
# via /register/ reçoivent déjà ces règles à la création (RegisterView) ;
# cette étape couvre les organisations existantes (ex: legacy).
echo "Chargement des règles de corrélation par défaut (par organisation)..."
python manage.py seed_default_rules || true

# Crée automatiquement un compte administrateur au premier démarrage si
# DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD sont définis (ex: via
# le script d'installation). Idempotent : ne fait rien si le compte existe déjà.
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo "Vérification du compte administrateur..."
  python manage.py shell -c "
from django.db import IntegrityError
from apps.users.models import User
import os

email = os.environ['DJANGO_SUPERUSER_EMAIL']
try:
    if not User.objects.filter(email=email).exists():
        User.objects.create_superuser(
            email=email,
            password=os.environ['DJANGO_SUPERUSER_PASSWORD'],
            first_name=os.environ.get('DJANGO_SUPERUSER_FIRST_NAME', 'Admin'),
            last_name=os.environ.get('DJANGO_SUPERUSER_LAST_NAME', 'Argus'),
        )
        print(f'Compte administrateur cree : {email}')
    else:
        print(f'Compte administrateur deja existant : {email}')
except IntegrityError:
    print('Compte administrateur deja en cours de creation, ignore.')
" || true
fi

exec "$@"
