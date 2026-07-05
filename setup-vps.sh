#!/usr/bin/env bash
# ============================================================
# Log+ — installation complète sur VPS Ubuntu 22.04
#
# Usage (en tant que root sur le VPS) :
#   curl -fsSL https://raw.githubusercontent.com/VOTRE_REPO/main/setup-vps.sh | bash
#   -- ou --
#   chmod +x setup-vps.sh && sudo ./setup-vps.sh
#
# Ce script :
#   1. Met à jour le système et installe les dépendances
#   2. Installe Docker et Docker Compose
#   3. Configure le firewall (ufw)
#   4. Clone le dépôt Git dans /opt/siem
#   5. Génère les secrets et configure .env
#   6. Démarre toute la stack en mode production
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}  [+]${NC} $1"; }
warn()  { echo -e "${YELLOW}  [!]${NC} $1"; }
error() { echo -e "${RED}  [✗]${NC} $1"; exit 1; }
step()  { echo -e "\n${BLUE}==>${NC} $1"; }

echo ""
echo "  ██╗      ██████╗  ██████╗    ██╗"
echo "  ██║     ██╔═══██╗██╔════╝    ██║"
echo "  ██║     ██║   ██║██║  ███╗   ██║"
echo "  ██║     ██║   ██║██║   ██║   ╚═╝"
echo "  ███████╗╚██████╔╝╚██████╔╝   ██╗"
echo "  ╚══════╝ ╚═════╝  ╚═════╝    ╚═╝"
echo "  SIEM Platform — Installation VPS"
echo ""

# ─── 1. Vérification root ─────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Ce script doit être exécuté en tant que root : sudo ./setup-vps.sh"
fi

# ─── 2. Mise à jour du système ────────────────────────────────────────────────
step "Mise à jour du système Ubuntu..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl git ufw python3 python3-pip
info "Système à jour."

# ─── 3. Installation Docker ───────────────────────────────────────────────────
step "Installation de Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    info "Docker installé et démarré."
else
    info "Docker déjà installé : $(docker --version)"
fi

# ─── 4. Configurer le firewall ────────────────────────────────────────────────
step "Configuration du firewall (ufw)..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment 'SSH'
ufw allow 80/tcp   comment 'HTTP'
ufw allow 443/tcp  comment 'HTTPS'
ufw allow 514/udp  comment 'Syslog'
ufw --force enable
info "Firewall activé — ports ouverts : 22/tcp, 80/tcp, 443/tcp, 514/udp"

# ─── 5. Cloner le dépôt ──────────────────────────────────────────────────────
REPO_DIR="/opt/siem"
step "Clonage du projet dans $REPO_DIR..."

if [ ! -d "$REPO_DIR/.git" ]; then
    echo ""
    read -p "  URL du dépôt Git (ex: https://github.com/EmmanuelTAHI/PFE.git) : " REPO_URL
    git clone "$REPO_URL" "$REPO_DIR"
    info "Projet cloné."
else
    info "Dépôt existant — mise à jour..."
    cd "$REPO_DIR" && git pull origin main
fi

cd "$REPO_DIR"
chmod +x deploy.sh install.sh 2>/dev/null || true

# ─── 6. Configuration du fichier .env ────────────────────────────────────────
step "Configuration des variables d'environnement..."

if [ ! -f .env ]; then
    cp .env.production.example .env

    random()     { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
    fernet_key() { python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || random 32; }

    SECRET_KEY_VAL=$(random 50)
    DB_PASSWORD_VAL=$(random 24)
    ADMIN_PASSWORD_VAL=$(random 16)
    ENCRYPTION_KEY_VAL=$(fernet_key)

    # Détection automatique de l'IP publique du VPS
    VPS_IP=$(curl -4 -s --max-time 5 ifconfig.me 2>/dev/null \
          || curl -4 -s --max-time 5 ipecho.net/plain 2>/dev/null \
          || curl -4 -s --max-time 5 api.ipify.org 2>/dev/null \
          || echo "0.0.0.0")
    info "IP publique du VPS : $VPS_IP"

    sed -i \
        -e "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY_VAL}|" \
        -e "s|^DB_PASSWORD=.*|DB_PASSWORD=${DB_PASSWORD_VAL}|" \
        -e "s|^DJANGO_SUPERUSER_PASSWORD=.*|DJANGO_SUPERUSER_PASSWORD=${ADMIN_PASSWORD_VAL}|" \
        -e "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY_VAL}|" \
        -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://siem_user:${DB_PASSWORD_VAL}@db:5432/siem_db|" \
        -e "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${VPS_IP},localhost,127.0.0.1|" \
        -e "s|^FRONTEND_URL=.*|FRONTEND_URL=http://${VPS_IP}|" \
        -e "s|^BACKEND_URL=.*|BACKEND_URL=http://${VPS_IP}|" \
        -e "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=http://${VPS_IP}|" \
        .env

    info "Fichier .env généré avec des secrets aléatoires."
    warn "Si vous avez un nom de domaine, éditez .env et mettez à jour ALLOWED_HOSTS, FRONTEND_URL, BACKEND_URL, CORS_ALLOWED_ORIGINS."
else
    info ".env déjà existant — configuration conservée."
fi

# ─── 7. Démarrage de la stack ─────────────────────────────────────────────────
step "Démarrage de la stack Docker en mode production..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# ─── 8. Attente des services ─────────────────────────────────────────────────
step "Attente du démarrage des services (jusqu'à 3 minutes)..."
TIMEOUT=60
COUNT=0
echo -n "  "
while [ $COUNT -lt $TIMEOUT ]; do
    if docker compose ps backend 2>/dev/null | grep -qE "Up|running"; then
        echo ""
        break
    fi
    echo -n "."
    sleep 3
    COUNT=$((COUNT + 1))
done
echo ""

# ─── 9. Résumé ────────────────────────────────────────────────────────────────
ADMIN_EMAIL=$(grep -E '^DJANGO_SUPERUSER_EMAIL=' .env | cut -d= -f2-)
ADMIN_PASS=$(grep -E '^DJANGO_SUPERUSER_PASSWORD=' .env | cut -d= -f2-)
VPS_IP=$(curl -4 -s --max-time 5 ifconfig.me 2>/dev/null || echo "VOTRE_IP")

echo ""
echo "  =============================================="
echo "   Log+ déployé avec succès !"
echo "  =============================================="
echo ""
echo "  Interface web    : http://${VPS_IP}"
echo "  API              : http://${VPS_IP}/api/"
echo "  Admin Django     : http://${VPS_IP}/admin/"
echo ""
echo "  Compte administrateur :"
echo "    Email          : ${ADMIN_EMAIL}"
echo "    Mot de passe   : ${ADMIN_PASS}"
echo ""
echo "  Commandes utiles :"
echo "    Voir les logs  : docker compose logs -f"
echo "    Arrêter        : docker compose -f docker-compose.yml -f docker-compose.prod.yml down"
echo "    Mettre à jour  : cd ${REPO_DIR} && ./deploy.sh"
echo ""
warn "Conservez ces identifiants dans un endroit sûr !"
echo ""
