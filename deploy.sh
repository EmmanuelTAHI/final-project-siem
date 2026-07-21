#!/usr/bin/env bash
# ============================================================
# Argus — script de mise à jour rapide (VPS)
#
# Usage : ./deploy.sh
#
# Ce script :
#   1. Tire les dernières modifications depuis Git
#   2. Reconstruit et redémarre les conteneurs en mode production
#   3. Nettoie les images Docker inutilisées
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'
NC='\033[0m'
step() { echo -e "\n${GREEN}==>${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

step "Récupération des dernières modifications..."
git pull origin main

step "Reconstruction et redémarrage des conteneurs..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

step "Nettoyage des images inutilisées..."
docker image prune -f

step "Statut des services :"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo ""
echo "Déploiement terminé !"
