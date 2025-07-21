param (
    [string]$Tag = "__DEV__VERSION__"
)

$ErrorActionPreference = "Stop"

function Run-Exit_On_Error {
    param([string]$cmd)
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed: $cmd with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}


# Check if Python 3.13 is installed
$pythonCheck = py -3.13 -V 2>&1
if ($pythonCheck -match "not be located" -or $pythonCheck -contains "No suitable") {
    Write-Host "Python 3.13 not found. Install / activate Python 3.13"
    exit 1
}else{
    "Python 3.13 found"
}

# Check if Poetry is installed
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Host "Poetry not found. Installing Poetry..."
    pip install poetry
}else{
    "Poetry found"
}

"Set up environment for poetry..."
Run-Exit_On_Error "poetry add --group dev pyinstaller"

"Install dependencies..."
Run-Exit_On_Error  "poetry install --no-root"

"Reading tag..."
$Tag | Out-File -Encoding ASCII version.txt

"Writing tag into config.py ..."
(Get-Content config.py) -replace '__DEV__VERSION__', $Tag | Set-Content config.py

"Building executable with PyInstaller via Poetry"
Run-Exit_On_Error 'poetry run pyinstaller --clean --onefile --name "FlightUpdater_$Tag" --add-data="version.txt;version.txt" --hidden-import=tkcalendar  main.py'

"Copying config.json.template to dist/config.json"
Copy-Item -Path "config.json.template" -Destination "dist\config.json" -Force

Write-Host ""
Write-Host "Build complete. Executable is dist\FlightUpdater_$Tag.exe"
Write-Host "Remember to EDIT dist\config.json and enter the correct information (url, API key, ...)"
Pause
