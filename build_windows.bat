@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

if not exist requirements.txt (
    echo ERROR: requirements.txt not found in current directory: %CD%
    exit /b 1
)

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

if "!USE_UV!"=="0" (
    for /f %%v in ('!PY_CMD! -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set "PY_VER=%%v"
    if not "!PY_VER!"=="3.13" (
        echo ERROR: Python 3.13 is required, but current is !PY_VER!
        echo Please activate/create a conda env with Python 3.13:
        echo   conda create -n snackstock313 python=3.13 -y
        echo   conda activate snackstock313
        exit /b 1
    )
)

echo [2/5] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist SnackStock.spec del /f /q SnackStock.spec
if exist dist (
    echo ERROR: dist folder is still locked by another process.
    echo Please close SnackStock.exe and retry.
    exit /b 1
)

echo [3/5] Installing dependencies...
if "!USE_UV!"=="1" (
    call uv sync
    if not %ERRORLEVEL%==0 (
        echo ERROR: uv sync failed.
        exit /b 1
    )
    call uv run python -c "import PyQt6"
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyQt6 is not available in uv environment.
        exit /b 1
    )
    call uv run python -c "from PyQt6 import QtCore, QtGui, QtWidgets"
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyQt6 is installed but QtWidgets import failed in uv environment.
        exit /b 1
    )
    echo [4/5] Building with PyInstaller via uv...
    call uv run pyinstaller --noconfirm --clean --windowed --name SnackStock --collect-all PyQt6 --hidden-import PyQt6 --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets main.py
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
    call !PY_CMD! -m pip install PyQt6
    if not %ERRORLEVEL%==0 (
        echo ERROR: pip install PyQt6 failed.
        exit /b 1
    )
    call !PY_CMD! -c "import PyQt6"
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyQt6 import failed in current environment.
        exit /b 1
    )
    call !PY_CMD! -c "from PyQt6 import QtCore, QtGui, QtWidgets"
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyQt6 is installed but QtWidgets import failed in current environment.
        exit /b 1
    )
    echo [4/5] Building with PyInstaller via !PY_CMD!...
    call !PY_CMD! -m PyInstaller --noconfirm --clean --windowed --name SnackStock --collect-all PyQt6 --hidden-import PyQt6 --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets main.py
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyInstaller build failed.
        exit /b 1
    )
)

if not exist dist\SnackStock\SnackStock.exe (
    echo ERROR: Build finished but output exe not found.
    exit /b 1
)

echo [5/5] Build completed.
echo Output: dist\SnackStock\SnackStock.exe
exit /b 0
