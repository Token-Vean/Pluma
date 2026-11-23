@echo off
REM =============================================================================
REM pluma-uninstall-core.bat
REM -----------------------------------------------------------------------------
REM Parte del panel del paquete para Windows (panel\PlumAPanel.ps1).
REM Desinstalacion no interactiva para el panel de Windows; la confirmacion la
REM pide el panel. Elimina contenedores, volumenes de PlumA y la imagen local de
REM la aplicacion. En modo host NO toca el Ollama del equipo ni sus modelos.
REM La carpeta del proyecto no se borra.
REM =============================================================================
setlocal EnableExtensions EnableDelayedExpansion
call "%~dp0..\..\tools\windows\pluma-env.bat" >nul 2>nul
call "%~dp0pluma-mode.bat"
cd /d "%~dp0..\.."

set "APP_IMAGE="
for /f "usebackq delims=" %%I in (`docker compose config --images 2^>nul ^| findstr /B /C:"pluma-app"`) do set "APP_IMAGE=%%I"

echo Eliminando contenedores y volumenes de PlumA (motor de IA: !PLUMA_OLLAMA_MODE!)...
docker compose down -v
if errorlevel 1 exit /b 1
if defined APP_IMAGE (
    echo Eliminando la imagen local !APP_IMAGE!...
    docker image rm "!APP_IMAGE!" >nul 2>&1
)
echo Desinstalacion completada. La carpeta del proyecto no se ha borrado.
exit /b 0
