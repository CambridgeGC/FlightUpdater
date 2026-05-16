$ErrorActionPreference = "Stop"

function Run-Exit-On-Error {
    param([string]$cmd)

    Write-Host "Running: $cmd"
    Invoke-Expression $cmd

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $cmd with exit code $LASTEXITCODE"
    }
}

# Always run from script folder
Set-Location $PSScriptRoot

$MainFile = "src\main.py"
$ConfigFile = "src\config.py"
$WorkPath = "$env:TEMP\FlightUpdater_build"

# Check Python 3.13
$pythonCheck = py -3.13 -V 2>&1

if ($pythonCheck -match "not be located" -or $pythonCheck -match "No suitable") {
    throw "Python 3.13 not found. Install / activate Python 3.13"
}

Write-Host "Python 3.13 found: $pythonCheck"

# Ensure Poetry path exists in fresh PowerShell / VS Code sessions
$env:Path += ";$env:APPDATA\Python\Scripts"

if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    throw "Poetry not found. Install Poetry first."
}

Write-Host "Poetry found"

# Sanity checks
if (-not (Test-Path "pyproject.toml")) {
    throw "pyproject.toml not found"
}

if (-not (Test-Path $MainFile)) {
    throw "Main file not found: $MainFile"
}

if (-not (Test-Path $ConfigFile)) {
    throw "Config file not found: $ConfigFile"
}

# Install/update dependencies
Run-Exit-On-Error "poetry install --no-root"

# Version comes from pyproject.toml
$Tag = (poetry version -s).Trim()

if (-not $Tag) {
    throw "Could not read version from pyproject.toml"
}

Write-Host "Building FlightUpdater version $Tag"

# Write version into src\config.py
$configText = Get-Content $ConfigFile -Raw

if ($configText -notmatch 'VERSION\s*=\s*".*"') {
    throw "VERSION setting not found in $ConfigFile"
}

$configText = $configText -replace 'VERSION\s*=\s*".*"', "VERSION = `"$Tag`""
Set-Content -Path $ConfigFile -Value $configText -Encoding UTF8

Write-Host "Updated $ConfigFile with VERSION = $Tag"

# Clean old build outputs
Write-Host "Cleaning old build folders..."

if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}

if (Test-Path $WorkPath) {
    Remove-Item -Recurse -Force $WorkPath
}

# Build executable
Write-Host "Building executable..."

Run-Exit-On-Error "poetry run pyinstaller --clean --onefile --workpath `"$WorkPath`" --name `"FlightUpdater_$Tag`" --paths `"src;..\glidinglib\src`" --hidden-import=tkcalendar `"$MainFile`""

$ExePath = "dist\FlightUpdater_$Tag.exe"

if (-not (Test-Path $ExePath)) {
    throw "PyInstaller failed - executable not created: $ExePath"
}

# Copy runtime config/mapping files
Write-Host "Copying runtime files..."

if (Test-Path "config.json") {
    Copy-Item -Path "config.json" -Destination "dist\config.json" -Force
}

if (Test-Path "config.json.template") {
    Copy-Item -Path "config.json.template" -Destination "dist\config.json.template" -Force
}


Write-Host ""
Write-Host "✅ Build complete"
Write-Host "→ $ExePath"