@echo off
REM =============================================================================
REM PlumA - instalador para Windows en modo local bloqueado
REM =============================================================================
setlocal EnableDelayedExpansion
if exist "%~dp0tools\windows\pluma-env.bat" call "%~dp0tools\windows\pluma-env.bat" >nul 2>nul
cd /d "%~dp0"

echo.
echo PlumA - instalacion local bloqueada
echo ----------------------------------------
echo.

echo [1/6] Comprobando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta instalado.
    echo Descarga Docker Desktop desde: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker esta instalado pero no esta arrancado.
    echo Abre Docker Desktop y vuelve a intentarlo.
    pause
    exit /b 1
)
echo OK - Docker disponible

echo.
echo [2/6] Comprobando Docker Compose...
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose no esta disponible. Actualiza Docker Desktop.
    pause
    exit /b 1
)
echo OK - Docker Compose disponible

echo.
echo [3/6] Aplicando configuracion local bloqueada...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\windows\enforce-local-config.ps1"
if errorlevel 1 (
    echo ERROR: No se pudo sanear la configuracion local.
    pause
    exit /b 1
)
echo OK - Configuracion saneada

echo.
echo [4/6] Preparando imagen y servicios...
set COMPOSE_PROFILES=
docker compose up -d --build
if errorlevel 1 (
    echo ERROR: No se pudieron arrancar los servicios.
    pause
    exit /b 1
)
echo OK - Servicios arrancados

echo.
echo [5/6] Esperando a que la aplicacion responda...
set PUERTO=8082
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PUERTO=" .env 2^>nul') do set PUERTO=%%a
)
set MAX_INTENTOS=30
set INTENTO=0
:wait_loop
set /a INTENTO+=1
curl -sfm 2 http://localhost:!PUERTO!/api/estado >nul 2>&1
if not errorlevel 1 goto wait_ok
if !INTENTO! GEQ !MAX_INTENTOS! goto wait_timeout
timeout /t 1 /nobreak >nul
goto wait_loop
:wait_ok
echo OK - Aplicacion lista
goto open
:wait_timeout
echo AVISO - PlumA tarda mas de lo habitual. Puede estar descargando el modelo.
:open
echo.
echo [6/6] Abriendo PlumA...
start "" "http://localhost:!PUERTO!"
echo.
echo Instalacion completada en modo local bloqueado.
echo PlumA no admite endpoint remoto ni publicacion en red en esta release.
echo.
pause
