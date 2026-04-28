@echo off
setlocal EnableExtensions EnableDelayedExpansion
call "%~dp0pluma-env.bat" >nul 2>nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PLUMA_DIR=%%~fI"
set "ROOT_DIR=%PLUMA_DIR%"
set "MODELS_DIR=%ROOT_DIR%\offline\models"
set "ENV_FILE=%PLUMA_DIR%\.env"
set "MODEL_NAME=pluma"
if exist "%ENV_FILE%" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /I "MODELO_NOMBRE=" "%ENV_FILE%"`) do set "MODEL_NAME=%%B"
)
if not exist "%MODELS_DIR%" exit /b 0
set "GGUF_FILE="
for %%F in ("%MODELS_DIR%\*.gguf") do if not defined GGUF_FILE set "GGUF_FILE=%%~nxF"
if not defined GGUF_FILE (
  echo No hay modelo GGUF offline. Ollama usara el flujo normal de modelo base si hace falta.
  exit /b 0
)
set "GENERATED=%MODELS_DIR%\Modelfile.offline.generated"
echo Generando Modelfile offline para %GGUF_FILE%
> "%GENERATED%" echo FROM /offline/models/%GGUF_FILE%
if exist "%MODELS_DIR%\Modelfile.template.parameters" type "%MODELS_DIR%\Modelfile.template.parameters" >> "%GENERATED%"
echo Importando modelo offline en Ollama como %MODEL_NAME% ...
docker exec pluma-ollama ollama create "%MODEL_NAME%" -f /offline/models/Modelfile.offline.generated
if errorlevel 1 exit /b 1
echo Modelo offline importado correctamente: %MODEL_NAME%
exit /b 0
