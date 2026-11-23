@echo off
REM =============================================================================
REM pluma-stop-core.bat
REM -----------------------------------------------------------------------------
REM Parte del panel del paquete para Windows (panel\PlumAPanel.ps1).
REM Detiene PlumA sin pause (panel de Windows). Activa el perfil bundled cuando
REM Ollama corre en Docker: sin el perfil, "docker compose down" deja ese
REM contenedor en marcha.
REM =============================================================================
setlocal EnableExtensions
call "%~dp0..\..\tools\windows\pluma-env.bat" >nul 2>nul
call "%~dp0pluma-mode.bat"
cd /d "%~dp0..\.."
echo Deteniendo PlumA (motor de IA: %PLUMA_OLLAMA_MODE%)...
docker compose down
if errorlevel 1 exit /b 1
echo Servicios detenidos. Los datos y el modelo se conservan.
exit /b 0
