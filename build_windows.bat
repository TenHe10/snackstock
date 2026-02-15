@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

echo [1/5] Checking environment...
where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    set "USE_UV=1"
) else (
    set "USE_UV=0"
)

set "PY_CMD="
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PY_CMD=py"
    )
)

if "!USE_UV!"=="0" if "!PY_CMD!"=="" (
    echo ERROR: Neither uv nor python/py found.
    echo Please activate your conda env first, for example:
    echo   conda activate snackstock
    exit /b 1
)

echo [2/5] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist SnackStock.spec del /f /q SnackStock.spec

echo [3/5] Installing dependencies...
if "!USE_UV!"=="1" (
    call uv sync
    if not %ERRORLEVEL%==0 (
        echo ERROR: uv sync failed.
        exit /b 1
    )
    echo [4/5] Building with PyInstaller via uv...
    call uv run pyinstaller --noconfirm --clean --windowed --name SnackStock main.py
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyInstaller build failed.
        exit /b 1
    )
) else (
    call !PY_CMD! -m pip install -r requirements.txt
    if not %ERRORLEVEL%==0 (
        echo ERROR: pip install requirements failed.
        exit /b 1
    )
    call !PY_CMD! -m pip install pyinstaller
    if not %ERRORLEVEL%==0 (
        echo ERROR: pip install pyinstaller failed.
        exit /b 1
    )
    echo [4/5] Building with PyInstaller via !PY_CMD!...
    call !PY_CMD! -m PyInstaller --noconfirm --clean --windowed --name SnackStock main.py
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyInstaller build failed.
        exit /b 1
    )
)

echo [5/5] Build completed.
echo Output: dist\SnackStock\SnackStock.exe
exit /b 0
