@echo off
setlocal EnableExtensions EnableDelayedExpansion
call "%~dp0pluma-env.bat" >nul 2>nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PLUMA_DIR=%%~fI"
set "ROOT_DIR=%PLUMA_DIR%"
cd /d "%PLUMA_DIR%"
echo Aplicando configuracion local bloqueada...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%enforce-local-config.ps1"
if errorlevel 1 exit /b 1
call "%SCRIPT_DIR%pluma-load-offline-assets.bat"
if errorlevel 1 exit /b 1

set "PLUMA_OLLAMA_MODE=container"
if exist "%PLUMA_DIR%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "PLUMA_OLLAMA_MODE=" "%PLUMA_DIR%\.env"`) do set "PLUMA_OLLAMA_MODE=%%B"
)

set COMPOSE_PROFILES=
set "OFFLINE_APP_IMAGE=0"
for %%F in ("%ROOT_DIR%\offline\images\pluma-app*.tar") do if exist "%%~fF" set "OFFLINE_APP_IMAGE=1"

set "OFFLINE_GGUF=0"
for %%F in ("%ROOT_DIR%\offline\models\*.gguf") do if exist "%%~fF" set "OFFLINE_GGUF=1"

if /I "%PLUMA_OLLAMA_MODE%"=="container" if "%OFFLINE_GGUF%"=="1" (
  echo Modelo GGUF offline detectado. Iniciando primero Ollama para importarlo antes de arrancar la app...
  docker compose up -d ollama
  if errorlevel 1 exit /b 1
  call "%SCRIPT_DIR%pluma-import-offline-model.bat"
  if errorlevel 1 exit /b 1
)

if /I "%PLUMA_OLLAMA_MODE%"=="container" (
  if "%OFFLINE_APP_IMAGE%"=="1" (
    echo Iniciando PlumA y Ollama Docker con imagen offline precargada, sin reconstruir la app...
    docker compose up -d --no-build ollama app
  ) else (
    echo No se ha detectado imagen offline de PlumA. Construyendo localmente la app e iniciando Ollama Docker...
    docker compose up -d --build ollama app
  )
) else (
  if "%OFFLINE_APP_IMAGE%"=="1" (
    echo Iniciando PlumA con imagen offline precargada y Ollama local del usuario...
    docker compose up -d --no-build app
  ) else (
    echo No se ha detectado imagen offline de PlumA. Construyendo localmente la app y usando Ollama local del usuario...
    docker compose up -d --build app
  )
)
if errorlevel 1 exit /b 1

echo Verificando publicacion local del puerto 127.0.0.1:8082...
docker compose port app 8081 | findstr /C:"127.0.0.1:8082" >nul
if errorlevel 1 (
  echo ERROR: Docker no ha publicado el puerto local esperado 127.0.0.1:8082.
  docker compose ps
  exit /b 1
)

if /I not "%PLUMA_OLLAMA_MODE%"=="container" (
  echo Ollama local del usuario detectado. No se descarga el modelo dentro del contenedor.
) else if "%OFFLINE_GGUF%"=="0" (
  echo No hay modelo GGUF offline. La app usara el flujo normal de Ollama Docker si falta el modelo base.
)

echo Esperando a que el servicio web de PlumA este listo...
call "%SCRIPT_DIR%pluma-wait-ready.bat"
if errorlevel 1 exit /b 1
echo PlumA instalada e iniciada correctamente en http://localhost:8082
echo Modo: local bloqueado. No se permite endpoint remoto ni publicacion en red.
exit /b 0
