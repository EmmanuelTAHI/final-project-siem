#Requires -Version 5.1
<#
.SYNOPSIS
  Installe l'agent Log+ natif sur Windows (service natif via SCM).
.DESCRIPTION
  Telecharge le binaire depuis l'instance Log+ elle-meme (aucune dependance
  externe, pas de NXLog), verifie son integrite (SHA-256) avant execution,
  s'eleve en administrateur si necessaire, puis installe le service.
.EXAMPLE
  # Telecharge et execute depuis le tableau de bord Agents :
  .\install-windows.ps1 -Url "https://logplus.duckdns.org" -Token "logplus_agt_xxxxx"
.NOTES
  Ce fichier est volontairement en ASCII pur (pas d'accents, pas de
  caracteres speciaux) : Windows PowerShell 5.1 lit un script .ps1 sans BOM
  avec l'encodage ANSI du systeme (pas UTF-8), ce qui corrompt tout
  caractere non-ASCII et peut casser la syntaxe (chaine mal terminee).
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
    Write-Host "Droits administrateur requis - relance avec elevation..."
    $argList = @("-Url", $Url, "-Token", $Token)
    if ($Insecure) { $argList += "-Insecure" }
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) {
        throw "Ce script doit etre enregistre dans un fichier local avant execution elevee (pas de relance possible depuis un pipeline 'iex' direct)."
    }
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath) + $argList)
    exit 0
}

$arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { throw "Architecture 32 bits non supportee." }
$binName = "logplus-agent-windows-$arch.exe"
$baseUrl = $Url.TrimEnd("/")
$downloadUrl = "$baseUrl/agents/$binName"
$checksumUrl = "$downloadUrl.sha256"

$tmpDir = Join-Path $env:TEMP "logplus-agent-install"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$binPath = Join-Path $tmpDir $binName
$checksumPath = "$binPath.sha256"

try {
    Write-Host "Telechargement de $binName..."
    Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $binPath
    Invoke-WebRequest -UseBasicParsing -Uri $checksumUrl -OutFile $checksumPath

    Write-Host "Verification de l'integrite (SHA-256)..."
    $expected = (Get-Content $checksumPath).Split(" ")[0].Trim().ToLower()
    $actual = (Get-FileHash -Path $binPath -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) {
        throw "Somme de controle invalide : binaire potentiellement corrompu ou altere. Installation annulee.`nAttendu: $expected`nObtenu : $actual"
    }
    Write-Host "Integrite verifiee."

    $installArgs = @("install", "--url", $Url)
    if ($Insecure) { $installArgs += "--insecure" }

    # Le token passe par variable d'environnement, pas en argument : un
    # argument de ligne de commande reste visible dans la colonne "Ligne de
    # commande" du Gestionnaire des taches tant que le processus tourne.
    $env:LOGPLUS_AGENT_TOKEN = $Token
    try {
        & $binPath @installArgs
        if ($LASTEXITCODE -ne 0) {
            throw "L'installation de l'agent a echoue (code $LASTEXITCODE)."
        }
    }
    finally {
        Remove-Item Env:\LOGPLUS_AGENT_TOKEN -ErrorAction SilentlyContinue
    }
}
finally {
    Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Termine - l'agent Log+ tourne comme service Windows (demarrage automatique)."
