@echo off
REM =============================================================================
REM PlumA - instalador para Windows
REM -----------------------------------------------------------------------------
REM Comprueba requisitos, detecta Ollama, reconstruye la imagen si el
REM codigo ha cambiado, arranca los servicios, espera a que la API
REM responda y abre el navegador.
REM =============================================================================

setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo.
echo PlumA - instalacion
echo ----------------------------------------
echo.

REM -----------------------------------------------------------------------------
REM 1. Docker
REM -----------------------------------------------------------------------------
echo [1/8] Comprobando Docker...

docker --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo    ERROR: Docker no esta instalado.
    echo.
    echo    Descarga Docker Desktop desde:
    echo      https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo    ERROR: Docker esta instalado pero no esta arrancado.
    echo    Abre Docker Desktop y espera a que termine de iniciarse.
    echo.
    pause
    exit /b 1
)

echo    OK - Docker instalado y arrancado

REM -----------------------------------------------------------------------------
REM 2. Docker Compose
REM -----------------------------------------------------------------------------
echo.
echo [2/8] Comprobando Docker Compose...

docker compose version >nul 2>&1
if errorlevel 1 (
    echo.
    echo    ERROR: Docker Compose no esta disponible.
    echo    Actualiza Docker Desktop.
    echo.
    pause
    exit /b 1
)

echo    OK - Docker Compose disponible

REM -----------------------------------------------------------------------------
REM 3. Deteccion de Ollama
REM -----------------------------------------------------------------------------
echo.
echo [3/8] Detectando motor de IA...

set PERFIL=bundled

curl -sfm 3 http://localhost:11434/api/tags >nul 2>&1
if not errorlevel 1 (
    set PERFIL=external
    echo    OK - Ollama detectado en el equipo ^(puerto 11434^)
    echo        La aplicacion usara tu Ollama y los modelos que tengas.
) else (
    echo    OK - No se ha detectado Ollama en el equipo
    echo        Se instalara Ollama dentro de Docker.
    echo        La primera vez se descargaran ~4-5 GB.
)

REM -----------------------------------------------------------------------------
REM 4. Puerto configurado (leido del .env)
REM -----------------------------------------------------------------------------
echo.
echo [4/8] Comprobando puerto de la aplicacion...

set PUERTO=8082
if exist .env (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PUERTO=" .env 2^>nul') do set PUERTO=%%a
)

netstat -an | findstr ":!PUERTO! " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo    OK - Puerto !PUERTO! disponible
) else (
    REM Miramos si es nuestro propio contenedor el que lo ocupa
    docker ps --filter "name=archivo-ia-app" --format "{{.Names}}" | findstr "archivo-ia-app" >nul
    if not errorlevel 1 (
        echo    OK - Puerto !PUERTO! ocupado por la propia aplicacion ^(reinicio^)
    ) else (
        echo    AVISO - El puerto !PUERTO! esta en uso por otra aplicacion
        echo           Si el arranque falla, cambia PUERTO en .env a otro libre.
    )
)

REM -----------------------------------------------------------------------------
REM 5. Configuracion (.env)
REM -----------------------------------------------------------------------------
echo.
echo [5/8] Preparando configuracion...

if exist .env (
    echo    OK - Fichero .env ya existe
) else (
    if exist .env.example (
        copy .env.example .env >nul
        echo    OK - Fichero .env creado
    )
)

REM Guardar el perfil detectado
findstr /b "PERFIL=" .env >nul 2>&1
if not errorlevel 1 (
    powershell -Command "(Get-Content .env) -replace '^PERFIL=.*', 'PERFIL=!PERFIL!' | Set-Content .env"
) else (
    echo.>> .env
    echo # Perfil detectado automaticamente>> .env
    echo PERFIL=!PERFIL!>> .env
)

REM Actualizacion segura del modelo por defecto: solo cambia el valor antiguo.
findstr /b /c:"MODELO_BASE=gemma3:4b" .env >nul 2>&1
if not errorlevel 1 (
    powershell -Command "(Get-Content .env) -replace '^MODELO_BASE=gemma3:4b$', 'MODELO_BASE=gemma4:e2b' | Set-Content .env"
) else (
    findstr /b "MODELO_BASE=" .env >nul 2>&1
    if errorlevel 1 echo MODELO_BASE=gemma4:e2b>> .env
)

REM -----------------------------------------------------------------------------
REM 5.5. Tipografias
REM -----------------------------------------------------------------------------
echo.
echo [5.5/8] Comprobando tipografias...
echo    La interfaz usa tipografias del sistema.
echo    Las fuentes autohospedadas son opcionales.
echo    Si quieres instalarlas, ejecuta frontend\static\fonts\descargar-fuentes.bat manualmente.

REM -----------------------------------------------------------------------------
REM 6. Reconstruir la imagen si es necesario
REM -----------------------------------------------------------------------------
echo.
echo [6/8] Preparando la imagen de la aplicacion...
echo        ^(si has actualizado el codigo, esto tardara ~30s^)

set COMPOSE_PROFILES=!PERFIL!

docker compose build >nul 2>build.log
if errorlevel 1 (
    echo.
    echo    ERROR: Fallo al construir la imagen. Detalles en build.log
    type build.log
    pause
    exit /b 1
)
echo    OK - Imagen preparada
del build.log >nul 2>&1

REM -----------------------------------------------------------------------------
REM 7. Arrancar servicios
REM -----------------------------------------------------------------------------
echo.
echo [7/8] Arrancando los servicios...

REM Detenemos primero por si habia una version anterior corriendo
docker compose down >nul 2>&1

docker compose up -d
if errorlevel 1 (
    echo.
    echo    ERROR: No se pudieron arrancar los servicios.
    echo.
    echo    Causas habituales:
    echo      - Puerto !PUERTO! en uso por otra aplicacion.
    echo      - Espacio en disco insuficiente.
    echo.
    pause
    exit /b 1
)

echo    OK - Servicios arrancados

REM -----------------------------------------------------------------------------
REM 8. Esperar a que la API responda y abrir navegador
REM -----------------------------------------------------------------------------
echo.
echo [8/8] Esperando a que la aplicacion este lista...

set MAX_INTENTOS=30
set INTENTO=0

:wait_loop
set /a INTENTO+=1
curl -sfm 2 http://localhost:!PUERTO!/api/estado >nul 2>&1
if not errorlevel 1 goto wait_ok
if !INTENTO! GEQ !MAX_INTENTOS! goto wait_timeout
timeout /t 1 /nobreak >nul
goto wait_loop

:wait_ok
echo    OK - Aplicacion lista
goto abrir_navegador

:wait_timeout
echo    AVISO - La aplicacion esta tardando mas de lo habitual.
echo           Abriendo el navegador igualmente; si no se ve nada,
echo           espera unos segundos y recarga la pagina.

:abrir_navegador
echo.
echo ----------------------------------------
echo.
echo Instalacion completada.
echo.
echo Abriendo el navegador en: http://localhost:!PUERTO!
echo.
echo Modo de despliegue activo:   !PERFIL!
echo Para detener la aplicacion:   detener.bat
echo Para ver el estado:           docker compose ps
echo Para ver los logs:            docker compose logs -f
echo.

REM Abrir el navegador
start "" "http://localhost:!PUERTO!"

echo La ventana del navegador deberia haberse abierto.
echo Si no, copia esta URL manualmente: http://localhost:!PUERTO!
echo.
pause
