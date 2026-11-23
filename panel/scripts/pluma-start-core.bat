@echo off
REM =============================================================================
REM pluma-start-core.bat
REM -----------------------------------------------------------------------------
REM Parte del panel del paquete para Windows (panel\PlumAPanel.ps1).
REM Arranque cotidiano no interactivo para el panel de Windows (equivale a
REM iniciar.bat). No toca el .env ni descarga modelos; construye la imagen solo
REM si no existe. Respeta el modo host/container elegido al instalar.
REM =============================================================================
setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PLUMA_DIR=%%~fI"
set "TOOLS_DIR=%PLUMA_DIR%\tools\windows"
call "%TOOLS_DIR%\pluma-env.bat" >nul 2>nul
cd /d "%PLUMA_DIR%"

if not exist ".env" (
    echo ERROR: PlumA aun no esta instalada en esta carpeta. Usa primero "Instalar".
    exit /b 1
)

echo [1/3] Comprobando Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta arrancado. Abre Docker Desktop y vuelve a intentarlo.
    exit /b 1
)
call "%SCRIPT_DIR%pluma-mode.bat"
echo OK - Docker disponible. Motor de IA: !PLUMA_OLLAMA_MODE!

echo [2/3] Levantando servicios...
set "APP_IMAGE="
for /f "usebackq delims=" %%I in (`docker compose config --images 2^>nul ^| findstr /B /C:"pluma-app"`) do set "APP_IMAGE=%%I"
set "NECESITA_BUILD=1"
if defined APP_IMAGE (
    docker image inspect "!APP_IMAGE!" >nul 2>&1
    if not errorlevel 1 set "NECESITA_BUILD=0"
)
if "!NECESITA_BUILD!"=="1" (
    echo No se encuentra la imagen de PlumA. Construyendola ^(puede tardar^)...
    docker compose up -d --build
) else (
    docker compose up -d
)
if errorlevel 1 (
    echo ERROR: No se pudieron arrancar los servicios. Si es la primera vez, usa "Instalar".
    exit /b 1
)

echo [3/3] Esperando a que PlumA responda...
call "%TOOLS_DIR%\pluma-wait-ready.bat"
if errorlevel 1 exit /b 1
echo PlumA en marcha en http://127.0.0.1:8082
exit /b 0
