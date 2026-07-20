#Requires -Version 5.1
<#
.SYNOPSIS
  Installe l'agent Log+ natif sur Windows (service natif via SCM).
.DESCRIPTION
  Télécharge le binaire depuis l'instance Log+ elle-même (aucune dépendance
  externe, pas de NXLog), vérifie son intégrité (SHA-256) avant exécution,
  s'élève en administrateur si nécessaire, puis installe le service.
.EXAMPLE
  # Téléchargé et exécuté depuis le tableau de bord Agents :
  .\install-windows.ps1 -Url "https://logplus.duckdns.org" -Token "logplus_agt_xxxxx"
#>
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Token,
    [switch]$Insecure
)

$ErrorActionPreference = "Stop"

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "Droits administrateur requis — relance avec élévation..."
    $argList = @("-Url", $Url, "-Token", $Token)
    if ($Insecure) { $argList += "-Insecure" }
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) {
        throw "Ce script doit être enregistré dans un fichier local avant exécution élevée (pas de relance possible depuis un pipeline 'iex' direct)."
    }
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath) + $argList)
    exit 0
}

$arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { throw "Architecture 32 bits non supportée." }
$binName = "logplus-agent-windows-$arch.exe"
$baseUrl = $Url.TrimEnd("/")
$downloadUrl = "$baseUrl/agents/$binName"
$checksumUrl = "$downloadUrl.sha256"

$tmpDir = Join-Path $env:TEMP "logplus-agent-install"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$binPath = Join-Path $tmpDir $binName
$checksumPath = "$binPath.sha256"

try {
    Write-Host "Téléchargement de $binName..."
    Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $binPath
    Invoke-WebRequest -UseBasicParsing -Uri $checksumUrl -OutFile $checksumPath

    Write-Host "Vérification de l'intégrité (SHA-256)..."
    $expected = (Get-Content $checksumPath).Split(" ")[0].Trim().ToLower()
    $actual = (Get-FileHash -Path $binPath -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) {
        throw "Somme de contrôle invalide : binaire potentiellement corrompu ou altéré. Installation annulée.`nAttendu: $expected`nObtenu : $actual"
    }
    Write-Host "Intégrité vérifiée."

    $installArgs = @("install", "--url", $Url)
    if ($Insecure) { $installArgs += "--insecure" }

    # Le token passe par variable d'environnement, pas en argument : un
    # argument de ligne de commande reste visible dans la colonne "Ligne de
    # commande" du Gestionnaire des tâches tant que le processus tourne.
    $env:LOGPLUS_AGENT_TOKEN = $Token
    try {
        & $binPath @installArgs
        if ($LASTEXITCODE -ne 0) {
            throw "L'installation de l'agent a échoué (code $LASTEXITCODE)."
        }
    }
    finally {
        Remove-Item Env:\LOGPLUS_AGENT_TOKEN -ErrorAction SilentlyContinue
    }
}
finally {
    Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Terminé — l'agent Log+ tourne comme service Windows (démarrage automatique)."
