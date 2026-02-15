@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not exist pyproject.toml (
    echo ERROR: pyproject.toml not found in current directory: %CD%
    exit /b 1
)

if not exist SnackStock.spec (
    echo ERROR: SnackStock.spec not found in current directory: %CD%
    exit /b 1
)

echo [1/6] Checking uv...
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv not found.
    echo Please install uv first: https://docs.astral.sh/uv/
    exit /b 1
)

echo [2/6] Syncing dependencies with uv lock...
call uv sync --frozen
if errorlevel 1 (
    echo ERROR: uv sync --frozen failed.
    exit /b 1
)

echo [3/6] Verifying PyQt6 in uv environment...
call uv run python -c "import sys; from PyQt6 import QtCore, QtGui, QtWidgets; print(sys.executable)"
if errorlevel 1 (
    echo ERROR: PyQt6 import failed in uv environment.
    exit /b 1
)

echo [4/6] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist dist (
    echo ERROR: dist folder is locked by another process.
    echo Please close SnackStock.exe and retry.
    exit /b 1
)

echo [5/6] Building from SnackStock.spec...
call uv run --with pyinstaller python -m PyInstaller --noconfirm --clean SnackStock.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo [6/6] Validating bundled Qt runtime files...
if not exist dist\SnackStock\SnackStock.exe (
    echo ERROR: Build output missing: dist\SnackStock\SnackStock.exe
    exit /b 1
)
if not exist dist\SnackStock\_internal\PyQt6\Qt6\bin\Qt6Widgets.dll (
    echo ERROR: Missing Qt6Widgets.dll in bundle.
    echo Try upgrading pyinstaller and pyinstaller-hooks-contrib, then rebuild.
    exit /b 1
)
if not exist dist\SnackStock\_internal\PyQt6\Qt6\plugins\platforms\qwindows.dll (
    echo ERROR: Missing qwindows.dll platform plugin in bundle.
    echo Try upgrading pyinstaller and pyinstaller-hooks-contrib, then rebuild.
    exit /b 1
)

echo Build completed successfully.
echo Output: dist\SnackStock\SnackStock.exe
echo.
echo If launch still reports DLL load errors, install Microsoft Visual C++ 2015-2022 Redistributable (x64) and retry.
exit /b 0
