@echo off
REM =============================================================================
REM pluma-mode.bat
REM -----------------------------------------------------------------------------
REM Parte del panel del paquete para Windows (panel\PlumAPanel.ps1).
REM Lee PLUMA_OLLAMA_MODE del .env (lo escribe enforce-local-config.ps1) y
REM establece COMPOSE_PROFILES en consecuencia:
REM   host       -> sin perfil: la app usa el Ollama nativo del equipo.
REM   container  -> perfil bundled: Ollama corre dentro de Docker.
REM Sin .env o sin la variable se asume container, como iniciar.bat.
REM
REM Se invoca con CALL y sin SETLOCAL propio para que las variables lleguen
REM al script que lo llama.
REM =============================================================================
set "PLUMA_OLLAMA_MODE=container"
if exist "%~dp0..\..\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "PLUMA_OLLAMA_MODE=" "%~dp0..\..\.env"`) do set "PLUMA_OLLAMA_MODE=%%B"
)
if /I "%PLUMA_OLLAMA_MODE%"=="host" (
    set "COMPOSE_PROFILES="
) else (
    set "PLUMA_OLLAMA_MODE=container"
    set "COMPOSE_PROFILES=bundled"
)
exit /b 0
