# ============================================================
# Log+ — installation en une commande (Windows / PowerShell)
#
# Usage : .\install.ps1
#
# Ce script :
#   1. vérifie que Docker / Docker Compose sont installés
#   2. crée .env depuis .env.example (si absent) et génère des secrets
#      aléatoires (SECRET_KEY, mots de passe DB, clé de chiffrement)
#   3. construit et démarre toute la stack (docker compose up -d --build)
#   4. attend que les services soient prêts
#   5. affiche les identifiants du compte administrateur
# ============================================================

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Write-Bold($text) { Write-Host $text -ForegroundColor Cyan }
function Write-Step($text) { Write-Host "  -> $text" }

Write-Bold "Log+ — installation"

# 1. Vérification des prérequis
try {
    docker --version | Out-Null
} catch {
    Write-Host "Docker n'est pas installé. Voir https://docs.docker.com/get-docker/" -ForegroundColor Red
    exit 1
}
try {
    docker compose version | Out-Null
} catch {
    Write-Host "Le plugin 'docker compose' est introuvable. Installez Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Step "Docker et Docker Compose détectés."

function New-RandomString([int]$Length) {
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Replace("+","").Replace("/","").Replace("=","").Substring(0, $Length)
}

function New-FernetKey {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Replace("+","-").Replace("/","_")
}

# 2. Préparation du fichier .env
if (-not (Test-Path ".env")) {
    Write-Step "Création de .env depuis .env.example..."
    Copy-Item ".env.example" ".env"

    $secretKey = New-RandomString 50
    $dbPassword = New-RandomString 24
    $adminPassword = New-RandomString 16
    $encryptionKey = New-FernetKey

    $content = Get-Content ".env"
    $content = $content -replace '^SECRET_KEY=.*', "SECRET_KEY=$secretKey"
    $content = $content -replace '^DB_PASSWORD=.*', "DB_PASSWORD=$dbPassword"
    $content = $content -replace '^DJANGO_SUPERUSER_PASSWORD=.*', "DJANGO_SUPERUSER_PASSWORD=$adminPassword"
    $content = $content -replace '^ENCRYPTION_KEY=.*', "ENCRYPTION_KEY=$encryptionKey"
    $content = $content -replace '^DATABASE_URL=.*', "DATABASE_URL=postgresql://siem_user:$dbPassword@db:5432/siem_db"
    Set-Content ".env" $content

    Write-Step "Secrets générés automatiquement dans .env"
} else {
    Write-Step ".env existe déjà, conservation de la configuration actuelle."
}

# 3. Démarrage de la stack
Write-Bold "Construction et démarrage des conteneurs (cela peut prendre quelques minutes)..."
docker compose up -d --build

# 4. Attente des services
Write-Bold "Attente du démarrage des services..."
for ($i = 0; $i -lt 60; $i++) {
    $status = docker compose ps backend 2>$null
    if ($status -match "running|Up") { break }
    Start-Sleep -Seconds 2
}

# 5. Récapitulatif
$envContent = Get-Content ".env"
$adminEmail = ($envContent | Where-Object { $_ -match '^DJANGO_SUPERUSER_EMAIL=' }) -replace '^DJANGO_SUPERUSER_EMAIL=', ''
$adminPasswordOut = ($envContent | Where-Object { $_ -match '^DJANGO_SUPERUSER_PASSWORD=' }) -replace '^DJANGO_SUPERUSER_PASSWORD=', ''

Write-Host ""
Write-Bold "Log+ est démarré !"
Write-Host "  Interface web          : http://localhost:3000"
Write-Host "  API backend            : http://localhost:8000"
Write-Host "  Compte administrateur :"
Write-Host "    Email        : $adminEmail"
Write-Host "    Mot de passe : $adminPasswordOut"
Write-Host ""
Write-Host "  (ces identifiants sont aussi stockés dans le fichier .env)"
Write-Host ""
Write-Host "Pour arrêter   : docker compose down"
Write-Host "Pour voir les logs : docker compose logs -f"
