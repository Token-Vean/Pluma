@echo off
REM =============================================================================
REM PlumA - instalador para Windows en modo local bloqueado
REM -----------------------------------------------------------------------------
REM A partir de v0.6 el instalador detecta si tienes Ollama nativo en el host
REM con el modelo base ya descargado. Si lo tiene, configura PlumA para usarlo
REM via host.docker.internal:11434 y NO arranca el contenedor de Ollama. Si no,
REM activa el perfil `bundled` de Docker Compose y levanta Ollama dentro de
REM Docker como antes.
REM
REM Revision de endurecimiento del instalador:
REM - Deteccion de modo con fallo cerrado: la salida del PS1 se captura en un
REM   fichero temporal y el exit code de PowerShell se comprueba directamente.
REM   Antes, `if errorlevel 1` tras un `for /f` con `set` dentro del bloque
REM   nunca se disparaba, y un fallo del saneador se interpretaba en silencio
REM   como "modo host".
REM - 127.0.0.1 en lugar de localhost: el puerto se publica solo en loopback
REM   IPv4 (host_ip 127.0.0.1) y localhost puede resolver a ::1.
REM - cd a %TEMP% antes del pause final para no retener bloqueada la carpeta
REM   de instalacion (cmd.exe mantiene un handle sobre su CWD).
REM =============================================================================

setlocal EnableDelayedExpansion

if exist "%~dp0tools\windows\pluma-env.bat" call "%~dp0tools\windows\pluma-env.bat" >nul 2>nul
cd /d "%~dp0"

echo.
echo PlumA - instalacion local bloqueada
echo ----------------------------------------
echo.

echo [1/6] Comprobando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta instalado.
    echo Descarga Docker Desktop desde: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker esta instalado pero no esta arrancado.
    echo Abre Docker Desktop y vuelve a intentarlo.
    pause
    exit /b 1
)
echo OK - Docker disponible
echo.

echo [2/6] Comprobando Docker Compose...
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose no esta disponible. Actualiza Docker Desktop.
    pause
    exit /b 1
)
echo OK - Docker Compose disponible
echo.

echo [3/6] Aplicando configuracion local bloqueada y detectando Ollama...
REM Contrato con enforce-local-config.ps1:
REM   - "PLUMA_INSTALADOR_PROFILE=bundled"  -> levantar Ollama en Docker.
REM   - "PLUMA_INSTALADOR_PROFILE=host"     -> usar Ollama nativo (recomendado
REM     que el PS1 lo imprima explicitamente).
REM   - Sin linea (contrato heredado)       -> modo host, SOLO si exit code 0.
REM La salida se redirige a fichero para que el exit code de PowerShell sea
REM comprobable: con `for /f` directo se pierde y el `set` del bloque lo
REM resetea a 0.
set "PLUMA_PROFILE="
set "PLUMA_PS1_OUT=%TEMP%\pluma-instalador-perfil.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\windows\enforce-local-config.ps1" > "!PLUMA_PS1_OUT!" 2>&1
if errorlevel 1 (
    echo ERROR: No se pudo sanear la configuracion local. Salida del saneador:
    if exist "!PLUMA_PS1_OUT!" type "!PLUMA_PS1_OUT!"
    del "!PLUMA_PS1_OUT!" >nul 2>&1
    pause
    exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in ("!PLUMA_PS1_OUT!") do (
    if /I "%%A"=="PLUMA_INSTALADOR_PROFILE" set "PLUMA_PROFILE=%%B"
)
del "!PLUMA_PS1_OUT!" >nul 2>&1
echo OK - Configuracion saneada
echo.

echo [4/6] Preparando imagen y servicios...
if /I "!PLUMA_PROFILE!"=="bundled" (
    set "COMPOSE_PROFILES=bundled"
    echo Modo: container ^(Ollama se levantara dentro de Docker^)
) else (
    REM Valor "host" explicito o ausencia de linea con exit code 0.
    set "COMPOSE_PROFILES="
    echo Modo: host ^(la app usara el Ollama nativo del sistema^)
)
docker compose up -d --build
if errorlevel 1 (
    echo ERROR: No se pudieron arrancar los servicios.
    pause
    exit /b 1
)
echo OK - Servicios arrancados
echo.

echo [5/6] Esperando a que la aplicacion responda...
REM Puerto fijo por diseno en la release local bloqueada. Debe coincidir con
REM `published` en docker-compose.yml; no se lee de .env.
set "PUERTO=8082"
set MAX_INTENTOS=30
set INTENTO=0
:wait_loop
set /a INTENTO+=1
curl -sfm 2 http://127.0.0.1:!PUERTO!/api/estado >nul 2>&1
if not errorlevel 1 goto wait_ok
if !INTENTO! GEQ !MAX_INTENTOS! goto wait_timeout
timeout /t 1 /nobreak >nul
goto wait_loop
:wait_ok
echo OK - Aplicacion lista
goto open
:wait_timeout
echo AVISO - PlumA tarda mas de lo habitual. Puede estar descargando el modelo.
:open
echo.
echo [6/6] Abriendo PlumA...
start "" "http://127.0.0.1:!PUERTO!"
echo.
echo Instalacion completada en modo local bloqueado.
echo PlumA no admite endpoint remoto ni publicacion en red en esta release.
echo.
if /I not "!PLUMA_PROFILE!"=="bundled" (
    echo AVISO de seguridad - Ollama nativo
    echo ----------------------------------------
    echo Comprueba que tu Ollama del host esta escuchando SOLO en 127.0.0.1.
    echo Por defecto, Ollama escucha en 0.0.0.0:11434, lo que significa que
    echo cualquier dispositivo en tu red puede enviarle peticiones.
    echo.
    echo Para limitarlo a tu equipo en Windows, define la variable de entorno
    echo del sistema:
    echo     OLLAMA_HOST=127.0.0.1
    echo y reinicia Ollama. Mas detalles en INSTALACION.md.
    echo.
)
REM Soltar el directorio de instalacion antes del pause: cmd.exe retiene un
REM handle sobre su CWD y bloquearia mover o eliminar la carpeta mientras la
REM ventana siga abierta.
cd /d "%TEMP%"
pause
