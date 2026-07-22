#!/usr/bin/env bash
# Installe le démon de blocage réseau réel sur l'hôte VPS (hors Docker).
# Usage : sudo ./install.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Ce script doit être exécuté en root (sudo)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/argus-firewall-agent"
CONFIG_DIR="/etc/argus-firewall-agent"

echo "-> Création de l'utilisateur système dédié (argus-fw, sans shell, sans home)..."
if ! id -u argus-fw >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin argus-fw
fi

echo "-> Installation des fichiers..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"
cp "$SCRIPT_DIR/firewall_agent.py" "$INSTALL_DIR/firewall_agent.py"
cp "$SCRIPT_DIR/argus-ufw-block" /usr/local/sbin/argus-ufw-block
cp "$SCRIPT_DIR/argus-ufw-unblock" /usr/local/sbin/argus-ufw-unblock
chmod 755 /usr/local/sbin/argus-ufw-block /usr/local/sbin/argus-ufw-unblock
chmod 750 "$INSTALL_DIR"
chown -R argus-fw:argus-fw "$INSTALL_DIR"

echo "-> Génération du jeton d'authentification..."
if [ ! -f "$CONFIG_DIR/token" ]; then
  TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "$TOKEN" > "$CONFIG_DIR/token"
else
  TOKEN=$(cat "$CONFIG_DIR/token")
  echo "   (jeton déjà existant, conservé)"
fi
chmod 600 "$CONFIG_DIR/token"
chown argus-fw:argus-fw "$CONFIG_DIR/token"

echo "-> Écriture de la règle sudoers restreinte (2 binaires précis, jamais ALL)..."
cat > /etc/sudoers.d/argus-firewall <<'EOF'
# Autorise UNIQUEMENT l'utilisateur argus-fw à exécuter ces deux scripts
# précis, sans mot de passe (nécessaire pour un appel depuis un démon non
# interactif) -- jamais un accès root plus large.
argus-fw ALL=(root) NOPASSWD: /usr/local/sbin/argus-ufw-block, /usr/local/sbin/argus-ufw-unblock
EOF
chmod 440 /etc/sudoers.d/argus-firewall
visudo -c -f /etc/sudoers.d/argus-firewall

echo "-> Installation du service systemd..."
cp "$SCRIPT_DIR/argus-firewall-agent.service" /etc/systemd/system/argus-firewall-agent.service
systemctl daemon-reload
systemctl enable --now argus-firewall-agent.service

echo ""
echo "Terminé. Le démon écoute sur le port 8765 (bloqué depuis l'extérieur par la politique par défaut d'ufw, atteignable uniquement depuis les conteneurs Docker locaux)."
echo "Jeton (à mettre dans le .env du SIEM comme HOST_FIREWALL_TOKEN) :"
echo "  $TOKEN"
echo ""
echo "Vérification : curl http://127.0.0.1:8765/healthz"
systemctl status argus-firewall-agent.service --no-pager || true
