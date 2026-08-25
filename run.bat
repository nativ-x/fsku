@echo off
REM FSKU Runner for Windows
SETLOCAL

where python >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
    python fsku_cli.py serve --host 127.0.0.1 --port 8000
    GOTO :EOF
)

where py >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
    py fsku_cli.py serve --host 127.0.0.1 --port 8000
    GOTO :EOF
)

where wsl >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
    echo Launching FSKU via WSL...
    wsl bash -c "cd /mnt/d/apps/sku_futures && python3 fsku_cli.py serve --host 0.0.0.0 --port 8000"
    GOTO :EOF
)

echo [ERROR] Neither Python nor WSL was detected on your system.
pause
