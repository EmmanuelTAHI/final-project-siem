#!/usr/bin/env bash
# Compile l'agent Log+ pour toutes les plateformes cibles (statique,
# CGO_ENABLED=0) et génère les sommes de contrôle SHA-256 à côté de chaque
# binaire — utilisé aussi bien en local (Git Bash) que sur le VPS.
set -euo pipefail
cd "$(dirname "$0")"

DIST="dist"
BINARY="logplus-agent"

mkdir -p "$DIST"

build() {
  local os="$1" arch="$2" out="$3"
  echo "Build $os/$arch -> $out"
  GOOS="$os" GOARCH="$arch" CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o "$DIST/$out" ./cmd/$BINARY
}

build linux amd64 "${BINARY}-linux-amd64"
build linux arm64 "${BINARY}-linux-arm64"
build windows amd64 "${BINARY}-windows-amd64.exe"

echo "Génération des sommes de contrôle SHA-256..."
cd "$DIST"
if command -v sha256sum >/dev/null 2>&1; then
  for f in ${BINARY}-linux-amd64 ${BINARY}-linux-arm64 ${BINARY}-windows-amd64.exe; do
    sha256sum "$f" > "$f.sha256"
  done
else
  # macOS / environnements sans sha256sum
  for f in ${BINARY}-linux-amd64 ${BINARY}-linux-arm64 ${BINARY}-windows-amd64.exe; do
    shasum -a 256 "$f" > "$f.sha256"
  done
fi

cd ..
echo "Copie des scripts d'installation..."
cp scripts/install-linux.sh "$DIST/"
cp scripts/install-windows.ps1 "$DIST/"

echo "Build terminé :"
ls -la "$DIST"
