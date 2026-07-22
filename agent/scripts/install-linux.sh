#!/usr/bin/env bash
# Installe l'agent Log+ natif sur Linux (systemd) : détecte l'architecture,
# télécharge le binaire depuis l'instance Log+ elle-même (aucune dépendance
# externe), vérifie son intégrité (SHA-256) avant de l'exécuter, puis
# installe le service.
#
# Usage :
#   curl -fsSL https://<votre-instance>/agents/install-linux.sh | sudo bash -s -- \
#     --url https://<votre-instance> --token argus_agt_xxxxx
set -euo pipefail

URL=""
TOKEN=""
INSECURE=""
SYSLOG_ADDR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --insecure) INSECURE="--insecure"; shift ;;
    --linux-syslog-addr) SYSLOG_ADDR="$2"; shift 2 ;;
    *) echo "Option inconnue: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$URL" ] || [ -z "$TOKEN" ]; then
  echo "Usage: install-linux.sh --url <https://...> --token <argus_agt_...> [--insecure] [--linux-syslog-addr <addr>]" >&2
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Ce script doit être exécuté en root (sudo)." >&2
  exit 1
fi

case "$(uname -m)" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Architecture non supportée: $(uname -m)" >&2; exit 1 ;;
esac

BIN_NAME="logplus-agent-linux-${ARCH}"
DOWNLOAD_URL="${URL%/}/agents/${BIN_NAME}"
CHECKSUM_URL="${DOWNLOAD_URL}.sha256"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "Téléchargement de ${BIN_NAME}..."
curl -fsSL "$DOWNLOAD_URL" -o "$TMPDIR/$BIN_NAME"
curl -fsSL "$CHECKSUM_URL" -o "$TMPDIR/$BIN_NAME.sha256"

echo "Vérification de l'intégrité (SHA-256)..."
EXPECTED="$(awk '{print $1}' "$TMPDIR/$BIN_NAME.sha256")"
ACTUAL="$(sha256sum "$TMPDIR/$BIN_NAME" | awk '{print $1}')"
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "ERREUR : somme de contrôle invalide, binaire potentiellement corrompu ou altéré. Installation annulée." >&2
  echo "Attendu: $EXPECTED" >&2
  echo "Obtenu : $ACTUAL" >&2
  exit 1
fi
echo "Intégrité vérifiée."

chmod +x "$TMPDIR/$BIN_NAME"

INSTALL_ARGS=(install --url "$URL")
[ -n "$INSECURE" ] && INSTALL_ARGS+=(--insecure)
[ -n "$SYSLOG_ADDR" ] && INSTALL_ARGS+=(--linux-syslog-addr "$SYSLOG_ADDR")

# Le token passe par variable d'environnement, pas en argument : un argument
# de ligne de commande reste visible en clair dans `ps aux` pour tout
# utilisateur du système tant que la commande tourne.
LOGPLUS_AGENT_TOKEN="$TOKEN" "$TMPDIR/$BIN_NAME" "${INSTALL_ARGS[@]}"
