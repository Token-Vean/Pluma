@echo off
if exist "%~dp0tools\windows\pluma-env.bat" call "%~dp0tools\windows\pluma-env.bat" >nul 2>nul
REM =============================================================================
REM PlumA - desinstalacion
REM -----------------------------------------------------------------------------
REM Elimina los contenedores y, si la instalacion uso el modo container, el
REM volumen Docker con el modelo descargado dentro de Ollama Docker.
REM
REM Importante: si la instalacion uso el modo host (Ollama nativo del equipo),
REM NO se toca el Ollama ni los modelos del anfitrion.
REM =============================================================================

setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM Recuperar modo del .env
set "MODO=container"
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PLUMA_OLLAMA_MODE=" .env 2^>nul') do set "MODO=%%a"
)

echo.
echo Esta operacion va a eliminar:
echo   - Los contenedores Docker de PlumA.

if /I "!MODO!"=="container" (
    echo   - El volumen Docker con el modelo de IA ^(3-5 GB^).
    echo.
    echo NO se eliminara:
    echo   - Docker ni ninguna otra aplicacion del sistema.
    echo   - La carpeta del proyecto.
) else (
    echo.
    echo NO se eliminara:
    echo   - Tu instalacion de Ollama en el equipo.
    echo   - Los modelos que tengas descargados en Ollama.
    echo   - Docker ni ninguna otra aplicacion del sistema.
    echo   - La carpeta del proyecto.
)
echo.

set /p CONFIRMACION=Para confirmar, escribe 'si' y pulsa Enter:

if not "!CONFIRMACION!"=="si" (
    echo Desinstalacion cancelada.
    pause
    exit /b 0
)

if /I "!MODO!"=="host" (
    set "COMPOSE_PROFILES="
) else (
    set "COMPOSE_PROFILES=bundled"
)

echo.
echo Eliminando contenedores y volumenes...
docker compose down -v

docker image rm pluma-app:0.6.0-beta >nul 2>&1
docker image rm pluma-app >nul 2>&1

echo.
echo Desinstalacion completada.
echo.
echo Si quieres eliminar tambien los ficheros del proyecto,
echo borra esta carpeta manualmente.
echo.
pause
