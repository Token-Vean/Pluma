@echo off
REM =============================================================================
REM PlumA - instalador para Windows en modo local bloqueado
REM -----------------------------------------------------------------------------
REM A partir de v0.6 el instalador detecta si tienes Ollama nativo en el host
REM con el modelo base ya descargado. Si lo tiene, configura PlumA para usarlo
REM via host.docker.internal:11434 y NO arranca el contenedor de Ollama. Si no,
REM activa el perfil `bundled` de Docker Compose y levanta Ollama dentro de
REM Docker como antes.
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
echo [3/6] Aplicando configuracion local bloqueada y detectando Ollama...
REM El PS1 imprime al final la linea "PLUMA_INSTALADOR_PROFILE=bundled" o vacio.
REM Capturamos esa linea para saber que profile de Compose activar.
set "PLUMA_PROFILE="
for /f "usebackq tokens=1,* delims==" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\windows\enforce-local-config.ps1"`) do (
    if /I "%%A"=="PLUMA_INSTALADOR_PROFILE" set "PLUMA_PROFILE=%%B"
)
if errorlevel 1 (
    echo ERROR: No se pudo sanear la configuracion local.
    pause
    exit /b 1
)
echo OK - Configuracion saneada

echo.
echo [4/6] Preparando imagen y servicios...
if defined PLUMA_PROFILE (
    set "COMPOSE_PROFILES=%PLUMA_PROFILE%"
    echo Modo: container ^(Ollama se levantara dentro de Docker^)
) else (
    set "COMPOSE_PROFILES="
    echo Modo: host ^(la app usara el Ollama nativo del sistema^)
)
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
if not defined PLUMA_PROFILE (
    echo AVISO de seguridad - Ollama nativo
    echo ----------------------------------------
    echo Comprueba que tu Ollama del host esta escuchando SOLO en localhost.
    echo Por defecto, Ollama escucha en 0.0.0.0:11434, lo que significa que
    echo cualquier dispositivo en tu red puede enviarle peticiones.
    echo.
    echo Para limitarlo a tu equipo en Windows, define la variable de entorno
    echo del sistema:
    echo    OLLAMA_HOST=127.0.0.1
    echo y reinicia Ollama. Mas detalles en INSTALACION.md.
    echo.
)
pause
