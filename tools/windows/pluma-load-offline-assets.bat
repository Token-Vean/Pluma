@echo off
setlocal EnableExtensions EnableDelayedExpansion
call "%~dp0pluma-env.bat" >nul 2>nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PLUMA_DIR=%%~fI"
for %%I in ("%PLUMA_DIR%\..") do set "ROOT_DIR=%%~fI"
set "IMAGES_DIR=%ROOT_DIR%\offline\images"
if not exist "%IMAGES_DIR%" exit /b 0
set "FOUND=0"
for %%F in ("%IMAGES_DIR%\*.tar") do (
  if exist "%%~fF" (
    set "FOUND=1"
    echo Cargando imagen Docker offline: %%~nxF
    docker image load -i "%%~fF"
    if errorlevel 1 exit /b 1
  )
)
if "%FOUND%"=="0" echo No hay imagenes Docker offline. Se usara instalacion normal.
exit /b 0
