@echo off
REM Check if pipreqs is installed
pip show pipreqs >nul 2>&1
if errorlevel 1 (
    echo pipreqs not found, installing...
    pip install pipreqs
    if errorlevel 1 (
        echo Failed to install pipreqs. Please install it manually.
        goto :eof
    )
) else (
    echo pipreqs is installed.
)

REM Check if poetry is installed
where poetry >nul 2>&1
if errorlevel 1 (
    echo Poetry not found in PATH. Please install Poetry before running this script.
    pause
    goto :eof
) else (
    echo Poetry is installed.
)

REM Check if pyproject.toml exists, and create it if not
if not exist pyproject.toml (
    echo pyproject.toml not found. Initializing poetry project...
    echo | poetry init --no-interaction
    if errorlevel 1 (
        echo Failed to initialize poetry project.
        goto :eof
    )
) else (
    echo pyproject.toml already exists.
)

REM Run pipreqs to generate requirements.txt in current directory
pipreqs . --force
if errorlevel 1 (
    echo pipreqs failed. Please check if it is installed and try again.
    goto :eof
)

REM Read requirements.txt line by line and add each package to poetry
for /f "usebackq tokens=1 delims==>< " %%a in ("requirements.txt") do (
    echo Adding package %%a to poetry...
    poetry add %%a
    if errorlevel 1 (
        echo Failed to add package %%a to poetry.
    )
)

REM Delete requirements.txt
del requirements.txt

echo Done!
pause