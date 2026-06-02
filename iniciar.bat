@echo off
REM =============================================================================
REM PlumA - arranque cotidiano (Windows)
REM -----------------------------------------------------------------------------
REM Script ligero para arrancar PlumA cuando ya esta instalado. NO reconstruye
REM imagenes, NO descarga modelos, NO toca el .env. Solo levanta los
REM contenedores y abre el navegador.
REM
REM Respeta el modo elegido por el instalador (PLUMA_OLLAMA_MODE en .env):
REM   container  -> activa COMPOSE_PROFILES=bundled para levantar Ollama Docker.
REM   host       -> no activa profile; se usa el Ollama nativo del sistema.
REM
REM La primera vez, usa instalar.bat.
REM Para detener: detener.bat.
REM =============================================================================
setlocal EnableDelayedExpansion
if exist "%~dp0tools\windows\pluma-env.bat" call "%~dp0tools\windows\pluma-env.bat" >nul 2>nul
cd /d "%~dp0"

echo.
echo PlumA - arranque
echo --------------------
echo.

echo [1/3] Comprobando Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta arrancado.
    echo Abre Docker Desktop y vuelve a intentarlo.
    pause
    exit /b 1
)
echo OK - Docker disponible

echo.
echo [2/3] Levantando servicios...
set "MODO=container"
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PLUMA_OLLAMA_MODE=" .env 2^>nul') do set "MODO=%%a"
)
if /I "!MODO!"=="host" (
    set "COMPOSE_PROFILES="
    echo Modo: host ^(la app usara el Ollama nativo^)
) else (
    set "COMPOSE_PROFILES=bundled"
    echo Modo: container ^(se levantara el Ollama de Docker^)
)
docker compose up -d
if errorlevel 1 (
    echo ERROR: No se pudieron arrancar los servicios.
    echo Si es la primera vez, ejecuta instalar.bat en su lugar.
    pause
    exit /b 1
)
echo OK - Servicios arrancados

echo.
echo [3/3] Esperando a que la aplicacion responda...
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
echo AVISO - PlumA tarda mas de lo habitual. Puede estar cargando el modelo.
:open
echo.
echo Abriendo PlumA en el navegador...
start "" "http://localhost:!PUERTO!"
echo.
echo URL: http://localhost:!PUERTO!
echo Para detener: detener.bat
echo.
pause
