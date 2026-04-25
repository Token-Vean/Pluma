@echo off
REM ============================================================================
REM PlumA - desinstalacion
REM ----------------------------------------------------------------------------
REM Elimina los contenedores Docker, las imagenes y los volumenes de PlumA.
REM Los ficheros del proyecto en disco NO se borran: si quieres eliminar PlumA
REM por completo, borra tambien la carpeta tras ejecutar este script.
REM ============================================================================

cd /d "%~dp0"

if not exist "sistema\" (
    echo ERROR: no encuentro la carpeta 'sistema'.
    pause
    exit /b 1
)

cd sistema

echo.
echo PlumA - desinstalacion
echo.
echo Esta accion eliminara:
echo   - Los contenedores Docker de PlumA.
echo   - Las imagenes Docker (la proxima instalacion las reconstruira).
echo   - Los volumenes (modelos descargados de Ollama, ~5 GB liberados).
echo.
echo Los ficheros del proyecto en disco NO se borran; si quieres eliminar PlumA
echo por completo, borra tambien la carpeta del proyecto despues de este script.
echo.

set /p RESPUESTA="Continuar? (s/N): "
if /i not "%RESPUESTA%"=="s" (
    echo Cancelado. No se ha eliminado nada.
    pause
    exit /b 0
)

echo.
echo Eliminando contenedores y volumenes...
docker compose down -v

echo Eliminando imagenes...
docker compose down --rmi all >nul 2>&1
docker rmi pluma-app:latest >nul 2>&1
docker rmi pluma-app-external:latest >nul 2>&1

echo.
echo OK - PlumA desinstalada de Docker.
echo.
echo Para eliminar tambien los ficheros del proyecto, borra esta carpeta.
echo.
pause
