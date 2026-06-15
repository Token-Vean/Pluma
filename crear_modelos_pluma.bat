@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo PlumA - creacion opcional de perfiles Ollama
echo ---------------------------------------------
echo.

echo Comprobando Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo ERROR: No se encuentra Ollama en el PATH.
    echo Instala Ollama o abre una consola donde ollama este disponible.
    pause
    exit /b 1
)

ollama --version
if errorlevel 1 (
    echo ERROR: Ollama esta instalado, pero no responde correctamente.
    pause
    exit /b 1
)

echo.
echo Modelos disponibles en Ollama:
ollama list

echo.
set "CREADOS=0"
set "FALLOS=0"

REM Crear primero el perfil visual. Es el mas importante para documentos escaneados.
ollama show qwen3.5:latest >nul 2>&1
if errorlevel 1 (
    echo AVISO: No se encuentra qwen3.5:latest. No se crea pluma-vision.
    echo        Puedes descargarlo con: ollama pull qwen3.5:latest
) else (
    echo Creando/actualizando pluma-vision desde qwen3.5:latest...
    ollama create pluma-vision -f "%~dp0modelos_ollama\pluma-vision.Modelfile"
    if errorlevel 1 (
        echo ERROR: No se pudo crear pluma-vision.
        echo        Ejecuta manualmente para ver el error completo:
        echo        ollama create pluma-vision -f "%~dp0modelos_ollama\pluma-vision.Modelfile"
        set /a FALLOS+=1
    ) else (
        set /a CREADOS+=1
    )
)

echo.
ollama show gemma4:e2b >nul 2>&1
if errorlevel 1 (
    echo AVISO: No se encuentra gemma4:e2b. No se crea pluma-texto.
    echo        Puedes descargarlo con: ollama pull gemma4:e2b
) else (
    echo Creando/actualizando pluma-texto desde gemma4:e2b...
    ollama create pluma-texto -f "%~dp0modelos_ollama\pluma-texto.Modelfile"
    if errorlevel 1 (
        echo ERROR: No se pudo crear pluma-texto.
        echo        Se mantiene pluma-vision si se creo correctamente.
        set /a FALLOS+=1
    ) else (
        set /a CREADOS+=1
    )
)

echo.
echo Verificacion final:
ollama list | findstr /I /C:"pluma-vision" /C:"pluma-texto"

echo.
if !CREADOS! EQU 0 (
    echo No se ha creado ningun perfil.
    echo Revisa los avisos anteriores y ejecuta los comandos manuales indicados.
) else (
    echo Perfiles creados/actualizados: !CREADOS!
)

if !FALLOS! GTR 0 (
    echo Fallos detectados: !FALLOS!
    echo Copia la salida completa si necesitas diagnostico.
)

echo.
pause
