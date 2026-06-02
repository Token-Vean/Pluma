@echo off
REM =============================================================================
REM pluma-install-core.bat
REM -----------------------------------------------------------------------------
REM Variante del instalador para distribución offline con imagen pluma-app
REM precargada. Se basa en el modo (host/container) elegido por el PS1 de
REM detección. A partir de v0.6 ya no hay flujo de importación de modelo
REM derivado: el system prompt vive en schemas/pluma-runtime.yaml.
REM =============================================================================
setlocal EnableExtensions EnableDelayedExpansion
call "%~dp0pluma-env.bat" >nul 2>nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PLUMA_DIR=%%~fI"
set "ROOT_DIR=%PLUMA_DIR%"
cd /d "%PLUMA_DIR%"

echo Aplicando configuracion local bloqueada y detectando Ollama...
set "PLUMA_PROFILE="
for /f "usebackq tokens=1,* delims==" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%enforce-local-config.ps1"`) do (
    if /I "%%A"=="PLUMA_INSTALADOR_PROFILE" set "PLUMA_PROFILE=%%B"
)
if errorlevel 1 exit /b 1

call "%SCRIPT_DIR%pluma-load-offline-assets.bat"
if errorlevel 1 exit /b 1

REM Leer el modo elegido por el PS1 desde el .env (host o container)
set "PLUMA_OLLAMA_MODE=container"
if exist "%PLUMA_DIR%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "PLUMA_OLLAMA_MODE=" "%PLUMA_DIR%\.env"`) do set "PLUMA_OLLAMA_MODE=%%B"
)

if defined PLUMA_PROFILE (
    set "COMPOSE_PROFILES=%PLUMA_PROFILE%"
) else (
    set "COMPOSE_PROFILES="
)

set "OFFLINE_APP_IMAGE=0"
for %%F in ("%ROOT_DIR%\offline\images\pluma-app*.tar") do if exist "%%~fF" set "OFFLINE_APP_IMAGE=1"

if "%OFFLINE_APP_IMAGE%"=="1" (
    echo Iniciando PlumA con imagen offline precargada en modo %PLUMA_OLLAMA_MODE%...
    docker compose up -d --no-build
) else (
    echo No se ha detectado imagen offline de PlumA. Construyendo localmente en modo %PLUMA_OLLAMA_MODE%...
    docker compose up -d --build
)
if errorlevel 1 exit /b 1

echo Verificando publicacion local del puerto 127.0.0.1:8082...
docker compose port app 8081 | findstr /C:"127.0.0.1:8082" >nul
if errorlevel 1 (
  echo ERROR: Docker no ha publicado el puerto local esperado 127.0.0.1:8082.
  docker compose ps
  exit /b 1
)

if /I "%PLUMA_OLLAMA_MODE%"=="host" (
  echo Ollama local del usuario detectado. No se descarga el modelo dentro del contenedor.
) else (
  echo Modo container. Si falta el modelo base, la app lo descargara via Ollama Docker.
)

echo Esperando a que el servicio web de PlumA este listo...
call "%SCRIPT_DIR%pluma-wait-ready.bat"
if errorlevel 1 exit /b 1
echo PlumA instalada e iniciada correctamente en http://localhost:8082
echo Modo: local bloqueado. No se permite endpoint remoto ni publicacion en red.
exit /b 0
