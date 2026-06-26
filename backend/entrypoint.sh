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

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

# Charge les règles de corrélation par défaut (brute force, impossible travel,
# off-hours, élévation de privilèges, MFA bypass, etc.). loaddata est
# idempotent : les règles existantes (même pk) sont simplement mises à jour.
echo "Chargement des règles de corrélation par défaut..."
python manage.py loaddata apps/correlation/fixtures/default_rules.json || true

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
            last_name=os.environ.get('DJANGO_SUPERUSER_LAST_NAME', 'LogPlus'),
        )
        print(f'Compte administrateur cree : {email}')
    else:
        print(f'Compte administrateur deja existant : {email}')
except IntegrityError:
    print('Compte administrateur deja en cours de creation, ignore.')
" || true
fi

exec "$@"
