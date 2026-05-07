param (
    [string]$Tag = "dev"
)

$ErrorActionPreference = "Stop"

function Run-Exit-On-Error {
    param([string]$cmd)

    Write-Host "Running: $cmd"
    Invoke-Expression $cmd

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed: $cmd with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

# Always run from script folder
Set-Location $PSScriptRoot

$MainFile = "src\main.py"
$VersionFile = "version.txt"
$TemplateConfig = "config.json.template"

# Sanity checks
if (-not (Test-Path "pyproject.toml")) {
    Write-Error "pyproject.toml not found"
    exit 1
}

if (-not (Test-Path $MainFile)) {
    Write-Error "Main file not found: $MainFile"
    exit 1
}

# Ensure dependencies installed
Run-Exit-On-Error "poetry install"

# Version from pyproject.toml
$BaseVersion = (poetry version -s).Trim()

if ($Tag -eq "dev") {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmm"
    $Version = "$BaseVersion-dev-$Stamp"
}
else {
    $Version = $BaseVersion
}

# Write version file
Write-Host "Writing version: $Version"
$Version | Out-File -Encoding ASCII $VersionFile

# Build EXE
Write-Host "Building executable..."

Run-Exit-On-Error "poetry run pyinstaller --clean --onefile --name `"FlightUpdater_$Version`" --paths `"src;..\glidinglib\src`" --add-data `"$VersionFile;$VersionFile`" --hidden-import=tkcalendar `"$MainFile`""

# Copy version file next to the EXE as a runtime fallback
Copy-Item $VersionFile "dist\version.txt" -Force

# Copy config template
if (Test-Path $TemplateConfig) {
    Write-Host "Copying config template..."
    Copy-Item $TemplateConfig "dist\config.json" -Force
}

Write-Host ""
Write-Host "✅ Build complete"
Write-Host "→ dist\FlightUpdater_$Version.exe"
Pause