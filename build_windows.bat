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

where py >nul 2>nul
if not %ERRORLEVEL%==0 (
    echo ERROR: Python launcher ^(py^) not found. Please install Python 3.13 first.
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
    call py -m pip install -r requirements.txt
    if not %ERRORLEVEL%==0 (
        echo ERROR: pip install requirements failed.
        exit /b 1
    )
    call py -m pip install pyinstaller
    if not %ERRORLEVEL%==0 (
        echo ERROR: pip install pyinstaller failed.
        exit /b 1
    )
    echo [4/5] Building with PyInstaller via py...
    call py -m PyInstaller --noconfirm --clean --windowed --name SnackStock main.py
    if not %ERRORLEVEL%==0 (
        echo ERROR: PyInstaller build failed.
        exit /b 1
    )
)

echo [5/5] Build completed.
echo Output: dist\SnackStock\SnackStock.exe
exit /b 0
