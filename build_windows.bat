@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not exist main.py (
    echo ERROR: main.py not found in current directory: %CD%
    exit /b 1
)

if not exist pyproject.toml (
    echo ERROR: pyproject.toml not found in current directory: %CD%
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

echo [3/6] Verifying runtime environment...
call uv run python -c "import sys; import PyQt6; from PyQt6 import QtCore, QtGui, QtWidgets; print(sys.executable)"
if errorlevel 1 (
    echo ERROR: PyQt6 is not importable in uv environment.
    exit /b 1
)

echo [4/6] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist SnackStock.spec del /f /q SnackStock.spec
if exist dist (
    echo ERROR: dist folder is locked by another process.
    echo Please close SnackStock.exe and retry.
    exit /b 1
)

echo [5/6] Building executable with PyInstaller in uv environment...
call uv run --with pyinstaller python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name SnackStock ^
    --runtime-hook hooks\pyi_rth_pyqt6_path.py ^
    --collect-all PyQt6 ^
    --hidden-import PyQt6 ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    main.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo [6/6] Verifying build output...
if not exist dist\SnackStock\SnackStock.exe (
    echo ERROR: Build finished but output exe not found.
    exit /b 1
)

echo Build completed successfully.
echo Output: dist\SnackStock\SnackStock.exe
exit /b 0
