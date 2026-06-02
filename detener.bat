@echo off
REM =============================================================================
REM PlumA - detener servicios
REM =============================================================================

setlocal EnableDelayedExpansion
if exist "%~dp0tools\windows\pluma-env.bat" call "%~dp0tools\windows\pluma-env.bat" >nul 2>nul

cd /d "%~dp0"

REM Recuperar modo del .env
set "MODO=container"
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PLUMA_OLLAMA_MODE=" .env 2^>nul') do set "MODO=%%a"
)
if /I "!MODO!"=="host" (
    set "COMPOSE_PROFILES="
) else (
    set "COMPOSE_PROFILES=bundled"
)

echo Deteniendo servicios...
docker compose down

echo.
echo Servicios detenidos.
echo.
echo Los datos y el modelo se conservan. Para volver a arrancar:
echo   iniciar.bat
echo.
echo Para eliminar TODO (contenedores, modelo descargado, configuracion):
echo   desinstalar.bat
echo.
pause
