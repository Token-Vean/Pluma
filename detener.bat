@echo off
REM =============================================================================
REM PlumA - detener servicios
REM =============================================================================

setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM Recuperar perfil del .env
set PERFIL=bundled,external
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PERFIL=" .env 2^>nul') do set PERFIL=%%a
)

set COMPOSE_PROFILES=!PERFIL!

echo Deteniendo servicios...
docker compose down

echo.
echo Servicios detenidos.
echo.
echo Los datos y el modelo se conservan. Para volver a arrancar, ejecuta:
echo   instalar.bat
echo.
echo Para eliminar TODO (contenedores, modelo descargado, configuracion):
echo   desinstalar.bat
echo.
pause
