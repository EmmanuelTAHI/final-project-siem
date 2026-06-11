#!/usr/bin/env bash
# ============================================================
# Log+ — installation en une commande
#
# Usage : ./install.sh
#
# Ce script :
#   1. vérifie que Docker / Docker Compose sont installés
#   2. crée .env depuis .env.example (si absent) et génère des secrets
#      aléatoires (SECRET_KEY, mots de passe DB, clé de chiffrement)
#   3. construit et démarre toute la stack (docker compose up -d --build)
#   4. attend que les services soient prêts
#   5. affiche les identifiants du compte administrateur
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
info() { printf "  -> %s\n" "$1"; }

bold "Log+ — installation"

# 1. Vérification des prérequis
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker n'est pas installé. Voir https://docs.docker.com/get-docker/"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Le plugin 'docker compose' est introuvable. Installez Docker Desktop ou docker-compose-plugin."
  exit 1
fi
info "Docker et Docker Compose détectés."

# 2. Préparation du fichier .env
if [ ! -f .env ]; then
  info "Création de .env depuis .env.example..."
  cp .env.example .env

  random() { python3 -c "import secrets; print(secrets.token_urlsafe($1))" 2>/dev/null || head -c "$1" /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c "$1"; }
  fernet_key() { python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || head -c 32 /dev/urandom | base64 | tr '+/' '-_'; }

  SECRET_KEY_VAL=$(random 50)
  DB_PASSWORD_VAL=$(random 24)
  ADMIN_PASSWORD_VAL=$(random 16)
  ENCRYPTION_KEY_VAL=$(fernet_key)

  sed -i.bak \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY_VAL}|" \
    -e "s|^DB_PASSWORD=.*|DB_PASSWORD=${DB_PASSWORD_VAL}|" \
    -e "s|^DJANGO_SUPERUSER_PASSWORD=.*|DJANGO_SUPERUSER_PASSWORD=${ADMIN_PASSWORD_VAL}|" \
    -e "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY_VAL}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://siem_user:${DB_PASSWORD_VAL}@db:5432/siem_db|" \
    .env
  rm -f .env.bak

  info "Secrets générés automatiquement dans .env"
else
  info ".env existe déjà, conservation de la configuration actuelle."
fi

# 3. Démarrage de la stack
bold "Construction et démarrage des conteneurs (cela peut prendre quelques minutes)..."
docker compose up -d --build

# 4. Attente des services
bold "Attente du démarrage des services..."
for i in $(seq 1 60); do
  if docker compose ps backend 2>/dev/null | grep -qi "running\|up"; then
    break
  fi
  sleep 2
done

# 5. Récapitulatif
ADMIN_EMAIL=$(grep -E '^DJANGO_SUPERUSER_EMAIL=' .env | cut -d= -f2-)
ADMIN_PASSWORD=$(grep -E '^DJANGO_SUPERUSER_PASSWORD=' .env | cut -d= -f2-)

echo ""
bold "Log+ est démarré !"
echo "  Interface web      : http://localhost:3000"
echo "  API backend        : http://localhost:8000"
echo "  Compte administrateur :"
echo "    Email    : ${ADMIN_EMAIL}"
echo "    Mot de passe : ${ADMIN_PASSWORD}"
echo ""
echo "  (ces identifiants sont aussi stockés dans le fichier .env)"
echo ""
echo "Pour arrêter : docker compose down"
echo "Pour voir les logs : docker compose logs -f"
