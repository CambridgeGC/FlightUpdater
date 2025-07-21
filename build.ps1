param (
    [string]$Tag = "__DEV__VERSION__"
)

# Check if Python 3.13 is installed
$pythonCheck = py -3.13 -V 2>&1
if ($pythonCheck -match "not be located" -or $pythonCheck -contains "No suitable") {
    Write-Host "Python 3.13 not found. Install / activate Python 3.13"
    exit 1
}

# Check if Poetry is installed
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Host "Poetry not found. Installing Poetry..."
    pip install poetry
}

# Set up environment for poetry
poetry env use (py -3.13 -c "import sys; print(sys.executable)")
poetry add --group dev pyinstaller

# Install dependencies
poetry install --with-dev *> install_output.txt

if (Select-String -Path "install_output.txt" -Pattern "pyproject.toml changed significantly since poetry.lock was last generated") {
    Write-Host "Detected outdated poetry.lock, running poetry lock..."
    poetry lock
    Write-Host "Re-running poetry install..."
    poetry install --no-root --with-dev
} else {
    Write-Host "Poetry install completed without lock file errors."
}

Remove-Item "install_output.txt"

# Inject version tag into version.txt
$Tag | Out-File -Encoding ASCII version.txt

# Replace tag in config.py
(Get-Content config.py) -replace '__DEV__VERSION__', $Tag | Set-Content config.py

# Build executable with PyInstaller via Poetry
poetry run pyinstaller --clean --onefile --name "FlightUpdater_$Tag" --add-data="version.txt;version.txt" main.py

# Copy config.json.template to dist/config.json
Copy-Item -Path "config.json.template" -Destination "dist\config.json" -Force

Write-Host ""
Write-Host "Build complete. Executable is dist\FlightUpdater_$Tag.exe"
Write-Host "Remember to EDIT dist\config.json and enter the correct information (url, API key, ...)"
Pause
