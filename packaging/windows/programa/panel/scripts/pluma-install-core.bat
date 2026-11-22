@echo off
REM =============================================================================
REM pluma-install-core.bat
REM -----------------------------------------------------------------------------
REM Parte del panel del paquete para Windows.
REM Instalacion no interactiva que usa el panel (panel\PlumAPanel.ps1).
REM Sigue el mismo flujo que instalar.bat:
REM   - deteccion de perfil host/bundled con fallo cerrado;
REM   - en bundled, Ollama en Docker y modelo base (solo se descarga si falta);
REM   - en host, el Ollama nativo del equipo.
REM Anade la carga de imagenes offline (offline\images\*.tar) y no hace pause:
REM la salida la recoge el panel. Devuelve 0 si PlumA queda respondiendo.
REM =============================================================================
setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PLUMA_DIR=%%~fI"
set "TOOLS_DIR=%PLUMA_DIR%\tools\windows"
call "%TOOLS_DIR%\pluma-env.bat" >nul 2>nul
cd /d "%PLUMA_DIR%"

echo [1/6] Comprobando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta instalado o no se encuentra docker.exe.
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker esta instalado pero no esta arrancado. Abre Docker Desktop y vuelve a intentarlo.
    exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose v2 no esta disponible. Actualiza Docker Desktop.
    exit /b 1
)
echo OK - Docker y Docker Compose disponibles

echo [2/6] Aplicando configuracion local bloqueada y detectando Ollama...
REM Contrato con enforce-local-config.ps1: imprime
REM "PLUMA_INSTALADOR_PROFILE=host|bundled". La salida va a un fichero para
REM poder comprobar el codigo de salida de PowerShell; dentro de un for /f se
REM perderia y un fallo del saneador pasaria inadvertido.
set "PLUMA_PROFILE="
set "PLUMA_PS1_OUT=%TEMP%\pluma-panel-perfil-%RANDOM%%RANDOM%.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TOOLS_DIR%\enforce-local-config.ps1" > "!PLUMA_PS1_OUT!" 2>&1
if errorlevel 1 (
    echo ERROR: No se pudo sanear la configuracion local. Salida del saneador:
    if exist "!PLUMA_PS1_OUT!" type "!PLUMA_PS1_OUT!"
    del "!PLUMA_PS1_OUT!" >nul 2>&1
    exit /b 1
)
type "!PLUMA_PS1_OUT!"
for /f "usebackq tokens=1,* delims==" %%A in ("!PLUMA_PS1_OUT!") do (
    if /I "%%A"=="PLUMA_INSTALADOR_PROFILE" set "PLUMA_PROFILE=%%B"
)
del "!PLUMA_PS1_OUT!" >nul 2>&1
if /I not "!PLUMA_PROFILE!"=="host" if /I not "!PLUMA_PROFILE!"=="bundled" (
    echo ERROR: El saneador no devolvio un perfil valido ^(host o bundled^).
    exit /b 1
)
echo OK - Perfil seleccionado: !PLUMA_PROFILE!

echo [3/6] Buscando imagenes Docker offline...
call "%TOOLS_DIR%\pluma-load-offline-assets.bat"
if errorlevel 1 (
    echo ERROR: No se pudieron cargar las imagenes de offline\images.
    exit /b 1
)

echo [4/6] Preparando el motor de IA...
set "MODELO_BASE=gemma4:e2b"
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "MODELO_BASE=" ".env"`) do set "MODELO_BASE=%%B"
if /I "!PLUMA_PROFILE!"=="bundled" (
    set "COMPOSE_PROFILES=bundled"
    echo Modo: Ollama dentro de Docker ^(perfil bundled^)
    docker compose up -d ollama
    if errorlevel 1 (
        echo ERROR: No se pudo arrancar Ollama en Docker.
        exit /b 1
    )
    echo Esperando a Ollama...
    set "OLLAMA_LISTO="
    for /L %%I in (1,1,60) do (
        if not defined OLLAMA_LISTO (
            docker compose exec -T ollama ollama list >nul 2>&1
            if not errorlevel 1 (
                set "OLLAMA_LISTO=1"
            ) else (
                ping -n 2 127.0.0.1 >nul
            )
        )
    )
    if not defined OLLAMA_LISTO (
        echo ERROR: Ollama no ha respondido dentro del tiempo esperado.
        exit /b 1
    )
    docker compose exec -T ollama ollama show "!MODELO_BASE!" >nul 2>&1
    if errorlevel 1 (
        echo Descargando el modelo !MODELO_BASE! ^(puede tardar y ocupar varios GB^)...
        docker compose exec -T ollama ollama pull "!MODELO_BASE!"
        if errorlevel 1 (
            echo ERROR: No se pudo descargar el modelo !MODELO_BASE!.
            exit /b 1
        )
    ) else (
        echo Modelo !MODELO_BASE! ya disponible en el volumen de Ollama.
    )
) else (
    set "COMPOSE_PROFILES="
    echo Modo: Ollama del equipo ^(perfil host^)
    docker compose --profile bundled stop ollama >nul 2>&1
)

echo [5/6] Arrancando PlumA...
set "OFFLINE_APP_IMAGE=0"
for %%F in ("%PLUMA_DIR%\offline\images\pluma-app*.tar") do if exist "%%~fF" set "OFFLINE_APP_IMAGE=1"
if "!OFFLINE_APP_IMAGE!"=="1" (
    echo Usando la imagen de PlumA cargada desde offline\images.
    docker compose up -d --no-build app
) else (
    echo Construyendo la imagen de PlumA ^(la primera vez puede tardar varios minutos^)...
    docker compose up -d --build app
)
if errorlevel 1 (
    echo ERROR: No se pudieron arrancar los servicios.
    exit /b 1
)

echo [6/6] Verificando la publicacion local y el servicio...
docker compose port app 8081 | findstr /C:"127.0.0.1:8082" >nul
if errorlevel 1 (
    echo ERROR: Docker no ha publicado el puerto local esperado 127.0.0.1:8082.
    docker compose ps
    exit /b 1
)
call "%TOOLS_DIR%\pluma-wait-ready.bat"
if errorlevel 1 exit /b 1
echo PlumA instalada e iniciada en http://127.0.0.1:8082
echo Modo local bloqueado: no se admite endpoint remoto ni publicacion en red.
if /I "!PLUMA_PROFILE!"=="host" (
    echo AVISO: comprueba que el Ollama del equipo escucha solo en 127.0.0.1 ^(variable OLLAMA_HOST=127.0.0.1^). Detalles en INSTALACION.md.
)
exit /b 0
