@echo off
REM =============================================================================
REM PlumA - desinstalacion
REM -----------------------------------------------------------------------------
REM Elimina los contenedores y, si procede, el volumen con el modelo
REM descargado dentro de Docker.
REM
REM Importante: si la instalacion uso el perfil "external", NO se toca
REM el Ollama ni los modelos del anfitrion.
REM =============================================================================

setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM Recuperar perfil del .env
set PERFIL=bundled,external
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PERFIL=" .env 2^>nul') do set PERFIL=%%a
)

echo.
echo Esta operacion va a eliminar:
echo   - Los contenedores Docker de PlumA.

if "!PERFIL!"=="bundled" (
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

set COMPOSE_PROFILES=!PERFIL!

echo.
echo Eliminando contenedores y volumenes...
docker compose down -v

docker image rm pluma-app >nul 2>&1

echo.
echo Desinstalacion completada.
echo.
echo Si quieres eliminar tambien los ficheros del proyecto,
echo borra esta carpeta manualmente.
echo.
pause
