@echo off
REM ============================================================================
REM PlumA - instalador para Windows
REM ----------------------------------------------------------------------------
REM Doble clic en este fichero para instalar y arrancar PlumA.
REM
REM Requisito: Docker Desktop instalado y arrancado.
REM Descargalo gratis desde: https://www.docker.com/products/docker-desktop/
REM ============================================================================

setlocal enabledelayedexpansion

REM Localizar la carpeta donde esta este script
cd /d "%~dp0"

if not exist "sistema\" (
    echo.
    echo  ERROR: no encuentro la carpeta 'sistema'.
    echo  Descomprime el zip completo de PlumA y ejecuta el instalador desde
    echo  la carpeta raiz.
    echo.
    pause
    exit /b 1
)

cd sistema

echo.
echo PlumA - instalacion
echo ----------------------------------------
echo.

REM ------------------------------------------------------------
REM 1. Docker
REM ------------------------------------------------------------
echo [1/7] Comprobando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo    ERROR: Docker no esta instalado.
    echo    Descargalo desde: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo    ERROR: Docker no esta arrancado.
    echo    Abre Docker Desktop y vuelve a ejecutar este instalador.
    pause
    exit /b 1
)
echo    OK - Docker instalado y arrancado

REM ------------------------------------------------------------
REM 2. Docker Compose
REM ------------------------------------------------------------
echo [2/7] Comprobando Docker Compose...
docker compose version >nul 2>&1
if errorlevel 1 (
    echo    ERROR: Docker Compose no disponible. Actualiza Docker Desktop.
    pause
    exit /b 1
)
echo    OK - Docker Compose disponible

REM ------------------------------------------------------------
REM 3. Detectar Ollama
REM ------------------------------------------------------------
echo [3/7] Detectando motor de IA...
set PERFIL=bundled
curl -sfm 3 http://localhost:11434/api/tags >nul 2>&1
if not errorlevel 1 (
    set PERFIL=external
)

if "!PERFIL!"=="external" (
    echo    OK - Ollama detectado en el equipo
    echo        PlumA usara tu Ollama y los modelos que tengas.
) else (
    echo    OK - No se ha detectado Ollama en el equipo
    echo        Se instalara Ollama dentro de Docker ^(~4-5 GB la primera vez^).
)

REM ------------------------------------------------------------
REM 4. Puerto
REM ------------------------------------------------------------
echo [4/7] Comprobando puerto de la aplicacion...
set PUERTO=8082
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /B "PUERTO=" .env 2^>nul') do set PUERTO=%%a
)
echo    OK - Puerto !PUERTO! configurado

REM ------------------------------------------------------------
REM 5. Configuracion (.env)
REM ------------------------------------------------------------
echo [5/7] Preparando configuracion...
if exist .env (
    echo    OK - Configuracion (.env) ya existe
) else if exist .env.example (
    copy .env.example .env >nul
    echo    OK - Configuracion inicial creada
) else (
    echo    ERROR: no encuentro .env.example
    pause
    exit /b 1
)

REM Anadir/actualizar PERFIL y MODELO_BASE
findstr /B "PERFIL=" .env >nul 2>&1
if errorlevel 1 (
    echo PERFIL=!PERFIL!>> .env
) else (
    REM No hay sed nativo en Windows; reescribimos el fichero filtrado
    type .env | findstr /V "^PERFIL=" > .env.tmp
    echo PERFIL=!PERFIL!>> .env.tmp
    move /Y .env.tmp .env >nul
)

findstr /B "MODELO_BASE=" .env >nul 2>&1
if errorlevel 1 (
    echo MODELO_BASE=gemma4:e2b>> .env
)

REM ------------------------------------------------------------
REM 6. Construir y arrancar
REM ------------------------------------------------------------
echo [6/7] Preparando PlumA ^(la primera vez tarda 1-3 minutos^)...
set COMPOSE_PROFILES=!PERFIL!

docker compose build >nul 2>&1
if errorlevel 1 (
    echo    ERROR: fallo al construir la imagen.
    echo    Detalle:
    docker compose build
    pause
    exit /b 1
)
echo    OK - Imagen preparada

echo [7/7] Arrancando los servicios...
docker compose down >nul 2>&1
docker compose up -d
if errorlevel 1 (
    echo    ERROR: no se pudieron arrancar los servicios.
    echo    Causas habituales: puerto !PUERTO! ocupado, espacio en disco, permisos.
    pause
    exit /b 1
)
echo    OK - Servicios arrancados

REM ------------------------------------------------------------
REM Esperar a que la API responda
REM ------------------------------------------------------------
echo.
echo Esperando a que PlumA este lista...
set INTENTOS=0
:esperar
set /a INTENTOS+=1
curl -sfm 2 "http://localhost:!PUERTO!/api/estado" >nul 2>&1
if not errorlevel 1 goto :listo
if !INTENTOS! geq 30 goto :timeout
timeout /t 1 /nobreak >nul
goto :esperar

:listo
echo    OK - PlumA lista
goto :final

:timeout
echo    AVISO: tarda mas de lo habitual; abro el navegador igualmente.
echo           Si no carga, espera 30 segundos y refresca.

:final
echo.
echo ========================================
echo PlumA esta lista.
echo.
echo Abriendo el navegador en: http://localhost:!PUERTO!
echo.
echo Para parar PlumA:        ejecuta 2_DETENER.bat
echo Para desinstalar PlumA:  ejecuta 3_DESINSTALAR.bat
echo ========================================
echo.

start http://localhost:!PUERTO!

timeout /t 3 /nobreak >nul
endlocal
